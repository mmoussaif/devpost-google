"""
Secondus coaching engine.

Owns the non-live coaching generation path used to turn the latest counterparty
statement plus grounded context into one actionable line for the user.
"""

import asyncio
import json
import os
import re

from google import genai
from google.genai import types

from contract_state import ContractState
from presence_engine import PresenceSnapshot


PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "platinum-depot-489523-a7")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

coaching_client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

COACHING_PROMPT = """You are Secondus, a negotiation coach for a CONSULTING/SERVICES deal.

SCENARIO: User is negotiating a consulting contract. Topics include:
- Price/budget (e.g., $50K, $80K, etc.)
- Payment terms (Net-30, Net-60, Net-90)
- Scope of work
- Revision rounds
- Possibly equity

COUNTERPARTY JUST SAID:
"{adversary_text}"

USER'S POSITION:
- Goals: {goals}
- BATNA: {batna}
- Recent commitments: {user_history}
- Structured contract terms: {contract_terms}
- Presence snapshot: {presence_summary}

RULES:
1. Respond ONLY to what the counterparty said - do NOT invent topics
2. Keep response to 1-2 sentences
3. If they mention price, respond about price
4. If they mention equity, respond about equity
5. Do NOT mention topics they didn't bring up

CRITICAL — AGREEMENT DETECTION:
If the counterparty is AGREEING, ACCEPTING, or saying "let's move forward":
- Do NOT push back or demand more
- CLOSE THE DEAL immediately
- Example: "Great, let's lock that in. I'll send the contract today."

OUTPUT FORMAT (exactly three lines):
CLOSING: [YES or NO] - Is this a deal closure, agreement, or end of negotiation?
CIRCLING: [YES or NO] - Is the conversation stuck repeating the same point without progress?
SAY THIS: [your coaching phrase]

CLOSING = YES when:
- "Great, we have a deal", "That works", "I'll move that forward"
- "Goodbye", "Thanks for your time", "We'll proceed"

CLOSING = NO when:
- Questions, counter-offers, new topics, objections

CIRCLING = YES when:
- Same objection repeated 3+ times with no new information
- Counterparty keeps restating the same position without movement
- "As I said before...", "I already mentioned...", repeating exact numbers
- No progress despite multiple exchanges on the same topic

CIRCLING = NO when:
- New numbers or terms are being proposed (even if on same topic)
- Negotiation is progressing with counter-offers
- New information or conditions are added
- First or second time discussing a topic

CLOSING:"""

TERM_EXTRACTION_PROMPT = """Analyze this contract/document screenshot and extract key terms.

Return JSON with these fields:
{
  "price": "the price/fee amount (e.g., '$75,000' or '$75K')",
  "timeline": "delivery timeline (e.g., '6 weeks', '30 days')",
  "payment_terms": "payment terms (e.g., 'Net-30', '50% upfront')",
  "scope": "brief scope description (e.g., 'AI integration services')",
  "revisions": "revision rounds if mentioned",
  "parties": "names of parties involved",
  "summary": "one-sentence summary of the contract"
}

Use null for any field not visible in the document.
Return ONLY valid JSON, no other text.
"""


def build_user_history_text(user_history: list[str]) -> str:
    if not user_history:
        return "No prior commitments yet"
    return "\n".join([f'- User said: "{stmt}"' for stmt in user_history[-3:]])


async def generate_coaching(
    adversary_text: str,
    goals: str,
    batna: str,
    user_history: str = "",
    contract_state: ContractState | None = None,
    presence_snapshot: PresenceSnapshot | None = None,
) -> dict:
    """Generate real-time coaching response to the latest adversary statement."""
    try:
        if contract_state:
            await ensure_contract_terms(contract_state)

        prompt = COACHING_PROMPT.format(
            goals=goals or "Close the deal",
            batna=batna or "Walk away",
            adversary_text=adversary_text,
            user_history=user_history or "No prior commitments yet",
            contract_terms=contract_state.as_prompt_text() if contract_state else "No structured contract terms available yet.",
            presence_summary=format_presence_summary(presence_snapshot),
        )

        contents: list[types.Part | str] = [prompt]
        screen_bytes = contract_state.get_latest_screen() if contract_state else None
        if screen_bytes and len(screen_bytes) > 500:
            contents.append(types.Part.from_bytes(data=screen_bytes, mime_type="image/jpeg"))
            contents.append(
                "CRITICAL: Look at the provided screen capture of the contract. "
                "If the counterparty's spoken text contradicts the document terms in a way that hurts the user, "
                "output a 'DRIFT: [Contract says X, they said Y]' alert alongside your SAY THIS response!"
            )

        response = await asyncio.to_thread(
            coaching_client.models.generate_content,
            model="gemini-2.0-flash",
            contents=contents,
        )

        coaching_text = response.text.strip()
        
        # Parse CLOSING indicator
        is_closing = False
        if "CLOSING:" in coaching_text.upper():
            closing_match = re.search(r"CLOSING:\s*(YES|NO)", coaching_text.upper())
            if closing_match:
                is_closing = closing_match.group(1) == "YES"
        
        # Parse CIRCLING indicator
        is_circling = False
        if "CIRCLING:" in coaching_text.upper():
            circling_match = re.search(r"CIRCLING:\s*(YES|NO)", coaching_text.upper())
            if circling_match:
                is_circling = circling_match.group(1) == "YES"
        
        # Parse SAY THIS phrase
        phrase = ""
        if "SAY THIS:" in coaching_text.upper():
            idx = coaching_text.upper().find("SAY THIS:")
            phrase = coaching_text[idx + 9 :].strip().strip('"').strip("'")
            # Clean up any trailing lines
            phrase = phrase.split("\n")[0].strip()
        else:
            # Fallback: use the whole text if no SAY THIS marker
            phrase = coaching_text.split("\n")[-1].strip()
        
        return {
            "type": "coaching",
            "say_this": phrase,
            "context": f"Response to: {adversary_text[:50]}...",
            "is_closing": is_closing,
            "is_circling": is_circling,
        }

    except Exception as e:
        print(f"Coaching generation error: {e}")
        return {
            "type": "coaching",
            "say_this": "I hear you. Let me think about the best way forward.",
            "context": "Fallback response",
            "is_closing": False,
            "is_circling": False,
        }


async def ensure_contract_terms(contract_state: ContractState) -> None:
    """Best-effort extraction of structured terms from the latest contract image."""
    if not contract_state or not contract_state.needs_refresh():
        return

    screen_bytes = contract_state.get_latest_screen()
    if not screen_bytes:
        return

    try:
        response = await asyncio.to_thread(
            coaching_client.models.generate_content,
            model="gemini-2.0-flash",
            contents=[
                TERM_EXTRACTION_PROMPT,
                types.Part.from_bytes(data=screen_bytes, mime_type="image/jpeg"),
            ],
        )
        raw = response.text.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = json.loads(match.group(0) if match else raw)
        if isinstance(payload, dict):
            contract_state.set_structured_terms(payload, extracted_at=asyncio.get_event_loop().time())
    except Exception as e:
        print(f"Contract extraction error: {e}")


async def analyze_document(screen_bytes: bytes) -> dict:
    """
    Analyze a document screenshot using Gemini Vision.
    Returns extracted terms and a summary for sharing with both parties.
    """
    if not screen_bytes or len(screen_bytes) < 500:
        return {"success": False, "error": "Invalid image data"}

    try:
        response = await asyncio.to_thread(
            coaching_client.models.generate_content,
            model="gemini-2.0-flash",
            contents=[
                TERM_EXTRACTION_PROMPT,
                types.Part.from_bytes(data=screen_bytes, mime_type="image/jpeg"),
            ],
        )
        raw = response.text.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {"success": False, "error": "Could not parse response"}

        terms = json.loads(match.group(0))

        # Build a human-readable summary for the session
        summary_parts = []
        if terms.get("price"):
            summary_parts.append(f"Price: {terms['price']}")
        if terms.get("payment_terms"):
            summary_parts.append(f"Payment: {terms['payment_terms']}")
        if terms.get("timeline"):
            summary_parts.append(f"Timeline: {terms['timeline']}")
        if terms.get("scope"):
            summary_parts.append(f"Scope: {terms['scope']}")

        context_summary = " | ".join(summary_parts) if summary_parts else "Document analyzed"

        return {
            "success": True,
            "terms": terms,
            "summary": terms.get("summary", context_summary),
            "context_for_session": f"[SHARED DOCUMENT CONTEXT: {context_summary}]",
        }

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return {"success": False, "error": "Failed to parse extracted terms"}
    except Exception as e:
        print(f"Document analysis error: {e}")
        return {"success": False, "error": str(e)}


def format_presence_summary(presence_snapshot: PresenceSnapshot | None) -> str:
    if not presence_snapshot:
        return "No presence snapshot yet."
    data = presence_snapshot.summary()
    return (
        f"eye_contact={data['eye_contact']}%, "
        f"posture={data['posture']}%, "
        f"tension={data['tension']}%, "
        f"emotion={data['dominant_emotion']}"
    )
