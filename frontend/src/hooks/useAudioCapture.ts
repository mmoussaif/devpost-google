import { useRef, useCallback, useState, type MutableRefObject } from "react";

function resampleTo16k(float32: Float32Array, inputRate: number): Float32Array {
  if (inputRate === 16000 || float32.length === 0) return float32;
  const outLength = Math.max(1, Math.round((float32.length * 16000) / inputRate));
  const out = new Float32Array(outLength);
  const lastIdx = float32.length - 1;
  for (let i = 0; i < outLength; i++) {
    const srcIdx = lastIdx > 0 ? (i * lastIdx) / (outLength - 1) : 0;
    const lo = Math.min(Math.floor(srcIdx), lastIdx);
    const hi = Math.min(lo + 1, lastIdx);
    const t = srcIdx - lo;
    out[i] = float32[lo] * (1 - t) + float32[hi] * t;
  }
  return out;
}

function float32ToBase64Int16(float32: Float32Array): string {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  const bytes = new Uint8Array(int16.buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

interface UseAudioCaptureOptions {
  onAudioChunk: (base64: string) => void;
  onBargeIn: () => void;
  isAdversarySpeakingRef: MutableRefObject<boolean>;
}

export function useAudioCapture({
  onAudioChunk,
  onBargeIn,
  isAdversarySpeakingRef,
}: UseAudioCaptureOptions) {
  const [isMuted, setIsMuted] = useState(true);
  const [micLevel, setMicLevel] = useState(0);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const wasSpeakingRef = useRef(false);
  const rafRef = useRef<number>(0);

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    streamRef.current = stream;

    const ctx = new AudioContext({ sampleRate: stream.getAudioTracks()[0].getSettings().sampleRate || 48000 });
    ctxRef.current = ctx;

    const source = ctx.createMediaStreamSource(stream);
    sourceRef.current = source;

    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    analyserRef.current = analyser;
    source.connect(analyser);

    const processor = ctx.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0);
      const resampled = resampleTo16k(input, ctx.sampleRate);
      const base64 = float32ToBase64Int16(resampled);
      onAudioChunk(base64);
    };

    source.connect(processor);
    processor.connect(ctx.destination);

    const timeDomain = new Uint8Array(analyser.fftSize);
    const tick = () => {
      analyser.getByteTimeDomainData(timeDomain);
      let sum = 0;
      for (let i = 0; i < timeDomain.length; i++) {
        const v = (timeDomain[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / timeDomain.length);
      const level = Math.min(100, Math.round(rms * 200));
      setMicLevel(level);

      const speaking = rms > 0.05;
      setIsSpeaking(speaking);

      if (speaking && !wasSpeakingRef.current && isAdversarySpeakingRef.current) {
        onBargeIn();
      }
      wasSpeakingRef.current = speaking;

      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);

    setIsMuted(false);
  }, [onAudioChunk, onBargeIn, isAdversarySpeakingRef]);

  const stop = useCallback(() => {
    cancelAnimationFrame(rafRef.current);

    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    analyserRef.current?.disconnect();
    processorRef.current = null;
    sourceRef.current = null;
    analyserRef.current = null;

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    ctxRef.current?.close();
    ctxRef.current = null;

    setIsMuted(true);
    setMicLevel(0);
    setIsSpeaking(false);
    wasSpeakingRef.current = false;
  }, []);

  return { start, stop, isMuted, micLevel, isSpeaking };
}
