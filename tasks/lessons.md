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
