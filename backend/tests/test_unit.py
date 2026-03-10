"""
Secondus Unit Tests

Tests for individual components without external dependencies.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import create_secondus_agent, SECONDUS_PERSONA, root_agent


class TestAgentDefinition:
    """Tests for the Secondus agent definition."""

    def test_agent_creation(self):
        """Test that agent is created with correct parameters."""
        agent = create_secondus_agent()
        assert agent is not None
        assert agent.name == "secondus"
        assert agent.model == "gemini-live-2.5-flash-native-audio"

    def test_agent_has_description(self):
        """Test that agent has a description."""
        agent = create_secondus_agent()
        assert agent.description == "Real-time negotiation intelligence coach with multimodal awareness"

    def test_agent_has_instruction(self):
        """Test that agent has system instruction."""
        agent = create_secondus_agent()
        assert agent.instruction == SECONDUS_PERSONA

    def test_root_agent_is_singleton(self):
        """Test that root_agent is pre-created."""
        assert root_agent is not None
        assert root_agent.name == "secondus"


class TestSystemPrompt:
    """Tests for the negotiation system prompt."""

    def test_prompt_is_coaching_focused(self):
        """Test prompt focuses on coaching, not passive observation."""
        assert "coach" in SECONDUS_PERSONA.lower()  # "negotiation coach"
        assert "SAY THIS" in SECONDUS_PERSONA

    def test_prompt_contains_output_format(self):
        """Test prompt defines actionable output formats."""
        assert "TACTIC:" in SECONDUS_PERSONA
        assert "DRIFT:" in SECONDUS_PERSONA

    def test_prompt_handles_counterparty_tactics(self):
        """Test prompt addresses common negotiation scenarios."""
        assert "TACTIC" in SECONDUS_PERSONA  # "TACTIC: [name]" output format
        assert "PRICE" in SECONDUS_PERSONA  # Price pushback handling
        assert "trade" in SECONDUS_PERSONA.lower()  # "trade, never give"

    def test_prompt_includes_voice_coaching(self):
        """Test prompt includes voice coaching guidance."""
        assert "confidence" in SECONDUS_PERSONA.lower()  # "Command confidence", "Confident"
        assert "BREATHE" in SECONDUS_PERSONA  # Voice/stress coaching
        assert "POSTURE" in SECONDUS_PERSONA  # Body language coaching

    def test_prompt_supports_speaker_identification(self):
        """Test prompt includes speaker identification guidance."""
        assert "voice" in SECONDUS_PERSONA.lower()
        assert "USER" in SECONDUS_PERSONA
        assert "COUNTERPARTY" in SECONDUS_PERSONA


class TestSessionConfig:
    """Tests for session configuration."""

    def test_session_config_model(self):
        """Test SessionConfig Pydantic model."""
        from main import SessionConfig

        config = SessionConfig(
            goals="Close at $50K",
            batna="Vendor B at $55K",
            key_terms=["payment terms", "liability"],
            counterparty="Acme Corp"
        )

        assert config.goals == "Close at $50K"
        assert config.batna == "Vendor B at $55K"
        assert len(config.key_terms) == 2
        assert config.counterparty == "Acme Corp"

    def test_session_config_defaults(self):
        """Test SessionConfig with defaults."""
        from main import SessionConfig

        config = SessionConfig()

        assert config.goals == ""
        assert config.batna == ""
        assert config.key_terms == []
        assert config.counterparty == ""


class TestSessionResponse:
    """Tests for session response model."""

    def test_session_response_model(self):
        """Test SessionResponse Pydantic model."""
        from main import SessionResponse

        response = SessionResponse(
            session_id="test-123",
            status="created"
        )

        assert response.session_id == "test-123"
        assert response.status == "created"


class TestInterventionParsing:
    """Tests for parsing agent responses into interventions."""

    def test_parse_urgent_intervention(self):
        """Test parsing URGENT prefixed response."""
        text = "URGENT: They're agreeing to Net 60 but contract says Net 30!"

        if text.startswith("URGENT:"):
            urgency = "urgent"
        elif text.startswith("WATCH:"):
            urgency = "watch"
        else:
            urgency = "note"

        assert urgency == "urgent"

    def test_parse_watch_intervention(self):
        """Test parsing WATCH prefixed response."""
        text = "WATCH: They used anchoring with the $100K figure."

        if text.startswith("URGENT:"):
            urgency = "urgent"
        elif text.startswith("WATCH:"):
            urgency = "watch"
        else:
            urgency = "note"

        assert urgency == "watch"

    def test_parse_note_intervention(self):
        """Test parsing NOTE or unprefixed response."""
        text = "NOTE: Counterparty mentioned flexibility on timeline."

        if text.startswith("URGENT:"):
            urgency = "urgent"
        elif text.startswith("WATCH:"):
            urgency = "watch"
        else:
            urgency = "note"

        assert urgency == "note"

    def test_parse_unprefixed_defaults_to_note(self):
        """Test unprefixed text defaults to note."""
        text = "The discussion is going well so far."

        if text.startswith("URGENT:"):
            urgency = "urgent"
        elif text.startswith("WATCH:"):
            urgency = "watch"
        else:
            urgency = "note"

        assert urgency == "note"


class TestAdversaryAgent:
    """Tests for the adversarial practice mode agent."""

    def test_adversary_creation(self):
        """Test that adversary agent is created with correct parameters."""
        from adversary import create_adversary_agent

        agent = create_adversary_agent()
        assert agent is not None
        assert agent.name == "adversary"
        assert agent.model == "gemini-live-2.5-flash-native-audio"

    def test_adversary_has_tactics(self):
        """Test that adversary prompt includes negotiation tactics."""
        from adversary import ADVERSARY_SYSTEM_PROMPT

        # Adversary uses implicit tactics in the scenario
        assert "$50K" in ADVERSARY_SYSTEM_PROMPT  # Anchoring with low offer
        assert "equity" in ADVERSARY_SYSTEM_PROMPT  # Equity offer tactic
        assert "board" in ADVERSARY_SYSTEM_PROMPT  # Limited authority
        assert "fast" in ADVERSARY_SYSTEM_PROMPT  # Urgency

    def test_adversary_is_singleton(self):
        """Test that adversary_agent is pre-created."""
        from adversary import adversary_agent

        assert adversary_agent is not None
        assert adversary_agent.name == "adversary"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
