# Secondus — Agent Architecture & System Design

> Your trusted second in high-stakes deals — like the advisor who stands behind you in a duel, knowing your strategy and protecting your interests.

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Diagrams](#architecture-diagrams)
3. [Agent Design](#agent-design)
4. [Visual Intelligence Pipeline](#visual-intelligence-pipeline)
5. [Learning System](#learning-system)
6. [Practice Mode](#practice-mode)
7. [API Reference](#api-reference)
8. [Cost Management](#cost-management)
9. [Deployment Architecture](#deployment-architecture)

---

## System Overview

Secondus is a **real-time negotiation intelligence agent** built for the Gemini Live Agent Challenge 2026. It breaks the traditional "text box" paradigm by proactively coaching users during live negotiations.

### Core Capabilities

| Capability | Description | Technology |
|------------|-------------|------------|
| **Drift Detection** | Spots contradictions between spoken and written terms | Gemini Live multimodal |
| **Tactic Recognition** | Identifies manipulation tactics with counters | ADK streaming |
| **Visual Coaching** | Real-time body language feedback | MediaPipe |
| **Personalized Learning** | Tracks patterns, provides research-backed advice | Pattern analysis |
| **Barge-In** | Interrupts conversation at critical moments | ADK bidi-streaming |

---

## Architecture Diagrams

### High-Level System Architecture

```mermaid
flowchart TB
    subgraph Client["Frontend (Browser)"]
        UI[Session UI]
        WS[WebSocket Client]
        MP[MediaPipe<br/>Face/Pose/Hands]
        MIC[Microphone<br/>16kHz PCM]
        SCR[Screen Capture<br/>JPEG frames]
    end

    subgraph Backend["Backend (Cloud Run)"]
        FP[FastAPI Server]
        ADK[Google ADK<br/>Runner.run_live]
        LS[Learning System]
        SS[Session Service]
    end

    subgraph Google["Google Cloud"]
        GL[Gemini Live API<br/>gemini-live-2.5-flash]
        FS[Cloud Firestore]
        VA[Vertex AI]
    end

    MIC --> WS
    SCR --> WS
    MP --> UI
    WS <--> FP
    FP <--> ADK
    ADK <--> GL
    LS <--> FS
    GL --> VA
    FP --> LS

    style GL fill:#4285F4,color:white
    style ADK fill:#34A853,color:white
    style MP fill:#EA4335,color:white
```

### Component Diagram

```mermaid
flowchart LR
    subgraph Frontend
        direction TB
        A1[index.html]
        A2[WebSocket Handler]
        A3[MediaPipe Processor]
        A4[Audio Processor]
        A5[Cost Tracker]
        A6[Learning UI]
    end

    subgraph Backend
        direction TB
        B1[main.py<br/>FastAPI]
        B2[agent.py<br/>Secondus Agent]
        B3[learnings.py<br/>Pattern Tracker]
    end

    subgraph External
        direction TB
        C1[Gemini Live API]
        C2[Firestore]
    end

    A1 --> A2
    A1 --> A3
    A1 --> A4
    A1 --> A5
    A1 --> A6
    A2 <--> B1
    B1 --> B2
    B1 --> B3
    B2 <--> C1
    B3 <--> C2
```

### Data Flow — Practice Session

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant B as Backend
    participant G as Gemini Live
    participant L as Learning System

    Note over U,L: Session Setup
    U->>F: Enter goals, BATNA, terms
    F->>B: POST /practice/start
    B->>L: GET briefing
    L-->>B: Focus areas, past patterns
    B-->>F: Session ready + briefing

    Note over U,L: Live Practice (5 min max)
    loop Every frame
        F->>F: MediaPipe analysis
        F->>F: Update visual coaching UI
    end

    loop Real-time audio
        U->>F: Speak
        F->>B: Audio chunk (16kHz PCM)
        B->>G: Send audio
        G-->>B: Adversary response
        B-->>F: Audio + coaching
        F-->>U: Play audio + show tactics
    end

    Note over U,L: Session End
    U->>F: End session
    F->>B: Session data
    B->>L: POST /learnings/analyze
    L-->>B: Patterns + recommendations
    B-->>F: Session report
    F-->>U: Display analysis
```

### Real-Time Audio Pipeline

```mermaid
flowchart LR
    subgraph Input["User Input"]
        MIC[Microphone] --> WA[Web Audio API<br/>16kHz PCM]
        WA --> B64E[Base64 Encode]
    end

    subgraph Transport["WebSocket"]
        B64E --> WS[WebSocket Frame]
        WS --> ADK[ADK Runner]
    end

    subgraph Gemini["Gemini Live"]
        ADK --> GL[Gemini Live API]
        GL --> RESP[Response Audio<br/>24kHz PCM]
    end

    subgraph Output["User Output"]
        RESP --> B64D[Base64 Decode]
        B64D --> SPK[Speaker]
    end

    style GL fill:#4285F4,color:white
```

---

## Agent Design

### Core Agent: Secondus

| Property | Value |
|----------|-------|
| **Model** | `gemini-live-2.5-flash-native-audio` |
| **Framework** | Google ADK with bidi-streaming |
| **Mode** | Real-time multimodal (audio + vision) |
| **Session Timeout** | 5 minutes (cost control) |

### Agent State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle: Initialize
    Idle --> Listening: Session Start
    Listening --> Analyzing: Audio/Screen Input
    Analyzing --> Coaching: Tactic Detected
    Analyzing --> Listening: Normal Exchange
    Coaching --> Listening: Guidance Delivered
    Listening --> Reporting: Session End
    Reporting --> [*]: Analysis Complete

    Listening --> [*]: Timeout (5 min)
```

### Input Streams

| Stream | Format | Frequency | Cost |
|--------|--------|-----------|------|
| Audio | 16kHz PCM, base64 | Continuous | ~$0.00025/sec |
| Screen | JPEG frames, base64 | Every 2s | ~$0.001315/image |
| Context | Text (goals, BATNA) | Session start | Minimal |

### Output Format

The agent responds with urgency-coded interventions:

```
SAY THIS: [Exact phrase for user to speak] — Most important!
TACTIC: [Name] - [One-line counter] — For manipulation tactics
DRIFT: [Contract says X, they said Y] — For contradictions
CONFIDENCE: [Voice coaching tip] — For delivery improvement
```

### System Prompt Architecture

```mermaid
flowchart TB
    subgraph SystemPrompt["System Prompt (agent.py)"]
        ROLE[Role Definition<br/>"You are Secondus, a real-time negotiation COACH"]
        CONTEXT[Context Awareness<br/>Audio, Screen, Goals, BATNA]
        TACTICS[Tactic Counters<br/>Anchoring, Urgency, Nibbling...]
        OUTPUT[Output Format<br/>SAY THIS, TACTIC, DRIFT]
        VOICE[Voice Coaching<br/>Pace, Tone, Confidence]
    end

    ROLE --> CONTEXT
    CONTEXT --> TACTICS
    TACTICS --> OUTPUT
    OUTPUT --> VOICE
```

### Tactic Detection Library

| Tactic | Detection Signal | Counter Response |
|--------|------------------|------------------|
| **ANCHORING** | Low first offer | "State YOUR number first" |
| **FLINCHING** | Price surprise reaction | "Silence for 3 seconds, then explain ROI" |
| **NIBBLING** | Extra asks after agreement | "That's outside scope. I can add for $X" |
| **LIMITED AUTHORITY** | "Need to check with boss" | "Let's get them on a call" |
| **URGENCY** | Artificial deadlines | "If timing is critical, let's lock terms now" |
| **CIRCLING** | Same topic repeated | "What's the real concern here?" |

---

## Visual Intelligence Pipeline

### MediaPipe Integration

```mermaid
flowchart TB
    subgraph Input["Camera Input"]
        CAM[Webcam Stream]
    end

    subgraph MediaPipe["MediaPipe Processing"]
        FM[Face Mesh<br/>468 landmarks]
        PS[Pose<br/>33 landmarks]
        HD[Hands<br/>21 landmarks x2]
    end

    subgraph Analysis["Analysis Layer"]
        EYE[Eye Contact<br/>Gaze direction]
        EMO[Emotion<br/>Facial tension]
        POST[Posture<br/>Lean, distance]
        GEST[Gestures<br/>Steepling, palms]
    end

    subgraph Output["Coaching Output"]
        SCORE[Quality Scores<br/>0-100%]
        COACH[Visual Coaching<br/>Tips & alerts]
        BARS[Progress Bars<br/>Color-coded]
    end

    CAM --> FM
    CAM --> PS
    CAM --> HD
    FM --> EYE
    FM --> EMO
    PS --> POST
    HD --> GEST
    EYE --> SCORE
    EMO --> SCORE
    POST --> SCORE
    GEST --> SCORE
    SCORE --> COACH
    COACH --> BARS

    style FM fill:#EA4335,color:white
    style PS fill:#EA4335,color:white
    style HD fill:#EA4335,color:white
```

### Landmark Detection

| Model | Landmarks | What We Detect |
|-------|-----------|----------------|
| **Face Mesh** | 468 points | Eye contact, facial tension, head tilt |
| **Pose** | 33 points | Forward/back lean, shoulder width, framing |
| **Hands** | 21 x 2 points | Steepling, open palms, face touching |

### Gesture Detection (Research-Based)

Based on Joe Navarro's body language principles:

| Gesture | MediaPipe Detection | Score Impact |
|---------|---------------------|--------------|
| **Steepling** | Fingertips within 30px, hands above waist | +25 points |
| **Open Palms** | Palm angle facing camera | +15 points |
| **Face Touching** | Hand landmarks near face landmarks | -20 points |

### Visual Coaching UI

```
┌─────────────────────────────────────┐
│ VISUAL COACH              😐 neutral │
│ ┌─────────────────────────────────┐ │
│ │    [Webcam + Face/Hand Mesh]    │ │
│ └─────────────────────────────────┘ │
│ Eye Contact [████████░░] 80%        │  ← Green (70%+)
│ Posture     [██████░░░░] 60%        │  ← Yellow (40-70%)
│ Gestures    [███░░░░░░░] 30%        │  ← Red (<40%)
│ ✋ Open palms — signals honesty      │
│                                     │
│ Est. Cost: $0.42 | Time: 3:24/5:00  │
└─────────────────────────────────────┘
```

**Color Coding:**
- 🟢 Green (70%+): Excellent
- 🟡 Yellow (40-70%): Needs attention
- 🔴 Red (<40%): Needs improvement

---

## Learning System

### Pattern Tracking Architecture

```mermaid
flowchart TB
    subgraph Session["Practice Session"]
        EX[Exchanges]
        TC[Tactics Detected]
        VS[Visual Scores]
        CO[Concessions Made]
    end

    subgraph Analysis["Pattern Analysis (learnings.py)"]
        AS[analyze_session]
        EW[Extract Weaknesses]
        ES[Extract Strengths]
        GR[Generate Recommendations]
    end

    subgraph Storage["Persistent Storage"]
        FS[(user_learnings.json)]
        PT[Patterns]
        RC[Recommendations]
    end

    subgraph Output["Pre-Session Briefing"]
        BR[get_pre_session_briefing]
        FA[Focus Areas]
        ST[Stats: Close Rate]
    end

    EX --> AS
    TC --> AS
    VS --> AS
    CO --> AS
    AS --> EW
    AS --> ES
    EW --> GR
    ES --> GR
    GR --> FS
    FS --> PT
    FS --> RC
    PT --> BR
    RC --> BR
    BR --> FA
    BR --> ST
```

### Tracked Patterns

**Weaknesses (Auto-Detected):**

| Pattern | Detection Trigger | Recommendation |
|---------|-------------------|----------------|
| `STALLING_TOLERANCE` | >5 stall instances | Set time limits early |
| `GAVE_EQUITY` | Equity mentioned in concessions | Demand extended commitment |
| `PAYMENT_TERMS_WEAKNESS` | Net-90 accepted | Counter with discount offer |
| `LOW_EYE_CONTACT` | <40% average eye contact | Look at camera lens |
| `NIBBLING_VULNERABILITY` | 3+ nibble tactics faced | "That's outside scope" |
| `ALLOWED_CIRCLING` | 3+ topic repetitions | Call out directly |

**Strengths (Auto-Detected):**

| Pattern | Detection Trigger |
|---------|-------------------|
| `HELD_PRICE` | No price drops in exchanges |
| `CLOSED_DEAL` | Deal marked as closed |
| `STRONG_EYE_CONTACT` | >70% average eye contact |

### Research-Backed Recommendations

| Source | Applied To |
|--------|------------|
| **Harvard PON** | Time pressure, BATNA usage |
| **Chris Voss** | Trading concessions, labeling |
| **Joe Navarro** | Body language, eye contact |

### Recommendation Engine

```mermaid
flowchart LR
    subgraph Input
        WK[Weaknesses<br/>sorted by frequency]
        TC[Tactics Faced<br/>sorted by count]
    end

    subgraph Library
        RL[RECOMMENDATION_LIBRARY<br/>weakness → action]
        TR[TACTICS_RESPONSES<br/>tactic → counter]
    end

    subgraph Output
        REC[Recommendations<br/>with priority]
    end

    WK --> RL
    TC --> TR
    RL --> REC
    TR --> REC
```

---

## Practice Mode

### Adversary Agent

```mermaid
flowchart TB
    subgraph Config["Practice Config"]
        SC[Scenario<br/>SaaS Contract, etc.]
        GO[Goals<br/>User objectives]
        BT[BATNA<br/>Best alternative]
        DF[Difficulty<br/>easy/medium/hard]
        LC[Low Cost Mode<br/>TEXT vs AUDIO]
    end

    subgraph Adversary["Adversary Agent"]
        AP[Adversary Prompt<br/>Tough counterparty role]
        TL[Tactics Library<br/>Based on difficulty]
        VO[Voice/Text Output]
    end

    subgraph Analysis["Real-Time Analysis"]
        TD[Tactic Detection]
        SP[Stalling Tracker]
        NB[Nibble Counter]
    end

    Config --> Adversary
    AP --> TL
    TL --> VO
    VO --> Analysis
    Analysis --> Adversary
```

### Difficulty Levels

| Level | Tactics Used | Frequency |
|-------|--------------|-----------|
| **Easy** | Anchoring, Flinching | Occasional |
| **Medium** | + Nibbling, Urgency | Regular |
| **Hard** | + Limited Authority, Circling, Good Cop/Bad Cop | Aggressive |

### Session Flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as Adversary Agent
    participant C as Coach System

    Note over U,C: Opening
    A->>U: Anchoring move
    C-->>U: TACTIC: Counter-anchor immediately

    Note over U,C: Negotiation
    loop Until timeout or close
        U->>A: Response
        A->>U: Counter or tactic
        C-->>U: Real-time coaching
    end

    Note over U,C: Closing
    alt Deal Closed
        U->>A: Agreement
        A->>U: Confirmation
    else Timeout
        C-->>U: Time limit reached
    end

    Note over U,C: Analysis
    C->>C: Extract patterns
    C-->>U: Session report
```

---

## API Reference

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with model status |
| `/learnings/briefing` | GET | Pre-session personalized briefing |
| `/learnings/analyze` | POST | Analyze session and extract patterns |
| `/learnings/tip/{tactic}` | GET | Quick counter-tip for a tactic |

### WebSocket Endpoints

| Endpoint | Purpose | Message Format |
|----------|---------|----------------|
| `/ws/negotiate` | Live negotiation session | `{type, data, sessionId}` |
| `/ws/practice` | Practice with AI adversary | `{type, audio, config}` |

### WebSocket Message Types

**Client → Server:**
```json
{
  "type": "audio_chunk",
  "data": "<base64 PCM 16kHz>",
  "sessionId": "uuid"
}

{
  "type": "screen_capture",
  "data": "<base64 JPEG>",
  "sessionId": "uuid"
}

{
  "type": "end_session",
  "data": {
    "metrics": {...},
    "exchanges": [...],
    "tacticsDetected": [...],
    "visualPresence": {...}
  }
}
```

**Server → Client:**
```json
{
  "type": "intervention",
  "urgency": "URGENT|WATCH|NOTE",
  "text": "SAY THIS: ..."
}

{
  "type": "audio_response",
  "audio": "<base64 PCM 24kHz>"
}

{
  "type": "session_analysis",
  "patterns": {...},
  "recommendations": [...]
}

{
  "type": "timeout_warning",
  "remaining_seconds": 60
}
```

---

## Cost Management

### API Pricing Model

```mermaid
pie title Session Cost Distribution
    "Audio Output (70%)" : 70
    "Audio Input (20%)" : 20
    "Screen Captures (10%)" : 10
```

### Rate Structure

| Resource | Rate | Per Session (5 min) |
|----------|------|---------------------|
| Audio Input | $0.00025/sec | ~$0.075 |
| Audio Output | $0.001/sec | ~$0.30 |
| Screen Captures | $0.001315/image | ~$0.20 (150 images) |
| **Total Estimate** | | **~$0.58/session** |

### Cost Control Features

```mermaid
flowchart TB
    subgraph Controls["Cost Control Mechanisms"]
        TO[Session Timeout<br/>5 minutes max]
        LC[Low-Cost Mode<br/>TEXT modality]
        CT[Real-Time Tracker<br/>UI display]
        BA[Budget Alerts<br/>GCP billing]
    end

    subgraph Implementation
        TO --> |"SESSION_TIMEOUT = 300"| BE[Backend]
        LC --> |"response_modalities=['TEXT']"| BE
        CT --> |"costTracker object"| FE[Frontend]
        BA --> |"gcloud billing budgets"| GCP[GCP Console]
    end
```

### Low-Cost Mode

When enabled:
- Uses `TEXT` modality instead of `AUDIO`
- Reduces output costs by ~70%
- Still provides real-time coaching via text

### Budget Alert Setup

```bash
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="Secondus Budget Alert" \
  --budget-amount=50USD \
  --threshold-rule=percent=0.50,basis=current-spend \
  --threshold-rule=percent=0.90,basis=current-spend \
  --threshold-rule=percent=1.00,basis=current-spend
```

---

## Deployment Architecture

### Cloud Run Deployment

```mermaid
flowchart TB
    subgraph Source["Source"]
        GH[GitHub Repo]
    end

    subgraph Build["Cloud Build"]
        DF[Dockerfile]
        CB[Cloud Build Trigger]
    end

    subgraph Deploy["Cloud Run"]
        CR[Cloud Run Service<br/>secondus]
        ENV[Environment<br/>GOOGLE_CLOUD_PROJECT]
        SA[Service Account<br/>Vertex AI access]
    end

    subgraph Services["Google Cloud Services"]
        VA[Vertex AI API]
        FS[Firestore]
        BB[Billing Budgets]
    end

    GH --> CB
    CB --> DF
    DF --> CR
    CR --> ENV
    CR --> SA
    SA --> VA
    SA --> FS
    SA --> BB
```

### Deployment Script (deploy.sh)

```bash
#!/bin/bash
gcloud run deploy secondus \
  --source=./backend \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
  --memory=1Gi \
  --timeout=300
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `PORT` | Server port (default: 8080) |

### Required APIs

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  firestore.googleapis.com \
  billingbudgets.googleapis.com
```

---

## Development Guide

### Local Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export GOOGLE_CLOUD_PROJECT="your-project-id"
gcloud auth application-default login
python main.py
```

### Testing

```bash
cd backend
pytest tests/ -v
```

### Adding New Capabilities

1. Update system prompt in `backend/agent.py`
2. Add UI handling in `frontend/index.html`
3. Update pattern tracking in `backend/learnings.py`
4. Add tests in `backend/tests/`
5. Update this documentation

### Debugging

| Component | Debug Method |
|-----------|--------------|
| Frontend | Browser console, MediaPipe overlay |
| WebSocket | Network tab, message logging |
| Backend | FastAPI logs, `/health` endpoint |
| ADK | Session service inspection |
| Gemini | Vertex AI console, usage metrics |

---

## Future Roadmap

### Planned Features

```mermaid
timeline
    title Secondus Roadmap
    section MVP (Current)
      Practice Mode : Adversary agent, visual coaching
      Learning System : Pattern tracking, recommendations
    section v1.1
      Live Mode : Real negotiation support
      Contract Analysis : Document parsing
    section v1.2
      Multi-Party : Support for group negotiations
      Mobile : PWA support
    section v2.0
      Enterprise : Team analytics, CRM integration
      Custom Adversaries : Train on real counterparties
```

### Contract Comparator (Planned)

Compare final agreed terms against:
- Original document
- Industry benchmarks
- Previous deals

---

## References

### Official Hackathon Resources

- [ADK Bidi-Streaming Development Guide](https://google.github.io/adk-docs/streaming/dev-guide/part1/) — Core implementation patterns
- [ADK Bidi-Streaming Demo](https://github.com/google/adk-samples/tree/main/python/agents/bidi-demo) — Reference architecture
- [ADK Visual Guide (Medium)](https://medium.com/google-cloud/adk-bidi-streaming-a-visual-guide-to-real-time-multimodal-ai-agent-development-62dd08c81399) — Agent lifecycle
- [ADK Bidi-Streaming in 5 Minutes (YouTube)](https://www.youtube.com/watch?v=vLUkAGeLR1k) — Quick overview
- [Live API Notebooks](https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/multimodal-live-api) — Multimodal patterns
- [Live Bidirectional Streaming Agent Codelab](https://codelabs.developers.google.com/way-back-home-level-3/instructions#0) — Step-by-step tutorial
- [Google Developer Community](https://developers.google.com/community) — GDG network

### Negotiation Research

- [Harvard Program on Negotiation](https://www.pon.harvard.edu/) — Time pressure, BATNA
- [Never Split the Difference — Chris Voss](https://www.blackswanltd.com/) — Tactical empathy, labeling
- [What Every BODY is Saying — Joe Navarro](https://www.jnforensics.com/) — Body language signals

### Technical Documentation

- [Google ADK Documentation](https://cloud.google.com/vertex-ai/docs/generative-ai/agent-builder/adk)
- [MediaPipe Documentation](https://developers.google.com/mediapipe)
- [Gemini Live API](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/multimodal-live)

---

Built for [Gemini Live Agent Challenge 2026](https://geminiliveagentchallenge.devpost.com)

`#GeminiLiveAgentChallenge`
