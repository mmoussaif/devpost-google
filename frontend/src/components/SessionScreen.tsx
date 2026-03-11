import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CoachRecommendation,
  SessionConfig,
  Signal,
  TranscriptEntry,
  TurnState,
  SessionRecording,
  ScreenAnalysisStatus,
  ExtractedTerms,
} from "../types";
import { useSession } from "../hooks/useSession";
import { useAudioCapture } from "../hooks/useAudioCapture";
import { useAudioPlayback } from "../hooks/useAudioPlayback";
import { useScreenShare } from "../hooks/useScreenShare";
import { useCamera } from "../hooks/useCamera";
import type { PresenceMetrics } from "../hooks/usePresenceDetection";
import SessionControls from "./SessionControls";
import ChatMessage from "./ChatMessage";
import WebcamPip from "./WebcamPip";
import CoachCard from "./CoachCard";
import SignalToast from "./SignalToast";
import DocumentAnalysis from "./DocumentAnalysis";

interface SessionScreenProps {
  config: SessionConfig;
  onSessionEnd: (recording: SessionRecording) => void;
}

function formatElapsed(start: number): string {
  const s = Math.floor((Date.now() - start) / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export default function SessionScreen({ config, onSessionEnd }: SessionScreenProps) {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [coach, setCoach] = useState<CoachRecommendation | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [turn, setTurn] = useState<TurnState>("waiting");
  const [timer, setTimer] = useState("00:00");
  const [phase, setPhase] = useState<"ready" | "live" | "ended">("ready");
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  const startTimeRef = useRef(Date.now());
  const chatEndRef = useRef<HTMLDivElement>(null);
  const isAdversarySpeakingRef = useRef(false);
  const recordingRef = useRef<SessionRecording>({
    startTime: null,
    exchanges: [],
    tacticsDetected: [],
    coachingGiven: [],
    metrics: {
      totalTurns: 0,
      userTurns: 0,
      userAudioChunks: 0,
      stallingInstances: 0,
      progressInstances: 0,
      circlingInstances: 0,
      dealClosed: false,
    },
  });

  const lastAdversaryTextRef = useRef("");
  const lastUserTextRef = useRef("");
  const cameraActiveRef = useRef(false);
  
  // Accumulate presence metrics for averaging
  const presenceMetricsRef = useRef<{
    eyeContact: number[];
    posture: number[];
    tension: number[];
  }>({ eyeContact: [], posture: [], tension: [] });

  const { bufferChunk, playBuffered, clearAudio, isPlaying } = useAudioPlayback();
  isAdversarySpeakingRef.current = isPlaying;

  const lastMessageTimeRef = useRef<number>(0);
  
    const isDuplicate = (text: string, lastRef: React.MutableRefObject<string>) => {
    const normalized = text.replace(/\s*[—–-]\s*\[interrupted\]\s*$/i, "").trim();
    const last = lastRef.current;
    const now = Date.now();
    const timeSinceLast = now - lastMessageTimeRef.current;
    
    // Exact match within 3 seconds = duplicate (catches "0.7%" repeated)
    if (last === normalized && timeSinceLast < 3000) {
      return true;
    }
    
    // For longer texts, check substring containment
    if (last && normalized.length > 5 && (last === normalized || normalized.includes(last) || last.includes(normalized))) {
      return true;
    }
    
    lastRef.current = normalized;
    lastMessageTimeRef.current = now;
    return false;
  };

  const handleTranscript = useCallback((entry: TranscriptEntry) => {
    // Filter out system/instruction messages that leak into transcript
    const text = entry.text.trim();
    if (text.startsWith("[") && text.endsWith("]")) return;
    if (text.startsWith("—") && text.includes("INTERRUPT")) return;
    if (text.toUpperCase().includes("(USER INTERRUPT")) return;
    if (text.toUpperCase().includes("USER INTERRUPTS")) return;
    if (text.toLowerCase().includes("acknowledging the interruption")) return;
    if (text.toLowerCase().includes("no verbal input")) return;
    if (text.toLowerCase().includes("proceeding with")) return;
    if (text.toLowerCase().includes("silent context")) return;
    if (text.toLowerCase().includes("system:")) return;
    if (text.toLowerCase().includes("critical instruction")) return;

    if (entry.speaker === "adversary") {
      if (isDuplicate(entry.text, lastAdversaryTextRef)) return;
      recordingRef.current.metrics.totalTurns++;
      playBuffered();
    } else {
      if (isDuplicate(entry.text, lastUserTextRef)) return;
      recordingRef.current.metrics.userTurns++;
    }
    setTranscript((prev) => [...prev, entry]);
    recordingRef.current.exchanges.push({
      speaker: entry.speaker,
      text: entry.text,
      timestamp: entry.timestamp,
    });

    // Detect deal closure from closing language
    const lower = entry.text.toLowerCase();
    const closingPhrases = [
      "let's do it", "sounds like a deal", "we have a deal", "deal",
      "send the contract", "draw up the paperwork", "get the paperwork",
      "send over the contract", "finalize", "let's make it happen",
      "pleasure doing business", "looking forward to working",
      "let's get started", "excited to get started",
      "proceed with", "we'll proceed", "let's proceed",
      "that works", "that could work", "sounds good",
      "agreed", "we accept", "we'll take it",
      "we can do that", "can do that", "i can do that",
      "move that forward", "move forward",
      "good bye", "goodbye", "talk soon", "talk later",
    ];
    if (closingPhrases.some((p) => lower.includes(p))) {
      recordingRef.current.metrics.dealClosed = true;
    }
  }, [playBuffered]);

  const handleCoach = useCallback((rec: CoachRecommendation) => {
    // Filter out internal placeholders and system messages
    const phrase = rec.phrase?.trim() || "";
    if (!phrase || phrase === "[phrase]" || phrase === "(phrase)") return;
    if (phrase.toUpperCase().includes("USER INTERRUPT")) return;
    if (phrase.toUpperCase().includes("(USER INTERRUPT")) return;
    if (phrase.startsWith("[") && phrase.endsWith("]")) return;
    if (phrase.toLowerCase().includes("silent context")) return;
    if (phrase.toLowerCase().includes("system:")) return;
    
    setCoach(rec);
    recordingRef.current.coachingGiven.push({
      phrase: rec.phrase,
      context: rec.context,
      timestamp: rec.timestamp,
    });
  }, []);

  const lastSignalTypeRef = useRef<string>("");
  const lastSignalTimeRef = useRef<number>(0);
  
  const handleSignal = useCallback((signal: Signal) => {
    if (signal.signalType === "presence" && !cameraActiveRef.current) return;
    
    // Prevent duplicate signal types within 30 seconds
    const now = Date.now();
    const signalKey = signal.signalType + "_" + signal.title;
    if (signalKey === lastSignalTypeRef.current && now - lastSignalTimeRef.current < 30000) {
      return; // Skip duplicate
    }
    lastSignalTypeRef.current = signalKey;
    lastSignalTimeRef.current = now;
    
    // If progress signal comes in, clear any existing circling/stalling signals
    const titleLower = (signal.title || "").toLowerCase();
    if (titleLower.includes("progress")) {
      setSignals(prev => prev.filter(s => 
        !s.title?.toLowerCase().includes("circling") && 
        !s.title?.toLowerCase().includes("stalling")
      ));
    }
    
    setSignals((prev) => [signal, ...prev]);
    if (signal.title) {
      recordingRef.current.tacticsDetected.push({
        name: signal.title.toUpperCase(),
        desc: signal.message,
        timestamp: signal.timestamp,
      });

      // Track momentum metrics for scoring
      if (titleLower.includes("stalling")) {
        recordingRef.current.metrics.stallingInstances++;
      } else if (titleLower.includes("circling")) {
        recordingRef.current.metrics.circlingInstances++;
      } else if (titleLower.includes("progress")) {
        recordingRef.current.metrics.progressInstances++;
      }
    }
  }, []);

  const handleTurnChange = useCallback((t: TurnState) => {
    setTurn(t);
  }, []);

  const handleSessionEnd = useCallback((_reason: string) => {
    setPhase("ended");
    setTimeout(() => {
      onSessionEnd(recordingRef.current);
    }, 800);
  }, [onSessionEnd]);

  const handleError = useCallback((msg: string) => {
    setError(msg);
  }, []);

  const handleWarning = useCallback((msg: string) => {
    setWarning(msg);
    setTimeout(() => setWarning(null), 10000);
  }, []);

  const [screenCaptureFlash, setScreenCaptureFlash] = useState(false);
  const handleScreenCaptured = useCallback(() => {
    setScreenCaptureFlash(true);
    setTimeout(() => setScreenCaptureFlash(false), 500);
  }, []);

  const [screenAnalysis, setScreenAnalysis] = useState<{
    status: ScreenAnalysisStatus;
    terms?: ExtractedTerms;
    isShared: boolean;
  }>({ status: null, isShared: false });

  const handleScreenAnalysis = useCallback((result: {
    status: ScreenAnalysisStatus;
    terms?: ExtractedTerms;
    error?: string;
  }) => {
    setScreenAnalysis(prev => ({
      status: result.status,
      terms: result.terms ? { ...prev.terms, ...result.terms } : prev.terms,
      isShared: prev.isShared,
    }));
  }, []);

  const handleContractShared = useCallback((success: boolean) => {
    if (success) {
      setScreenAnalysis(prev => ({ ...prev, isShared: true }));
    }
  }, []);

  const handleDealClosed = useCallback((detectedBy: string) => {
    console.log(`Deal closure detected by: ${detectedBy}`);
    recordingRef.current.metrics.dealClosed = true;
  }, []);

  const session = useSession({
    onTranscript: handleTranscript,
    onCoachUpdate: handleCoach,
    onSignal: handleSignal,
    onAudioChunk: bufferChunk,
    onAudioClear: clearAudio,
    onTurnChange: handleTurnChange,
    onSessionEnd: handleSessionEnd,
    onError: handleError,
    onWarning: handleWarning,
    onScreenCaptured: handleScreenCaptured,
    onScreenAnalysis: handleScreenAnalysis,
    onContractShared: handleContractShared,
    onDealClosed: handleDealClosed,
  });

  const handleBargeIn = useCallback(() => {
    clearAudio();
    session.send({ type: "client_barge_in" });
  }, [clearAudio, session]);

  const audio = useAudioCapture({
    onAudioChunk: useCallback(
      (b64: string) => session.send({ type: "audio", data: b64 }),
      [session]
    ),
    onBargeIn: handleBargeIn,
    isAdversarySpeakingRef,
  });

  const screenShare = useScreenShare();
  
  const lastMetricsSentRef = useRef<number>(0);
  const handlePresenceMetrics = useCallback(
    (metrics: PresenceMetrics) => {
      // Accumulate for averaging
      presenceMetricsRef.current.eyeContact.push(metrics.eye_contact);
      presenceMetricsRef.current.posture.push(metrics.posture);
      presenceMetricsRef.current.tension.push(metrics.tension);
      
      // Rate-limit sending to backend
      const now = Date.now();
      if (now - lastMetricsSentRef.current < 2000) return;
      lastMetricsSentRef.current = now;
      session.send({ type: "presence_metrics", data: metrics });
    },
    [session]
  );
  
  const camera = useCamera({
    onPresenceMetrics: handlePresenceMetrics,
    onError: handleError,
  });
  const camVideoRef = useRef<HTMLVideoElement | null>(null);

  // Create session on mount
  useEffect(() => {
    let cancelled = false;
    session.createSession(config).then((sid) => {
      if (!cancelled) {
        session.connect(sid);
      }
    }).catch(() => {
      setError("Failed to create session. Please try again.");
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Timer
  useEffect(() => {
    if (phase !== "live") return;
    startTimeRef.current = Date.now();
    recordingRef.current.startTime = Date.now();
    const id = setInterval(() => setTimer(formatElapsed(startTimeRef.current)), 1000);
    return () => clearInterval(id);
  }, [phase]);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  const beginNegotiation = () => {
    session.send({ type: "start" });
    session.send({ type: "mic_state", muted: true });
    setPhase("live");
    setTimeout(() => audio.start(), 500);
  };

  const handleMicToggle = () => {
    if (audio.isMuted) {
      audio.start();
      session.send({ type: "mic_state", muted: false });
    } else {
      audio.stop();
      session.send({ type: "mic_state", muted: true });
    }
  };

  const handleScreenToggle = () => {
    if (screenShare.isSharing) {
      screenShare.stop();
      // Keep the analysis panel visible if terms were shared
      if (!screenAnalysis.isShared) {
        setTimeout(() => setScreenAnalysis({ status: null, isShared: false }), 3000);
      }
    } else {
      screenShare.start((b64) => session.send({ type: "screen", data: b64 }));
    }
  };

  const handleStartScan = () => {
    screenShare.startScanning();
  };

  const handleStopScan = () => {
    screenShare.stopScanning();
  };

  const handleDocShare = () => {
    session.send({ type: "share_contract" });
  };

  const handleCameraToggle = async () => {
    if (camera.isOn) {
      camera.stop();
      cameraActiveRef.current = false;
      session.send({ type: "camera_state", active: false });
    } else if (camVideoRef.current) {
      await camera.start(camVideoRef.current);
      cameraActiveRef.current = true;
      recordingRef.current.cameraEnabled = true; // Track that camera was used
      session.send({ type: "camera_state", active: true });
    }
  };

  const handleEnd = () => {
    session.disconnect();
    audio.stop();
    screenShare.stopScanning();
    screenShare.stop();
    camera.stop();
    setPhase("ended");
    
    // Calculate presence averages if camera was used
    const pm = presenceMetricsRef.current;
    if (pm.eyeContact.length > 0) {
      const avg = (arr: number[]) => Math.round(arr.reduce((a, b) => a + b, 0) / arr.length);
      recordingRef.current.visualPresence = {
        avgEyeContact: avg(pm.eyeContact),
        avgPosture: avg(pm.posture),
        avgTension: avg(pm.tension),
      };
    }
    
    onSessionEnd(recordingRef.current);
  };

  const handleCopyCoach = () => {
    if (coach) {
      navigator.clipboard.writeText(coach.phrase);
    }
  };

  const dismissSignal = useCallback((id: string) => {
    setSignals((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const turnLabel =
    turn === "adversary"
      ? "They're speaking..."
      : turn === "user"
        ? audio.isMuted
          ? "Tap mic to speak"
          : "Your turn"
        : "Waiting...";

  const turnColor =
    turn === "adversary"
      ? "bg-red-400/10 text-red-400"
      : turn === "user"
        ? audio.isMuted
          ? "bg-amber-400/10 text-amber-400"
          : "bg-emerald-400/10 text-emerald-400"
        : "bg-slate-500/10 text-slate-500";

  return (
    <div className="flex h-dvh flex-col">
      <SessionControls
        timer={timer}
        isMicOn={!audio.isMuted}
        isScreenSharing={screenShare.isSharing}
        isCameraOn={camera.isOn}
        screenCaptureFlash={screenCaptureFlash}
        onMicToggle={handleMicToggle}
        onScreenToggle={handleScreenToggle}
        onCameraToggle={handleCameraToggle}
        onEnd={handleEnd}
      />

      {/* Start prompt */}
      {phase === "ready" && session.isConnected && (
        <div className="flex justify-center border-b border-white/[0.07] bg-[#151C28] px-4 py-3">
          <button
            onClick={beginNegotiation}
            className="rounded-xl bg-indigo-500 px-8 py-2.5 text-sm font-semibold text-white transition-all hover:bg-indigo-600 hover:shadow-lg hover:shadow-indigo-500/25"
          >
            Begin Negotiation
          </button>
        </div>
      )}

      {/* Warning banner */}
      {warning && (
        <div className="animate-slide-down bg-amber-500 px-4 py-2 text-center text-sm font-semibold text-black">
          {warning}
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="flex items-center justify-between bg-red-500/90 px-4 py-2 text-sm text-white">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-2 rounded px-2 py-0.5 text-xs hover:bg-white/20"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Turn indicator */}
      {phase === "live" && (
        <div className="flex justify-center py-2">
          <span
            className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide transition-all ${turnColor}`}
          >
            {turn === "adversary" && (
              <span className="flex gap-0.5">
                {[1, 2, 3].map((i) => (
                  <span
                    key={i}
                    className="h-2.5 w-0.5 animate-pulse rounded-full bg-current"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </span>
            )}
            {turnLabel}
          </span>
        </div>
      )}

      {/* Chat area */}
      <div className="chat-scroll flex-1 overflow-y-auto px-4 pb-36 pt-4">
        {transcript.length === 0 && (
          <p className="pt-16 text-center text-sm text-slate-600">
            {phase === "ready"
              ? "Press Begin Negotiation to start the conversation."
              : "The conversation will appear here..."}
          </p>
        )}
        <div className="mx-auto flex max-w-2xl flex-col gap-3">
          {transcript.map((entry) => (
            <ChatMessage
              key={entry.id}
              speaker={entry.speaker}
              text={entry.text}
            />
          ))}
          <div ref={chatEndRef} />
        </div>
      </div>

      {/* Signal toast — only the latest one */}
      {signals.length > 0 && (
        <div className="pointer-events-none fixed right-4 top-16 z-40 w-72">
          <div className="pointer-events-auto">
            <SignalToast
              key={signals[0].id}
              urgency={signals[0].urgency}
              title={signals[0].title}
              message={signals[0].message}
              onDismiss={() => dismissSignal(signals[0].id)}
            />
          </div>
        </div>
      )}

      {/* Document analysis panel */}
      <DocumentAnalysis
        isSharing={screenShare.isSharing}
        status={screenAnalysis.status}
        terms={screenAnalysis.terms}
        isShared={screenAnalysis.isShared}
        frameCount={screenShare.frameCount}
        onStartScan={handleStartScan}
        onStopScan={handleStopScan}
        onShare={handleDocShare}
      />

      {/* Webcam PiP */}
      <WebcamPip
        visible={camera.isOn}
        onVideoRef={useCallback((el: HTMLVideoElement) => { camVideoRef.current = el; }, [])}
        metrics={camera.latestMetrics}
        presenceReady={camera.presenceReady}
      />

      {/* Coach card */}
      <CoachCard
        phrase={coach?.phrase ?? "Waiting for the negotiation to begin..."}
        context={coach?.context ?? ""}
        onCopy={handleCopyCoach}
        visible={phase === "live"}
      />
    </div>
  );
}
