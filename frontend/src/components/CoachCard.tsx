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
      className={`fixed bottom-4 left-1/2 z-50 w-[92%] max-w-xl -translate-x-1/2 rounded-2xl border border-emerald-400/20 bg-emerald-950/25 px-5 py-4 shadow-2xl backdrop-blur-[2px] transition-all duration-300 ${
        visible
          ? "translate-y-0 opacity-100"
          : "pointer-events-none translate-y-4 opacity-0"
      }`}
    >
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[0.6875rem] font-bold uppercase tracking-wider text-emerald-300/70">
          You could say
        </span>
        <button
          onClick={onCopy}
          className="rounded-md p-1.5 text-white/30 transition-colors hover:bg-white/10 hover:text-white/60"
        >
          <Copy size={13} />
        </button>
      </div>

      <p className="text-base font-semibold leading-snug text-white/95 drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]">
        {phrase}
      </p>
      {context && (
        <p className="mt-1 truncate text-xs text-white/40">{context}</p>
      )}
    </div>
  );
}
