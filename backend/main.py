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
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from agent import root_agent

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "platinum-depot-489523-a7")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# Session management
session_service = InMemorySessionService()
active_sessions: dict[str, dict[str, Any]] = {}


class SessionConfig(BaseModel):
    """Configuration for a new negotiation session."""
    goals: str = ""
    batna: str = ""
    key_terms: list[str] = []
    counterparty: str = ""


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
        "model": "gemini-3.1-flash",
        "project": PROJECT_ID,
    }


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

    # Run configuration for bidi-streaming
    run_config = types.LiveConnectConfig(
        response_modalities=["TEXT"],
    )

    try:
        # Start the live session
        async with runner.run_live(
            session_id=session_id,
            live_connect_config=run_config,
        ) as live_session:

            # Send initial context
            await live_session.send_content(
                types.Content(
                    parts=[types.Part(text=f"SESSION CONTEXT:\n{context}")]
                )
            )

            # Handle bidirectional communication
            async def receive_from_client():
                """Receive and forward client messages to the agent."""
                try:
                    while True:
                        data = await websocket.receive_json()
                        msg_type = data.get("type")

                        if msg_type == "audio":
                            # PCM audio chunk
                            audio_bytes = base64.b64decode(data["data"])
                            await live_session.send_realtime(
                                types.Blob(
                                    mime_type="audio/pcm",
                                    data=audio_bytes,
                                )
                            )

                        elif msg_type == "screen":
                            # JPEG screen capture
                            image_bytes = base64.b64decode(data["data"])
                            await live_session.send_content(
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
                            # Direct text input
                            await live_session.send_content(
                                types.Content(
                                    parts=[types.Part(text=data["data"])]
                                )
                            )

                        elif msg_type == "end":
                            break

                except WebSocketDisconnect:
                    pass

            async def send_to_client():
                """Forward agent responses to the client."""
                try:
                    async for event in live_session.receive():
                        if hasattr(event, "text") and event.text:
                            # Parse urgency from response
                            text = event.text
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

                        elif hasattr(event, "transcript") and event.transcript:
                            await websocket.send_json({
                                "type": "transcript",
                                "content": event.transcript,
                            })

                except WebSocketDisconnect:
                    pass

            # Run both directions concurrently
            await asyncio.gather(
                receive_from_client(),
                send_to_client(),
            )

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "content": str(e),
        })
    finally:
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
        "config": session_data["config"],
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
