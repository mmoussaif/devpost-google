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

  const bufferRef = useRef<string[]>([]);
  const ctxRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);

  const bufferChunk = useCallback((base64: string) => {
    bufferRef.current.push(base64);
  }, []);

  const playBuffered = useCallback(() => {
    const chunks = bufferRef.current;
    if (chunks.length === 0) return;

    const decoded = chunks.map(base64ToFloat32);
    let totalLength = 0;
    for (const d of decoded) totalLength += d.length;
    if (totalLength === 0) return;

    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const d of decoded) {
      merged.set(d, offset);
      offset += d.length;
    }

    bufferRef.current = [];

    if (!ctxRef.current || ctxRef.current.state === "closed") {
      ctxRef.current = new AudioContext({ sampleRate: 24000 });
    }
    const ctx = ctxRef.current;

    const audioBuffer = ctx.createBuffer(1, merged.length, 24000);
    audioBuffer.getChannelData(0).set(merged);

    sourceRef.current?.stop();
    const source = ctx.createBufferSource();
    sourceRef.current = source;
    source.buffer = audioBuffer;
    source.connect(ctx.destination);

    setIsPlaying(true);
    source.onended = () => {
      setIsPlaying(false);
      sourceRef.current = null;
    };
    source.start();
  }, []);

  const clearAudio = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.onended = null;
      sourceRef.current.stop();
      sourceRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  return { bufferChunk, playBuffered, clearAudio, isPlaying };
}
