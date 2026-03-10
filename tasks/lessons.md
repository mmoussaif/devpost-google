# Secondus — Lessons Learned

## Session Log

### 2026-03-09: Project Setup

**Context**: Initial project creation for Gemini Live Agent Challenge

**Corrections Applied**:
1. Use `gemini-live-2.5-flash-native-audio` not `gemini-2.0-flash-live-001`
2. Use Python 3.13+ not 3.11
3. Use `python:3.13-slim` Docker image

**Rules Derived**:
- Always confirm model version before writing agent code
- Default to latest stable Python (3.13) for new projects
- Check user preferences for runtime versions early

---

*Add new lessons below as corrections are received*

### 2026-03-10: Web Audio & UI Sync Lessons

**Context**: Audio detection conflicts and contradictory UI states during live tests.

**Issues Fixed**:
1. `SpeechRecognition` and `getUserMedia` can conflict if initialized too closely together on some browsers, resulting in silent `network` errors.
   - *Fix applied*: Added a 1500ms delay to `startSpeechRecognition` after mic stream is acquired.
2. The AI model's coaching response (server-side) can contradict client-side heuristic logic (e.g. client sees agreement, server complains about price).
   - *Fix applied*: Introduced `clientDetectedAgreement` flag. Client-side state overrides server coaching when closing signals are detected.
3. Transcripts can be totally missed if Speech Recognition fails completely.
   - *Fix applied*: Add a fallback `[Speech detected — transcript unavailable]` if raw audio volume exceeds threshold but speech API returns nothing.

### 2026-03-10: Practice Mode — Real Conversation Transcript & Screen Share

**Context**: User said "hello hello", adversary replied "Yes", but the live conversation UI showed other things; after sharing screen the flow was "a mess" and user hadn't spoken.

**Root causes**:
1. **Transcript source conflict**: In practice mode the UI used the browser’s Web Speech API for user lines, which was failing with `Speech recognition error: network`. The backend already sent the real transcript via `user_says` (Gemini input_transcription) but it was treated as a fallback and could be overwritten or duplicated by the broken client-side recognition.
2. **Screen share confusing the agent**: Screen frames were sent into the adversary’s live queue every 2s. The model received mixed audio + document images and reacted to the document instead of the user’s voice, breaking conversation and transcript sync.

**Fixes applied**:
1. **Backend-only transcript in practice mode**: Stopped starting Web Speech API in practice mode. The "LIVE CONVERSATION" panel now uses only backend messages: `user_says` (what Gemini heard) and `adversary_says` (what the model said). `user_says` handler now also updates `sessionRecording.exchanges`, `setTurnState('user')`, and `analyzeUserResponse()` so session analysis and UI stay in sync.
2. **Screen for coach only**: In practice WebSocket, on `screen` message we only store `latest_screen` for the coach (drift detection). We no longer send screen content to the adversary’s `live_queue`, so the live conversation stays audio-only and transcript matches what was actually said.
3. **Transcript entry selector**: Added speaker class to transcript entries (`transcript-entry user` / `transcript-entry adversary`) so duplicate checks for `user_says` work correctly.

**Rules derived**:
- In practice/live voice flows, prefer a single source of truth for transcript (backend = what the model heard/said); avoid mixing client-side speech recognition with backend transcript.
- When mixing modalities (audio + screen), don’t inject screen into the same stream the voice agent consumes if the goal is a clean voice conversation; use screen only in separate analysis (e.g. coach/drift).
