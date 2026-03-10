"""
Secondus Backend — ADK Bidi-Streaming Server

FastAPI server with WebSocket support for real-time negotiation intelligence.
Uses Google ADK's native bidi-streaming for Gemini Live API integration.
"""

import asyncio
import base64
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import Runner, RunConfig
from google.adk.agents.run_config import StreamingMode
from google.adk.sessions import InMemorySessionService
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.genai import types
from google import genai
from pydantic import BaseModel

from agent import root_agent, SECONDUS_PERSONA
from adversary import adversary_agent
from learnings import analyze_session, get_pre_session_briefing, get_quick_tip

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "platinum-depot-489523-a7")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# Set environment variables for ADK to use Vertex AI
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = LOCATION
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"

# Session management
session_service = InMemorySessionService()
active_sessions: dict[str, dict[str, Any]] = {}


class SessionConfig(BaseModel):
    """Configuration for a new negotiation session."""
    goals: str = ""
    batna: str = ""
    key_terms: list[str] = []
    counterparty: str = ""
    voice_sample: str | None = None  # Base64-encoded voice sample for speaker ID


class SessionResponse(BaseModel):
    """Response when creating a new session."""
    session_id: str
    status: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    print(f"Secondus starting — Project: {PROJECT_ID}, Location: {LOCATION}")
    yield
    # Cleanup
    active_sessions.clear()
    print("Secondus shutting down")


app = FastAPI(
    title="Secondus",
    description="Real-time negotiation intelligence agent",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run."""
    return {
        "status": "ok",
        "service": "secondus",
        "model": "gemini-live-2.5-flash-native-audio",
        "project": PROJECT_ID,
    }


# ============ Real-Time Coaching Generator ============

# Initialize Gemini client for coaching
coaching_client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

COACHING_PROMPT = """You are Secondus, a real-time negotiation coach.
The counterparty just said something. Give the user an IMMEDIATE response to say.

RULES:
- Output ONLY a "SAY THIS:" line with the exact phrase to say
- Address what the counterparty JUST said
- Consider what the USER already committed to (don't contradict their position)
- Keep it to 1-2 sentences max
- Be tactical and confident

CONTEXT:
User's goals: {goals}
User's BATNA: {batna}

CONVERSATION HISTORY (what the user already said/committed to):
{user_history}

COUNTERPARTY JUST SAID:
"{adversary_text}"

IMPORTANT: If the user already agreed to specific terms, your coaching should REINFORCE those terms, not contradict them.

YOUR COACHING (one SAY THIS line only):"""


async def generate_coaching(adversary_text: str, goals: str, batna: str, user_history: str = "") -> dict:
    """Generate real-time coaching response to what adversary said."""
    try:
        prompt = COACHING_PROMPT.format(
            goals=goals or "Close the deal",
            batna=batna or "Walk away",
            adversary_text=adversary_text,
            user_history=user_history or "No prior commitments yet"
        )

        response = await asyncio.to_thread(
            coaching_client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt,
        )

        coaching_text = response.text.strip()

        # Extract the SAY THIS portion
        if "SAY THIS:" in coaching_text.upper():
            # Find SAY THIS and extract the phrase
            idx = coaching_text.upper().find("SAY THIS:")
            phrase = coaching_text[idx + 9:].strip().strip('"').strip("'")
            return {
                "type": "coaching",
                "say_this": phrase,
                "context": f"Response to: {adversary_text[:50]}..."
            }
        else:
            return {
                "type": "coaching",
                "say_this": coaching_text,
                "context": f"Response to: {adversary_text[:50]}..."
            }

    except Exception as e:
        print(f"Coaching generation error: {e}")
        return {
            "type": "coaching",
            "say_this": "I hear you. Let me think about the best way forward.",
            "context": "Fallback response"
        }


# ============ Learning System Endpoints ============

@app.get("/learnings/briefing")
async def get_briefing():
    """Get personalized pre-session briefing based on past performance."""
    return get_pre_session_briefing()


@app.post("/learnings/analyze")
async def analyze_session_endpoint(session_data: dict):
    """Analyze completed session and store learnings."""
    return analyze_session(session_data)


@app.get("/learnings/tip/{tactic}")
async def get_tactic_tip(tactic: str):
    """Get quick counter-tip for a specific tactic."""
    tip = get_quick_tip(tactic)
    if tip:
        return {"tactic": tactic, "tip": tip}
    return {"tactic": tactic, "tip": "Stay calm and focus on your value."}


class PracticeConfig(BaseModel):
    """Configuration for practice mode with adversarial agent."""
    goals: str = "Close deal at $80K"
    low_cost_mode: bool = False  # Text-only responses (no audio generation)
    batna: str = "Walk away to other prospects"
    key_terms: list[str] = ["50% upfront", "Net-30", "3 revision rounds"]
    scenario: str = "AI consulting engagement"


# Session timeout in seconds (5 minutes max)
SESSION_TIMEOUT = 300


@app.post("/session/practice", response_model=SessionResponse)
async def create_practice_session(config: PracticeConfig):
    """Create a practice session with adversarial client agent."""
    session_id = str(uuid.uuid4())

    # Store practice mode flag
    active_sessions[session_id] = {
        "mode": "practice",
        "config": config.model_dump(),
        "context": f"PRACTICE MODE - Scenario: {config.scenario}\nYour goals: {config.goals}\nYour BATNA: {config.batna}",
        "last_audio_time": 0,
        "low_cost_mode": config.low_cost_mode,
        "created_at": asyncio.get_event_loop().time(),
    }

    # Create ADK session for adversary
    await session_service.create_session(
        app_name="adversary",
        user_id="user",
        session_id=session_id,
    )

    return SessionResponse(session_id=session_id, status="practice")


class VoiceValidationRequest(BaseModel):
    """Request to validate voice enrollment audio."""
    audio_base64: str  # Base64-encoded audio (webm format)


class VoiceValidationResponse(BaseModel):
    """Response from voice validation."""
    success: bool
    transcript: str
    match_percent: int
    message: str


# Expected script for voice enrollment
EXPECTED_SCRIPT = "the quick brown fox jumps over the lazy dog i'm ready to discuss terms and find a fair agreement"


def calculate_word_similarity(transcript: str, expected: str) -> int:
    """Calculate percentage of expected words found in transcript."""
    transcript_words = set(transcript.lower().replace("'", "").split())
    expected_words = expected.lower().replace("'", "").split()
    if not expected_words:
        return 0
    matches = sum(1 for word in expected_words if word in transcript_words)
    return int((matches / len(expected_words)) * 100)


@app.post("/voice/validate", response_model=VoiceValidationResponse)
async def validate_voice_enrollment(request: VoiceValidationRequest):
    """
    Validate voice enrollment by transcribing audio and comparing to expected script.
    Uses Google Cloud Speech-to-Text API.
    """
    from google.cloud import speech

    try:
        # Decode audio
        audio_bytes = base64.b64decode(request.audio_base64)

        # Create Speech-to-Text client
        client = speech.SpeechClient()

        # Configure recognition
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code="en-US",
            enable_automatic_punctuation=True,
        )

        # Perform transcription
        response = client.recognize(config=config, audio=audio)

        # Extract transcript
        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + " "
        transcript = transcript.strip()

        if not transcript:
            return VoiceValidationResponse(
                success=False,
                transcript="",
                match_percent=0,
                message="Could not detect speech. Please speak clearly and try again."
            )

        # Calculate similarity
        match_percent = calculate_word_similarity(transcript, EXPECTED_SCRIPT)

        if match_percent >= 50:
            return VoiceValidationResponse(
                success=True,
                transcript=transcript,
                match_percent=match_percent,
                message=f"Voice enrolled successfully! ({match_percent}% match)"
            )
        else:
            return VoiceValidationResponse(
                success=False,
                transcript=transcript,
                match_percent=match_percent,
                message=f"Please read the script more clearly. Detected: \"{transcript}\" ({match_percent}% match)"
            )

    except Exception as e:
        print(f"Voice validation error: {e}")
        return VoiceValidationResponse(
            success=False,
            transcript="",
            match_percent=0,
            message=f"Validation error: {str(e)}"
        )


@app.post("/session/create", response_model=SessionResponse)
async def create_session(config: SessionConfig):
    """Create a new negotiation session with context."""
    session_id = str(uuid.uuid4())

    # Build context from user's pre-negotiation setup
    context_parts = []
    if config.goals:
        context_parts.append(f"USER'S GOALS: {config.goals}")
    if config.batna:
        context_parts.append(f"USER'S BATNA (Walk-away alternative): {config.batna}")
    if config.key_terms:
        context_parts.append(f"KEY TERMS TO WATCH: {', '.join(config.key_terms)}")
    if config.counterparty:
        context_parts.append(f"COUNTERPARTY: {config.counterparty}")
    if config.voice_sample:
        context_parts.append("VOICE ENROLLMENT: User has enrolled their voice. The following audio is their voice sample — use it to distinguish the USER from the COUNTERPARTY. When you hear this voice pattern, it's the user speaking. When you hear a different voice, it's the counterparty.")

    context = "\n".join(context_parts) if context_parts else "No pre-session context provided."

    # Create ADK session
    session = await session_service.create_session(
        app_name="secondus",
        user_id="user",
        session_id=session_id,
    )

    active_sessions[session_id] = {
        "config": config.model_dump(),
        "context": context,
        "session": session,
        "created_at": asyncio.get_event_loop().time(),
    }

    return SessionResponse(session_id=session_id, status="created")


@app.websocket("/ws/negotiate/{session_id}")
async def negotiate_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time negotiation support.

    Receives:
    - Audio chunks (base64 PCM)
    - Screen frames (base64 JPEG)
    - Text messages

    Sends:
    - Agent interventions with urgency levels
    - Transcript updates
    """
    await websocket.accept()

    if session_id not in active_sessions:
        await websocket.send_json({"error": "Session not found"})
        await websocket.close()
        return

    session_data = active_sessions[session_id]
    context = session_data["context"]

    # Create ADK runner for this session
    runner = Runner(
        agent=root_agent,
        app_name="secondus",
        session_service=session_service,
    )

    # Create live request queue for bidirectional communication
    live_queue = LiveRequestQueue()

    try:
        # Send initial context (sync method)
        live_queue.send_content(
            types.Content(
                parts=[types.Part(text=f"SESSION CONTEXT:\n{context}")]
            )
        )

        # Send voice enrollment sample if provided
        voice_sample = session_data["config"].get("voice_sample")
        if voice_sample:
            voice_bytes = base64.b64decode(voice_sample)
            live_queue.send_content(
                types.Content(
                    parts=[
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="audio/webm",
                                data=voice_bytes,
                            )
                        ),
                        types.Part(
                            text="[USER VOICE SAMPLE: This is the user speaking. Remember this voice pattern to identify them during the negotiation.]"
                        ),
                    ]
                )
            )

        # Handle receiving from client and forwarding to queue
        async def receive_from_client():
            """Receive and forward client messages to the agent."""
            try:
                while True:
                    data = await websocket.receive_json()
                    msg_type = data.get("type")

                    if msg_type == "audio":
                        # PCM audio chunk (sync method)
                        audio_bytes = base64.b64decode(data["data"])
                        live_queue.send_realtime(
                            types.Blob(
                                mime_type="audio/pcm",
                                data=audio_bytes,
                            )
                        )
                        # Track audio activity for silence detection
                        active_sessions[session_id]["last_audio_time"] = asyncio.get_event_loop().time()

                    elif msg_type == "screen":
                        # JPEG screen capture (sync method)
                        image_bytes = base64.b64decode(data["data"])
                        live_queue.send_content(
                            types.Content(
                                parts=[
                                    types.Part(
                                        inline_data=types.Blob(
                                            mime_type="image/jpeg",
                                            data=image_bytes,
                                        )
                                    ),
                                    types.Part(
                                        text="[Screen capture update — analyze for term drift or relevant details]"
                                    ),
                                ]
                            )
                        )

                    elif msg_type == "text":
                        # Direct text input (sync method)
                        live_queue.send_content(
                            types.Content(
                                parts=[types.Part(text=data["data"])]
                            )
                        )

                    elif msg_type == "end":
                        live_queue.close()
                        break

            except WebSocketDisconnect:
                live_queue.close()

        # Handle receiving from agent and forwarding to client
        async def send_to_client():
            """Forward agent responses to the client."""
            try:
                run_config = RunConfig(
                    response_modalities=["AUDIO"],
                    streaming_mode=StreamingMode.BIDI,
                    output_audio_transcription=types.AudioTranscriptionConfig(),
                    input_audio_transcription=types.AudioTranscriptionConfig(),
                )

                # Accumulate transcription text and track timing
                accumulated_text = ""
                last_speech_time = asyncio.get_event_loop().time()
                last_intervention_hash = ""  # Prevent duplicate sends

                async for event in runner.run_live(
                    user_id="user",
                    session_id=session_id,
                    live_request_queue=live_queue,
                    run_config=run_config,
                ):
                    current_time = asyncio.get_event_loop().time()

                    # Check for output transcription (model's spoken response as text)
                    if hasattr(event, "output_transcription") and event.output_transcription:
                        trans = event.output_transcription
                        if hasattr(trans, "text") and trans.text:
                            # Only add if not a duplicate of what we just added
                            new_text = trans.text
                            if not accumulated_text.endswith(new_text):
                                accumulated_text += new_text
                            last_speech_time = current_time

                    # Check for turn_complete to send accumulated transcription
                    if hasattr(event, "turn_complete") and event.turn_complete:
                        if accumulated_text.strip():
                            text = accumulated_text.strip()
                            # Create hash to prevent duplicate sends
                            text_hash = hash(text)
                            if text_hash != last_intervention_hash:
                                last_intervention_hash = text_hash
                                # Parse urgency from transcription
                                if "URGENT" in text.upper():
                                    urgency = "urgent"
                                elif "WATCH" in text.upper():
                                    urgency = "watch"
                                else:
                                    urgency = "note"
                                await websocket.send_json({
                                    "type": "intervention",
                                    "urgency": urgency,
                                    "content": text,
                                    "timestamp": current_time,
                                })
                            accumulated_text = ""

                    # Check for text content in the event
                    if hasattr(event, "content") and event.content:
                        for part in event.content.parts:
                            # Handle text parts
                            if hasattr(part, "text") and part.text:
                                text = part.text
                                # Parse urgency from response
                                if text.startswith("URGENT:"):
                                    urgency = "urgent"
                                elif text.startswith("WATCH:"):
                                    urgency = "watch"
                                else:
                                    urgency = "note"

                                await websocket.send_json({
                                    "type": "intervention",
                                    "urgency": urgency,
                                    "content": text,
                                    "timestamp": asyncio.get_event_loop().time(),
                                })

                            # Handle audio parts (send as base64)
                            if hasattr(part, "inline_data") and part.inline_data:
                                blob = part.inline_data
                                if blob.mime_type and "audio" in blob.mime_type:
                                    await websocket.send_json({
                                        "type": "audio",
                                        "data": base64.b64encode(blob.data).decode(),
                                        "mime_type": blob.mime_type,
                                    })

                    # Check for input transcription (what the counterparty/user said)
                    if hasattr(event, "input_transcription") and event.input_transcription:
                        trans = event.input_transcription
                        if hasattr(trans, "text") and trans.text:
                            await websocket.send_json({
                                "type": "transcript",
                                "speaker": "counterparty",
                                "content": trans.text,
                                "timestamp": current_time,
                            })
                            # Update last speech time for silence detection
                            active_sessions[session_id]["last_audio_time"] = current_time

                    # Check for transcript (legacy)
                    if hasattr(event, "transcript") and event.transcript:
                        await websocket.send_json({
                            "type": "transcript",
                            "content": event.transcript,
                        })

            except WebSocketDisconnect:
                pass
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "content": str(e),
                })

        # Monitor for silence (strategic pauses)
        async def monitor_silence():
            """Detect strategic silence/pauses in negotiation."""
            silence_threshold = 5.0  # seconds
            silence_alerted = False
            try:
                while True:
                    await asyncio.sleep(1)
                    session_data = active_sessions.get(session_id, {})
                    last_audio = session_data.get("last_audio_time", 0)
                    current_time = asyncio.get_event_loop().time()
                    silence_duration = current_time - last_audio if last_audio > 0 else 0

                    if silence_duration > silence_threshold and not silence_alerted:
                        silence_alerted = True
                        await websocket.send_json({
                            "type": "signal",
                            "signal_type": "silence",
                            "duration": round(silence_duration, 1),
                            "message": f"Strategic pause detected ({round(silence_duration)}s). They may be processing or waiting for you to fill the gap.",
                            "timestamp": current_time,
                        })
                    elif silence_duration <= 2:
                        silence_alerted = False  # Reset after speech resumes

            except (WebSocketDisconnect, asyncio.CancelledError):
                pass

        async def session_timeout_monitor():
            """Auto-end session after 5 minutes to prevent runaway costs."""
            try:
                created_at = session_data.get("created_at", asyncio.get_event_loop().time())
                while True:
                    await asyncio.sleep(10)
                    elapsed = asyncio.get_event_loop().time() - created_at
                    remaining = SESSION_TIMEOUT - elapsed

                    if 50 <= remaining <= 60:
                        await websocket.send_json({
                            "type": "warning",
                            "content": "Session ending in 1 minute (cost control)",
                        })

                    if elapsed >= SESSION_TIMEOUT:
                        await websocket.send_json({
                            "type": "timeout",
                            "content": "Session ended (5 minute limit)",
                        })
                        live_queue.close()
                        break
            except (WebSocketDisconnect, asyncio.CancelledError):
                pass

        # Run all tasks concurrently
        await asyncio.gather(
            receive_from_client(),
            send_to_client(),
            monitor_silence(),
            session_timeout_monitor(),
        )

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "content": str(e),
        })
    finally:
        if session_id in active_sessions:
            del active_sessions[session_id]
        await websocket.close()


@app.websocket("/ws/practice/{session_id}")
async def practice_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for practice mode with adversarial client.

    The adversary agent simulates a tough counterparty.
    User speaks, adversary responds, creating realistic negotiation practice.
    """
    await websocket.accept()

    if session_id not in active_sessions:
        await websocket.send_json({"type": "error", "content": "Session not found"})
        await websocket.close()
        return

    session_data = active_sessions[session_id]
    if session_data.get("mode") != "practice":
        await websocket.send_json({"type": "error", "content": "Not a practice session"})
        await websocket.close()
        return

    # Create runner for adversary agent
    adversary_runner = Runner(
        agent=adversary_agent,
        app_name="adversary",
        session_service=session_service,
    )

    live_queue = LiveRequestQueue()

    try:
        # Send initial scenario context - IMPORTANT: Tell adversary to WAIT for user
        context = session_data.get("context", "Practice negotiation")
        live_queue.send_content(
            types.Content(
                parts=[types.Part(text=f"""SCENARIO: {context}

CRITICAL INSTRUCTION: You are the counterparty in this negotiation practice.
- DO NOT speak first. WAIT for the consultant to speak.
- Only respond AFTER you hear them talk.
- Keep your responses SHORT (1-3 sentences).
- This is a back-and-forth conversation. Wait for them to finish speaking before you respond.
- Listen to their audio input before generating a response.""")]
            )
        )

        async def receive_from_user():
            try:
                while True:
                    data = await websocket.receive_json()
                    msg_type = data.get("type")

                    if msg_type == "audio":
                        audio_bytes = base64.b64decode(data["data"])
                        live_queue.send_realtime(
                            types.Blob(mime_type="audio/pcm", data=audio_bytes)
                        )

                    elif msg_type == "text":
                        live_queue.send_content(
                            types.Content(parts=[types.Part(text=data["data"])])
                        )

                    elif msg_type == "end":
                        live_queue.close()
                        break

            except WebSocketDisconnect:
                live_queue.close()

        async def send_adversary_response():
            accumulated_text = ""
            user_history = []  # Track what the user has said/committed to
            low_cost = session_data.get("low_cost_mode", False)
            try:
                # Use TEXT modality in low-cost mode (no audio generation = 80% cheaper)
                run_config = RunConfig(
                    response_modalities=["TEXT"] if low_cost else ["AUDIO"],
                    streaming_mode=StreamingMode.BIDI,
                    output_audio_transcription=None if low_cost else types.AudioTranscriptionConfig(),
                    input_audio_transcription=types.AudioTranscriptionConfig(),  # Transcribe user speech
                )

                async for event in adversary_runner.run_live(
                    user_id="user",
                    session_id=session_id,
                    live_request_queue=live_queue,
                    run_config=run_config,
                ):
                    # Send audio to user
                    if hasattr(event, "content") and event.content:
                        for part in event.content.parts:
                            if hasattr(part, "inline_data") and part.inline_data:
                                blob = part.inline_data
                                if blob.mime_type and "audio" in blob.mime_type:
                                    await websocket.send_json({
                                        "type": "adversary_audio",
                                        "data": base64.b64encode(blob.data).decode(),
                                        "mime_type": blob.mime_type,
                                    })

                    # Capture what the USER said (input transcription)
                    if hasattr(event, "input_transcription") and event.input_transcription:
                        trans = event.input_transcription
                        if hasattr(trans, "text") and trans.text and trans.text.strip():
                            user_text = trans.text.strip()
                            # Add to history if not duplicate
                            if not user_history or user_history[-1] != user_text:
                                user_history.append(user_text)
                                # Keep last 5 user statements for context
                                if len(user_history) > 5:
                                    user_history.pop(0)

                    # Accumulate adversary transcription
                    if hasattr(event, "output_transcription") and event.output_transcription:
                        trans = event.output_transcription
                        if hasattr(trans, "text") and trans.text:
                            if not accumulated_text.endswith(trans.text):
                                accumulated_text += trans.text

                    # Send transcript on turn complete AND generate coaching
                    if hasattr(event, "turn_complete") and event.turn_complete:
                        if accumulated_text.strip():
                            adversary_statement = accumulated_text.strip()

                            # 1. Send what adversary said
                            await websocket.send_json({
                                "type": "adversary_says",
                                "content": adversary_statement,
                            })

                            # 2. Generate coaching response from Secondus
                            # Include what the user has committed to
                            config = session_data.get("config", {})
                            user_history_text = "\n".join([f"- User said: \"{stmt}\"" for stmt in user_history[-3:]])

                            coaching = await generate_coaching(
                                adversary_text=adversary_statement,
                                goals=config.get("goals", ""),
                                batna=config.get("batna", ""),
                                user_history=user_history_text,
                            )

                            # 3. Send coaching to frontend
                            await websocket.send_json({
                                "type": "say_this",
                                "phrase": coaching["say_this"],
                                "context": coaching["context"],
                            })

                            accumulated_text = ""

            except WebSocketDisconnect:
                pass
            except Exception as e:
                await websocket.send_json({"type": "error", "content": str(e)})

        async def session_timeout_monitor():
            """Auto-end session after 5 minutes to prevent runaway costs."""
            try:
                created_at = session_data.get("created_at", asyncio.get_event_loop().time())
                while True:
                    await asyncio.sleep(10)  # Check every 10 seconds
                    elapsed = asyncio.get_event_loop().time() - created_at
                    remaining = SESSION_TIMEOUT - elapsed

                    # Warn at 1 minute remaining
                    if 50 <= remaining <= 60:
                        await websocket.send_json({
                            "type": "warning",
                            "content": "Session ending in 1 minute (cost control)",
                        })

                    # End session at timeout
                    if elapsed >= SESSION_TIMEOUT:
                        await websocket.send_json({
                            "type": "timeout",
                            "content": "Session ended (5 minute limit reached)",
                        })
                        live_queue.close()
                        break
            except (WebSocketDisconnect, asyncio.CancelledError):
                pass

        await asyncio.gather(
            receive_from_user(),
            send_adversary_response(),
            session_timeout_monitor(),
        )

    except Exception as e:
        await websocket.send_json({"type": "error", "content": str(e)})
    finally:
        # Clean up session
        if session_id in active_sessions:
            del active_sessions[session_id]
        await websocket.close()


@app.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    """Get the status of a negotiation session."""
    if session_id not in active_sessions:
        return {"error": "Session not found"}

    session_data = active_sessions[session_id]
    return {
        "session_id": session_id,
        "status": "active",
        "config": session_data.get("config", {}),
        "mode": session_data.get("mode", "live"),
    }


# Serve frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
