import { useState } from "react";
import RoundSelector from "./components/RoundSelector";
import SessionView from "./components/SessionView";
import HistoryView from "./components/HistoryView";
import { api } from "./api";

export default function App() {
  const [view, setView] = useState("round-select"); // round-select | session | complete | history
  const [session, setSession] = useState(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);
  const [completion, setCompletion] = useState(null);

  async function handleStart(roundType) {
    setStarting(true);
    setStartError(null);
    try {
      const started = await api.startSession(roundType);
      setSession(started);
      setView("session");
    } catch (e) {
      setStartError(e.message);
    } finally {
      setStarting(false);
    }
  }

  function handleEnded(result) {
    setCompletion(result);
    setView("complete");
  }

  function handleStartOver() {
    setSession(null);
    setCompletion(null);
    setView("round-select");
  }

  return (
    <div className="app">
      {view !== "session" && (
        <button className="history-link" onClick={() => setView(view === "history" ? "round-select" : "history")}>
          {view === "history" ? "Close history" : "History"}
        </button>
      )}

      {view === "round-select" && (
        <RoundSelector onStart={handleStart} loading={starting} error={startError} />
      )}

      {view === "session" && session && <SessionView session={session} onEnded={handleEnded} />}

      {view === "complete" && (
        <div className="complete-screen">
          <h2>Session complete</h2>
          {completion?.graded ? (
            <>
              <p>Verdict: {completion.verdict}</p>
              <p className="muted">Report written to your Obsidian vault.</p>
            </>
          ) : (
            <p className="error">Grading failed: {completion?.error || "unknown error"}</p>
          )}
          <button onClick={handleStartOver}>Start another round</button>
        </div>
      )}

      {view === "history" && <HistoryView onBack={handleStartOver} />}
    </div>
  );
}
