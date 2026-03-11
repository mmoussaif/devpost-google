import { useCallback, useRef, useState, useEffect } from "react";
import { usePresenceDetection } from "./usePresenceDetection";
import type { PresenceMetrics } from "./usePresenceDetection";

interface UseCameraOptions {
  onPresenceMetrics?: (metrics: PresenceMetrics) => void;
  onError?: (message: string) => void;
}

export function useCamera(options: UseCameraOptions = {}) {
  const [isOn, setIsOn] = useState(false);
  const [latestMetrics, setLatestMetrics] = useState<PresenceMetrics | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const onPresenceMetricsRef = useRef(options.onPresenceMetrics);
  const onErrorRef = useRef(options.onError);
  
  // Keep the callback refs updated
  useEffect(() => {
    onPresenceMetricsRef.current = options.onPresenceMetrics;
    onErrorRef.current = options.onError;
  }, [options.onPresenceMetrics, options.onError]);

  const handleMetrics = useCallback((metrics: PresenceMetrics) => {
    setLatestMetrics(metrics);
    onPresenceMetricsRef.current?.(metrics);
  }, []);

  const presence = usePresenceDetection({
    onMetrics: handleMetrics,
    fps: 5,
  });

  // Store presence methods in refs to avoid dependency issues
  const presenceStartRef = useRef(presence.start);
  const presenceStopRef = useRef(presence.stop);
  const presenceIsReadyRef = useRef(presence.isReady);
  
  useEffect(() => {
    presenceStartRef.current = presence.start;
    presenceStopRef.current = presence.stop;
    presenceIsReadyRef.current = presence.isReady;
  }, [presence.start, presence.stop, presence.isReady]);

  // Auto-start presence detection when ready and camera is on
  useEffect(() => {
    if (isOn && presence.isReady && videoRef.current && !presence.isRunning) {
      presence.start(videoRef.current);
    }
  }, [isOn, presence.isReady, presence.isRunning, presence.start]);

  const start = useCallback(async (videoEl: HTMLVideoElement) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: "user" },
      });
      streamRef.current = stream;
      videoRef.current = videoEl;
      videoEl.srcObject = stream;
      await videoEl.play();
      setIsOn(true);
    } catch (err) {
      console.error("[Camera] Failed to start:", err);
      if (err instanceof Error) {
        if (err.name === "NotAllowedError") {
          onErrorRef.current?.("Camera access denied. Please allow camera permission in your browser settings.");
        } else if (err.name === "NotFoundError") {
          onErrorRef.current?.("No camera found. Please connect a camera and try again.");
        } else {
          onErrorRef.current?.(`Camera error: ${err.message}`);
        }
      }
    }
  }, []);

  const stop = useCallback(() => {
    presenceStopRef.current();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
      videoRef.current = null;
    }
    setLatestMetrics(null);
    setIsOn(false);
  }, []);

  return {
    start,
    stop,
    isOn,
    presenceReady: presence.isReady,
    presenceRunning: presence.isRunning,
    latestMetrics,
  };
}
