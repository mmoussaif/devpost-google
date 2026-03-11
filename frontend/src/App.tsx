import { useCallback, useState } from "react";
import type { Screen, SessionConfig, SessionRecording } from "./types";
import LandingScreen from "./components/LandingScreen";
import SessionScreen from "./components/SessionScreen";
import RecapOverlay from "./components/RecapOverlay";

export default function App() {
  const [screen, setScreen] = useState<Screen>("landing");
  const [config, setConfig] = useState<SessionConfig | null>(null);
  const [recording, setRecording] = useState<SessionRecording | null>(null);
  const [loading, setLoading] = useState(false);

  const handleStart = useCallback((cfg: SessionConfig) => {
    setConfig(cfg);
    setLoading(true);
    setScreen("session");
    setLoading(false);
  }, []);

  const handleSessionEnd = useCallback((rec: SessionRecording) => {
    setRecording(rec);
    if (rec.metrics.totalTurns > 0) {
      setScreen("recap");
    } else {
      setScreen("landing");
    }
  }, []);

  const handleRestart = useCallback(() => {
    setScreen("landing");
    setConfig(null);
    setRecording(null);
  }, []);

  return (
    <>
      {screen === "landing" && (
        <LandingScreen onStart={handleStart} loading={loading} />
      )}
      {screen === "session" && config && (
        <SessionScreen config={config} onSessionEnd={handleSessionEnd} />
      )}
      {screen === "recap" && recording && (
        <RecapOverlay recording={recording} onRestart={handleRestart} />
      )}
    </>
  );
}
