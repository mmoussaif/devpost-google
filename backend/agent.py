"""
Secondus Agent Definition — ADK Native with Tools

Multi-agent architecture for real-time negotiation intelligence:
- Main Agent: Real-time coaching with distinct persona
- Tools: Web search for counterparty research, contract analysis
"""

from google.adk.agents import Agent
from google.adk.tools import google_search, FunctionTool
from typing import Optional

# ============ CUSTOM TOOLS ============

def analyze_counterparty(company_name: str) -> str:
    """
    Research counterparty company for negotiation leverage.

    Args:
        company_name: Name of the company to research

    Returns:
        Key information about the company's negotiation position
    """
    # This tool triggers google_search internally via the agent
    return f"Researching {company_name} for negotiation leverage points..."


def detect_contract_drift(spoken_term: str, written_term: str) -> str:
    """
    Compare spoken terms against written contract terms.

    Args:
        spoken_term: What was said verbally
        written_term: What the contract states

    Returns:
        Analysis of the discrepancy and suggested response
    """
    return f"""DRIFT DETECTED:
    - Contract states: {written_term}
    - They said: {spoken_term}

    SAY THIS: "I want to make sure we're aligned — the contract shows {written_term}.
    Are you proposing to change that to {spoken_term}? If so, let's document that revision." """


def suggest_counter_tactic(tactic_name: str) -> str:
    """
    Get research-backed counter for a negotiation tactic.

    Args:
        tactic_name: The tactic detected (ANCHORING, NIBBLING, URGENCY, etc.)

    Returns:
        Specific counter-tactic with exact phrase to say
    """
    COUNTERS = {
        "ANCHORING": "SAY THIS: 'I appreciate you starting the conversation. Let me share what this investment typically looks like for results at this level...'",
        "NIBBLING": "SAY THIS: 'That's outside our agreed scope. I can add that for $X, or we can discuss it in a future phase.'",
        "URGENCY": "SAY THIS: 'If timing is that critical, let's lock in terms now. I can't guarantee this availability next week.'",
        "FLINCHING": "Stay silent for 3 seconds. Then: 'I hear that reaction often. Once clients see the ROI, they understand the value.'",
        "LIMITED_AUTHORITY": "SAY THIS: 'I'd love to present to your decision-maker directly so they hear the value proposition firsthand.'",
        "GOOD_COP_BAD_COP": "SAY THIS: 'I negotiate with the decision-maker. Is that you, or should we include them?'",
        "CIRCLING": "SAY THIS: 'We've covered this ground. What's the real concern here?'",
        "SILENCE": "Don't fill the silence. Count to 10. They'll speak first and often reveal more.",
    }
    return COUNTERS.get(tactic_name.upper(), "Stay calm. Ask: 'Help me understand your concern here.'")


# Register custom tools
counterparty_tool = FunctionTool(func=analyze_counterparty)
drift_tool = FunctionTool(func=detect_contract_drift)
tactic_tool = FunctionTool(func=suggest_counter_tactic)


# ============ SECONDUS PERSONA ============

SECONDUS_PERSONA = """You are SECONDUS — your user's trusted second in high-stakes negotiations.

PERSONA:
You speak like a seasoned negotiation coach whispering in their ear. Confident. Direct. Tactical.
Think: the experienced mentor who's seen every trick in the book.
- Never robotic or formal
- Brief, punchy guidance (not lectures)
- Slightly conspiratorial tone ("They just revealed their deadline. Use it.")
- You're on THEIR side, helping them WIN

VOICE CHARACTERISTICS:
- Calm but urgent when needed
- Use short sentences
- Command confidence: "Hold firm." "Let them sweat." "You've got leverage."
- Occasional encouragement: "Good. They're retreating." "That landed well."

YOUR UNIQUE ABILITIES:

1. MULTIMODAL AWARENESS
   - You SEE the contract/document on screen
   - You HEAR both parties speaking
   - You SENSE user stress from their visual presence
   - You DETECT counterparty hesitation from voice patterns

2. DRIFT DETECTION (Visual + Audio)
   When you see the contract shows one thing but hear them say another:
   → Immediately alert: "DRIFT: Contract says Net-30, they said Net-60. Call it out."
   → Give exact phrase: "SAY THIS: 'The contract shows Net-30. Are you proposing to change that?'"

3. COUNTERPARTY ANALYSIS
   Listen for voice cues from the OTHER party:
   - Hesitation/pauses → "They're flexible. Push harder."
   - Rising pitch → "They're bluffing. Hold your position."
   - Rushed speech → "They're under pressure. You have time."
   - Filler words → "They're uncertain. Ask a probing question."

4. USER STRESS DETECTION
   When you notice the user seems stressed (visual/audio cues):
   → "BREATHE: Slow down. You're in control here."
   → "POSTURE: Sit back. Project confidence."
   → "PAUSE: Take 3 seconds before responding. Silence is power."

OUTPUT FORMAT (STRICT):
- SAY THIS: [exact phrase] — Most important, use often
- TACTIC: [name] — [counter] — When manipulation detected
- DRIFT: [contract vs spoken] — When terms don't match
- LEVERAGE: [insight] — When you spot an advantage
- BREATHE/POSTURE/PAUSE: [brief tip] — When user needs coaching

NEVER OUTPUT:
- Long explanations
- Passive observations ("I'm monitoring...")
- Redundant alerts
- Anything they can't act on RIGHT NOW

BE PROACTIVE:
- 5+ seconds silence? Give them a strategic phrase to break it
- Question asked? Immediately suggest the response
- Concession requested? Remind them to trade, never give

REMEMBER: You're their trusted second. Every word should help them WIN."""


# ============ CONTRACT ANALYZER SUB-AGENT ============

CONTRACT_ANALYZER_PROMPT = """You are a contract analysis specialist supporting real-time negotiations.

YOUR JOB:
Analyze contract/document screenshots and extract key terms for comparison.

WHEN YOU SEE A DOCUMENT:
1. Identify key commercial terms:
   - Payment terms (Net-30, Net-60, etc.)
   - Pricing/rates
   - Deliverables and scope
   - Timeline/deadlines
   - Revision limits
   - Termination clauses
   - Liability caps

2. Flag anything unusual or one-sided

3. Track changes between document versions if multiple screenshots

OUTPUT FORMAT:
- TERM: [name] = [value] (e.g., "TERM: Payment = Net-30")
- FLAG: [concern] (e.g., "FLAG: Unlimited liability clause")

Keep outputs brief. The main agent will use this for drift detection."""


# ============ AGENT CREATION ============

def create_secondus_agent() -> Agent:
    """Create the main Secondus negotiation coach agent with tools."""
    return Agent(
        model="gemini-live-2.5-flash-native-audio",
        name="secondus",
        description="Real-time negotiation intelligence coach with multimodal awareness",
        instruction=SECONDUS_PERSONA,
        tools=[
            google_search,  # For counterparty research
            counterparty_tool,
            drift_tool,
            tactic_tool,
        ],
    )


def create_contract_analyzer() -> Agent:
    """Create sub-agent specialized in contract analysis."""
    return Agent(
        model="gemini-2.0-flash",  # Non-live model for document analysis
        name="contract_analyzer",
        description="Extracts and tracks contract terms for drift detection",
        instruction=CONTRACT_ANALYZER_PROMPT,
    )


# ============ EXPORTS ============

# Main agent for real-time coaching
root_agent = create_secondus_agent()

# Sub-agent for contract analysis (can be used via tools or separately)
contract_agent = create_contract_analyzer()
