import { useRef, useEffect } from "react";

interface WebcamPipProps {
  visible: boolean;
  onVideoRef: (el: HTMLVideoElement) => void;
}

export default function WebcamPip({ visible, onVideoRef }: WebcamPipProps) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (ref.current) onVideoRef(ref.current);
  }, [onVideoRef]);

  if (!visible) return null;

  return (
    <div className="fixed bottom-44 right-4 z-30 w-40 overflow-hidden rounded-xl border-2 border-white/10 shadow-xl">
      <video
        ref={ref}
        autoPlay
        muted
        playsInline
        className="block w-full -scale-x-100"
      />
      <div className="absolute bottom-0 left-0 right-0 bg-black/60 px-2 py-1 text-center text-[10px] text-white/70">
        Self-view
      </div>
    </div>
  );
}
