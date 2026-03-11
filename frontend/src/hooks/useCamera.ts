import { useCallback, useRef, useState } from "react";

export function useCamera() {
  const [isOn, setIsOn] = useState(false);
  const streamRef = useRef<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const start = useCallback(async (videoEl: HTMLVideoElement) => {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 320, height: 240, facingMode: "user" },
    });
    streamRef.current = stream;
    videoRef.current = videoEl;
    videoEl.srcObject = stream;
    await videoEl.play();
    setIsOn(true);
  }, []);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
      videoRef.current = null;
    }
    setIsOn(false);
  }, []);

  return { start, stop, isOn };
}
