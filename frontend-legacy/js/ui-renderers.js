import {
    createInterventionCardElement,
    createSignalCardElement,
    createTranscriptEntryElement,
    formatElapsed
} from "./ui-components.js";

export function addTranscriptEntry({ transcriptEl, speaker, text }) {
    if (!transcriptEl) return;
    const waitingMsg = transcriptEl.querySelector('[style*="italic"]');
    if (waitingMsg) waitingMsg.remove();

    const entry = createTranscriptEntryElement(speaker, text);
    transcriptEl.appendChild(entry);
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

export function setTurnState({ indicatorEl, labelEl, panelEl, micBtn, state }) {
    if (!indicatorEl || !labelEl || !panelEl) return;

    indicatorEl.className = "turn-indicator";
    panelEl.classList.remove("adversary-speaking", "user-speaking");

    if (state === "adversary") {
        indicatorEl.classList.add("adversary-turn");
        labelEl.textContent = "🎭 ADVERSARY SPEAKING";
        panelEl.classList.add("adversary-speaking");
        return;
    }

    if (state === "user") {
        const isMuted = micBtn && micBtn.classList.contains("muted");
        if (isMuted) {
            indicatorEl.classList.add("your-turn-muted");
            labelEl.textContent = "🔇 Turn on Mic to speak";
        } else {
            indicatorEl.classList.add("your-turn");
            labelEl.textContent = "🎙️ YOUR TURN";
        }
        panelEl.classList.add("user-speaking");
        return;
    }

    indicatorEl.classList.add("waiting");
    labelEl.textContent = "Waiting...";
}

export function updateMutedHint({ hintEl, micBtn, liveScreenEl }) {
    if (!hintEl) return;
    const isMuted = micBtn && micBtn.classList.contains("muted");
    hintEl.style.display = isMuted && liveScreenEl && liveScreenEl.style.display !== "none" ? "block" : "none";
}

export function updateTurnLabelIfUserTurn({ indicatorEl, labelEl, micBtn }) {
    if (!indicatorEl || !labelEl) return;
    if (!indicatorEl.classList.contains("your-turn") && !indicatorEl.classList.contains("your-turn-muted")) return;

    const isMuted = micBtn && micBtn.classList.contains("muted");
    if (isMuted) {
        indicatorEl.classList.remove("your-turn");
        indicatorEl.classList.add("your-turn-muted");
        labelEl.textContent = "🔇 Turn on Mic to speak";
        return;
    }

    indicatorEl.classList.remove("your-turn-muted");
    indicatorEl.classList.add("your-turn");
    labelEl.textContent = "🎙️ YOUR TURN";
}

export function updateCoachPanel({ coachPhraseEl, coachContextEl, coachPanelEl, phrase, context }) {
    if (!coachPhraseEl || !coachContextEl || !coachPanelEl) return;
    coachPhraseEl.textContent = `"${phrase}"`;
    coachContextEl.textContent = context;
    coachPanelEl.style.animation = "none";
    coachPanelEl.offsetHeight;
    coachPanelEl.style.animation = "pulse-coach 0.5s ease";
}

export function updateVoiceTip({ voiceTipEl, content }) {
    if (!voiceTipEl) return;
    const tip = content.split(":").slice(1).join(":").trim();
    voiceTipEl.textContent = tip || content;
}

export function showDriftBanner({ bannerEl, bannerTextEl, content }) {
    if (!bannerEl || !bannerTextEl) return;
    const driftMatch = content.match(/DRIFT:\s*(.+?)(?:\.|$)/i);
    if (driftMatch) {
        bannerTextEl.textContent = `⚠️ ${driftMatch[1]}`;
    } else {
        bannerTextEl.textContent = "⚠️ Contract terms don't match what was said!";
    }
    bannerEl.classList.add("show");
    setTimeout(() => {
        bannerEl.classList.remove("show");
    }, 10000);
}

export function hideDriftBanner({ bannerEl }) {
    if (bannerEl) bannerEl.classList.remove("show");
}

export function addSignal({ interventionsListEl, data, startTime }) {
    if (!interventionsListEl) return;
    const emptyState = interventionsListEl.querySelector(".empty-state");
    if (emptyState) emptyState.remove();

    let icon = "📊";
    if (data.signal_type === "silence") icon = "🤫";
    else if (data.signal_type === "tone") icon = "🎭";
    else if (data.signal_type === "pace") icon = "⏱️";

    const card = createSignalCardElement(data, formatElapsed(startTime), icon);
    interventionsListEl.insertBefore(card, interventionsListEl.firstChild);
}

export function addIntervention({ interventionsListEl, data, startTime, counts, countElements }) {
    if (!interventionsListEl) return;

    const emptyState = interventionsListEl.querySelector(".empty-state");
    if (emptyState) emptyState.remove();

    if (data.urgency && counts[data.urgency] !== undefined) {
        counts[data.urgency] += 1;
        const countEl = countElements?.[data.urgency];
        if (countEl) countEl.textContent = counts[data.urgency];
    }

    const typeLabels = {
        urgent: "⚡ URGENT",
        watch: "⚠️ WATCH",
        note: "● NOTE",
        drift: "📋 DRIFT",
        leverage: "💪 LEVERAGE",
        tactic: "🎯 TACTIC"
    };

    const card = createInterventionCardElement(
        data,
        formatElapsed(startTime),
        typeLabels[data.urgency] || "● NOTE"
    );

    interventionsListEl.insertBefore(card, interventionsListEl.firstChild);
}

export function updateTimer({ timerEl, startTime }) {
    if (timerEl) timerEl.textContent = formatElapsed(startTime);
}

export function setMicUIState({ active, micBtn, labelEl, vuLabelEl, vuMicEl }) {
    if (!micBtn) return;
    if (active) {
        micBtn.classList.remove("muted");
        micBtn.classList.add("active");
        micBtn.setAttribute("aria-pressed", "true");
        micBtn.title = "Microphone on (click to mute)";
        if (labelEl) labelEl.textContent = "Mic";
        if (vuLabelEl) vuLabelEl.textContent = "🎙️ Your Mic";
        return;
    }

    micBtn.classList.remove("active");
    micBtn.classList.add("muted");
    micBtn.setAttribute("aria-pressed", "false");
    micBtn.title = "Microphone off (click to turn on)";
    if (labelEl) labelEl.textContent = "Muted";
    if (vuLabelEl) vuLabelEl.textContent = "🔇 Muted";
    if (vuMicEl) vuMicEl.style.width = "0%";
}

export function showTimeoutWarning(message) {
    let warning = document.getElementById("timeout-warning");
    if (!warning) {
        warning = document.createElement("div");
        warning.id = "timeout-warning";
        warning.className = "timeout-warning";
        document.body.appendChild(warning);
    }
    warning.textContent = message;
    warning.style.display = "block";
}

export function showPracticeError(message, code) {
    let banner = document.getElementById("practice-error-banner");
    if (!banner) {
        banner = document.createElement("div");
        banner.id = "practice-error-banner";
        banner.className = "drift-banner show";
        banner.style.background = "rgba(239, 68, 68, 0.95)";
        banner.innerHTML = `
            <span class="drift-banner-icon">⚠️</span>
            <span class="drift-banner-text" id="practice-error-text"></span>
            <button class="drift-banner-close" type="button">Dismiss</button>
        `;
        banner.querySelector("button")?.addEventListener("click", () => banner.remove());
        document.body.appendChild(banner);
    }

    const textEl = banner.querySelector("#practice-error-text");
    let detail = message;
    if (code === "internal") {
        detail = `${message} End this session and start a new one.`;
    } else if (code === "audio_format") {
        detail = "Buddy could not process your microphone audio yet. End this session, refresh mic access, and retry.";
    } else if (code === "network") {
        detail = "Buddy could not reach the live model right now. Check your internet connection, then end this session and retry.";
    } else if (code === "runtime") {
        detail = `${message} Try ending this session and starting Buddy again.`;
    }
    if (textEl) textEl.textContent = detail;
    banner.classList.add("show");
}
