export interface SessionConfig {
  goals: string;
  batna: string;
  scenario: string;
  low_cost_mode: boolean;
}

export interface SessionResponse {
  session_id: string;
  status: string;
}

export type Screen = "landing" | "session" | "recap";

export type TurnState = "waiting" | "adversary" | "user";

export interface TranscriptEntry {
  id: string;
  speaker: "adversary" | "user";
  text: string;
  timestamp: string;
}

export interface CoachRecommendation {
  phrase: string;
  context: string;
  timestamp: string;
}

export interface Signal {
  id: string;
  urgency: "urgent" | "watch" | "note";
  title: string;
  message: string;
  signalType: string;
  timestamp: string;
}

export interface SessionRecording {
  startTime: number | null;
  exchanges: { speaker: string; text: string; timestamp: string }[];
  tacticsDetected: { name: string; desc: string; timestamp: string }[];
  coachingGiven: { phrase: string; context: string; timestamp: string }[];
  metrics: {
    totalTurns: number;
    userTurns: number;
    userAudioChunks: number;
    stallingInstances: number;
    progressInstances: number;
    circlingInstances: number;
    dealClosed: boolean;
  };
  cameraEnabled?: boolean;
  visualPresence?: {
    avgEyeContact: number;
    avgPosture: number;
    avgTension: number;
  };
  emotions?: { emotion: string; timestamp: string; confidence: number }[];
}

export interface RecapData {
  score: number;
  duration: string;
  user_participation: number;
  buddy_turns: number;
  pressure_signals: number;
  outcome: string;
  best_intervention: string;
  biggest_risk: string;
  next_focus: string;
  strengths: string[];
  moments: { phrase?: string; context?: string; timestamp?: string }[];
  visual_summary?: {
    avgEyeContact: number;
    avgPosture: number;
    avgTension: number;
    dominantEmotion: string;
    totalSamples: number;
  };
}

export type ScreenAnalysisStatus = "capturing" | "analyzing" | "complete" | null;

export interface ExtractedTerms {
  price?: string | null;
  timeline?: string | null;
  payment_terms?: string | null;
  scope?: string | null;
  revisions?: string | null;
  parties?: string | null;
  summary?: string | null;
}

export type ServerMessage =
  | { type: "session.state"; state: string }
  | { type: "transcript.append"; speaker: "adversary" | "user"; content: string; timestamp?: number }
  | { type: "coach.recommendation"; phrase: string; context: string }
  | { type: "signal.alert"; urgency: string; title: string; message: string; signal_type: string; timestamp?: number }
  | { type: "media.audio"; data: string; mime_type: string }
  | { type: "audio.clear" }
  | { type: "session.warning"; content: string }
  | { type: "session.timeout"; content: string }
  | { type: "session.complete"; content: string }
  | { type: "session.error"; content: string; code?: string }
  | { type: "screen.captured"; size: number }
  | { type: "screen.analyzing"; status: ScreenAnalysisStatus; terms?: ExtractedTerms; error?: string; shared?: boolean }
  | { type: "screen.share_result"; success: boolean; terms?: ExtractedTerms; error?: string; already_shared?: boolean }
  | { type: "session.info"; content: string }
  | { type: "session.deal_closed"; detected_by: string; context?: string };
