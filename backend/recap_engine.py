"""
Buddy recap helpers for backend-owned recap generation.

Scoring weights:
- When camera is NOT enabled: 100% voice/negotiation score
- When camera IS enabled: 70% voice/negotiation + 30% presence/emotional
"""

from typing import Any


def detect_deal_closed(exchanges: list[dict[str, Any]]) -> bool:
    """Check if a deal was reached based on conversation content."""
    closing_phrases = [
        "proceed with", "we'll proceed", "let's proceed",
        "that works", "that could work", "sounds good",
        "we have a deal", "deal", "agreed",
        "let's do it", "let's finalize", "finalize",
        "send the contract", "draw up", "paperwork",
        "pleasure doing business",
        "looking forward to working", "excited to get started",
        "let's get started", "we'll take it", "we accept",
        "we can do that", "can do that", "i can do that",
        "move that forward", "move forward",
        "good bye", "goodbye", "talk soon", "talk later",
    ]
    
    # Check last few exchanges for closing language
    recent = exchanges[-5:] if len(exchanges) >= 5 else exchanges
    for exchange in recent:
        text = exchange.get("text", "").lower()
        if any(phrase in text for phrase in closing_phrases):
            return True
    return False


def build_buddy_recap(session_data: dict[str, Any]) -> dict[str, Any]:
    metrics = session_data.get("metrics", {})
    exchanges = session_data.get("exchanges", [])
    coaching = session_data.get("coachingGiven", [])
    visual = session_data.get("visualPresence") or {}
    camera_enabled = session_data.get("cameraEnabled", False)

    tactic_count = sum(metrics.get("tacticsUsed", {}).values())
    unique_tactics = len(metrics.get("tacticsUsed", {}))
    user_exchanges = [e for e in exchanges if e.get("speaker") == "user"]
    user_participation = len(user_exchanges)
    user_actually_spoke = user_participation > 0

    # Check for deal closure from both metrics and conversation analysis
    deal_closed = metrics.get("dealClosed", False) or detect_deal_closed(exchanges)

    # === VOICE/NEGOTIATION SCORE (base 100 points) ===
    turn_score = min(30, user_participation * 10) if user_actually_spoke else 0
    tactic_score = min(25, unique_tactics * 8)
    progress_score = min(20, metrics.get("progressInstances", 0) * 10) if user_actually_spoke else 0
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
    if metrics.get("progressInstances", 0) > 0 and user_actually_spoke:
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
    if metrics.get("tacticsUsed", {}).get("NIBBLING", 0) >= 2:
        improvements.append("Trade instead of giving extra concessions for free.")
    if metrics.get("tacticsUsed", {}).get("ANCHORING", 0):
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
    if metrics.get("tacticsUsed", {}).get("ANCHORING"):
        biggest_risk = "Low-anchor pressure on price."
    elif metrics.get("tacticsUsed", {}).get("NIBBLING"):
        biggest_risk = "Late-stage nibbling for extra concessions."
    elif metrics.get("tacticsUsed", {}).get("URGENCY"):
        biggest_risk = "Artificial urgency pressure."
    elif metrics.get("circlingInstances", 0) >= 2:
        biggest_risk = "Conversation circling without commitment."
    elif metrics.get("stallingInstances", 0) >= 2:
        biggest_risk = "Stalling instead of a direct objection."

    if not user_actually_spoke:
        outcome = "No real negotiation happened yet."
    elif deal_closed:
        outcome = "You reached a close or a clear commitment."
    elif metrics.get("progressInstances", 0) > 0:
        outcome = "You created movement, but did not fully close."
    else:
        outcome = "The counterpart exposed pressure points to improve next time."

    # Build scoring breakdown for transparency
    scoring_breakdown = {
        "voice_score": voice_score,
        "presence_score": presence_score if camera_enabled else None,
        "voice_weight": 70 if camera_enabled else 100,
        "presence_weight": 30 if camera_enabled else 0,
        "deal_closed": deal_closed,
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
