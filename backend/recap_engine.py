"""
Buddy recap helpers for backend-owned recap generation.

Hybrid approach: deterministic scoring + LLM-judge verification.

Scoring weights:
- When camera is NOT enabled: 100% voice/negotiation score
- When camera IS enabled: 70% voice/negotiation + 30% presence/emotional
"""

import asyncio
import json
import logging
import os
import re
from typing import Any

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "platinum-depot-489523-a7")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gemini-2.5-flash")

_judge_client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

LLM_JUDGE_PROMPT = """You are an expert negotiation evaluator. Analyze this negotiation transcript and score the USER's performance.

USER'S GOALS: {goals}
USER'S BATNA (walk-away alternative): {batna}

TRANSCRIPT:
{transcript}

SCORING CRITERIA (0-100):
1. **Outcome** (0-30): Did the user achieve their goals? Close to target price? Good terms?
2. **Tactics** (0-25): Did the user handle pressure well? Counter anchors? Trade concessions?
3. **Communication** (0-25): Clear, confident, assertive? Avoided hedging/apologizing?
4. **Progress** (0-20): Kept the negotiation moving? Made counter-offers? Avoided circling?

Return ONLY a valid JSON object:
{{
  "score": <int 0-100>,
  "deal_closed": <bool>,
  "deal_terms": "<brief summary of agreed terms or null>",
  "outcome_summary": "<1 sentence outcome>",
  "top_strength": "<1 sentence>",
  "top_improvement": "<1 sentence>",
  "breakdown": {{
    "outcome": <int 0-30>,
    "tactics": <int 0-25>,
    "communication": <int 0-25>,
    "progress": <int 0-20>
  }}
}}"""


async def llm_judge_score(session_data: dict) -> dict | None:
    """Get an unbiased LLM evaluation of the negotiation."""
    exchanges = session_data.get("exchanges", [])
    if len(exchanges) < 3:
        return None

    config = session_data.get("config", {})
    transcript_lines = []
    for ex in exchanges:
        speaker = "USER" if ex.get("speaker") == "user" else "COUNTERPART"
        transcript_lines.append(f"[{ex.get('timestamp', '')}] {speaker}: {ex.get('text', '')}")

    prompt = LLM_JUDGE_PROMPT.format(
        goals=config.get("goals", "Close the deal at a good price"),
        batna=config.get("batna", "Walk away"),
        transcript="\n".join(transcript_lines),
    )

    try:
        response = await asyncio.to_thread(
            _judge_client.models.generate_content,
            model=JUDGE_MODEL,
            contents=[prompt],
        )
        raw = response.text.strip()
        for marker in ("```json", "```"):
            if marker in raw:
                start = raw.find(marker) + len(marker)
                end = raw.find("```", start)
                raw = raw[start:end].strip() if end != -1 else raw[start:].strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as exc:
        logger.warning("LLM judge failed: %s", exc)
    return None


def detect_deal_closed(exchanges: list[dict[str, Any]]) -> bool:
    """Check if the transcript shows deal-closing language from both sides."""
    closing_phrases = [
        "we have a deal", "we've got a deal", "let's finalize",
        "finalize the contract", "send the contract", "send it over",
        "draw up the contract", "draw up the paperwork",
        "agreed on terms", "we're agreed", "works for us",
        "pleasure doing business", "looking forward to working",
        "excited to get started", "we accept", "we'll take it",
        "let's do it", "let's proceed", "we'll proceed",
        "move forward", "get the ball rolling", "that works",
        "receiving the contract", "talk soon", "send over",
        "let's make it happen", "can we close",
    ]
    if not exchanges:
        return False
    recent = exchanges[-8:] if len(exchanges) >= 8 else exchanges
    user_closing = False
    adversary_closing = False
    for exchange in recent:
        text = (exchange.get("text") or "").lower().strip()
        speaker = exchange.get("speaker", "")
        if any(phrase in text for phrase in closing_phrases):
            if speaker == "user":
                user_closing = True
            else:
                adversary_closing = True
    return user_closing or adversary_closing


def build_buddy_recap(session_data: dict[str, Any], llm_judge: dict | None = None) -> dict[str, Any]:
    metrics = session_data.get("metrics", {})
    exchanges = session_data.get("exchanges", [])
    coaching = session_data.get("coachingGiven", [])
    visual = session_data.get("visualPresence") or {}
    camera_enabled = session_data.get("cameraEnabled", False)

    # Count tactics from the tacticsDetected array (not metrics.tacticsUsed which doesn't exist)
    tactics_list = session_data.get("tacticsDetected", [])
    tactic_names = {t.get("name", "").upper() for t in tactics_list if t.get("name")}
    unique_tactics = len(tactic_names)
    tactic_count = len(tactics_list)

    user_exchanges = [e for e in exchanges if e.get("speaker") == "user"]
    user_participation = len(user_exchanges)
    user_actually_spoke = user_participation > 0

    # Deal closed only when BOTH LLM flagged closure AND transcript has explicit closing language
    # (avoids false "You reached a commitment" when user did not actually close)
    llm_said_closing = metrics.get("dealClosed", False)
    transcript_has_closing = detect_deal_closed(exchanges)
    deal_closed = llm_said_closing and transcript_has_closing

    # Detect progress from transcript (counter-offers, concessions, movement)
    progress_phrases = [
        "could we", "how about", "what if", "i can do", "i'm flexible",
        "meet in the middle", "compromise", "counter", "let's agree",
        "works for us", "that works", "we can do", "i'll accept",
        "in exchange", "if you", "trade", "offer", "adjusted",
    ]
    progress_instances = metrics.get("progressInstances", 0)
    for ex in exchanges:
        text = (ex.get("text") or "").lower()
        if any(p in text for p in progress_phrases):
            progress_instances += 1

    # === VOICE/NEGOTIATION SCORE (base 100 points) ===
    turn_score = min(30, user_participation * 10) if user_actually_spoke else 0
    tactic_score = min(25, unique_tactics * 8)
    progress_score = min(20, progress_instances * 5) if user_actually_spoke else 0
    outcome_score = 25 if deal_closed and user_actually_spoke else 0
    
    penalties = (metrics.get("stallingInstances", 0) * 5) + (metrics.get("circlingInstances", 0) * 3)
    voice_score = turn_score + tactic_score + progress_score + outcome_score - penalties
    voice_score = max(0, min(100, voice_score))

    # === PRESENCE SCORE (only when camera enabled, base 100 points) ===
    presence_score = 0
    if camera_enabled and visual and user_participation >= 2:
        eye_contact = visual.get("avgEyeContact", 50)  # Default to neutral if no data
        posture = visual.get("avgPosture", 50)
        tension = visual.get("avgTension", 30)  # Lower is better
        
        # Eye contact: 0-100 maps to 0-40 points
        presence_score += min(40, int(eye_contact * 0.4))
        # Posture: 0-100 maps to 0-35 points
        presence_score += min(35, int(posture * 0.35))
        # Low tension bonus: tension < 40 gives up to 25 points
        presence_score += max(0, min(25, int((100 - tension) * 0.25)))
        
        presence_score = max(0, min(100, presence_score))

    # === FINAL WEIGHTED SCORE ===
    if camera_enabled and visual:
        # Camera enabled: 70% voice + 30% presence
        score = int(voice_score * 0.7 + presence_score * 0.3)
    else:
        # Camera not enabled: 100% voice score (no penalty for missing presence)
        score = voice_score

    # Apply participation gates
    if not user_actually_spoke:
        score = 0
    elif user_participation < 2:
        score = min(score, 30)
    elif user_participation < 4:
        score = min(score, 60)
    
    score = max(10, min(100, score))
    
    # Deal closed bonus
    if deal_closed and user_actually_spoke:
        score = max(score, 75)

    # === LLM JUDGE BLEND ===
    # If we have an LLM judge score, blend 50/50 with deterministic for unbiased result
    llm_score = None
    if llm_judge and isinstance(llm_judge.get("score"), (int, float)):
        llm_score = max(10, min(100, int(llm_judge["score"])))
        if llm_judge.get("deal_closed") and not deal_closed:
            deal_closed = True
            score = max(score, 75)
        score = int(score * 0.4 + llm_score * 0.6)

    strengths: list[str] = []
    improvements: list[str] = []

    if not user_actually_spoke:
        improvements.append("You need to actually speak during the negotiation.")
    elif user_participation < 3:
        improvements.append("Stay in the conversation longer to build momentum.")

    if unique_tactics >= 3:
        strengths.append("Encountered diverse negotiation tactics — strong practice exposure.")
    if deal_closed and user_actually_spoke:
        strengths.append("Successfully reached a close or clear commitment.")
    if progress_instances > 0 and user_actually_spoke:
        strengths.append("Created forward movement in the negotiation.")
    if user_participation >= 5:
        strengths.append("Sustained a meaningful negotiation conversation.")

    # Presence feedback only when camera was enabled
    if camera_enabled and visual:
        if visual.get("avgEyeContact", 0) >= 70:
            strengths.append("Excellent eye contact on camera.")
        elif visual.get("avgEyeContact", 0) < 40:
            improvements.append("Maintain eye contact more consistently.")
        if visual.get("avgPosture", 0) >= 70:
            strengths.append("Strong posture throughout the round.")
        elif visual.get("avgPosture", 0) < 50:
            improvements.append("Improve posture and keep your shoulders open.")
        if visual.get("avgTension", 0) > 60:
            improvements.append("Relax facial tension before the next round.")
    elif camera_enabled and not visual:
        # Camera was enabled but no data collected
        improvements.append("Enable camera earlier to get presence coaching.")

    if metrics.get("stallingInstances", 0) >= 2:
        improvements.append("Push through stalling by asking directly for the real concern.")
    if metrics.get("circlingInstances", 0) >= 2:
        improvements.append("Recognize circling earlier and force a decision or follow-up.")
    if "NIBBLING" in tactic_names:
        improvements.append("Trade instead of giving extra concessions for free.")
    if "ANCHORING PRESSURE" in tactic_names:
        improvements.append("Counter-anchor confidently before discussing their budget.")

    all_user_text = " ".join(e.get("text", "").lower() for e in user_exchanges)
    if all_user_text:
        if not any(token in all_user_text for token in ["my rate", "my price", "i charge"]):
            improvements.append("State your price confidently earlier.")
        if any(token in all_user_text for token in ["maybe", "i guess", "i think so"]):
            improvements.append("Avoid hedging language — be more assertive.")
        if any(token in all_user_text for token in ["what do you think", "is that okay"]):
            improvements.append("Avoid seeking approval for your own terms.")
        if "sorry" in all_user_text or "apologize" in all_user_text:
            improvements.append("Do not apologize for your value.")
        if any(token in all_user_text for token in ["based on", "given that", "considering"]):
            strengths.append("Backed up your position with justification.")
        if any(token in all_user_text for token in ["if you", "in exchange", "trade"]):
            strengths.append("Used trading language well.")
        if any(token in all_user_text for token in ["walk away", "other options", "alternatives"]):
            strengths.append("Referenced your BATNA and showed leverage.")

    best_coaching = next((c for c in reversed(coaching) if c.get("phrase")), None)
    best_intervention = best_coaching.get("phrase") if best_coaching else "The coach kept the conversation moving with live prompts."

    biggest_risk = "No major pressure signal stood out."
    if "ANCHORING PRESSURE" in tactic_names:
        biggest_risk = "Low-anchor pressure on price."
    elif "NIBBLING" in tactic_names:
        biggest_risk = "Late-stage nibbling for extra concessions."
    elif "TIMELINE PRESSURE" in tactic_names:
        biggest_risk = "Artificial urgency/timeline pressure."
    elif metrics.get("circlingInstances", 0) >= 2:
        biggest_risk = "Conversation circling without commitment."
    elif metrics.get("stallingInstances", 0) >= 2:
        biggest_risk = "Stalling instead of a direct objection."

    if not user_actually_spoke:
        outcome = "No real negotiation happened yet."
    elif deal_closed:
        outcome = "You reached a close or a clear commitment."
    elif progress_instances > 0:
        outcome = "You created movement, but did not fully close."
    else:
        outcome = "The counterpart exposed pressure points to improve next time."

    # Merge LLM judge insights
    if llm_judge:
        if llm_judge.get("outcome_summary"):
            outcome = llm_judge["outcome_summary"]
        if llm_judge.get("deal_terms"):
            outcome += f" Terms: {llm_judge['deal_terms']}"
        if llm_judge.get("top_strength") and llm_judge["top_strength"] not in strengths:
            strengths.insert(0, llm_judge["top_strength"])
        if llm_judge.get("top_improvement") and llm_judge["top_improvement"] not in improvements:
            improvements.insert(0, llm_judge["top_improvement"])

    scoring_breakdown = {
        "voice_score": voice_score,
        "presence_score": presence_score if camera_enabled else None,
        "voice_weight": 70 if camera_enabled else 100,
        "presence_weight": 30 if camera_enabled else 0,
        "deal_closed": deal_closed,
        "llm_judge_score": llm_score,
        "llm_judge_breakdown": llm_judge.get("breakdown") if llm_judge else None,
    }

    # Build visual_summary in the format frontend expects
    visual_summary = None
    if camera_enabled and visual:
        visual_summary = {
            "avgEyeContact": visual.get("avgEyeContact", 50),
            "avgPosture": visual.get("avgPosture", 50),
            "avgTension": visual.get("avgTension", 30),
            "dominantEmotion": visual.get("dominantEmotion", "neutral"),
            "totalSamples": visual.get("totalSamples", 0),
        }

    return {
        "score": score,
        "scoring_breakdown": scoring_breakdown,
        "duration": session_data.get("session", {}).get("duration", ""),
        "user_participation": user_participation,
        "buddy_turns": metrics.get("totalTurns", 0),
        "pressure_signals": tactic_count,
        "outcome": outcome,
        "best_intervention": best_intervention,
        "biggest_risk": biggest_risk,
        "next_focus": improvements[0] if improvements else "Keep sessions longer and respond directly to pressure.",
        "strengths": strengths[:5] or ["Complete a few more turns for sharper feedback."],
        "moments": coaching[-3:],
        "visual_summary": visual_summary,
        "camera_enabled": camera_enabled,
        "improvements": improvements[:6],
    }
