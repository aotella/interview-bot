import { useEffect, useRef, useState } from "react";
import { api } from "../api";

function formatElapsed(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function SessionView({ session, onEnded }) {
  const [answerText, setAnswerText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [lastDecision, setLastDecision] = useState(null); // { action, text }
  const [lastCheckpointId, setLastCheckpointId] = useState(null);
  const [paused, setPaused] = useState(false);
  const [pausePending, setPausePending] = useState(false);
  const [diagramMsg, setDiagramMsg] = useState(null);
  const [ending, setEnding] = useState(false);

  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const startedAtRef = useRef(Date.now());

  useEffect(() => {
    if (paused) return;
    const interval = setInterval(() => {
      setElapsedSeconds((s) => s + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [paused]);

  async function handleSaveCheckpoint() {
    if (!answerText.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      const result = await api.saveCheckpoint(session.session_id, answerText, "typed");
      setLastCheckpointId(result.checkpoint_id);
      setLastDecision(result.action === "continue" ? null : result);
      setAnswerText("");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleTogglePause() {
    setPausePending(true);
    setError(null);
    try {
      if (paused) {
        await api.resume(session.session_id);
        setPaused(false);
      } else {
        await api.pause(session.session_id);
        setPaused(true);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setPausePending(false);
    }
  }

  async function handleAttachDiagram() {
    setError(null);
    try {
      await api.attachDiagram(session.session_id, lastCheckpointId || "cp_0");
      setDiagramMsg("Diagram attached.");
      setTimeout(() => setDiagramMsg(null), 4000);
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleEnd() {
    setEnding(true);
    setError(null);
    try {
      const result = await api.endSession(session.session_id);
      onEnded(result);
    } catch (e) {
      setError(e.message);
      setEnding(false);
    }
  }

  return (
    <div className="session-view">
      <div className="elapsed-time">{formatElapsed(elapsedSeconds)}</div>

      <div className="question-panel">{session.question}</div>

      <textarea
        className="answer-input"
        value={answerText}
        onChange={(e) => setAnswerText(e.target.value)}
        placeholder="Type or dictate your answer..."
        disabled={paused || saving || ending}
      />

      {lastDecision && (
        <div className={`inline-panel inline-panel--${lastDecision.action}`}>
          <strong>{lastDecision.action === "interject" ? "Interjection" : "Follow-up"}:</strong>{" "}
          {lastDecision.text}
        </div>
      )}

      <div className="session-controls">
        <button onClick={handleSaveCheckpoint} disabled={saving || paused || ending || !answerText.trim()}>
          {saving ? "Saving..." : "Save Checkpoint"}
        </button>
        <button onClick={handleTogglePause} disabled={pausePending || ending}>
          {paused ? "Resume" : "Pause"}
        </button>
        <button onClick={handleAttachDiagram} disabled={ending}>
          Attach latest diagram
        </button>
        <button onClick={handleEnd} disabled={ending} className="end-button">
          {ending ? "Ending..." : "End Session"}
        </button>
      </div>

      {paused && <p className="muted">Paused</p>}
      {diagramMsg && <p className="muted">{diagramMsg}</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
