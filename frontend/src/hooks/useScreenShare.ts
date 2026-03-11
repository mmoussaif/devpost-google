import { useCallback, useRef, useState } from "react";

const SCAN_INTERVAL_MS = 3000; // Capture every 3 seconds during scanning
const JPEG_QUALITY = 0.7;
const MIN_BASE64_LENGTH = 2000;

export function useScreenShare() {
  const [isSharing, setIsSharing] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [frameCount, setFrameCount] = useState(0);
  const streamRef = useRef<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const sendFrameRef = useRef<((base64: string) => void) | null>(null);
  const scanIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastHashRef = useRef<string>("");

  const captureFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !streamRef.current || !sendFrameRef.current) return false;
    
    const v = videoRef.current;
    const c = canvasRef.current;
    if (v.readyState < 2) return false;
    
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    const ctx = c.getContext("2d");
    if (!ctx) return false;
    ctx.drawImage(v, 0, 0);
    const dataUrl = c.toDataURL("image/jpeg", JPEG_QUALITY);
    const base64 = dataUrl.split(",")[1];
    
    if (base64 && base64.length > MIN_BASE64_LENGTH) {
      // Simple change detection - only send if frame changed
      const hash = base64.slice(0, 100) + base64.slice(-100);
      if (hash !== lastHashRef.current) {
        lastHashRef.current = hash;
        sendFrameRef.current(base64);
        setFrameCount(c => c + 1);
        return true;
      }
    }
    return false;
  }, []);

  const startScanning = useCallback(() => {
    if (scanIntervalRef.current) return;
    setIsScanning(true);
    setFrameCount(0);
    lastHashRef.current = "";
    // Capture immediately, then at intervals
    captureFrame();
    scanIntervalRef.current = setInterval(captureFrame, SCAN_INTERVAL_MS);
  }, [captureFrame]);

  const stopScanning = useCallback(() => {
    if (scanIntervalRef.current) {
      clearInterval(scanIntervalRef.current);
      scanIntervalRef.current = null;
    }
    setIsScanning(false);
  }, []);

  const stop = useCallback(() => {
    stopScanning();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    const video = videoRef.current;
    if (video) {
      video.srcObject = null;
      video.remove();
      videoRef.current = null;
    }
    const canvas = canvasRef.current;
    if (canvas) {
      canvas.remove();
      canvasRef.current = null;
    }
    sendFrameRef.current = null;
    setIsSharing(false);
    setFrameCount(0);
  }, [stopScanning]);

  const start = useCallback(async (sendFrame: (base64: string) => void) => {
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: {
        cursor: "never",
        width: { ideal: 1920 },
        height: { ideal: 1080 },
      } as MediaTrackConstraints,
    });
    streamRef.current = stream;
    sendFrameRef.current = sendFrame;

    const video = document.createElement("video");
    video.autoplay = true;
    video.muted = true;
    video.playsInline = true;
    video.style.display = "none";
    video.srcObject = stream;
    document.body.appendChild(video);
    videoRef.current = video;

    const canvas = document.createElement("canvas");
    canvasRef.current = canvas;

    const onEnded = () => stop();
    stream.getVideoTracks()[0]?.addEventListener("ended", onEnded);

    await video.play();
    setIsSharing(true);
  }, [stop]);

  return { start, stop, startScanning, stopScanning, isSharing, isScanning, frameCount };
}
