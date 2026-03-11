# Secondus — Task Tracker

## Current Sprint
Final polish for Gemini Live Agent Challenge submission.

## North Star
One flagship experience: **Secondus Buddy** — a seamless AI negotiation partner that pressures, detects contract drift, catches tactics, and coaches with one sharp intervention at a time.

## Completed Features ✓

### Frontend (React/TypeScript/Tailwind)
- [x] Modern React 18 + TypeScript + Vite build system
- [x] Tailwind CSS v4 styling
- [x] Clean session UI: Transcript + Coach Card + Signals
- [x] WebSocket-based real-time communication
- [x] Audio capture with 16kHz resampling
- [x] Audio playback with buffering queue
- [x] Screen share with manual capture/share flow
- [x] Document Scanner panel with extracted terms display
- [x] Webcam Picture-in-Picture self-view
- [x] Signal toasts with auto-dismiss and rate limiting
- [x] Session recap overlay with scoring breakdown

### Backend (FastAPI/Python)
- [x] Session orchestrator with state machine
- [x] Coach engine with Gemini 2.0 Flash
- [x] **LLM-based deal closure detection**
- [x] **LLM-based conversation circling detection**
- [x] Hybrid signal detection (LLM + deterministic)
- [x] Contract state management with term extraction
- [x] Gemini Vision document analysis
- [x] Signal rate limiting (30-45s cooldowns)
- [x] Recap engine with dynamic scoring
- [x] Camera-aware scoring weights (70/30 split)

### Multimodal Grounding
- [x] Structured contract term extraction (price, timeline, payment, scope)
- [x] Contract drift detection with evidence
- [x] Pressure tactic detection (anchoring, timeline, nibbling)
- [x] Transcript deduplication (time-based + content-based)
- [x] System message filtering from transcript

### UX Improvements
- [x] Session never auto-ends (user clicks End)
- [x] Deal closure updates metrics only
- [x] Manual document capture and share flow
- [x] No false circling signals during active negotiation
- [x] "THEM" label for counterparty (not "Buddy")
- [x] Filtered internal messages from transcript

### MediaPipe Presence Detection
- [x] MediaPipe Face Landmarker (468 landmarks + 52 blendshapes)
- [x] MediaPipe Pose Landmarker (33 body landmarks)
- [x] Real-time eye contact tracking via iris position
- [x] Posture analysis via shoulder/head alignment
- [x] Tension detection via facial blendshapes
- [x] Client-side ML processing (privacy-preserving)
- [x] Live presence metrics overlay in WebcamPip
- [x] Presence score breakdown in RecapOverlay
- [x] 70/30 voice/presence weighted scoring

## Remaining Tasks

### GCP Deployment ✓
- [x] Build frontend for production (`npm run build`)
- [x] Copy dist to backend/frontend-dist
- [x] Deploy to Cloud Run (`./deploy.sh`)
- [x] Health check passing
- [ ] Test full flow on Cloud Run (WebSocket + MediaPipe)

**Live URL:** https://secondus-853650293423.us-central1.run.app

### Submission Deliverables
- [ ] Record proof of live Google Cloud deployment
- [ ] Record 4-minute demo video
- [ ] Write Devpost submission copy
- [ ] Publish build write-up (bonus points)

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    SECONDUS BUDDY                           │
├─────────────────────────────────────────────────────────────┤
│  Frontend (React)           │  Backend (FastAPI)            │
│  ├─ SessionScreen           │  ├─ session_orchestrator.py   │
│  ├─ DocumentAnalysis        │  ├─ coach_engine.py           │
│  ├─ CoachCard               │  ├─ contract_state.py         │
│  ├─ SignalToast             │  ├─ recap_engine.py           │
│  └─ WebcamPip               │  └─ presence_engine.py        │
├─────────────────────────────────────────────────────────────┤
│  Google Cloud                                               │
│  ├─ Gemini Live API (2.5 Flash Native Audio)                │
│  ├─ Gemini Vision (Document Analysis)                       │
│  └─ Cloud Run (Deployment)                                  │
└─────────────────────────────────────────────────────────────┘
```

## Key Detection System

| Feature | Method | Trigger |
|---------|--------|---------|
| Deal Closure | LLM | "That works", "We'll proceed", etc. |
| Conversation Circling | LLM + Deterministic | Same topic without progress |
| Contract Drift | Deterministic | Spoken ≠ written terms |
| Pressure Tactics | Deterministic | Keyword patterns |

## Scoring System

| Camera State | Voice Score Weight | Presence Score Weight |
|--------------|-------------------|----------------------|
| Disabled | 100% | 0% (no penalty) |
| Enabled | 70% | 30% |

## Key Dates
- **March 13, 12:00 PM PT**: GCP credits request deadline
- **March 16, 5:00 PM PT**: Submission deadline
- **Demo video**: Only first 4 minutes judged
