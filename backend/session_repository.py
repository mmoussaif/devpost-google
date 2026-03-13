"""
Session persistence to Firestore (optional, fire-and-forget).

Used for: Session Memory, progress tracking, future learnings aggregation.
Does not affect the live flow or recap response. If Firestore is disabled
or fails, the app continues normally.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _to_firestore_value(val: Any) -> Any:
    """Convert to Firestore-serializable types (dict, list, str, int, float, bool, None)."""
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, dict):
        return {k: _to_firestore_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_to_firestore_value(v) for v in val]
    return str(val)

# Enable persistence only when explicitly set or when running in GCP (project set)
PERSIST_ENV = os.getenv("PERSIST_SESSIONS_TO_FIRESTORE", "").lower() in ("1", "true", "yes")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
COLLECTION = "sessions"


def _client():
    """Return Firestore client or None if persistence is disabled."""
    if not PROJECT_ID:
        return None
    if not PERSIST_ENV and "K_SERVICE" not in os.environ:
        # Local dev: only persist if env is set; Cloud Run has K_SERVICE
        return None
    try:
        from google.cloud import firestore

        return firestore.Client(project=PROJECT_ID)
    except Exception as e:
        logger.debug("Firestore client not available: %s", e)
        return None


def _build_user_session_summary(
    session_data: dict[str, Any],
    stored_analysis: dict[str, Any] | None,
    recap_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a rich user-session summary for analytics and Session Memory."""
    session_block = session_data.get("session", {})
    metrics = session_data.get("metrics", {})
    visual = session_data.get("visualPresence") or {}
    completed_at = datetime.now(tz=timezone.utc).isoformat()

    user_session: dict[str, Any] = {
        "completed_at": completed_at,
        "duration": session_block.get("duration", ""),
        "mode": session_block.get("mode", "secondus_buddy"),
        "session_date": session_block.get("date"),
        "session_id": session_block.get("session_id"),
        "config": session_block.get("config"),
        "score": None,
        "outcome": None,
        "user_participation": metrics.get("userTurns", 0),
        "total_turns": metrics.get("totalTurns", 0),
        "deal_closed": metrics.get("dealClosed", False),
        "camera_enabled": session_data.get("cameraEnabled", False),
        "pressure_signals_count": len(session_data.get("tacticsDetected", [])),
        "stalling_instances": metrics.get("stallingInstances", 0),
        "circling_instances": metrics.get("circlingInstances", 0),
        "progress_instances": metrics.get("progressInstances", 0),
    }

    if recap_summary:
        user_session["score"] = recap_summary.get("score")
        user_session["outcome"] = recap_summary.get("outcome")
        user_session["user_participation"] = recap_summary.get("user_participation", user_session["user_participation"])
        user_session["buddy_turns"] = recap_summary.get("buddy_turns")
        user_session["pressure_signals"] = recap_summary.get("pressure_signals")
        user_session["best_intervention"] = recap_summary.get("best_intervention")
        user_session["biggest_risk"] = recap_summary.get("biggest_risk")
        user_session["next_focus"] = recap_summary.get("next_focus")
        user_session["strengths"] = recap_summary.get("strengths", [])
        user_session["improvements"] = recap_summary.get("improvements", [])
        user_session["scoring_breakdown"] = recap_summary.get("scoring_breakdown")
        user_session["visual_summary"] = recap_summary.get("visual_summary")

    if visual:
        user_session["visual_presence"] = {
            "avg_eye_contact": visual.get("avgEyeContact"),
            "avg_posture": visual.get("avgPosture"),
            "avg_tension": visual.get("avgTension"),
        }

    if stored_analysis:
        sa = stored_analysis.get("session_analysis", {})
        user_session["learnings"] = {
            "weaknesses_identified": sa.get("weaknesses_identified", []),
            "strengths_identified": sa.get("strengths_identified", []),
            "tactics_faced": sa.get("tactics_faced", []),
        }

    return user_session


def save_session(
    session_data: dict[str, Any],
    stored_analysis: dict[str, Any] | None = None,
    recap_summary: dict[str, Any] | None = None,
) -> None:
    """
    Persist one session to Firestore. Safe to call from any thread.
    Never raises; logs and returns on failure.
    Stores raw payload, stored_analysis, and a rich user_session summary.
    """
    db = _client()
    if db is None:
        logger.info(
            "Firestore persistence skipped (client unavailable). "
            "Set GOOGLE_CLOUD_PROJECT and run on Cloud Run or PERSIST_SESSIONS_TO_FIRESTORE=1."
        )
        return
    try:
        user_session = _build_user_session_summary(session_data, stored_analysis, recap_summary)
        doc = {
            "session": session_data.get("session", {}),
            "metrics": session_data.get("metrics", {}),
            "exchanges": session_data.get("exchanges", []),
            "tacticsDetected": session_data.get("tacticsDetected", []),
            "coachingGiven": session_data.get("coachingGiven", []),
            "cameraEnabled": session_data.get("cameraEnabled", False),
            "visualPresence": session_data.get("visualPresence") or {},
            "stored_analysis": stored_analysis,
            "completed_at": user_session["completed_at"],
            "user_session": user_session,
        }
        doc = _to_firestore_value(doc)
        db.collection(COLLECTION).add(doc)
        logger.info("Session persisted to Firestore")
    except Exception as e:
        logger.warning("Firestore save failed (non-fatal): %s", e, exc_info=True)
