import { Copy } from "lucide-react";

interface CoachCardProps {
  phrase: string;
  context: string;
  onCopy: () => void;
  visible: boolean;
}

export default function CoachCard({
  phrase,
  context,
  onCopy,
  visible,
}: CoachCardProps) {
  return (
    <div
      className={`fixed bottom-4 left-1/2 z-50 w-[92%] max-w-xl -translate-x-1/2 rounded-2xl border border-emerald-400/25 bg-emerald-900/90 px-5 py-4 shadow-2xl backdrop-blur-xl transition-all duration-300 ${
        visible
          ? "translate-y-0 opacity-100"
          : "pointer-events-none translate-y-4 opacity-0"
      }`}
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[0.6875rem] font-bold uppercase tracking-wider text-white/70">
          Say this now
        </span>
        <button
          onClick={onCopy}
          className="rounded-md p-1.5 text-white/40 transition-colors hover:bg-white/10 hover:text-white/70"
        >
          <Copy size={14} />
        </button>
      </div>

      <p className="text-lg font-semibold leading-relaxed text-white">
        {phrase}
      </p>
      {context && (
        <p className="mt-1 text-sm text-white/60">{context}</p>
      )}
    </div>
  );
}
