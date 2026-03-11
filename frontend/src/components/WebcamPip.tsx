import { useRef, useEffect } from "react";
import { Eye, User, Activity } from "lucide-react";
import type { PresenceMetrics } from "../hooks/usePresenceDetection";

interface WebcamPipProps {
  visible: boolean;
  onVideoRef: (el: HTMLVideoElement) => void;
  metrics?: PresenceMetrics | null;
  presenceReady?: boolean;
}

function MetricBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="h-1 w-full rounded-full bg-white/20">
      <div
        className={`h-full rounded-full transition-all duration-300 ${color}`}
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

function getColor(value: number, invert = false): string {
  const v = invert ? 100 - value : value;
  if (v >= 70) return "bg-emerald-400";
  if (v >= 40) return "bg-amber-400";
  return "bg-red-400";
}

export default function WebcamPip({
  visible,
  onVideoRef,
  metrics,
  presenceReady,
}: WebcamPipProps) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (ref.current) onVideoRef(ref.current);
  }, [onVideoRef]);

  return (
    <div
      className={`fixed bottom-44 right-4 z-30 w-44 overflow-hidden rounded-xl border-2 border-white/10 shadow-xl transition-opacity duration-300 ${
        visible ? "opacity-100" : "pointer-events-none opacity-0"
      }`}
      style={{ visibility: visible ? "visible" : "hidden" }}
    >
      <video
        ref={ref}
        autoPlay
        muted
        playsInline
        className="block w-full -scale-x-100"
      />

      {/* Presence metrics overlay */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/70 to-transparent px-2 pb-1.5 pt-4">
        {metrics && presenceReady ? (
          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <Eye className="h-3 w-3 text-white/60" />
              <MetricBar value={metrics.eye_contact} color={getColor(metrics.eye_contact)} />
              <span className="w-6 text-right text-[9px] text-white/70">{metrics.eye_contact}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <User className="h-3 w-3 text-white/60" />
              <MetricBar value={metrics.posture} color={getColor(metrics.posture)} />
              <span className="w-6 text-right text-[9px] text-white/70">{metrics.posture}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Activity className="h-3 w-3 text-white/60" />
              <MetricBar value={100 - metrics.tension} color={getColor(metrics.tension, true)} />
              <span className="w-6 text-right text-[9px] text-white/70">{100 - metrics.tension}</span>
            </div>
          </div>
        ) : (
          <div className="text-center text-[10px] text-white/50">
            {presenceReady === false ? "Loading AI..." : "Self-view"}
          </div>
        )}
      </div>
    </div>
  );
}
