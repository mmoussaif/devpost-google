"""
Presence signal scaffolding for future frontend->backend visual fusion.

This module establishes the backend contract for presence metrics so the
architecture can evolve without keeping all visual logic frontend-only.
"""

from dataclasses import dataclass


@dataclass
class PresenceSnapshot:
    # None means camera not active / no data received yet
    eye_contact: int | None = None
    posture: int | None = None
    tension: int | None = None
    dominant_emotion: str | None = None

    def has_data(self) -> bool:
        """Returns True if any camera metrics have been received."""
        return self.eye_contact is not None or self.tension is not None

    def summary(self) -> dict:
        return {
            "eye_contact": self.eye_contact or 0,
            "posture": self.posture or 0,
            "tension": self.tension or 0,
            "dominant_emotion": self.dominant_emotion or "neutral",
        }
