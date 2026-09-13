import { useEffect, useState } from "react";
import { api } from "../api";
import { formatDuration, humanizeDimension, truncate, verdictClass } from "../format";

const CAPABILITIES = [
  {
    title: "Rubric-graded reports",
    body: "Every round is scored against a versioned rubric with cited evidence from your transcript, not a vibe check.",
  },
  {
    title: "Senior SDE reference",
    body: "Generate a senior-level solve for the same question and compare it to your own, dimension by dimension.",
  },
  {
    title: "Personalized study guides",
    body: "Turn the gap between your answer and the reference into a one-time teaching page for that question.",
  },
];

export default function RoundSelector({ onStart, loading, error, onResumeSession, onOpenHistory, onOpenWeakpoints }) {
  const [sessions, setSessions] = useState([]);
  const [weakpoints, setWeakpoints] = useState(null);
  const [resuming, setResuming] = useState(false);
  const [resumeError, setResumeError] = useState(null);

  useEffect(() => {
    api.listSessions().then(setSessions).catch(() => {});
    Promise.all([api.getWeakpoints("hld"), api.getWeakpoints("lld_deepdive")])
      .then(([hld, lld]) => setWeakpoints({ ...hld, ...lld }))
      .catch(() => {});
  }, []);

  const inProgressSessions = sessions.filter((s) => s.status === "in_progress" && !s.source_session_id);
  const continueSession = inProgressSessions[0];
  const otherInProgressCount = inProgressSessions.length - (continueSession ? 1 : 0);

  const latestGraded = sessions.find((s) => s.status === "ended" && s.verdict && !s.source_session_id);

  let weakestEntry = null;
  if (weakpoints) {
    const tested = Object.entries(weakpoints).filter(([, c]) => c.opportunities > 0);
    if (tested.length > 0) {
      weakestEntry = tested.reduce((worst, cur) => (cur[1].success_rate < worst[1].success_rate ? cur : worst));
    }
  }

  async function handleContinue() {
    setResuming(true);
    setResumeError(null);
    try {
      await onResumeSession(continueSession);
    } catch (e) {
      setResumeError(e.message);
    } finally {
      setResuming(false);
    }
  }

  return (
    <div className="round-selector">
      {continueSession && (
        <div className="continue-card">
          <span className="panel-label">Continue where you left off</span>
          <p className="continue-question">{truncate(continueSession.question, 130)}</p>
          <div className="continue-meta">
            <span className="muted">{formatDuration(continueSession.elapsed_seconds)} elapsed</span>
            <button className="btn-primary" onClick={handleContinue} disabled={resuming}>
              {resuming ? "Resuming..." : continueSession.paused ? "Resume" : "Continue"}
            </button>
          </div>
          {otherInProgressCount > 0 && (
            <button className="btn-ghost continue-more" onClick={onOpenHistory}>
              +{otherInProgressCount} more in progress
            </button>
          )}
          {resumeError && <p className="error">{resumeError}</p>}
        </div>
      )}

      {latestGraded && (
        <div className="progress-strip">
          <span>
            Last round: <span className={verdictClass(latestGraded.verdict)}>{latestGraded.verdict}</span>
          </span>
          {weakestEntry && (
            <span className="muted">
              Weakest area: {humanizeDimension(weakestEntry[0])} ({Math.round(weakestEntry[1].success_rate * 100)}%)
            </span>
          )}
          <button className="btn-ghost progress-strip-link" onClick={onOpenWeakpoints}>
            View weak points
          </button>
        </div>
      )}

      <h2>Start a round</h2>
      <p className="muted">Pick a format and we'll find you a question.</p>
      <div className="round-buttons">
        <button className="round-card" disabled={loading} onClick={() => onStart("hld")}>
          <span className="round-card-title">High-Level Design</span>
          <span className="round-card-desc">
            System design at scale &mdash; architecture, trade-offs, failure behavior.
          </span>
        </button>
        <button className="round-card" disabled={loading} onClick={() => onStart("lld_deepdive")}>
          <span className="round-card-title">LLD + Deep-Dive</span>
          <span className="round-card-desc">
            Object/class design plus a resume-driven project deep-dive.
          </span>
        </button>
      </div>
      {loading && <p className="muted">Finding your question...</p>}
      {error && <p className="error">{error}</p>}

      <div className="capabilities-strip">
        {CAPABILITIES.map((c) => (
          <div className="capability" key={c.title}>
            <span className="capability-title">{c.title}</span>
            <span className="muted">{c.body}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
