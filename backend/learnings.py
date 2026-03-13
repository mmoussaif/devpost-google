"""
Secondus Learning System — Personalized Negotiation Intelligence

Stores user performance patterns and provides research-backed recommendations.
Based on: Harvard PON, Chris Voss (Never Split the Difference), Joe Navarro body language.

Persistence:
- Learnings (patterns, recommendations, session list) are stored in data/user_learnings.json.
- Each completed session is also persisted to Firestore by session_repository (optional,
  see PERSIST_SESSIONS_TO_FIRESTORE / GOOGLE_CLOUD_PROJECT). Stored sessions include
  stored_analysis from this module, enabling future learnings aggregation from Firestore.
"""

import json
import os
from datetime import datetime
from typing import Optional
from pathlib import Path

# Persistent storage for learnings
LEARNINGS_FILE = Path(__file__).parent / "data" / "user_learnings.json"


def ensure_data_dir():
    """Ensure data directory exists."""
    LEARNINGS_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_learnings() -> dict:
    """Load user learnings from disk."""
    ensure_data_dir()
    if LEARNINGS_FILE.exists():
        with open(LEARNINGS_FILE, "r") as f:
            return json.load(f)
    return {
        "sessions": [],
        "patterns": {
            "weaknesses": {},      # {weakness: count}
            "strengths": {},       # {strength: count}
            "tactics_faced": {},   # {tactic: count}
            "concessions_made": [] # List of what user gave away
        },
        "recommendations": [],
        "last_updated": None
    }


def save_learnings(learnings: dict):
    """Save learnings to disk."""
    ensure_data_dir()
    learnings["last_updated"] = datetime.now().isoformat()
    with open(LEARNINGS_FILE, "w") as f:
        json.dump(learnings, f, indent=2)


def analyze_session(session_data: dict) -> dict:
    """
    Analyze a completed session and extract learnings.
    Returns personalized recommendations for next session.
    """
    learnings = load_learnings()

    metrics = session_data.get("metrics", {})
    exchanges = session_data.get("exchanges", [])
    tactics = session_data.get("tacticsDetected", [])
    coaching = session_data.get("coachingGiven", [])
    visual = session_data.get("visualPresence", {})

    # Extract patterns from this session
    session_analysis = {
        "date": datetime.now().isoformat(),
        "duration": session_data.get("session", {}).get("duration", "00:00"),
        "deal_closed": metrics.get("dealClosed", False),
        "user_turns": metrics.get("userTurns", 0),
        "stalling_instances": metrics.get("stallingInstances", 0),
        "tactics_faced": list(metrics.get("tacticsUsed", {}).keys()),
        "weaknesses_identified": [],
        "strengths_identified": []
    }

    # Identify weaknesses based on patterns
    weaknesses = []
    strengths = []

    # 1. Stalling tolerance
    if metrics.get("stallingInstances", 0) > 5:
        weaknesses.append("STALLING_TOLERANCE")

    # 2. Concession patterns (check if they gave equity, extended payment, etc.)
    concessions = extract_concessions(exchanges)
    if concessions:
        session_analysis["concessions"] = concessions
        if "equity" in str(concessions).lower():
            weaknesses.append("GAVE_EQUITY")
        if "net-90" in str(concessions).lower() or "net 90" in str(concessions).lower():
            weaknesses.append("PAYMENT_TERMS_WEAKNESS")

    # 3. Eye contact / visual presence
    if visual.get("avgEyeContact", 50) < 40:
        weaknesses.append("LOW_EYE_CONTACT")
    elif visual.get("avgEyeContact", 50) > 70:
        strengths.append("STRONG_EYE_CONTACT")

    # 4. Held price
    if metrics.get("dealClosed") and not any("dropped" in str(e).lower() or "lower" in str(e).lower() for e in exchanges if e.get("speaker") == "user"):
        strengths.append("HELD_PRICE")

    # 5. Closed the deal
    if metrics.get("dealClosed"):
        strengths.append("CLOSED_DEAL")

    # 6. Circling (repeated topics without progress)
    if metrics.get("circlingInstances", 0) >= 3:
        weaknesses.append("ALLOWED_CIRCLING")

    # 7. Nibbling response
    nibbling_count = metrics.get("tacticsUsed", {}).get("NIBBLING", 0)
    if nibbling_count >= 3:
        weaknesses.append("NIBBLING_VULNERABILITY")

    session_analysis["weaknesses_identified"] = weaknesses
    session_analysis["strengths_identified"] = strengths

    # Update cumulative patterns
    for w in weaknesses:
        learnings["patterns"]["weaknesses"][w] = learnings["patterns"]["weaknesses"].get(w, 0) + 1
    for s in strengths:
        learnings["patterns"]["strengths"][s] = learnings["patterns"]["strengths"].get(s, 0) + 1
    for t in session_analysis["tactics_faced"]:
        learnings["patterns"]["tactics_faced"][t] = learnings["patterns"]["tactics_faced"].get(t, 0) + 1

    # Store session
    learnings["sessions"].append(session_analysis)

    # Generate recommendations based on patterns
    recommendations = generate_recommendations(learnings["patterns"])
    learnings["recommendations"] = recommendations

    save_learnings(learnings)

    return {
        "session_analysis": session_analysis,
        "cumulative_patterns": learnings["patterns"],
        "recommendations": recommendations
    }


def extract_concessions(exchanges: list) -> list:
    """Extract concessions made during negotiation."""
    concessions = []

    # Keywords indicating concessions
    concession_keywords = [
        ("net-90", "Extended payment to Net-90"),
        ("net 90", "Extended payment to Net-90"),
        ("equity", "Gave equity stake"),
        ("0.5%", "Gave 0.5% equity"),
        ("0.75%", "Gave 0.75% equity"),
        ("1%", "Gave 1% equity"),
        ("discount", "Gave discount"),
        ("free", "Gave something free"),
        ("two rounds", "Reduced revision rounds"),
        ("rush", "Agreed to rush timeline"),
    ]

    full_text = " ".join([e.get("text", "").lower() for e in exchanges])

    for keyword, description in concession_keywords:
        if keyword in full_text:
            concessions.append(description)

    return list(set(concessions))


def generate_recommendations(patterns: dict) -> list:
    """
    Generate personalized recommendations based on accumulated patterns.
    Uses research-backed negotiation tactics.
    """
    recommendations = []
    weaknesses = patterns.get("weaknesses", {})
    tactics_faced = patterns.get("tactics_faced", {})

    # Research-backed recommendation library
    RECOMMENDATION_LIBRARY = {
        "STALLING_TOLERANCE": {
            "title": "Control the Pace",
            "research": "Harvard PON: Time pressure shifts power",
            "action": "Set a deadline early: 'I have 20 minutes before my next call. Let's see if we can reach agreement today.'",
            "practice": "In your next session, end any stalling after 2 instances with a direct close attempt."
        },
        "GAVE_EQUITY": {
            "title": "Trade, Never Give",
            "research": "Chris Voss: Every concession should get something in return",
            "action": "If they ask for equity, say: 'I can consider that. In exchange, I'd need a 2-year engagement minimum and quarterly referral introductions.'",
            "practice": "Never offer equity without getting extended commitment, referrals, or case study rights."
        },
        "PAYMENT_TERMS_WEAKNESS": {
            "title": "Protect Your Cash Flow",
            "research": "Net-90 at $80K = $6,000+ in implicit interest cost",
            "action": "Counter with: 'I can do Net-45 with a 3% early payment discount, or Net-30 at standard rate.'",
            "practice": "Practice refusing Net-90 three times before considering it."
        },
        "LOW_EYE_CONTACT": {
            "title": "Command Presence",
            "research": "Joe Navarro: Eye contact signals confidence and honesty",
            "action": "Look at your camera lens (not the screen) when making key points. Practice the 50/70 rule: 50% eye contact while talking, 70% while listening.",
            "practice": "Put a small sticker next to your camera as a reminder."
        },
        "ALLOWED_CIRCLING": {
            "title": "Break the Loop",
            "research": "Circling indicates hidden objection or lack of authority",
            "action": "Say: 'We seem to be covering the same ground. What's the real concern here?' Or: 'Is there someone else who needs to be part of this decision?'",
            "practice": "After 2 repetitions of same topic, call it out directly."
        },
        "NIBBLING_VULNERABILITY": {
            "title": "Shut Down Nibbling",
            "research": "Nibbling erodes deal value by 10-20% on average",
            "action": "Say: 'That's not part of our agreed scope. I can add that for $X, or we can discuss in a future phase.'",
            "practice": "Track every extra ask. If they nibble 3x, say: 'I notice we keep adding scope. Let's finalize the core deal first.'"
        },
    }

    # Add recommendations for top weaknesses (sorted by frequency)
    sorted_weaknesses = sorted(weaknesses.items(), key=lambda x: x[1], reverse=True)

    for weakness, count in sorted_weaknesses[:3]:  # Top 3 weaknesses
        if weakness in RECOMMENDATION_LIBRARY:
            rec = RECOMMENDATION_LIBRARY[weakness].copy()
            rec["frequency"] = f"Occurred in {count} session(s)"
            rec["priority"] = "HIGH" if count >= 2 else "MEDIUM"
            recommendations.append(rec)

    # Add tactics-specific recommendations
    TACTICS_RESPONSES = {
        "ANCHORING": {
            "title": "Counter-Anchor Immediately",
            "action": "Never react to their anchor. State your number first: 'Before we discuss budget, let me share what this investment looks like...'",
        },
        "FLINCHING": {
            "title": "Ignore the Flinch",
            "action": "Stay silent for 3 seconds after their flinch. Then: 'I hear that reaction often. Once clients see the ROI, they understand.'",
        },
        "LIMITED AUTHORITY": {
            "title": "Involve the Decision Maker",
            "action": "Say: 'I'd love to present to your CFO directly so they hear the value proposition firsthand. Can we schedule that?'",
        },
        "URGENCY": {
            "title": "Flip the Urgency",
            "action": "Say: 'If timing is that critical, we should lock in terms today. I can't guarantee availability next week.'",
        },
    }

    for tactic, count in tactics_faced.items():
        if tactic in TACTICS_RESPONSES and count >= 2:
            rec = TACTICS_RESPONSES[tactic].copy()
            rec["frequency"] = f"Faced {count} times"
            rec["priority"] = "MEDIUM"
            recommendations.append(rec)

    return recommendations


def get_pre_session_briefing() -> dict:
    """
    Get personalized briefing before starting a new session.
    Based on accumulated learnings.
    """
    learnings = load_learnings()

    if not learnings["sessions"]:
        return {
            "message": "First session! Focus on: stating your price confidently, holding firm on first objection.",
            "focus_areas": ["State price first", "Don't flinch at their reaction", "Trade, never give"],
            "recommendations": []
        }

    # Get top weaknesses to focus on
    weaknesses = learnings["patterns"]["weaknesses"]
    sorted_weaknesses = sorted(weaknesses.items(), key=lambda x: x[1], reverse=True)

    focus_areas = []
    for w, count in sorted_weaknesses[:2]:
        if w == "STALLING_TOLERANCE":
            focus_areas.append("Set time limits early - don't let them stall")
        elif w == "GAVE_EQUITY":
            focus_areas.append("If they ask for equity, demand extended commitment")
        elif w == "PAYMENT_TERMS_WEAKNESS":
            focus_areas.append("Hold Net-30 - counter Net-90 with discount offer")
        elif w == "LOW_EYE_CONTACT":
            focus_areas.append("Look at camera lens when making key points")
        elif w == "NIBBLING_VULNERABILITY":
            focus_areas.append("Every extra ask = extra cost. No free additions.")

    # Session stats
    total_sessions = len(learnings["sessions"])
    closed_deals = sum(1 for s in learnings["sessions"] if s.get("deal_closed"))
    close_rate = (closed_deals / total_sessions * 100) if total_sessions > 0 else 0

    return {
        "message": f"Session #{total_sessions + 1}. Close rate: {close_rate:.0f}%",
        "focus_areas": focus_areas or ["Stay confident", "Trade, never give"],
        "recommendations": learnings["recommendations"][:3],
        "stats": {
            "total_sessions": total_sessions,
            "deals_closed": closed_deals,
            "close_rate": f"{close_rate:.0f}%"
        }
    }


def get_quick_tip(tactic: str) -> Optional[str]:
    """Get a quick counter-tip for a detected tactic."""
    QUICK_TIPS = {
        "ANCHORING": "Don't react. State YOUR number confidently.",
        "FLINCHING": "Silence. Then: 'I hear that often. The ROI speaks for itself.'",
        "NIBBLING": "That's outside scope. I can add it for $X.",
        "STALLING": "I have 10 minutes left. Are we ready to decide?",
        "LIMITED AUTHORITY": "Let's get them on a call so they hear the value directly.",
        "CIRCLING": "We've covered this. What's the real concern?",
        "URGENCY": "If timing is critical, let's lock terms now.",
        "BUNDLING": "Let's address one term at a time.",
        "GOOD COP/BAD COP": "I negotiate with the decision maker. Is that you?",
    }
    return QUICK_TIPS.get(tactic.upper())
