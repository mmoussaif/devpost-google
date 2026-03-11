import { useEffect } from "react";
import { X } from "lucide-react";

interface SignalToastProps {
  urgency: "urgent" | "watch" | "note";
  title: string;
  message: string;
  onDismiss: () => void;
}

const urgencyStyles: Record<
  SignalToastProps["urgency"],
  { border: string; bg: string; title: string }
> = {
  urgent: {
    border: "border-l-red-400",
    bg: "bg-red-400/10",
    title: "text-red-400",
  },
  watch: {
    border: "border-l-amber-400",
    bg: "bg-amber-400/[0.08]",
    title: "text-amber-400",
  },
  note: {
    border: "border-l-slate-500",
    bg: "",
    title: "text-slate-400",
  },
};

export default function SignalToast({
  urgency,
  title,
  message,
  onDismiss,
}: SignalToastProps) {
  useEffect(() => {
    // Different dismiss times based on urgency and signal type
    const titleLower = title.toLowerCase();
    let dismissTime = 4000;
    
    if (urgency === "urgent") {
      dismissTime = 6000; // Contract drift, pressure tactics - keep longer
    } else if (titleLower.includes("circling") || titleLower.includes("stalling")) {
      dismissTime = 5000; // Momentum signals - medium duration
    } else if (urgency === "note") {
      dismissTime = 3000; // Notes dismiss faster
    }
    
    const id = setTimeout(onDismiss, dismissTime);
    return () => clearTimeout(id);
  }, [onDismiss, urgency, title]);

  const s = urgencyStyles[urgency];

  return (
    <div
      className={`relative animate-slide-in-right border-l-[3px] px-3 py-2.5 ${s.border} ${s.bg} rounded-xl border border-white/[0.07] bg-[#151C28] shadow-xl`}
    >
      <button
        onClick={onDismiss}
        className="absolute right-2 top-2 rounded p-0.5 text-slate-500 transition-colors hover:text-slate-300"
      >
        <X size={12} />
      </button>

      <p
        className={`text-xs font-bold uppercase tracking-wide ${s.title}`}
      >
        {title}
      </p>
      <p className="mt-0.5 text-sm text-slate-300">{message}</p>
    </div>
  );
}
