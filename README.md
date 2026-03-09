# Secondus

**Real-Time Negotiation Intelligence Agent**

> Your trusted second in high-stakes deals — like the advisor who stands behind you in a duel, knowing your strategy and protecting your interests.

[![Category](https://img.shields.io/badge/Category-Live%20Agent-blue)]()
[![Gemini](https://img.shields.io/badge/Model-Gemini%203.1%20Flash-orange)]()
[![Cloud Run](https://img.shields.io/badge/Hosted-Google%20Cloud%20Run-green)]()

![Architecture](docs/architecture.svg)

## The Problem

In high-stakes negotiations, you're on your own. Legal review happens before and after — never during the moment that matters. Skilled counterparties use tactics like anchoring, artificial urgency, and nibbling to extract concessions you didn't intend to make. By the time you realize what happened, the deal is signed.

## The Solution

Secondus is a **real-time negotiation intelligence agent** that:

- **Listens** to your live conversation via microphone
- **Watches** your contract or term sheet via screen share
- **Interrupts** at the right moment with tactical guidance (barge-in capability)

This breaks the "text box" paradigm — Secondus doesn't wait for you to ask a question. It proactively alerts you when it spots:

- **Drift Detection** — Spoken terms contradicting the written document
- **Tactic Recognition** — Manipulation tactics (anchoring, artificial urgency, nibbling) with suggested counters
- **Leverage Moments** — When the counterparty reveals flexibility you can exploit

## Tech Stack

| Component | Technology |
|-----------|------------|
| Model | **Gemini 3.1 Flash** via Gemini Live API |
| Framework | **Google ADK** with bidi-streaming (`run_live()`) |
| Backend | **FastAPI** on **Cloud Run** |
| Frontend | Vanilla HTML/JS with WebSocket, WebRTC |
| Storage | **Cloud Firestore** for session state |

## Quick Start

### Prerequisites

- Python 3.13+
- Google Cloud project with Vertex AI enabled
- `gcloud` CLI authenticated

### Local Development

```bash
# Clone and setup
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
export GOOGLE_CLOUD_PROJECT="your-project-id"
gcloud auth application-default login

# Run
python main.py
```

Open http://localhost:8080

### Deploy to Cloud Run

```bash
chmod +x deploy.sh
./deploy.sh
```

## Project Structure

```
secondus/
├── backend/
│   ├── main.py          # FastAPI + ADK bidi-streaming server
│   ├── agent.py         # Secondus agent definition
│   └── requirements.txt
├── frontend/
│   └── index.html       # Live session UI
├── docs/
│   └── architecture.svg # System architecture diagram
├── deploy.sh            # One-command Cloud Run deployment
└── README.md
```

## How It Works

1. **Setup Phase** — User enters goals, BATNA, key terms, and counterparty info
2. **Live Session** — Browser captures mic audio (16kHz PCM) and screen (JPEG frames)
3. **ADK Processing** — `Runner.run_live()` streams data to Gemini 3.1 Flash
4. **Interventions** — Agent responds with urgency-coded alerts:
   - `URGENT` — Requires immediate attention (barge-in)
   - `WATCH` — Important tactical observation
   - `NOTE` — Detail to remember for later

## Gemini Live Agent Challenge 2026

Built for the [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com) hackathon.

| | |
|---|---|
| **Category** | Live Agent |
| **Mandatory Tech** | Gemini Live API via ADK bidi-streaming |
| **Cloud Hosting** | Google Cloud Run |

### Google Cloud Services Used

| Service | Purpose |
|---------|---------|
| **Vertex AI** | Gemini 3.1 Flash model access |
| **Cloud Run** | Serverless backend hosting |
| **Cloud Firestore** | Session state persistence |

### Key Features for Judging

- **Beyond Text Box**: Proactive barge-in interruptions, not reactive Q&A
- **Multimodal**: Simultaneous audio + vision processing
- **Barge-In**: Agent interrupts conversation at critical moments
- **ADK Native**: Uses `Runner.run_live()` for proper bidi-streaming
- **Automated Deployment**: `deploy.sh` for infrastructure-as-code

---

Built by [@mmoussaif](https://github.com/mmoussaif)

`#GeminiLiveAgentChallenge`
