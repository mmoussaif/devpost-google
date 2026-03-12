# Secondus — Task Tracker

## Current Status: SUBMITTED ✓

Secondus has been submitted to the **Gemini Live Agent Challenge** on Devpost.

**Live Demo:** https://secondus-svmgok3hyq-uc.a.run.app  
**GitHub:** https://github.com/mmoussaif/devpost-google  
**Demo Video:** https://youtu.be/ffmS4bpW0UQ  
**Medium Article:** Published for bonus points  

## Challenge Requirements Met ✓

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Leverage Gemini model | ✓ | Gemini 2.5 Flash (Live) + 2.0 Flash (Vision) |
| Built with GenAI SDK or ADK | ✓ | Google ADK for adversary agent |
| Google Cloud service | ✓ | Cloud Run, Cloud Build, Vertex AI |
| Text description | ✓ | Devpost Project Story complete |
| PUBLIC Code Repo + README | ✓ | github.com/mmoussaif/devpost-google |
| Proof of GCP deployment | ✓ | Live URL + Cloud Run console |
| Architecture Diagram | ✓ | In AGENTS.md + Medium images |
| 4-min Demo Video | ✓ | YouTube link submitted |
| **Bonus: Published content** | ✓ | Medium article (0.6 pts) |
| **Bonus: Automated deployment** | ✓ | deploy.sh script (0.2 pts) |
| **Bonus: GDG Profile** | ✓ | g.dev/mohammedaminemoussaif (0.2 pts) |

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
- [x] LLM-based deal closure detection
- [x] LLM-based conversation circling detection
- [x] Hybrid signal detection (LLM + deterministic)
- [x] Contract state management with term extraction
- [x] Gemini Vision document analysis
- [x] Signal rate limiting (30-45s cooldowns)
- [x] Recap engine with dynamic scoring
- [x] Camera-aware scoring weights (70/30 split)

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

### GCP Deployment
- [x] Build frontend for production
- [x] Deploy to Cloud Run
- [x] Health check passing
- [x] Full flow tested (WebSocket + MediaPipe)

### Submission Deliverables
- [x] Proof of live Google Cloud deployment
- [x] 4-minute demo video on YouTube
- [x] Devpost submission copy complete
- [x] Medium article published (bonus)
- [x] GDG profile public (bonus)
- [x] Automated deployment script (bonus)

---

## Product Roadmap (Post-Hackathon)

### Phase 1: Enhanced Agent Capabilities

#### Agent Marketplace
- [ ] Multiple agent personalities (aggressive buyer, friendly vendor, skeptical investor)
- [ ] Industry-specific agents (real estate, salary negotiation, vendor contracts)
- [ ] Difficulty levels (beginner, intermediate, advanced)
- [ ] Custom agent builder via prompt configuration

#### Multi-Agent Simulations
- [ ] Board meeting simulations with multiple AI participants
- [ ] Team negotiation scenarios (2v2, 3v3)
- [ ] Role-switching (practice both sides of the table)
- [ ] Observer mode for learning from agent-vs-agent

### Phase 2: Personalization & Learning

#### Agent Memory
- [ ] Session history persistence across sessions
- [ ] Progress tracking over time
- [ ] Weakness identification and targeted practice
- [ ] "Last session you struggled with anchoring" feedback
- [ ] Achievement system and skill badges

#### Learning Paths
- [ ] Structured curriculum based on negotiation frameworks
- [ ] Harvard PON module (BATNA, ZOPA, anchoring)
- [ ] Chris Voss module (tactical empathy, mirroring)
- [ ] Fisher & Ury module (principled negotiation)
- [ ] Adaptive difficulty based on performance

### Phase 3: Enterprise & Integration

#### Calendar & CRM Integration
- [ ] Pre-meeting practice powered by prospect data
- [ ] Salesforce/HubSpot integration
- [ ] Google Calendar meeting prep reminders
- [ ] Post-meeting analysis and coaching

#### Team Features
- [ ] Team dashboards with aggregate analytics
- [ ] Manager review of team practice sessions
- [ ] Benchmarking against team averages
- [ ] Shared scenario library

#### API & SDK
- [ ] REST API for session management
- [ ] Embeddable widget for LMS platforms
- [ ] Webhook notifications for session events
- [ ] White-label deployment option

### Phase 4: Advanced Intelligence

#### Enhanced Presence Analysis
- [ ] Hand gesture recognition
- [ ] Micro-expression detection
- [ ] Voice tone analysis (confidence, hesitation)
- [ ] Real-time physiological stress indicators

#### Advanced Coaching
- [ ] Multi-language support (Spanish, French, Mandarin)
- [ ] Cultural negotiation style adaptation
- [ ] Industry jargon recognition
- [ ] Legal/compliance boundary detection

#### Analytics & Insights
- [ ] Trend analysis across sessions
- [ ] A/B testing of coaching strategies
- [ ] ROI calculator for enterprise customers
- [ ] Exportable reports for performance reviews

### Phase 5: Platform Expansion

#### Mobile App
- [ ] iOS and Android native apps
- [ ] Offline practice mode with local models
- [ ] Push notification reminders
- [ ] Apple Watch/WearOS presence metrics

#### Browser Extension
- [ ] Real-time coaching during Zoom/Meet calls
- [ ] Non-intrusive overlay mode
- [ ] Post-call summary and recommendations
- [ ] Privacy-first design (all local processing)

#### VR/AR Integration
- [ ] Oculus Quest practice environment
- [ ] Realistic meeting room simulations
- [ ] Full-body presence tracking
- [ ] Spatial audio for immersive scenarios

---

## Technical Debt & Improvements

### Performance
- [ ] WebSocket reconnection with exponential backoff
- [ ] Audio worklet migration (replace ScriptProcessorNode)
- [ ] MediaPipe WASM optimization
- [ ] Lazy loading for non-critical components

### Reliability
- [ ] End-to-end tests with Playwright
- [ ] Error boundary implementation
- [ ] Sentry integration for error tracking
- [ ] Health check dashboard

### Security
- [ ] Rate limiting on WebSocket connections
- [ ] Input validation on all endpoints
- [ ] CSP headers configuration
- [ ] Dependency audit automation

---

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
│  ├─ WebcamPip + MediaPipe   │  └─ presence_engine.py        │
│  └─ RecapOverlay            │                               │
├─────────────────────────────────────────────────────────────┤
│  Google Cloud                                               │
│  ├─ Gemini Live API (2.5 Flash Native Audio)                │
│  ├─ Gemini 2.0 Flash (Vision + Coaching)                    │
│  ├─ Vertex AI (Enterprise API access)                       │
│  ├─ Cloud Run (Serverless deployment)                       │
│  └─ Cloud Build (CI/CD pipeline)                            │
├─────────────────────────────────────────────────────────────┤
│  Client-Side ML                                             │
│  ├─ MediaPipe Face Landmarker (468 landmarks)               │
│  ├─ MediaPipe Pose Landmarker (33 landmarks)                │
│  └─ Privacy-first (no video sent to server)                 │
└─────────────────────────────────────────────────────────────┘
```

## Scoring System

| Camera State | Voice Weight | Presence Weight |
|--------------|--------------|-----------------|
| Disabled | 100% | 0% (no penalty) |
| Enabled | 70% | 30% |

## Key Dates
- **March 11, 2026**: Devpost submission completed
- **March 16, 2026, 5:00 PM PT**: Submission deadline
- **March 17-23, 2026**: Judging period (estimated)
