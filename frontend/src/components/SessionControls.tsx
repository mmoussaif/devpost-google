import { Mic, MicOff, Monitor, Video, VideoOff, PhoneOff } from "lucide-react";

interface SessionControlsProps {
  timer: string;
  isMicOn: boolean;
  isScreenSharing: boolean;
  isCameraOn: boolean;
  screenCaptureFlash?: boolean;
  onMicToggle: () => void;
  onScreenToggle: () => void;
  onCameraToggle: () => void;
  onEnd: () => void;
}

const btn =
  "inline-flex items-center gap-1.5 rounded-lg border border-white/[0.07] bg-[#1C2536] px-3 py-2 text-sm font-medium transition-all hover:border-white/15";

const active = "border-indigo-400/30 bg-indigo-500/15 text-indigo-400";

export default function SessionControls({
  timer,
  isMicOn,
  isScreenSharing,
  isCameraOn,
  screenCaptureFlash,
  onMicToggle,
  onScreenToggle,
  onCameraToggle,
  onEnd,
}: SessionControlsProps) {
  return (
    <div className="flex items-center justify-between border-b border-white/[0.07] bg-[#151C28] px-4 py-2.5">
      <div className="flex items-center gap-3">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-400/10 px-2.5 py-1 text-xs font-medium text-emerald-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          Live Practice
        </span>
        <span className={`font-mono text-sm ${timer <= "01:00" ? "text-red-400 animate-pulse" : "text-slate-500"}`}>{timer}</span>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onMicToggle}
          className={`${btn} ${isMicOn ? active : "text-slate-500 opacity-70"}`}
        >
          {isMicOn ? <Mic size={16} /> : <MicOff size={16} />}
        </button>

        <button
          onClick={onCameraToggle}
          className={`${btn} ${isCameraOn ? active : "text-slate-400"}`}
        >
          {isCameraOn ? <Video size={16} /> : <VideoOff size={16} />}
        </button>

        <button
          onClick={onScreenToggle}
          className={`${btn} relative ${isScreenSharing ? active : "text-slate-400"} ${screenCaptureFlash ? "ring-2 ring-green-400/50" : ""}`}
        >
          <Monitor size={16} />
          {screenCaptureFlash && (
            <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-green-400 animate-ping" />
          )}
        </button>

        <button
          onClick={onEnd}
          className={`${btn} border-red-400/30 text-red-400`}
        >
          <PhoneOff size={16} />
          End
        </button>
      </div>
    </div>
  );
}
