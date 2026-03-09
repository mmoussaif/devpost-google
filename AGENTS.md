# Secondus — Agent Architecture

## Overview

Secondus is a **real-time negotiation intelligence agent** that acts as the user's trusted advisor during live deal conversations. The name comes from dueling tradition — your "second" is the person who stands behind you, knows your strategy, and protects your interests.

## Agent Design

### Core Agent: Secondus

**Model**: `gemini-3.1-flash`
**Framework**: Google ADK with bidi-streaming
**Mode**: Real-time multimodal (audio + vision)

### Input Streams

| Stream | Format | Frequency |
|--------|--------|-----------|
| Audio | 16kHz PCM, base64 | Continuous |
| Screen | JPEG frames, base64 | Every 2 seconds |
| Context | Text (goals, BATNA, terms) | Session start |

### Output Format

The agent responds with urgency-coded interventions:

```
URGENT: [Immediate barge-in required] Brief, actionable intervention
WATCH: [Important but not immediate] Tactical observation
NOTE: [For later review] Pattern or detail to remember
```

## Agent Capabilities

### 1. Drift Detection
Compares spoken terms against the written document on screen. Flags contradictions immediately.

**Example**: Contract says "Net 30" but they're verbally agreeing to "Net 60"

### 2. Tactic Recognition
Identifies manipulation tactics and suggests counters:
- Anchoring
- Artificial urgency
- Good cop/bad cop
- Nibbling
- Flinching
- Silence pressure
- Limited authority claims

### 3. Leverage Spotting
Catches moments when the counterparty reveals:
- Flexibility on terms
- Concession patterns
- Information that shifts leverage

### 4. Barge-In Behavior
The agent can interrupt the conversation for high-urgency situations:
- User about to agree to contradictory terms
- Manipulation tactic requires immediate counter
- Leverage opportunity about to pass

Lower-urgency observations are queued as notes.

## System Prompt

Located in `backend/agent.py`. Key characteristics:
- Concise, direct tone (1-2 sentences max per intervention)
- Tactical, not emotional
- Never condescending
- Whisper-style brevity

## ADK Integration

### Session Management
```python
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

runner = Runner(
    agent=root_agent,
    app_name="secondus",
    session_service=session_service,
)
```

### Bidi-Streaming
```python
async with runner.run_live(
    session_id=session_id,
    live_connect_config=run_config,
) as live_session:
    # Send audio/screen
    await live_session.send_realtime(audio_blob)
    await live_session.send_content(screen_content)

    # Receive interventions
    async for event in live_session.receive():
        process_intervention(event)
```

## Future Agents (Planned)

### Post-Session Analyzer
Reviews the full negotiation transcript and provides:
- Summary of concessions made
- Tactics used by counterparty
- Recommendations for follow-up

### Contract Comparator
Compares the final agreed terms against:
- Original document
- Industry benchmarks
- Previous deals

## Development Notes

### Adding New Capabilities
1. Update the system prompt in `backend/agent.py`
2. Add corresponding UI handling in `frontend/index.html`
3. Test with mock negotiation scenarios

### Debugging
- Check `/health` endpoint for model status
- WebSocket messages logged in browser console
- ADK session state in `InMemorySessionService`
