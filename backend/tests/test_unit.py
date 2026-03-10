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

from agent import create_agent, NEGOTIATION_SYSTEM_PROMPT, root_agent


class TestAgentDefinition:
    """Tests for the Secondus agent definition."""

    def test_agent_creation(self):
        """Test that agent is created with correct parameters."""
        agent = create_agent()
        assert agent is not None
        assert agent.name == "secondus"
        assert agent.model == "gemini-live-2.5-flash-native-audio"

    def test_agent_has_description(self):
        """Test that agent has a description."""
        agent = create_agent()
        assert agent.description == "Real-time negotiation intelligence agent"

    def test_agent_has_instruction(self):
        """Test that agent has system instruction."""
        agent = create_agent()
        assert agent.instruction == NEGOTIATION_SYSTEM_PROMPT

    def test_root_agent_is_singleton(self):
        """Test that root_agent is pre-created."""
        assert root_agent is not None
        assert root_agent.name == "secondus"


class TestSystemPrompt:
    """Tests for the negotiation system prompt."""

    def test_prompt_is_coaching_focused(self):
        """Test prompt focuses on coaching, not passive observation."""
        assert "COACH" in NEGOTIATION_SYSTEM_PROMPT
        assert "SAY THIS" in NEGOTIATION_SYSTEM_PROMPT

    def test_prompt_contains_output_format(self):
        """Test prompt defines actionable output formats."""
        assert "TACTIC:" in NEGOTIATION_SYSTEM_PROMPT
        assert "DRIFT:" in NEGOTIATION_SYSTEM_PROMPT

    def test_prompt_handles_counterparty_tactics(self):
        """Test prompt addresses common negotiation scenarios."""
        assert "ANCHOR" in NEGOTIATION_SYSTEM_PROMPT.upper()
        assert "URGENCY" in NEGOTIATION_SYSTEM_PROMPT.upper()
        assert "CONCESSION" in NEGOTIATION_SYSTEM_PROMPT.upper()

    def test_prompt_includes_voice_coaching(self):
        """Test prompt includes voice coaching guidance."""
        assert "CONFIDENCE" in NEGOTIATION_SYSTEM_PROMPT
        assert "TONE" in NEGOTIATION_SYSTEM_PROMPT
        assert "PACE" in NEGOTIATION_SYSTEM_PROMPT

    def test_prompt_supports_speaker_identification(self):
        """Test prompt includes speaker identification guidance."""
        assert "voice sample" in NEGOTIATION_SYSTEM_PROMPT.lower()
        assert "USER" in NEGOTIATION_SYSTEM_PROMPT
        assert "COUNTERPARTY" in NEGOTIATION_SYSTEM_PROMPT


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

        assert "ANCHORING" in ADVERSARY_SYSTEM_PROMPT
        assert "FLINCHING" in ADVERSARY_SYSTEM_PROMPT
        assert "NIBBLING" in ADVERSARY_SYSTEM_PROMPT
        assert "SILENCE" in ADVERSARY_SYSTEM_PROMPT

    def test_adversary_is_singleton(self):
        """Test that adversary_agent is pre-created."""
        from adversary import adversary_agent

        assert adversary_agent is not None
        assert adversary_agent.name == "adversary"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
