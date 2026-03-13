"""
Secondus Backend — ADK Bidi-Streaming Server

FastAPI server with WebSocket support for real-time negotiation intelligence.
Uses Google ADK's native bidi-streaming for Gemini Live API integration.
"""

import asyncio
import base64
import os
import uuid
import warnings
from contextlib import asynccontextmanager
from typing import Any

# Suppress Pydantic serialization warning for response_modalities enum
# This is a known issue in Google ADK's internal serialization
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings",
    category=UserWarning,
    module="pydantic.main",
)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.runners import Runner, RunConfig
from google.adk.agents.run_config import StreamingMode
from google.adk.sessions import InMemorySessionService
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.genai import types
from pydantic import BaseModel

from agent import root_agent
from adversary import adversary_agent
from coach_engine import generate_coaching
from session_orchestrator import ActiveSessionStore, BuddySessionOrchestrator
from learnings import analyze_session, get_pre_session_briefing, get_quick_tip
from recap_engine import build_buddy_recap
from session_repository import save_session as persist_session

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "platinum-depot-489523-a7")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# Set environment variables for ADK to use Vertex AI
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = LOCATION
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"

# Session management
session_service = InMemorySessionService()
session_store = ActiveSessionStore()


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
    session_store.clear()
    print("Secondus shutting down")


OPENAPI_DESCRIPTION = """
**Secondus** is a real-time negotiation copilot API built around a **Gemini Live Agent**. It powers the Secondus web app with:

- **Live Agent (Gemini Live API)** — Voice-based AI agent (Google ADK) that speaks and listens in real time as the negotiation counterparty (Maya Chen, TechNova CTO). Uses the Gemini Live female voice. Native bidirectional audio via WebSocket.
- **WebSocket** — Live session with the agent: start, audio stream, end.
- **REST** — Session lifecycle, recap, learnings (briefing, analyze, tactic tips).
- **Firestore** — Persistence of completed sessions (Session Memory) for analytics and future learnings.

### Authentication
Endpoints are currently unauthenticated (demo). In production, protect with IAP or API keys.

### Base URL
- Local: `http://localhost:8080`
- Cloud Run: `https://<service-url>.run.app`
"""
OPENAPI_TAGS = [
    {"name": "Health", "description": "Liveness and readiness"},
    {"name": "Learnings", "description": "Pre-session briefing, session analysis, tactic tips"},
    {"name": "Session", "description": "Recap generation and session completion"},
]

app = FastAPI(
    title="Secondus API",
    description=OPENAPI_DESCRIPTION.strip(),
    version="1.0.0",
    openapi_tags=OPENAPI_TAGS,
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


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check for Cloud Run and load balancers. Returns service name and project."""
    return {
        "status": "ok",
        "service": "secondus",
        "model": "gemini-live-2.5-flash-native-audio",
        "project": PROJECT_ID,
    }


# ============ Learning System Endpoints ============

@app.get("/learnings/briefing", tags=["Learnings"])
async def get_briefing():
    """Get personalized pre-session briefing from accumulated learnings (focus areas, stats)."""
    return get_pre_session_briefing()


@app.post("/learnings/analyze", tags=["Learnings"])
async def analyze_session_endpoint(session_data: dict):
    """Analyze a completed session and persist patterns to learnings store (JSON + optional Firestore)."""
    return analyze_session(session_data)


@app.post("/session/buddy/recap", tags=["Session"])
async def build_buddy_recap_endpoint(session_data: dict):
    """Build recap (score, outcome, strengths, improvements). Persists session to Firestore in background."""
    normalized = dict(session_data)
    normalized["visualPresence"] = session_data.get("visualPresence") or {}
    stored = analyze_session(normalized)
    recap = build_buddy_recap(normalized)
    recap["stored_analysis"] = stored
    # Fire-and-forget persist to Firestore (Session Memory); no impact on response or demo flow
    asyncio.get_event_loop().run_in_executor(
        None,
        lambda: persist_session(normalized, stored, recap_summary=recap),
    )
    return recap


@app.get("/learnings/tip/{tactic}", tags=["Learnings"])
async def get_tactic_tip(tactic: str):
    """Get a short counter-tip for a given tactic (e.g. ANCHORING, NIBBLING)."""
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
    context = f"PRACTICE MODE - Scenario: {config.scenario}\nYour goals: {config.goals}\nYour BATNA: {config.batna}"
    session_store.create_buddy_session(
        session_id=session_id,
        config=config.model_dump(),
        context=context,
        low_cost_mode=config.low_cost_mode,
    )

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

    session_store.create_live_session(
        session_id=session_id,
        config=config.model_dump(),
        context=context,
        session=session,
    )

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

    if not session_store.exists(session_id):
        await websocket.send_json({"type": "session.error", "content": "Session not found", "error": "Session not found"})
        await websocket.close()
        return

    session_data = session_store.require(session_id)
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
        async def emit_live_event(payload: dict[str, Any]) -> None:
            await websocket.send_json(payload)

        async def emit_live_text_signal(text: str, timestamp: float) -> None:
            upper = text.upper()
            if "SAY THIS:" in upper:
                idx = upper.find("SAY THIS:")
                phrase = text[idx + 9 :].strip().strip('"').strip("'")
                await emit_live_event(
                    {
                        "type": "coach.recommendation",
                        "phrase": phrase,
                        "context": "Live coaching recommendation",
                    }
                )
                return

            signal_type = "note"
            title = "Coach signal"
            if upper.startswith("TACTIC:"):
                signal_type = "tactic"
                title = "Tactic detected"
            elif upper.startswith("DRIFT:"):
                signal_type = "drift"
                title = "Contract drift"
            elif upper.startswith("LEVERAGE:"):
                signal_type = "leverage"
                title = "Leverage"
            elif upper.startswith("WATCH:"):
                signal_type = "watch"
                title = "Watch closely"
            elif upper.startswith("URGENT:"):
                signal_type = "urgent"
                title = "Act now"

            await emit_live_event(
                {
                    "type": "signal.alert",
                    "urgency": signal_type if signal_type in {"urgent", "watch"} else "note",
                    "title": title,
                    "message": text,
                    "signal_type": signal_type,
                    "timestamp": timestamp,
                }
            )

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
                                mime_type="audio/pcm;rate=16000",
                                data=audio_bytes,
                            )
                        )
                        # Track audio activity for silence detection
                        session_store.update_last_audio_time(session_id, asyncio.get_event_loop().time())

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
                                        text="[Screen capture from user. This is likely a contract or scope document. Extract key terms like price, payment schedule, timeline, revisions, and liability. CRITICAL: Analyze this against the counterparty's verbal offers. If they verbally offer terms worse than what is in this document, immediately issue a 'DRIFT: [Contract says X, they said Y]' alert.]"
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
                    response_modalities=[types.Modality.AUDIO],
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
                                await emit_live_text_signal(text, current_time)
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

                                await emit_live_text_signal(text, asyncio.get_event_loop().time())

                            # Handle audio parts (send as base64)
                            if hasattr(part, "inline_data") and part.inline_data:
                                blob = part.inline_data
                                if blob.mime_type and "audio" in blob.mime_type:
                                    await emit_live_event({
                                        "type": "media.audio",
                                        "data": base64.b64encode(blob.data).decode(),
                                        "mime_type": blob.mime_type,
                                    })

                    # Check for input transcription (what the counterparty/user said)
                    if hasattr(event, "input_transcription") and event.input_transcription:
                        trans = event.input_transcription
                        if hasattr(trans, "text") and trans.text:
                            await emit_live_event({
                                "type": "transcript.append",
                                "speaker": "adversary",
                                "content": trans.text,
                                "timestamp": current_time,
                            })
                            # Update last speech time for silence detection
                            session_store.update_last_audio_time(session_id, current_time)

                    # Check for transcript (legacy)
                    if hasattr(event, "transcript") and event.transcript:
                        await emit_live_event({
                            "type": "transcript.append",
                            "speaker": "adversary",
                            "content": event.transcript,
                        })

            except WebSocketDisconnect:
                pass
            except Exception as e:
                await emit_live_event({
                    "type": "session.error",
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
                    session_data = session_store.get(session_id) or {}
                    last_audio = session_data.get("last_audio_time", 0)
                    current_time = asyncio.get_event_loop().time()
                    silence_duration = current_time - last_audio if last_audio > 0 else 0

                    if silence_duration > silence_threshold and not silence_alerted:
                        silence_alerted = True
                        await emit_live_event({
                            "type": "signal.alert",
                            "urgency": "watch",
                            "signal_type": "silence",
                            "title": "Strategic pause",
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
                        await emit_live_event({
                            "type": "session.warning",
                            "content": "Session ending in 1 minute (cost control)",
                        })

                    if elapsed >= SESSION_TIMEOUT:
                        await emit_live_event({
                            "type": "session.timeout",
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
            "type": "session.error",
            "content": str(e),
        })
    finally:
        session_store.pop(session_id)
        await websocket.close()


@app.websocket("/ws/practice/{session_id}")
async def practice_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for practice mode with adversarial client.

    The adversary agent simulates a tough counterparty.
    User speaks, adversary responds, creating realistic negotiation practice.
    """
    await websocket.accept()

    if not session_store.exists(session_id):
        await websocket.send_json({"type": "session.error", "content": "Session not found", "error": "Session not found"})
        await websocket.close()
        return

    session_data = session_store.require(session_id)
    if session_data.get("mode") != "practice":
        await websocket.send_json({"type": "session.error", "content": "Not a Buddy session", "error": "Not a Buddy session"})
        await websocket.close()
        return

    adversary_runner = Runner(
        agent=adversary_agent,
        app_name="adversary",
        session_service=session_service,
    )

    live_queue = LiveRequestQueue()
    orchestrator = BuddySessionOrchestrator(
        session_id=session_id,
        session_data=session_data,
        session_store=session_store,
        websocket=websocket,
        live_queue=live_queue,
        coaching_fn=generate_coaching,
    )

    try:
        await asyncio.gather(
            orchestrator.receive_from_user(),
            orchestrator.send_adversary_response(adversary_runner),
            orchestrator.session_timeout_monitor(),
            orchestrator.silence_monitor(),
        )

    except (ConnectionClosedOK, ConnectionClosed) as e:
        # Normal when user clicks End: client closes WS, Gemini Live closes with 1000 (OK)
        if e.code != 1000:
            print(f"Practice websocket closed: {e}", flush=True)
    except Exception as e:
        import traceback
        print(f"Practice websocket error: {e}", flush=True)
        traceback.print_exc()
        try:
            await orchestrator.emit({"type": "session.error", "content": str(e)})
        except Exception:
            pass
    finally:
        session_store.pop(session_id)
        try:
            await websocket.close()
        except Exception:
            pass


@app.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    """Get the status of a negotiation session."""
    if not session_store.exists(session_id):
        return {"error": "Session not found"}
    return session_store.status_payload(session_id)


# Serve frontend — try Vite build output, then Docker-copied dist, then legacy
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
frontend_docker = os.path.join(os.path.dirname(__file__), "frontend-dist")
frontend_legacy = os.path.join(os.path.dirname(__file__), "..", "frontend-legacy")

frontend_path = next(
    (p for p in [frontend_dist, frontend_docker, frontend_legacy] if os.path.exists(p)),
    frontend_legacy,
)

if os.path.exists(frontend_path):
    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "index.html"))

    @app.get("/contract.html")
    async def serve_contract():
        contract = os.path.join(frontend_path, "contract.html")
        if not os.path.exists(contract):
            contract = os.path.join(frontend_legacy, "contract.html")
        return FileResponse(contract)

    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
