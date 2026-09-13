import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { roundLabel } from "../format";

function formatElapsed(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function SessionView({ session, onEnded }) {
  const [turns, setTurns] = useState([]); // [{ speaker: "candidate"|"interviewer", action, text }]
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [answerText, setAnswerText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [lastCheckpointId, setLastCheckpointId] = useState(null);
  const [paused, setPaused] = useState(false);
  const [pausePending, setPausePending] = useState(false);
  const [diagramMsg, setDiagramMsg] = useState(null);
  const [ending, setEnding] = useState(false);

  const [elapsedSeconds, setElapsedSeconds] = useState(session.elapsed_seconds || 0);
  const scrollRef = useRef(null);

  useEffect(() => {
    api
      .getTranscript(session.session_id)
      .then((t) => setTurns(t.turns))
      .catch((e) => setError(e.message))
      .finally(() => setLoadingHistory(false));
  }, [session.session_id]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [turns]);

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
    const text = answerText;
    setTurns((prev) => [...prev, { speaker: "candidate", action: null, text }]);
    setAnswerText("");
    try {
      const result = await api.saveCheckpoint(session.session_id, text, "typed");
      setLastCheckpointId(result.checkpoint_id);
      if (result.action !== "continue") {
        setTurns((prev) => [...prev, { speaker: "interviewer", action: result.action, text: result.text }]);
      }
    } catch (e) {
      setError(e.message);
      setAnswerText(text);
      setTurns((prev) => prev.slice(0, -1));
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
      <div className="session-header">
        <span className="session-round-label">{roundLabel(session.round_type)}</span>
        <span className="elapsed-time">{formatElapsed(elapsedSeconds)}</span>
      </div>

      <div>
        <span className="panel-label">Question</span>
        <div className="question-panel">{session.question}</div>
      </div>

      <div>
        <span className="panel-label">Conversation</span>
        <div className="chat-scroll" ref={scrollRef}>
        {loadingHistory && (
          <div className="skeleton-block">
            <div className="skeleton-line" style={{ width: "70%" }} />
            <div className="skeleton-line" style={{ width: "45%" }} />
          </div>
        )}
        {!loadingHistory && turns.length === 0 && (
          <p className="muted">Your answers and the interviewer's follow-ups will appear here.</p>
        )}
        {turns.map((t, i) => (
          <div
            key={i}
            className={
              t.speaker === "candidate" ? "transcript-turn transcript-turn--candidate" : `transcript-turn inline-panel--${t.action}`
            }
          >
            <span className="transcript-turn-label">
              {t.speaker === "candidate" ? "You" : t.action === "interject" ? "Interjection" : "Follow-up"}
            </span>
            {t.text}
          </div>
        ))}
        </div>
      </div>

      <textarea
        className="answer-input"
        value={answerText}
        onChange={(e) => setAnswerText(e.target.value)}
        placeholder="Type or dictate your answer..."
        disabled={paused || saving || ending}
      />

      <div className="session-controls">
        <button
          className="btn-primary"
          onClick={handleSaveCheckpoint}
          disabled={saving || paused || ending || !answerText.trim()}
        >
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
