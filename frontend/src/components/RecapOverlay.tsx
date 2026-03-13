import type { RecapData, SessionRecording } from "../types";
import { useEffect, useState } from "react";

interface RecapOverlayProps {
  recording: SessionRecording;
  onRestart: () => void;
}

export default function RecapOverlay({ recording, onRestart }: RecapOverlayProps) {
  const [recap, setRecap] = useState<RecapData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const payload = {
      session: {
        duration: formatDuration(recording.startTime),
        mode: "secondus_buddy",
        date: new Date().toISOString(),
        ...(recording.sessionId != null && { session_id: recording.sessionId }),
        ...(recording.config != null && { config: recording.config }),
      },
      metrics: recording.metrics,
      exchanges: recording.exchanges,
      tacticsDetected: recording.tacticsDetected,
      coachingGiven: recording.coachingGiven,
      cameraEnabled: recording.cameraEnabled ?? false,
      visualPresence: recording.visualPresence ?? {},
    };

    fetch("/session/buddy/recap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then((r) => r.json())
      .then((data) => setRecap(data))
      .catch(() => {
        setRecap({
          score: 50,
          duration: payload.session.duration,
          user_participation: recording.exchanges.filter((e) => e.speaker === "user").length,
          buddy_turns: recording.metrics.totalTurns,
          pressure_signals: recording.tacticsDetected.length,
          outcome: "Session completed.",
          best_intervention: recording.coachingGiven.at(-1)?.phrase ?? "No coaching captured.",
          biggest_risk: "No major signal stood out.",
          next_focus: "Run another round and respond directly to pressure.",
          strengths: [],
          moments: recording.coachingGiven.slice(-3),
        });
      })
      .finally(() => setLoading(false));
  }, [recording]);

  if (loading) {
    return (
      <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-md">
        <div className="text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
          <p className="text-sm text-slate-400">Building your recap...</p>
        </div>
      </div>
    );
  }

  if (!recap) return null;

  const scoreColor =
    recap.score >= 70 ? "border-emerald-400 text-emerald-400" : recap.score >= 50 ? "border-amber-400 text-amber-400" : "border-red-400 text-red-400";
  const scoreBg =
    recap.score >= 70 ? "bg-emerald-400/10" : recap.score >= 50 ? "bg-amber-400/10" : "bg-red-400/10";

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center overflow-y-auto bg-black/80 p-4 backdrop-blur-md">
      <div className="w-full max-w-2xl rounded-3xl border border-white/[0.07] bg-[#0B0F19] p-6 shadow-2xl">
        {/* Header */}
        <div className="mb-6 text-center">
          <span className="mb-3 inline-block rounded-full bg-indigo-500/10 px-3 py-1 text-[0.6875rem] font-bold uppercase tracking-wider text-indigo-400">
            Session Recap
          </span>
          <h2 className="text-2xl font-bold text-white">
            How your negotiation went
          </h2>
        </div>

        {/* Score */}
        <div className="mb-6 flex justify-center">
          <div
            className={`flex h-28 w-28 flex-col items-center justify-center rounded-full border-[3px] ${scoreColor} ${scoreBg}`}
          >
            <span className="text-3xl font-bold">{recap.score}</span>
            <span className="text-xs text-slate-400">/ 100</span>
          </div>
        </div>

        {/* Stats */}
        <div className="mb-6 grid grid-cols-4 gap-2 rounded-2xl border border-white/[0.05] bg-white/[0.02] p-3">
          <Stat value={recap.duration} label="Duration" />
          <Stat value={String(recap.user_participation)} label="Your turns" />
          <Stat value={String(recap.buddy_turns)} label="Opponent turns" />
          <Stat value={String(recap.pressure_signals)} label="Signals" />
        </div>

        {/* Sections */}
        <Section title="Outcome" text={recap.outcome} />
        <Section title="Best Intervention" text={recap.best_intervention} />
        <Section title="Biggest Risk Caught" text={recap.biggest_risk} />
        <Section title="Next Focus" text={recap.next_focus} />

        {/* Visual Presence Summary */}
        {recap.visual_summary && (
          <div className="mb-4 rounded-xl border border-white/[0.05] bg-white/[0.02] p-4">
            <h3 className="mb-3 text-xs font-bold uppercase tracking-wide text-indigo-300">
              Presence Metrics
            </h3>
            <div className="grid grid-cols-3 gap-3">
              <PresenceMetric
                label="Eye Contact"
                value={recap.visual_summary.avgEyeContact}
              />
              <PresenceMetric
                label="Posture"
                value={recap.visual_summary.avgPosture}
              />
              <PresenceMetric
                label="Relaxation"
                value={100 - recap.visual_summary.avgTension}
              />
            </div>
          </div>
        )}

        {recap.strengths.length > 0 && (
          <div className="mb-4 rounded-xl border border-white/[0.05] bg-white/[0.02] p-4">
            <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-indigo-300">
              Strengths
            </h3>
            <ul className="space-y-1 text-sm text-slate-300">
              {recap.strengths.slice(0, 3).map((s, i) => (
                <li key={i}>• {s}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex justify-center gap-3">
          <button
            onClick={onRestart}
            className="rounded-xl bg-indigo-500 px-6 py-2.5 text-sm font-semibold text-white transition-all hover:bg-indigo-600"
          >
            Run Again
          </button>
          <button
            onClick={() => downloadReport(recording)}
            className="rounded-xl border border-white/[0.07] bg-[#1C2536] px-6 py-2.5 text-sm font-medium text-slate-300 transition-all hover:border-white/15"
          >
            Download Report
          </button>
        </div>
      </div>
    </div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <span className="block text-lg font-semibold text-white">{value}</span>
      <span className="text-[0.6875rem] text-slate-500">{label}</span>
    </div>
  );
}

function PresenceMetric({ label, value }: { label: string; value: number }) {
  const color = value >= 70 ? "bg-emerald-400" : value >= 40 ? "bg-amber-400" : "bg-red-400";
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs text-slate-400">{label}</span>
        <span className="text-xs font-medium text-white">{value}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-white/10">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

function Section({ title, text }: { title: string; text: string }) {
  return (
    <div className="mb-4 rounded-xl border border-white/[0.05] bg-white/[0.02] p-4">
      <h3 className="mb-1 text-xs font-bold uppercase tracking-wide text-indigo-300">
        {title}
      </h3>
      <p className="text-sm leading-relaxed text-slate-300">{text}</p>
    </div>
  );
}

function formatDuration(startTime: number | null): string {
  if (!startTime) return "00:00";
  const s = Math.floor((Date.now() - startTime) / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function downloadReport(recording: SessionRecording) {
  const blob = new Blob([JSON.stringify(recording, null, 2)], {
    type: "application/json",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `secondus-session-${new Date().toISOString().split("T")[0]}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}
