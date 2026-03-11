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
    "Close at $80K minimum, net-30 payment terms, IP ownership retained"
  );
  const [batna, setBatna] = useState(
    "Walk away — another prospect at $70K"
  );
  const [scenario, setScenario] = useState(
    "Startup CTO, budget-conscious, wants AI integration"
  );
  const [lowCost, setLowCost] = useState(false);

  const handleStart = () => {
    onStart({ goals, batna, scenario, low_cost_mode: lowCost });
  };

  return (
    <div className="flex min-h-dvh items-center justify-center px-4">
      <div className="w-full max-w-md text-center">
        <h1 className="mb-2 bg-gradient-to-br from-indigo-400 to-purple-400 bg-clip-text text-4xl font-bold tracking-tight text-transparent">
          Secondus
        </h1>
        <p className="mx-auto mb-10 max-w-sm text-base leading-relaxed text-slate-400">
          Practice high-stakes negotiations with an AI counterpart that pushes
          back, then coaches you with the exact line to say.
        </p>

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
            <Field label="Scenario / counterparty">
              <input
                type="text"
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
                className="field-input"
              />
            </Field>
            <label className="mt-2 flex cursor-pointer items-center gap-2 text-sm text-slate-500">
              <input
                type="checkbox"
                checked={lowCost}
                onChange={(e) => setLowCost(e.target.checked)}
                className="accent-indigo-500"
              />
              Low-cost mode (text only, no AI voice)
            </label>
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
