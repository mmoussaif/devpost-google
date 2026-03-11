export function formatElapsed(startTime) {
    if (!startTime) return "00:00";
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const mins = Math.floor(elapsed / 60).toString().padStart(2, "0");
    const secs = (elapsed % 60).toString().padStart(2, "0");
    return `${mins}:${secs}`;
}

export function createTranscriptEntryElement(speaker, text) {
    const entry = document.createElement("div");
    entry.className = `transcript-entry ${speaker === "adversary" ? "adversary" : "user"}`;

    const tag = document.createElement("span");
    tag.className = `speaker-tag ${speaker === "adversary" ? "adversary" : "user"}`;
    tag.textContent = speaker === "adversary" ? "🎭 THEM" : "🎙️ YOU";

    const textSpan = document.createElement("span");
    textSpan.className = "entry-text";
    textSpan.textContent = text;

    entry.appendChild(tag);
    entry.appendChild(textSpan);
    return entry;
}

export function createSignalCardElement(data, timestampText, icon) {
    const card = document.createElement("div");
    card.className = "intervention-card signal";
    card.innerHTML = `
        <div class="intervention-header">
            <span class="intervention-type signal-type">${icon} ${data.signal_type.toUpperCase()}</span>
            <span class="intervention-time">${timestampText}</span>
        </div>
        <div class="intervention-content">
            <div class="intervention-summary">Buddy signal</div>
            <div class="intervention-body">${data.message}</div>
        </div>
    `;
    return card;
}

export function createInterventionCardElement(data, timestampText, typeLabel) {
    const card = document.createElement("div");
    card.className = `intervention-card ${data.urgency}`;
    card.innerHTML = `
        <div class="intervention-header">
            <span class="intervention-type">${typeLabel}</span>
            <span class="intervention-time">${timestampText}</span>
        </div>
        <div class="intervention-content">
            <div class="intervention-summary">${data.urgency === "urgent" ? "Act now" : data.urgency === "watch" ? "Watch closely" : "Context"}</div>
            <div class="intervention-body">${data.content}</div>
        </div>
    `;
    return card;
}
