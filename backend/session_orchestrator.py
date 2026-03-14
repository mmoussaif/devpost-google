"""
Session store and Buddy session orchestrator.

This is the first step away from a single giant backend file. The orchestrator
owns per-session runtime state for Buddy sessions and exposes focused methods
for input handling, transcript forwarding, coaching, and silence nudges.
"""

import asyncio
import base64
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import StreamingMode
from google.adk.runners import RunConfig
from google.genai import types

from contract_state import ContractState, compare_terms, extract_spoken_terms_from_text
from presence_engine import PresenceSnapshot
from coach_engine import analyze_document


SESSION_TIMEOUT = 300
SILENCE_NUDGE_SEC = 20   # Give user time to think/type/share screen
GOODBYE_NUDGE_SEC = 50   # Only nudge goodbye after a long silence


class ActiveSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def clear(self) -> None:
        self._sessions.clear()

    def create_live_session(self, session_id: str, config: dict[str, Any], context: str, session: Any) -> None:
        contract_state = ContractState()
        contract_state.seed_from_config(config)
        self._sessions[session_id] = {
            "mode": "live",
            "config": config,
            "context": context,
            "session": session,
            "created_at": asyncio.get_event_loop().time(),
            "contract_state": contract_state,
            "presence_snapshot": PresenceSnapshot(),
            "last_audio_time": 0.0,
        }

    def create_buddy_session(self, session_id: str, config: dict[str, Any], context: str) -> None:
        contract_state = ContractState()
        contract_state.seed_from_config(config)
        self._sessions[session_id] = {
            "mode": "practice",
            "config": config,
            "context": context,
            "created_at": asyncio.get_event_loop().time(),
            "contract_state": contract_state,
            "presence_snapshot": PresenceSnapshot(),
            "last_audio_time": 0.0,
        }

    def exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def get(self, session_id: str) -> dict[str, Any] | None:
        return self._sessions.get(session_id)

    def require(self, session_id: str) -> dict[str, Any]:
        return self._sessions[session_id]

    def pop(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def update_last_audio_time(self, session_id: str, timestamp: float) -> None:
        if session_id in self._sessions:
            self._sessions[session_id]["last_audio_time"] = timestamp

    def update_contract_screen(self, session_id: str, image_bytes: bytes) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        contract_state: ContractState = session["contract_state"]
        return contract_state.update_screen(image_bytes, asyncio.get_event_loop().time())

    def status_payload(self, session_id: str) -> dict[str, Any]:
        session = self.require(session_id)
        return {
            "session_id": session_id,
            "status": "active",
            "config": session.get("config", {}),
            "mode": session.get("mode", "live"),
        }

    def update_presence(self, session_id: str, payload: dict[str, Any]) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        presence: PresenceSnapshot = session["presence_snapshot"]
        presence.eye_contact = int(payload.get("eye_contact", presence.eye_contact or 0))
        presence.posture = int(payload.get("posture", presence.posture or 0))
        presence.tension = int(payload.get("tension", presence.tension or 0))
        presence.dominant_emotion = payload.get("dominant_emotion", presence.dominant_emotion or "neutral")


@dataclass
class BuddyRuntimeState:
    accumulated_text: str = ""
    last_adversary_finish_time: float | None = None
    silence_nudge_sent: bool = False
    goodbye_nudge_sent: bool = False
    mic_muted: bool = False
    user_history: list[str] = field(default_factory=list)
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    stalling_count: int = 0
    progress_signals: int = 0
    last_signal_times: dict[str, float] = field(default_factory=dict)
    recent_coaching: list[str] = field(default_factory=list)
    screen_sharing: bool = False
    deal_closed: bool = False
    last_coaching_time: float = 0.0

    def reset_silence(self) -> None:
        self.last_adversary_finish_time = None
        self.silence_nudge_sent = False
        self.goodbye_nudge_sent = False

    def record_user_text(self, user_text: str) -> None:
        if not self.user_history or self.user_history[-1] != user_text:
            self.user_history.append(user_text)
            if len(self.user_history) > 5:
                self.user_history.pop(0)
        self.reset_silence()


class BuddySessionOrchestrator:
    def __init__(
        self,
        session_id: str,
        session_data: dict[str, Any],
        session_store: ActiveSessionStore,
        websocket: WebSocket,
        live_queue: LiveRequestQueue,
        coaching_fn,
    ) -> None:
        self.session_id = session_id
        self.session_data = session_data
        self.session_store = session_store
        self.websocket = websocket
        self.live_queue = live_queue
        self.coaching_fn = coaching_fn
        self.state = BuddyRuntimeState()
        self.closed = False

    async def emit(self, payload: dict[str, Any]) -> None:
        if self.closed:
            return
        try:
            await self.websocket.send_json(payload)
        except (RuntimeError, WebSocketDisconnect):
            self.closed = True

    def mark_closed(self) -> None:
        self.closed = True

    async def emit_session_state(self, state: str) -> None:
        await self.emit({"type": "session.state", "state": state})

    async def emit_session_complete(self, content: str) -> None:
        await self.emit({"type": "session.complete", "content": content})

    async def emit_transcript_append(self, speaker: str, content: str) -> None:
        await self.emit(
            {
                "type": "transcript.append",
                "speaker": speaker,
                "content": content,
            }
        )

    async def emit_coach_recommendation(self, phrase: str, context: str) -> None:
        if not phrase or not phrase.strip():
            return
        phrase_clean = phrase.strip()
        # Skip single words or detection artifacts like "YES", "NO", "CLOSING"
        if len(phrase_clean.split()) < 3:
            return
        invalid_patterns = [
            "[phrase]", "(phrase)", "[say this]", "(say this)",
            "user interrupt", "(user interrupt", "[user interrupt",
            "silent context", "[system", "(system",
        ]
        if any(p in phrase_clean.lower() for p in invalid_patterns):
            return
        if phrase_clean.startswith("[") and phrase_clean.endswith("]"):
            return
        if phrase_clean.startswith("(") and phrase_clean.endswith(")"):
            return
        
        # Dedup: skip if too similar to recent coaching
        phrase_lower = phrase_clean.lower()
        for prev in self.state.recent_coaching[-3:]:
            overlap = sum(1 for w in phrase_lower.split() if w in prev) / max(len(phrase_lower.split()), 1)
            if overlap > 0.6:
                return
        self.state.recent_coaching.append(phrase_lower)
        if len(self.state.recent_coaching) > 6:
            self.state.recent_coaching.pop(0)
        
        await self.emit(
            {
                "type": "coach.recommendation",
                "phrase": phrase_clean,
                "context": context,
            }
        )

    async def emit_signal_alert(self, urgency: str, title: str, message: str, signal_type: str) -> None:
        # Rate limit signals - don't repeat same signal type within 30 seconds
        now = asyncio.get_event_loop().time()
        signal_key = f"{signal_type}_{title}"
        last_sent = self.state.last_signal_times.get(signal_key, 0)
        
        # Different cooldowns for different urgencies
        cooldown = 30 if urgency == "urgent" else 45  # momentum signals need longer cooldown
        if now - last_sent < cooldown:
            return  # Skip this signal, too soon
        
        self.state.last_signal_times[signal_key] = now
        await self.emit(
            {
                "type": "signal.alert",
                "urgency": urgency,
                "title": title,
                "message": message,
                "signal_type": signal_type,
            }
        )

    def analyze_negotiation_momentum(self, text: str) -> dict[str, Any]:
        lower = text.lower()
        stalling_patterns = [
            "need to think", "let me think", "get back to you", "not sure",
            "maybe", "possibly", "we'll see", "i don't know",
            "have to check", "need to discuss", "talk to my team",
            "circle back", "touch base", "revisit later", "not ready",
        ]
        progress_patterns = [
            "sounds good", "i like", "that works", "let's do",
            "agree", "deal", "yes", "okay let's", "makes sense",
            "can we finalize", "send the contract", "when can we start",
        ]

        is_stalling = any(p in lower for p in stalling_patterns)
        is_progress = any(p in lower for p in progress_patterns)
        current_topics = []
        if any(k in lower for k in ["budget", "price", "cost"]):
            current_topics.append("price")
        if any(k in lower for k in ["time", "deadline", "when"]):
            current_topics.append("timeline")
        if any(k in lower for k in ["scope", "deliverable"]):
            current_topics.append("scope")
        if any(k in lower for k in ["payment", "net-"]):
            current_topics.append("payment")

        self.state.conversation_history.append(
            {
                "text": lower,
                "topics": current_topics,
                "stalling": is_stalling,
                "progress": is_progress,
            }
        )
        if is_stalling:
            self.state.stalling_count += 1
        if is_progress:
            self.state.progress_signals += 1

        # Circling detection - only when truly stuck, not just discussing same topic
        is_circling = False
        if len(self.state.conversation_history) >= 5:
            recent = self.state.conversation_history[-5:]
            
            # Check if there's been NO progress in recent exchanges
            recent_progress = sum(1 for item in recent if item.get("progress"))
            recent_stalling = sum(1 for item in recent if item.get("stalling"))
            
            # Check topic repetition without movement
            recent_topics = []
            for item in recent:
                recent_topics.extend(item["topics"])
            topic_counts: dict[str, int] = {}
            for topic in recent_topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
            
            # Only circling if: same topic 4+ times AND no progress AND some stalling
            has_topic_repetition = any(count >= 4 for count in topic_counts.values())
            is_circling = has_topic_repetition and recent_progress == 0 and recent_stalling >= 2

        return {
            "is_stalling": is_stalling,
            "is_progress": is_progress,
            "is_circling": is_circling,
            "stalling_count": self.state.stalling_count,
            "progress_signals": self.state.progress_signals,
            "turns": len(self.state.conversation_history),
        }

    async def emit_backend_signals(self, adversary_statement: str, momentum: dict[str, Any]) -> None:
        lower = adversary_statement.lower()
        contract_state: ContractState = self.session_data["contract_state"]
        terms = contract_state.structured_terms
        presence: PresenceSnapshot = self.session_data["presence_snapshot"]
        spoken_terms = extract_spoken_terms_from_text(adversary_statement)

        if "budget" in lower or "$50" in lower or "$40" in lower or "$30" in lower:
            await self.emit_signal_alert(
                "urgent",
                "Anchoring pressure",
                "They set a low price anchor. Re-anchor on value and scope.",
                "tactic",
            )

        if "urgent" in lower or "deadline" in lower or "need it by" in lower or "6 weeks" in lower:
            await self.emit_signal_alert(
                "watch",
                "Timeline pressure",
                "Counterpart is using urgency. Probe the real constraint before conceding.",
                "tactic",
            )

        # Only emit drift signals if screen has been shared (real contract grounding)
        # For goal mismatch (no screen), wait until conversation has developed (4+ turns)
        has_screen = contract_state.latest_screen is not None
        turn_count = momentum.get("turns", 0)
        
        for diff in compare_terms(terms, spoken_terms):
            # Skip drift if adversary is accepting/agreeing with user's counter-proposal
            # Acceptance words indicate the adversary is going along with the user, not drifting
            acceptance_words = ["can do", "could do", "we can", "might be able", "open to", "works for us", "agree", "accept"]
            is_acceptance = any(w in lower for w in acceptance_words)
            if is_acceptance:
                continue

            if has_screen:
                await self.emit_signal_alert(
                    "urgent",
                    "Contract drift",
                    f"Contract says {diff['contract']}. They said {diff['spoken']} for {diff['field']}.",
                    "drift",
                )
            elif turn_count >= 4:
                # Only show goal mismatch after conversation develops
                await self.emit_signal_alert(
                    "watch",
                    "Goal mismatch",
                    f"Your target: {diff['contract']}. They offered: {diff['spoken']} ({diff['field']}).",
                    "goal_mismatch",
                )

        # Note: Circling detection is now handled by LLM in the main flow
        
        if momentum["stalling_count"] >= 3 and momentum["turns"] > 5:
            await self.emit_signal_alert(
                "watch",
                "Stalling detected",
                "Counterpart is avoiding commitment. Ask for the real objection directly.",
                "momentum",
            )

        # Only emit presence signals if camera data has actually been received
        if presence.has_data():
            if (presence.tension or 0) >= 65 or (presence.eye_contact or 100) <= 30:
                await self.emit_signal_alert(
                    "watch",
                    "Presence coaching",
                    "Visible tension or low eye contact detected. Slow down and project confidence.",
                    "presence",
                )

    def detect_completion(self, text: str) -> dict[str, bool]:
        lower = text.lower().strip()
        is_closing_phrase = bool(
            any(
                phrase in lower
                for phrase in [
                    "bye", "goodbye", "farewell", "talk soon", "take care",
                    "pleasure doing business", "look forward to working",
                ]
            )
        )
        is_closing_signal = any(
            phrase in lower
            for phrase in [
                "excited to get started",
                "draw up the paperwork",
                "i'll send the contract",
                "let's make it happen",
                "send over the contract",
                "get the ball rolling",
            ]
        )
        return {
            "is_closing_phrase": is_closing_phrase,
            "is_closing_signal": is_closing_signal,
        }

    def send_opening(self) -> None:
        goals = self.session_data.get("config", {}).get("goals", "Close at $70K minimum, net-45 payment terms")
        self.live_queue.send_content(
            types.Content(
                parts=[
                    types.Part(
                        text=f"""Start the call. You are Maya Chen, TechNova CTO. User's goals: {goals}

Open with one short pitch, e.g.: "Hi! Thanks for taking this call. We're excited about your AI consulting services. We have a $50K budget and need this done in 6 weeks. Can you work with that?"

Then LISTEN. Whatever the user says next — including if they interrupt you — respond only to that. Do not stick to a script. Accept interruptions and answer what they actually said."""
                    )
                ]
            )
        )

    async def handle_client_message(self, data: dict[str, Any]) -> bool:
        msg_type = data.get("type")

        if msg_type == "start":
            self.send_opening()
            await self.emit_session_state("listening")
            return True

        if msg_type == "audio":
            audio_bytes = base64.b64decode(data["data"])
            self.live_queue.send_realtime(types.Blob(mime_type="audio/pcm;rate=16000", data=audio_bytes))
            self.session_store.update_last_audio_time(self.session_id, asyncio.get_event_loop().time())
            return True

        if msg_type == "text":
            self.live_queue.send_content(types.Content(parts=[types.Part(text=data["data"])]))
            return True

        if msg_type == "screen":
            self.state.screen_sharing = True
            self.state.reset_silence()
            raw = data.get("data") or ""
            image_bytes = base64.b64decode(raw) if raw else b""
            if self.session_store.update_contract_screen(self.session_id, image_bytes):
                await self.emit({"type": "screen.analyzing", "status": "analyzing"})
                asyncio.create_task(self._analyze_screen_bg(image_bytes))
            return True

        if msg_type == "share_contract":
            contract_state: ContractState = self.session_data["contract_state"]
            all_terms = dict(contract_state.structured_terms) if contract_state.structured_terms else {}
            client_terms = data.get("terms")
            if not all_terms and isinstance(client_terms, dict) and client_terms:
                for k, v in client_terms.items():
                    if v is not None and str(v).strip():
                        all_terms[k] = str(v).strip()
                if all_terms:
                    contract_state.structured_terms.update(all_terms)
            
            if not all_terms:
                await self.emit({"type": "screen.share_result", "success": False, "error": "No terms to share"})
                return True
            
            if contract_state.context_sent_to_session:
                await self.emit({"type": "screen.share_result", "success": True, "already_shared": True})
                return True
            
            contract_state.context_sent_to_session = True
            contract_state.mark_terms_shared(all_terms)
            await self.emit({"type": "screen.share_result", "success": True, "terms": all_terms})
            asyncio.create_task(self._inject_contract_context_bg(all_terms))
            return True

        if msg_type in {"presence_metrics", "vision.metrics"}:
            payload = data.get("data") or data
            self.session_store.update_presence(self.session_id, payload)
            return True

        if msg_type == "camera_state":
            # Track camera active state (presence signals require actual metrics though)
            is_active = data.get("active", False)
            if is_active:
                await self.emit({"type": "session.info", "content": "Camera enabled for self-view"})
            return True

        if msg_type == "mic_state":
            self.state.mic_muted = data.get("muted", False)
            return True

        if msg_type == "client_barge_in":
            self.live_queue.send_content(
                types.Content(
                    parts=[
                        types.Part(
                            text="[The user is speaking now. Stop your current response immediately. You will hear what they said next — respond only to that.]"
                        )
                    ]
                )
            )
            if self.state.accumulated_text.strip():
                await self.emit_transcript_append("adversary", self.state.accumulated_text.strip() + " — [interrupted]")
            self.state.accumulated_text = ""
            return True

        if msg_type == "end":
            self.live_queue.close()
            return False

        return True

    async def _coaching_bg(self, adversary_statement: str, momentum: dict[str, Any]) -> None:
        """Run coaching LLM call in background so it doesn't block the conversation."""
        try:
            # Skip if screen is being shared (user is busy) or statement is too short to be real speech
            if self.state.screen_sharing:
                return
            if len(adversary_statement.split()) < 5:
                return

            # Guard: only one coaching per adversary turn (3s cooldown prevents duplicate turn_complete)
            now = asyncio.get_event_loop().time()
            if now - self.state.last_coaching_time < 3.0:
                return
            self.state.last_coaching_time = now

            config = self.session_data.get("config", {})
            contract_state: ContractState = self.session_data["contract_state"]
            presence_snapshot: PresenceSnapshot = self.session_data["presence_snapshot"]

            coaching = await self.coaching_fn(
                adversary_text=adversary_statement,
                goals=config.get("goals", ""),
                batna=config.get("batna", ""),
                user_history="\n".join([f'- User said: "{stmt}"' for stmt in self.state.user_history[-3:]]),
                contract_state=contract_state,
                presence_snapshot=presence_snapshot,
            )

            await self.emit_coach_recommendation(
                coaching.get("phrase", coaching.get("say_this", "")),
                coaching.get("context", ""),
            )

            if coaching.get("is_closing"):
                self.state.deal_closed = True
                await self.emit({
                    "type": "session.deal_closed",
                    "detected_by": "llm",
                    "context": adversary_statement[:100],
                })

            llm_circling = coaching.get("is_circling", False)
            det_circling = momentum.get("is_circling", False)
            turns = momentum.get("turns", 0)
            # Be strict: both LLM and deterministic must agree, and only after 8+ turns
            if llm_circling and det_circling and turns >= 8:
                await self.emit_signal_alert(
                    "note",
                    "Conversation may be circling",
                    "Same topic without new ground. Consider proposing a concrete number or pivoting.",
                    "momentum",
                )
        except Exception as exc:
            print(f"Background coaching error: {exc}", flush=True)

    async def _analyze_screen_bg(self, image_bytes: bytes) -> None:
        """Run document analysis in background so the WS loop stays responsive."""
        try:
            contract_state: ContractState = self.session_data["contract_state"]
            analysis = await analyze_document(image_bytes)
            if analysis.get("success"):
                terms = analysis.get("terms", {})
                contract_state.merge_terms(terms, extracted_at=asyncio.get_event_loop().time())
                await self.emit({
                    "type": "screen.analyzing",
                    "status": "complete",
                    "terms": contract_state.structured_terms,
                    "shared": contract_state.context_sent_to_session,
                })
            else:
                await self.emit({
                    "type": "screen.analyzing",
                    "status": "complete",
                    "error": analysis.get("error") or "Could not extract terms from this view",
                })
        except Exception as exc:
            await self.emit({
                "type": "screen.analyzing",
                "status": "complete",
                "error": f"Analysis failed: {exc}",
            })

    async def _inject_contract_context_bg(self, all_terms: dict) -> None:
        """Inject contract context into Live API without blocking the WS loop."""
        context_parts = []
        for key in ["price", "payment_terms", "timeline", "scope"]:
            if all_terms.get(key):
                context_parts.append(f"{key}: {all_terms[key]}")
        if not context_parts:
            return
        context_str = " | ".join(context_parts)
        try:
            self.live_queue.send_content(
                types.Content(
                    parts=[
                        types.Part(
                            text=f"""[INTERNAL CONTEXT - DO NOT REPLY OR SPEAK. Do not output any audio or text in response to this. Just store for reference.]
Contract terms you now know: {context_str}
When the user speaks next, use these terms naturally in negotiation. Do not acknowledge the document or this message aloud. Wait for the user's next spoken turn before saying anything."""
                        )
                    ]
                )
            )
        except Exception:
            pass

    async def receive_from_user(self) -> None:
        try:
            while True:
                data = await self.websocket.receive_json()
                should_continue = await self.handle_client_message(data)
                if not should_continue:
                    break
        except WebSocketDisconnect:
            self.mark_closed()
            self.live_queue.close()

    async def handle_adversary_event(self, event: Any) -> None:
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    blob = part.inline_data
                    if blob.mime_type and "audio" in blob.mime_type:
                        data = base64.b64encode(blob.data).decode()
                        await self.emit({"type": "media.audio", "data": data, "mime_type": blob.mime_type})

        if hasattr(event, "input_transcription") and event.input_transcription:
            trans = event.input_transcription
            user_text = ""
            if hasattr(trans, "text") and trans.text:
                user_text = trans.text.strip()

            # Strong noise filtering to prevent false interruptions
            # Common noise patterns that get falsely transcribed
            noise_patterns = {
                "uh", "um", "ah", "oh", "hmm", "hm", "mm", "mhm", 
                "yeah", "yep", "ok", "okay", "right", "sure",
                ".", "..", "...", "-", "--", "---",
                "the", "a", "i", "it", "is", "so", "and", "but",
            }
            
            words = user_text.lower().split() if user_text else []
            word_count = len(words)
            char_count = len(user_text)
            
            # Filter out noise: must have 4+ words OR 2+ words with 15+ chars
            # Also exclude single noise words
            is_noise = (
                word_count == 0 or
                (word_count == 1 and words[0] in noise_patterns) or
                (word_count == 2 and all(w in noise_patterns for w in words)) or
                (word_count < 4 and char_count < 15)
            )
            is_real_speech = not is_noise

            if is_real_speech:
                await self.emit({"type": "audio.clear"})
                if self.state.accumulated_text.strip():
                    await self.emit_transcript_append("adversary", self.state.accumulated_text.strip() + " — [interrupted]")
                self.state.accumulated_text = ""

            if is_real_speech:
                self.state.screen_sharing = False  # User spoke — no longer silent on screen share
                lower = user_text.lower()
                if "share" in lower and ("screen" in lower or "document" in lower):
                    self.state.screen_sharing = True
                    self.state.reset_silence()
                    self.live_queue.send_content(
                        types.Content(
                            parts=[
                                types.Part(
                                    text="[The user is sharing their screen/document. Say ONE short acknowledgment like 'Sure, go ahead' then STOP and WAIT silently. Do NOT speak again until the user speaks. They may be silent for 30-60 seconds while setting up — that is normal. Do NOT ask if they're still there.]"
                                )
                            ]
                        )
                    )

                await self.emit_transcript_append("user", user_text)
                self.state.record_user_text(user_text)

        if hasattr(event, "output_transcription") and event.output_transcription:
            trans = event.output_transcription
            if hasattr(trans, "text") and trans.text:
                if not self.state.accumulated_text.endswith(trans.text):
                    self.state.accumulated_text += trans.text

        if hasattr(event, "turn_complete") and event.turn_complete and self.state.accumulated_text.strip():
            adversary_statement = self.state.accumulated_text.strip()
            self.state.accumulated_text = ""

            # Dedup: skip if same statement fired within 4s (Gemini Live sometimes emits turn_complete twice)
            now = asyncio.get_event_loop().time()
            is_duplicate = (
                adversary_statement == getattr(self.state, "_last_adversary_stmt", "") and
                now - getattr(self.state, "_last_adversary_time", 0) < 4.0
            )
            self.state._last_adversary_stmt = adversary_statement  # type: ignore[attr-defined]
            self.state._last_adversary_time = now  # type: ignore[attr-defined]
            if is_duplicate:
                return

            self.state.last_adversary_finish_time = now
            await self.emit_transcript_append("adversary", adversary_statement)

            # If LLM already confirmed deal is closed on a prior turn, skip coaching entirely
            if self.state.deal_closed:
                await self.emit_session_state("user_turn")
                return

            # Deterministic signals are fast — run inline
            momentum = self.analyze_negotiation_momentum(adversary_statement)
            await self.emit_backend_signals(adversary_statement, momentum)

            # Tell user it's their turn IMMEDIATELY — don't wait for coaching LLM
            await self.emit_session_state("user_turn")

            # Coaching runs in background so the conversation isn't blocked
            asyncio.create_task(self._coaching_bg(adversary_statement, momentum))

    async def send_adversary_response(self, adversary_runner) -> None:
        try:
            run_config = RunConfig(
                response_modalities=[types.Modality.AUDIO],
                streaming_mode=StreamingMode.BIDI,
                output_audio_transcription=types.AudioTranscriptionConfig(),
                input_audio_transcription=types.AudioTranscriptionConfig(),
            )

            async for event in adversary_runner.run_live(
                user_id="user",
                session_id=self.session_id,
                live_request_queue=self.live_queue,
                run_config=run_config,
            ):
                await self.handle_adversary_event(event)
        except WebSocketDisconnect:
            self.mark_closed()
        except Exception as e:
            err_msg = str(e)
            friendly = err_msg
            code = "runtime"
            if "nodename nor servname provided" in err_msg or "name or service not known" in err_msg:
                friendly = "Network is unavailable. Please try again once your connection is back."
                code = "network"
            elif "1007" in err_msg or "16khz s16le pcm, mono channel" in err_msg.lower():
                friendly = "Could not process your microphone audio. Your mic is on, but the audio format was rejected. End this session, refresh mic access, and try again."
                code = "audio_format"
            elif "1011" in err_msg or "Internal error encountered" in err_msg:
                friendly = "The live model hit a temporary internal error. Please start a fresh session."
                code = "internal"
            await self.emit({"type": "session.error", "content": friendly, "code": code})
            self.live_queue.close()

    async def session_timeout_monitor(self) -> None:
        try:
            created_at = self.session_data.get("created_at", asyncio.get_event_loop().time())
            while True:
                if self.closed:
                    break
                await asyncio.sleep(10)
                elapsed = asyncio.get_event_loop().time() - created_at
                remaining = SESSION_TIMEOUT - elapsed

                if 50 <= remaining <= 60:
                    await self.emit({"type": "session.warning", "content": "Session ending in 1 minute (cost control)"})

                if elapsed >= SESSION_TIMEOUT:
                    await self.emit({"type": "session.timeout", "content": "Session ended (5 minute limit reached)"})
                    self.live_queue.close()
                    break
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass

    async def silence_monitor(self) -> None:
        """Nudge after silence, but never when the mic is intentionally muted."""
        try:
            while True:
                if self.closed:
                    break
                await asyncio.sleep(5)
                if self.state.mic_muted or self.state.screen_sharing:
                    continue
                t = self.state.last_adversary_finish_time
                if t is None:
                    continue
                now = asyncio.get_event_loop().time()
                silence_sec = now - t

                if silence_sec >= GOODBYE_NUDGE_SEC and not self.state.goodbye_nudge_sent:
                    self.state.goodbye_nudge_sent = True
                    self.live_queue.send_content(
                        types.Content(
                            parts=[
                                types.Part(
                                    text="[The user has been silent for a long time. Say a brief goodbye and suggest following up later, e.g. 'I don't seem to hear you — let's pick this up another time. I'll send over a summary and we can reconnect when it works for you. Goodbye!']"
                                )
                            ]
                        )
                    )
                elif silence_sec >= SILENCE_NUDGE_SEC and not self.state.silence_nudge_sent:
                    self.state.silence_nudge_sent = True
                    self.live_queue.send_content(
                        types.Content(
                            parts=[
                                types.Part(
                                    text="[The user has been silent for about 10 seconds. Say one short line only: e.g. 'Are you still there?' or 'Let me know when you're ready.' Then wait for their response.]"
                                )
                            ]
                        )
                    )
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
