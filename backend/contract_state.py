import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContractState:
    """Tracks the latest contract/screen context for a session."""

    latest_screen: bytes | None = None
    structured_terms: dict[str, Any] = field(default_factory=dict)
    shared_terms: dict[str, Any] = field(default_factory=dict)  # Terms already sent to session
    context_sent_to_session: bool = False  # Only send context to AI once
    updated_at: float | None = None
    extracted_at: float | None = None

    def seed_from_config(self, config: dict[str, Any]) -> None:
        """Seed structured terms from explicit setup context."""
        combined = " ".join(
            [
                str(config.get("goals", "")),
                str(config.get("batna", "")),
                str(config.get("scenario", "")),
                str(config.get("counterparty", "")),
                " ".join(config.get("key_terms", []) or []),
            ]
        )
        parsed = extract_structured_terms_from_text(combined)
        self.structured_terms.update({k: v for k, v in parsed.items() if v})

    def update_screen(self, image_bytes: bytes, updated_at: float | None = None) -> bool:
        """Store the latest usable screen image for contract grounding."""
        if not image_bytes or len(image_bytes) <= 500:
            return False
        self.latest_screen = image_bytes
        self.updated_at = updated_at
        return True

    def get_latest_screen(self) -> bytes | None:
        return self.latest_screen

    def needs_refresh(self) -> bool:
        return self.latest_screen is not None and (self.extracted_at is None or (self.updated_at and self.updated_at > self.extracted_at))

    def merge_terms(self, new_terms: dict[str, Any], extracted_at: float | None = None) -> dict[str, Any]:
        """
        Merge new terms with existing ones and return only NEW terms not yet shared.
        Returns dict of terms that are actually new/changed.
        """
        clean_terms = {k: v for k, v in new_terms.items() if v}
        new_additions: dict[str, Any] = {}
        
        for key, value in clean_terms.items():
            existing = self.structured_terms.get(key)
            shared = self.shared_terms.get(key)
            
            # If this is a new term or different from what we've shared
            if value and (not shared or str(value).lower() != str(shared).lower()):
                new_additions[key] = value
        
        # Update structured terms
        self.structured_terms.update(clean_terms)
        self.extracted_at = extracted_at
        
        return new_additions

    def mark_terms_shared(self, terms: dict[str, Any]) -> None:
        """Mark these terms as shared with the session."""
        self.shared_terms.update(terms)

    def set_structured_terms(self, terms: dict[str, Any], extracted_at: float | None = None) -> None:
        clean_terms = {k: v for k, v in terms.items() if v}
        if clean_terms:
            self.structured_terms.update(clean_terms)
        self.extracted_at = extracted_at

    def as_prompt_text(self) -> str:
        if not self.structured_terms:
            return "No structured contract terms available yet."
        ordered = []
        for key in ["price", "timeline", "payment_terms", "scope", "revisions"]:
            value = self.structured_terms.get(key)
            if value:
                ordered.append(f"{key}: {value}")
        return "; ".join(ordered) if ordered else "No structured contract terms available yet."

    def snapshot(self) -> dict[str, Any]:
        return {
            "has_screen": self.latest_screen is not None,
            "structured_terms": self.structured_terms,
            "shared_terms": self.shared_terms,
            "updated_at": self.updated_at,
            "extracted_at": self.extracted_at,
        }


def extract_structured_terms_from_text(text: str) -> dict[str, Any]:
    """Best-effort extraction of canonical deal terms from setup text."""
    lower = text.lower()

    price_match = re.search(r"\$ ?(\d[\d,]*k?|\d[\d,]*)", text, re.IGNORECASE)
    payment_match = re.search(r"net[- ]?\d+|upfront|50% upfront|milestone", lower, re.IGNORECASE)
    timeline_match = re.search(r"\b\d+\s*(week|weeks|day|days|month|months)\b", lower, re.IGNORECASE)
    revisions_match = re.search(r"\b\d+\s*(revision|revisions|round|rounds)\b", lower, re.IGNORECASE)

    scope = None
    if "consult" in lower:
        scope = "consulting engagement"
    elif "integration" in lower:
        scope = "integration work"
    elif "implementation" in lower:
        scope = "implementation work"

    return {
        "price": price_match.group(0) if price_match else None,
        "payment_terms": payment_match.group(0) if payment_match else None,
        "timeline": timeline_match.group(0) if timeline_match else None,
        "revisions": revisions_match.group(0) if revisions_match else None,
        "scope": scope,
    }


def extract_spoken_terms_from_text(text: str) -> dict[str, Any]:
    """Extract candidate commercial terms from a spoken utterance."""
    return extract_structured_terms_from_text(text)


def compare_terms(contract_terms: dict[str, Any], spoken_terms: dict[str, Any]) -> list[dict[str, str]]:
    """Return structured drift differences between contract and spoken terms."""
    diffs: list[dict[str, str]] = []
    for key in ["price", "payment_terms", "timeline", "revisions", "scope"]:
        contract_value = contract_terms.get(key)
        spoken_value = spoken_terms.get(key)
        if contract_value and spoken_value:
            norm_contract = normalize_term(contract_value, key)
            norm_spoken = normalize_term(spoken_value, key)
            if norm_contract != norm_spoken:
                diffs.append(
                    {
                        "field": key,
                        "contract": str(contract_value),
                        "spoken": str(spoken_value),
                    }
                )
    return diffs


def normalize_term(value: str, field: str = "") -> str:
    """Normalize a term for comparison, extracting core values."""
    text = str(value).lower().strip()
    
    # For payment terms, extract just the net-X or payment type
    if field == "payment_terms":
        match = re.search(r"net[- ]?(\d+)", text)
        if match:
            return f"net{match.group(1)}"
        if "upfront" in text:
            return "upfront"
        if "milestone" in text:
            return "milestone"
    
    # For price, extract just the number
    if field == "price":
        # Remove $ and K, extract number
        match = re.search(r"(\d+)", text.replace(",", "").replace("k", "000"))
        if match:
            return match.group(1)
    
    # For timeline, extract number and unit
    if field == "timeline":
        match = re.search(r"(\d+)\s*(week|day|month)", text)
        if match:
            return f"{match.group(1)}{match.group(2)}"
    
    # Default: remove whitespace and lowercase
    return re.sub(r"\s+", "", text)
