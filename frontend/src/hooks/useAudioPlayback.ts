import { useRef, useCallback, useState } from "react";

function base64ToFloat32(base64: string): Float32Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  const int16 = new Int16Array(bytes.buffer);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / 32768;
  }
  return float32;
}

export function useAudioPlayback() {
  const [isPlaying, setIsPlaying] = useState(false);

  const ctxRef = useRef<AudioContext | null>(null);
  const queueRef = useRef<Float32Array[]>([]);
  const isProcessingRef = useRef(false);
  const nextPlayTimeRef = useRef(0);
  const activeSourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());

  const getContext = useCallback(() => {
    if (!ctxRef.current || ctxRef.current.state === "closed") {
      ctxRef.current = new AudioContext({ sampleRate: 24000 });
    }
    return ctxRef.current;
  }, []);

  const processQueue = useCallback(() => {
    if (isProcessingRef.current) return;
    isProcessingRef.current = true;

    const ctx = getContext();

    while (queueRef.current.length > 0) {
      const samples = queueRef.current.shift()!;
      if (samples.length === 0) continue;

      const audioBuffer = ctx.createBuffer(1, samples.length, 24000);
      audioBuffer.getChannelData(0).set(samples);

      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);

      activeSourcesRef.current.add(source);
      source.onended = () => {
        activeSourcesRef.current.delete(source);
        if (activeSourcesRef.current.size === 0 && queueRef.current.length === 0) {
          setIsPlaying(false);
        }
      };

      const now = ctx.currentTime;
      const startTime = Math.max(now, nextPlayTimeRef.current);
      source.start(startTime);
      nextPlayTimeRef.current = startTime + audioBuffer.duration;
    }

    isProcessingRef.current = false;
  }, [getContext]);

  const bufferChunk = useCallback((base64: string) => {
    const samples = base64ToFloat32(base64);
    if (samples.length === 0) return;

    queueRef.current.push(samples);
    setIsPlaying(true);
    processQueue();
  }, [processQueue]);

  const playBuffered = useCallback(() => {
    // No-op now - audio plays immediately as chunks arrive
    // Kept for API compatibility
  }, []);

  const clearAudio = useCallback(() => {
    queueRef.current = [];
    for (const source of activeSourcesRef.current) {
      try {
        source.onended = null;
        source.stop();
      } catch {
        // Source may have already ended
      }
    }
    activeSourcesRef.current.clear();
    nextPlayTimeRef.current = 0;
    setIsPlaying(false);
  }, []);

  return { bufferChunk, playBuffered, clearAudio, isPlaying };
}
