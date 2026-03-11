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
- **Components:** SessionScreen, DocumentAnalysis, CoachCard, SignalToast, WebcamPip

### Backend
- **Framework:** FastAPI + Python 3.13
- **Orchestrator:** session_orchestrator.py (state machine)
- **Coach:** coach_engine.py (LLM-powered with CLOSING/CIRCLING detection)
- **Contract:** contract_state.py (term extraction and drift detection)
- **Recap:** recap_engine.py (dynamic scoring)

### Key Features Working
- LLM-based deal closure detection
- LLM-based conversation circling detection
- Manual document capture and share flow
- Contract drift detection with evidence
- Signal rate limiting
- Camera-aware scoring (70/30 split when enabled)
- Session never auto-ends (user clicks End)

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

## Architecture Rules

### Session Orchestrator Owns State
- Turn-taking and state transitions
- Signal emission with rate limiting
- Transcript accumulation
- Deal closure tracking

### LLM Detection Piggybacks on Coaching
- Same API call returns coaching + detection signals
- Structured output format for reliable parsing
- Hybrid approach combines LLM + deterministic

### Scoring Is Camera-Aware
| Camera State | Voice Weight | Presence Weight |
|--------------|--------------|-----------------|
| Disabled | 100% | 0% |
| Enabled | 70% | 30% |

### Signals Are Rate Limited
- Track last emission time per signal type
- 30s cooldown for urgent signals
- 45s cooldown for watch/note signals

## UX Rules

### Session Flow
1. Launch → Click "Start Negotiation"
2. Session → Transcript + Coach Card + Signals
3. Recap → User clicks "End" → Score + Summary

### Session UI Zones
- **Left:** Document Scanner (when screen sharing)
- **Center:** Transcript with YOUR TURN indicator
- **Bottom:** Coach Card with "Say this now"
- **Top Right:** Signal toasts (auto-dismiss)
- **Bottom Right:** Webcam PiP (when camera on)

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
| `backend/adversary.py` | AI counterparty agent |
| `frontend/src/components/SessionScreen.tsx` | Main session UI |
| `frontend/src/components/RecapOverlay.tsx` | Session recap display |
| `frontend/src/components/DocumentAnalysis.tsx` | Document scanner panel |
| `frontend/src/hooks/useSession.ts` | WebSocket management |
| `frontend/src/hooks/useScreenShare.ts` | Screen capture + scanning |
