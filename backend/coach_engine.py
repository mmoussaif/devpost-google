"""
Secondus coaching engine.

Owns the non-live coaching generation path used to turn the latest counterparty
statement plus grounded context into one actionable line for the user.
"""

import asyncio
import json
import logging
import os
import re

from google import genai
from google.genai import types

from contract_state import ContractState
from presence_engine import PresenceSnapshot

logger = logging.getLogger(__name__)


PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "platinum-depot-489523-a7")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
COACHING_MODEL = os.getenv("COACHING_MODEL", "gemini-2.5-flash-lite")
VISION_MODEL = os.getenv("VISION_MODEL", "gemini-2.5-flash")

coaching_client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

COACHING_PROMPT = """Negotiation coach. One sentence. Best next move only.

THEM: "{adversary_text}"
USER GOALS: {goals} | BATNA: {batna}
USER SAID SO FAR: {user_history}
CONTRACT: {contract_terms}

RULES:
- Don't repeat what user already said or did
- If user is winning/holding firm, acknowledge it ("Good — hold your ground" / "They're moving, lock it in")
- If they're agreeing, close immediately
- One sentence, natural spoken language
- VARY your opening words every time — never start two suggestions the same way (no "Let's" every time)

CLOSING: [YES/NO]
CIRCLING: [YES/NO]
SAY THIS: [one sentence]

CLOSING:"""

TERM_EXTRACTION_PROMPT = """Extract key commercial terms from this document image using Google Vision. Any document type: contract, agreement, proposal, invoice, or form.

Extract whatever you can see:
- price: total amount, fee, contract value (e.g. $75,000, $75K)
- payment_terms: Net-30, Net-45, upfront %, payment schedule
- timeline: duration, deadline (e.g. 10 weeks, 6 weeks)
- scope: short description of work or deliverables
- revisions: revision rounds, hourly rate for extra work
- parties: names of parties if visible
- summary: one sentence describing the document

Return ONLY a single JSON object with these keys. Use null only for keys you truly cannot find. Extract every number, amount, and date you see — do not return all nulls if the image contains document text.

Example: {"price": "$75,000", "payment_terms": "Net-30", "timeline": "10 weeks", "scope": "AI consulting", "revisions": "3 rounds", "parties": null, "summary": "Consulting agreement."}
"""

# Schema for structured JSON output (Vertex AI); ensures valid JSON from Gemini.
TERM_EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "price": {"type": "STRING", "nullable": True},
        "timeline": {"type": "STRING", "nullable": True},
        "payment_terms": {"type": "STRING", "nullable": True},
        "scope": {"type": "STRING", "nullable": True},
        "revisions": {"type": "STRING", "nullable": True},
        "parties": {"type": "STRING", "nullable": True},
        "summary": {"type": "STRING", "nullable": True},
    },
}

EXPECTED_TERM_KEYS = frozenset(TERM_EXTRACTION_SCHEMA["properties"].keys())


def _get_response_text(response) -> str | None:
    """Safely get text from GenerateContentResponse (handles blocked/empty or non-text parts)."""
    try:
        if hasattr(response, "text") and response.text is not None:
            return response.text.strip() or None
    except (ValueError, AttributeError):
        pass
    if getattr(response, "candidates", None) and len(response.candidates) > 0:
        parts = getattr(response.candidates[0], "content", None) and getattr(
            response.candidates[0].content, "parts", None
        )
        if parts:
            texts = []
            for p in parts:
                if hasattr(p, "text") and p.text:
                    texts.append(p.text)
            if texts:
                return "\n".join(texts).strip() or None
    return None


def _extract_json_from_text(raw: str) -> dict | None:
    """Extract a JSON object from model output (handles markdown code blocks and trailing text)."""
    if not raw or not raw.strip():
        return None
    # Strip markdown code blocks so we get raw JSON
    text = raw.strip()
    for marker in ("```json", "```"):
        if marker in text:
            start = text.find(marker) + len(marker)
            end = text.find("```", start)
            if end == -1:
                end = len(text)
            text = text[start:end].strip()
    match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if not match:
        match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


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
        prompt = COACHING_PROMPT.format(
            goals=goals or "Close the deal",
            batna=batna or "Walk away",
            adversary_text=adversary_text,
            user_history=user_history or "No prior commitments yet",
            contract_terms=contract_state.as_prompt_text() if contract_state else "No structured contract terms available yet.",
            presence_summary=format_presence_summary(presence_snapshot),
        )

        response = await asyncio.to_thread(
            coaching_client.models.generate_content,
            model=COACHING_MODEL,
            contents=[prompt],
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
        import traceback
        print(f"Coaching generation error ({COACHING_MODEL}): {e}", flush=True)
        traceback.print_exc()
        return {
            "type": "coaching",
            "say_this": "",
            "context": "",
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
            model=VISION_MODEL,
            contents=[
                TERM_EXTRACTION_PROMPT,
                types.Part.from_bytes(data=screen_bytes, mime_type="image/jpeg"),
            ],
        )
        raw = _get_response_text(response)
        payload = _extract_json_from_text(raw) if raw else None
        if isinstance(payload, dict) and payload:
            contract_state.set_structured_terms(payload, extracted_at=asyncio.get_event_loop().time())
    except Exception as e:
        logger.warning("Contract extraction error in ensure_contract_terms: %s", e, exc_info=False)


async def analyze_document(screen_bytes: bytes) -> dict:
    """
    Analyze a document screenshot using Gemini Vision.
    Returns extracted terms and a summary for sharing with both parties.
    """
    if not screen_bytes or len(screen_bytes) < 500:
        return {"success": False, "error": "Invalid image data"}

    contents = [
        TERM_EXTRACTION_PROMPT,
        types.Part.from_bytes(data=screen_bytes, mime_type="image/jpeg"),
    ]
    terms = None
    raw = None

    try:
        response = await asyncio.to_thread(
            coaching_client.models.generate_content,
            model=VISION_MODEL,
            contents=contents,
        )
        raw = _get_response_text(response)
        terms = _extract_json_from_text(raw) if raw else None
    except Exception as e:
        logger.warning("Document analysis (prompt-only) failed: %s", e, exc_info=False)
        try:
            response = await asyncio.to_thread(
                coaching_client.models.generate_content,
                model=VISION_MODEL,
                contents=contents,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": TERM_EXTRACTION_SCHEMA,
                },
            )
            raw = _get_response_text(response)
            if raw:
                try:
                    terms = json.loads(raw)
                except json.JSONDecodeError:
                    terms = _extract_json_from_text(raw)
        except Exception as fallback_err:
            logger.exception("Document analysis error")
            return {"success": False, "error": str(fallback_err)[:500]}

    if not raw:
        logger.warning("Document analysis: empty or blocked response from model")
        return {"success": False, "error": "Model returned no text (blocked or empty)"}

    if not terms or not isinstance(terms, dict):
        logger.warning("Document analysis: could not parse JSON from response (len=%s)", len(raw or ""))
        return {"success": False, "error": "Could not parse extracted terms from response"}

    # Normalize: only expected keys, string or None
    normalized = {}
    for k in EXPECTED_TERM_KEYS:
        v = terms.get(k)
        if v is not None and str(v).strip():
            normalized[k] = str(v).strip()
        else:
            normalized[k] = None

    has_any_term = any(normalized.get(k) for k in EXPECTED_TERM_KEYS)
    if not has_any_term:
        return {
            "success": False,
            "error": "No terms detected in this image. Share the tab or window that shows your document, then capture again.",
        }
    summary_parts = []
    for key in ("price", "payment_terms", "timeline", "scope"):
        if normalized.get(key):
            summary_parts.append(f"{key.replace('_', ' ').title()}: {normalized[key]}")
    context_summary = " | ".join(summary_parts) if summary_parts else "Document analyzed"

    return {
        "success": True,
        "terms": {k: v for k, v in normalized.items() if v is not None},
        "summary": normalized.get("summary") or context_summary,
        "context_for_session": f"[SHARED DOCUMENT CONTEXT: {context_summary}]",
    }


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
