# Secondus — Development Guidelines

## Mission

Build Secondus into a judge-ready, real-time negotiation copilot for the Gemini Live Agent Challenge.

The product should feel:
- seamless
- natural
- grounded
- calm under pressure

## Current State

### Frontend
- **Framework:** React 18 + TypeScript + Vite
- **Styling:** Tailwind CSS v4
- **ML:** MediaPipe Tasks Vision (Face + Pose Landmarker)
- **Components:** SessionScreen, DocumentAnalysis, CoachCard, SignalToast, WebcamPip, RecapOverlay

### Backend
- **Framework:** FastAPI + Python 3.13
- **Orchestrator:** session_orchestrator.py (state machine)
- **Coach:** coach_engine.py (LLM-powered with CLOSING/CIRCLING detection)
- **Contract:** contract_state.py (term extraction and drift detection)
- **Recap:** recap_engine.py (dynamic scoring with presence)
- **Presence:** presence_engine.py (MediaPipe metrics structure)

### Key Features Working
- LLM-based deal closure detection (via coaching LLM, not pattern matching)
- LLM-based conversation circling detection (hybrid: LLM + deterministic, strict threshold)
- Non-blocking document analysis (background tasks, never blocks WebSocket)
- Contract drift detection with acceptance-awareness (skips false positives)
- Signal rate limiting
- **MediaPipe presence detection** (eye contact, posture, tension)
- Camera-aware scoring (70/30 split when enabled)
- **LLM-judge scoring** (Gemini 2.5 Flash evaluates transcript, blended 40/60 with deterministic)
- 5-minute countdown timer with auto-cleanup on timeout
- Silence monitor suppressed during screen sharing
- Adversary transcript dedup (prevents "Sure, go ahead" x2)
- Coaching dedup (60% word overlap check + 3s per-turn cooldown)
- Session never auto-ends (user clicks End)
- **Presence metrics displayed in WebcamPip overlay**
- **Presence summary in RecapOverlay**

## Product Priorities

### 1. One Flagship Experience
- Default to `Secondus Buddy` as the live AI negotiation partner.
- Session only ends when user clicks "End" button.
- Deal closure detection updates metrics, doesn't end session.

### 2. LLM-Powered Detection
Coaching prompt returns structured signals:
```
CLOSING: YES/NO
CIRCLING: YES/NO
SAY THIS: [phrase]
```

Use hybrid approach: LLM + deterministic must agree for sensitive signals.

### 3. User-Controlled Document Sharing
- User clicks "Start Analysis" to begin scanning
- User scrolls through document while frames are captured
- User clicks "Done Scanning" to review terms
- User clicks "Share" to send context to counterpart
- Context sent to AI only once per explicit share

### 4. Real-Time Presence Analysis
- MediaPipe Face Landmarker (468 landmarks + 52 blendshapes)
- MediaPipe Pose Landmarker (33 body landmarks)
- All processing client-side (privacy-preserving)
- Metrics: eye_contact, posture, tension (0-100 each)
- Accumulated during session, averaged for recap

## Workflow

### Plan Before Large Changes
- Define target experience first.
- Work from product flow to architecture.
- Check if change supports the 4-minute demo story.

### Keep Docs In Sync
- Update `tasks.md` when sprint direction changes.
- Update `tasks/lessons.md` after corrections or discoveries.
- Update `AGENTS.md` when architecture changes.

### Verify Before Calling Work Done
- Run the app when changes affect the live flow.
- Test interruption handling when touching audio.
- Test transcript accuracy when touching voice pipelines.
- Test signal rate limiting when touching detection.
- Test presence detection when touching camera/MediaPipe.

## Architecture Rules

### Session Orchestrator Owns State
- Turn-taking and state transitions
- Signal emission with rate limiting
- Transcript accumulation
- Deal closure tracking
- Presence snapshot updates

### LLM Detection Piggybacks on Coaching
- Same API call returns coaching + detection signals
- Structured output format for reliable parsing
- Hybrid approach combines LLM + deterministic

### Scoring Is Camera-Aware
| Camera State | Voice Weight | Presence Weight |
|--------------|--------------|-----------------|
| Disabled | 100% | 0% |
| Enabled | 70% | 30% |

### Presence Detection Is Client-Side
- MediaPipe runs entirely in browser
- No video sent to server (privacy)
- Only aggregated metrics sent via WebSocket
- Metrics accumulated and averaged on session end

### Signals Are Rate Limited
- Track last emission time per signal type
- 30s cooldown for urgent signals
- 45s cooldown for watch/note signals

## Scoring Formula

### Voice Score (0-100)
```
turns = min(30, userTurns * 10)
tactics = min(25, uniqueTactics * 8)
progress = min(20, progressInstances * 10)
outcome = 25 if dealClosed else 0
penalties = stallingInstances * 5 + circlingInstances * 3

voiceScore = clamp(turns + tactics + progress + outcome - penalties, 0, 100)
```

### Presence Score (0-100, camera only)
```
eye = min(40, avgEyeContact * 0.4)
posture = min(35, avgPosture * 0.35)
tension = min(25, (100 - avgTension) * 0.25)

presenceScore = clamp(eye + posture + tension, 0, 100)
```

### Final Score
```
if cameraEnabled:
    final = voiceScore * 0.70 + presenceScore * 0.30
else:
    final = voiceScore

# Gates
if !userSpoke: final = 0
elif userTurns < 2: final = min(final, 30)
elif userTurns < 4: final = min(final, 60)

# Deal bonus
if dealClosed && userSpoke: final = max(final, 75)

final = clamp(final, 10, 100)
```

## UX Rules

### Session Flow
1. Launch → Click "Start Negotiation"
2. Session → Transcript + Coach Card + Signals
3. Recap → User clicks "End" → Score + Presence + Summary

### Session UI Zones
- **Left:** Document Scanner (when screen sharing)
- **Center:** Transcript with YOUR TURN indicator
- **Bottom:** Coach Card with "Say this now"
- **Top Right:** Signal toasts (auto-dismiss)
- **Bottom Right:** Webcam PiP with presence metrics overlay

### Webcam PiP Overlay
- Shows real-time eye contact, posture, relaxation bars
- Color-coded: green (≥70), amber (40-69), red (<40)
- "Loading AI..." while MediaPipe initializes

### Recap Presence Section
- Eye Contact bar with score
- Posture bar with score
- Relaxation bar (100 - tension)
- Feedback in strengths/improvements based on averages

### Signal Display
- One signal type visible at a time (rate limited)
- Auto-dismiss: urgent 6s, watch 5s, note 3s
- Click X to dismiss early

## Technical Rules

### Audio
- Resample to 16kHz before sending to Gemini
- Buffer playback audio before playing
- Clear buffer on interruption

### Transcript
- Filter system messages (starts with [, ends with ])
- Filter "(USER INTERRUPTS)" markers
- Deduplicate by time (3s) and content

### Contract
- Extract structured terms via Gemini Vision
- Normalize terms for comparison
- Show evidence in drift alerts

### Signals
- LLM detection for semantic concepts (closure, circling)
- Deterministic for patterns (anchoring, timeline)
- Hybrid when both must agree

### MediaPipe Presence
- Face Landmarker: 468 landmarks + 52 blendshapes
- Pose Landmarker: 33 landmarks (lite model)
- Process at 5 FPS to balance performance
- Send metrics to backend every 2s (rate-limited)
- Accumulate all metrics, average on session end

## Local Development

```bash
# Backend
cd backend
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
export GOOGLE_CLOUD_PROJECT="your-project-id"
python main.py
```

Frontend is served from `frontend/dist/` (built by `npm run build` in frontend/).

For frontend development with hot reload:
```bash
cd frontend
npm install
npm run dev
```

Then visit http://localhost:5173 (Vite dev server proxies API to backend).

## Deployment

```bash
./deploy.sh
```

This builds frontend, copies to backend, and deploys to Cloud Run.

## Key Files

| File | Purpose |
|------|---------|
| `backend/session_orchestrator.py` | Session state machine |
| `backend/coach_engine.py` | LLM coaching + detection |
| `backend/contract_state.py` | Term extraction + drift |
| `backend/recap_engine.py` | Scoring + recap generation |
| `backend/session_repository.py` | Optional Firestore session persistence |
| `backend/learnings.py` | Patterns, recommendations, briefing (JSON + Firestore) |
| `backend/presence_engine.py` | Presence metrics structure |
| `backend/adversary.py` | AI counterparty agent |
| `frontend/src/components/SessionScreen.tsx` | Main session UI |
| `frontend/src/components/WebcamPip.tsx` | Camera PiP + presence overlay |
| `frontend/src/components/RecapOverlay.tsx` | Session recap + presence display |
| `frontend/src/components/DocumentAnalysis.tsx` | Document scanner panel |
| `frontend/src/hooks/useSession.ts` | WebSocket management |
| `frontend/src/hooks/useCamera.ts` | Webcam + presence integration |
| `frontend/src/hooks/usePresenceDetection.ts` | MediaPipe Face + Pose |
| `frontend/src/hooks/useScreenShare.ts` | Screen capture + scanning |
