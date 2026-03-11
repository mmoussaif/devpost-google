import { useCallback, useRef, useState } from "react";
import type {
  SessionConfig,
  SessionResponse,
  ServerMessage,
  TranscriptEntry,
  CoachRecommendation,
  Signal,
  TurnState,
  ExtractedTerms,
  ScreenAnalysisStatus,
} from "../types";

interface ScreenAnalysisResult {
  status: ScreenAnalysisStatus;
  terms?: ExtractedTerms;
  error?: string;
}

interface SessionCallbacks {
  onTranscript: (entry: TranscriptEntry) => void;
  onCoachUpdate: (rec: CoachRecommendation) => void;
  onSignal: (signal: Signal) => void;
  onAudioChunk: (base64: string) => void;
  onAudioClear: () => void;
  onTurnChange: (turn: TurnState) => void;
  onSessionEnd: (reason: string) => void;
  onError: (message: string, code?: string) => void;
  onWarning: (message: string) => void;
  onScreenCaptured?: () => void;
  onScreenAnalysis?: (result: ScreenAnalysisResult) => void;
  onContractShared?: (success: boolean, error?: string) => void;
  onDealClosed?: (detectedBy: string) => void;
}

function formatTimestamp(startTime: number): string {
  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  const m = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const s = String(elapsed % 60).padStart(2, "0");
  return `${m}:${s}`;
}

export function useSession(callbacks: SessionCallbacks) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const startTimeRef = useRef<number>(Date.now());
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;

  const idCounter = useRef(0);
  const nextId = () => `${++idCounter.current}`;

  const handleMessage = useCallback((event: MessageEvent) => {
    const cb = callbacksRef.current;
    let msg: ServerMessage;
    try {
      msg = JSON.parse(event.data);
    } catch {
      return;
    }

    const ts = formatTimestamp(startTimeRef.current);

    switch (msg.type) {
      case "transcript.append":
        cb.onTranscript({
          id: nextId(),
          speaker: msg.speaker,
          text: msg.content,
          timestamp: ts,
        });
        break;

      case "coach.recommendation":
        cb.onCoachUpdate({
          phrase: msg.phrase,
          context: msg.context,
          timestamp: ts,
        });
        break;

      case "signal.alert":
        cb.onSignal({
          id: nextId(),
          urgency: (msg.urgency as Signal["urgency"]) || "note",
          title: msg.title,
          message: msg.message,
          signalType: msg.signal_type,
          timestamp: ts,
        });
        break;

      case "media.audio":
        cb.onAudioChunk(msg.data);
        break;

      case "audio.clear":
        cb.onAudioClear();
        break;

      case "session.state": {
        const map: Record<string, TurnState> = {
          counterpart_turn: "adversary",
          user_turn: "user",
        };
        cb.onTurnChange(map[msg.state] ?? "waiting");
        break;
      }

      case "session.complete":
        cb.onSessionEnd(msg.content);
        break;

      case "session.timeout":
        cb.onSessionEnd(msg.content);
        break;

      case "session.error":
        cb.onError(msg.content, msg.code);
        break;

      case "session.warning":
        cb.onWarning(msg.content);
        break;

      case "screen.captured":
        cb.onScreenCaptured?.();
        break;

      case "screen.analyzing":
        cb.onScreenAnalysis?.({
          status: msg.status,
          terms: msg.terms,
          error: msg.error,
        });
        break;

      case "screen.share_result":
        cb.onContractShared?.(msg.success, msg.error);
        break;

      case "session.info":
        // Info messages can be logged or shown briefly
        break;

      case "session.deal_closed":
        cb.onDealClosed?.(msg.detected_by);
        break;
    }
  }, []);

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      send({ type: "end" });
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, [send]);

  const connect = useCallback(
    (sid: string) => {
      if (wsRef.current) {
        wsRef.current.close();
      }

      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${proto}//${window.location.host}/ws/practice/${sid}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;
      startTimeRef.current = Date.now();

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = handleMessage;

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
      };

      ws.onerror = () => {
        callbacksRef.current.onError("WebSocket connection failed");
      };
    },
    [handleMessage],
  );

  const createSession = useCallback(
    async (config: SessionConfig): Promise<string> => {
      const res = await fetch("/session/practice", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (!res.ok) {
        throw new Error(`Session creation failed: ${res.status}`);
      }
      const data: SessionResponse = await res.json();
      setSessionId(data.session_id);
      return data.session_id;
    },
    [],
  );

  return { sessionId, isConnected, send, createSession, connect, disconnect };
}
