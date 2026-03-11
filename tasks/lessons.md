# Secondus — Lessons Learned

## Session Log

### 2026-03-09: Project Setup

**Context**: Initial project creation for Gemini Live Agent Challenge.

**Corrections Applied**:
1. Use `gemini-live-2.5-flash-native-audio` not `gemini-2.0-flash-live-001`.
2. Use Python 3.13+ not 3.11.
3. Use `python:3.13-slim` Docker image.

**Rules Derived**:
- Always confirm model version before writing agent code.
- Default to latest stable Python (3.13) for new projects.

---

### 2026-03-10: Audio Format Requirements

**Context**: User not being heard; Gemini returned 1007 error about invalid input audio format.

**Root Cause**: Browser's `AudioContext({ sampleRate: 16000 })` is a hint, not a guarantee. Actual sample rate varies (44.1kHz, 48kHz).

**Fix Applied**: Explicit resampling to 16kHz before sending to Gemini.

**Rules Derived**:
- Never trust browser sample-rate hints for strict APIs.
- Resample explicitly and send exact required format.

---

### 2026-03-10: Judge-First Redesign

**Context**: Product became fragmented with competing features.

**What We Learned**:
1. Judges score fluidity, multimodal naturalness, robustness, and demo clarity.
2. A negotiation copilot should feel calm and invisible, not like a control center.
3. One flagship live loop beats many partial features.

**Rules Derived**:
- Optimize for one memorable multimodal interaction.
- Keep one primary recommendation on screen at a time.
- Hide or cut features that don't improve the live loop.

---

### 2026-03-11: Frontend Modernization

**Context**: Vanilla HTML/JS frontend was hard to maintain and extend.

**What Changed**:
1. Migrated to React 18 + TypeScript + Vite.
2. Adopted Tailwind CSS v4 for styling.
3. Component-based architecture with custom hooks.

**Rules Derived**:
- Modern frameworks improve development velocity.
- Type safety catches bugs early.
- Component isolation improves testability.

---

### 2026-03-11: False Signal Detection

**Context**: "Conversation circling" triggered during active price negotiation.

**Root Cause**: Deterministic detection counted topic mentions without considering progress.

**Fix Applied**:
1. Added LLM-based circling detection to coaching prompt.
2. Hybrid approach: LLM + deterministic must agree.
3. Increased turn threshold to 5+ for LLM, 7+ for deterministic.

**Rules Derived**:
- Keyword matching is brittle for semantic concepts.
- LLM provides semantic understanding; deterministic provides guardrails.
- Require multiple signals to agree for sensitive detections.

---

### 2026-03-11: Session Auto-Ending

**Context**: Session ended automatically when "goodbye" detected, even during active negotiation.

**Root Cause**: Keyword-based closing detection triggered session.complete.

**Fix Applied**:
1. Removed all auto-end behavior.
2. Deal closure detection only updates metrics.
3. User must click "End" button to see recap.

**Rules Derived**:
- User should control session lifecycle.
- Detection should inform, not control.
- Separate "detection" from "action".

---

### 2026-03-11: Document Analysis UX

**Context**: AI repeatedly said "I see the document" when screen sharing.

**Root Cause**: Continuous frame capture sent context to AI on every scroll.

**Fix Applied**:
1. Manual "Start Analysis" / "Done Scanning" flow.
2. Frames captured every 3s while scanning (user scrolls).
3. Explicit "Share with Counterpart" button.
4. Context sent to AI only once per explicit share.

**Final Flow**:
```
Share Screen → Start Analysis → Scroll Document → Done Scanning → Review Terms → Share
```

**Rules Derived**:
- User should control what's shared with AI.
- Prevent repetitive acknowledgments.
- One-time context injection beats continuous.
- Show extracted terms before sharing for transparency.

---

### 2026-03-11: Scoring Without Camera

**Context**: Low scores when camera disabled, even for good negotiations.

**Root Cause**: Scoring weighted presence at 30% even when no camera data.

**Fix Applied**:
1. Dynamic scoring weights based on camera state.
2. Camera disabled: 100% voice score.
3. Camera enabled: 70% voice + 30% presence.

**Rules Derived**:
- Don't penalize for missing optional features.
- Dynamic weights based on available data.
- Voice is primary in negotiations.

---

### 2026-03-11: LLM-Based Detection

**Context**: Keyword matching missed nuanced deal closures like "Sure, we can do that."

**What Changed**:
1. Added CLOSING: YES/NO to coaching prompt.
2. Added CIRCLING: YES/NO to coaching prompt.
3. LLM now provides semantic classification.

**Output Format**:
```
CLOSING: YES/NO
CIRCLING: YES/NO
SAY THIS: [coaching phrase]
```

**Rules Derived**:
- Piggyback detection on existing LLM calls.
- Structured output format for reliable parsing.
- LLM understands semantic meaning better than keywords.

---

### 2026-03-11: Transcript Deduplication

**Context**: Short messages like "0.7%" appeared twice in transcript.

**Root Cause**: Deduplication only checked content length > 5, missing short exact matches.

**Fix Applied**:
1. Time-based deduplication (3s window).
2. Exact match detection regardless of length.
3. Substring containment for longer messages.

**Rules Derived**:
- Consider both content and timing for deduplication.
- Handle edge cases (short messages, rapid repeats).

---

### 2026-03-11: Signal Rate Limiting

**Context**: Same signal appeared multiple times in quick succession.

**Fix Applied**:
1. Track last emission time per signal type.
2. 30s cooldown for urgent signals.
3. 45s cooldown for watch/note signals.

**Rules Derived**:
- Rate limit by signal type, not globally.
- Different urgencies deserve different cooldowns.
- State tracking prevents spam.

---

## General Principles

### Voice-First Design
- Audio is primary; vision is supplementary.
- Interruption handling is mandatory.
- One recommendation at a time.

### Multimodal Grounding
- Extract structured data from visual input.
- Compare spoken claims against structured state.
- Show evidence in alerts, not just detection.

### User Control
- Never auto-end sessions.
- Let user choose when to share.
- Detection informs; user decides.

### Hybrid Intelligence
- LLM provides semantic understanding.
- Deterministic provides guardrails.
- Combine for robust detection.
