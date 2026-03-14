import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { SessionConfig } from "../types";

interface LandingScreenProps {
  onStart: (config: SessionConfig) => void;
  loading: boolean;
}

export default function LandingScreen({ onStart, loading }: LandingScreenProps) {
  const [showSettings, setShowSettings] = useState(false);
  const [goals, setGoals] = useState(
    "Close at $70K minimum, net-45 payment terms, IP ownership retained"
  );
  const [batna, setBatna] = useState(
    "Walk away — another prospect at $65K"
  );
  const handleStart = () => {
    onStart({ goals, batna });
  };

  return (
    <div className="flex min-h-dvh items-center justify-center px-4">
      <div className="w-full max-w-md text-center">
        <h1 className="mb-2 bg-gradient-to-br from-indigo-400 to-purple-400 bg-clip-text text-4xl font-bold tracking-tight text-transparent">
          Secondus
        </h1>
        <p className="mx-auto mb-8 max-w-sm text-base leading-relaxed text-slate-400">
          Practice high-stakes negotiations with an AI counterpart that pushes
          back, then coaches you with the exact line to say.
        </p>
        <div className="mx-auto mb-8 flex items-center gap-3 rounded-xl border border-white/[0.07] bg-[#151C28] px-4 py-3 max-w-xs">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-500/20 text-indigo-400 text-sm font-bold">MC</div>
          <div className="text-left">
            <p className="text-xs text-slate-500 mb-0.5">You will negotiate with</p>
            <p className="text-sm font-medium text-slate-200">Maya Chen, <span className="text-slate-400">CTO of TechNova</span></p>
          </div>
        </div>

        <button
          onClick={handleStart}
          disabled={loading}
          className="w-full rounded-xl bg-indigo-500 px-6 py-3.5 text-base font-semibold text-white transition-all hover:-translate-y-0.5 hover:bg-indigo-600 hover:shadow-lg hover:shadow-indigo-500/25 disabled:opacity-50 disabled:hover:translate-y-0"
        >
          {loading ? "Starting..." : "Start Session"}
        </button>

        <button
          onClick={() => setShowSettings((p) => !p)}
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-white/[0.07] px-3 py-1.5 text-sm text-slate-500 transition-colors hover:border-white/15 hover:text-slate-300"
        >
          Customize scenario
          {showSettings ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        {showSettings && (
          <div className="mt-4 animate-fade-in-up rounded-2xl border border-white/[0.07] bg-[#151C28] p-5 text-left">
            <Field label="Your negotiation goals">
              <textarea
                value={goals}
                onChange={(e) => setGoals(e.target.value)}
                rows={2}
                className="field-input"
              />
            </Field>
            <Field label="Walk-away alternative (BATNA)">
              <textarea
                value={batna}
                onChange={(e) => setBatna(e.target.value)}
                rows={2}
                className="field-input"
              />
            </Field>
          </div>
        )}

        <p className="mt-6 text-xs text-slate-600">
          Sessions run up to 5 minutes. Powered by Gemini Live API.
        </p>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-4">
      <label className="mb-1.5 block text-xs font-medium text-slate-400">
        {label}
      </label>
      {children}
    </div>
  );
}
