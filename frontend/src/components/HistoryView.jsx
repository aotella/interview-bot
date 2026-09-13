import { useEffect, useState } from "react";
import { api } from "../api";

function averageScore(scores) {
  if (!scores) return null;
  const values = Object.values(scores);
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function ScoreTrend({ sessions }) {
  const graded = sessions
    .filter((s) => s.status === "ended" && s.scores && !s.source_session_id)
    .slice()
    .reverse(); // oldest first for a left-to-right trend
  if (graded.length < 2) return null;

  const width = 400;
  const height = 80;
  const maxScore = 4;
  const points = graded.map((s, i) => {
    const x = (i / (graded.length - 1)) * (width - 20) + 10;
    const avg = averageScore(s.scores);
    const y = height - 10 - (avg / maxScore) * (height - 20);
    return `${x},${y}`;
  });

  return (
    <svg className="score-trend" width={width} height={height}>
      <polyline points={points.join(" ")} fill="none" stroke="currentColor" strokeWidth="2" />
      {points.map((p, i) => {
        const [x, y] = p.split(",");
        return <circle key={i} cx={x} cy={y} r="3" fill="currentColor" />;
      })}
    </svg>
  );
}

export default function HistoryView({ onBack, onResume, onOpenReport }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [resumingId, setResumingId] = useState(null);
  const [solverRunningId, setSolverRunningId] = useState(null);
  const [solverErrorId, setSolverErrorId] = useState(null);

  function refresh() {
    return api.listSessions().then(setSessions);
  }

  useEffect(() => {
    refresh()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleResume(s) {
    setResumingId(s.session_id);
    setError(null);
    try {
      if (s.paused) {
        await api.resume(s.session_id);
      }
      onResume(s);
    } catch (e) {
      setError(e.message);
      setResumingId(null);
    }
  }

  async function handleRunSolver(s) {
    setSolverRunningId(s.session_id);
    setSolverErrorId(null);
    try {
      await api.runSolverComparison(s.session_id);
      await refresh();
    } catch (e) {
      setSolverErrorId({ id: s.session_id, message: e.message });
    } finally {
      setSolverRunningId(null);
    }
  }

  return (
    <div className="history-view">
      <button onClick={onBack} className="back-button">
        &larr; Back
      </button>
      <h2>Session History</h2>

      {loading && <p className="muted">Loading...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && (
        <>
          <ScoreTrend sessions={sessions} />
          <ul className="session-list">
            {sessions
              .filter((s) => !s.source_session_id)
              .map((s) => (
                <li key={s.session_id} className="session-list-item">
                  <span className="session-date">{s.session_id.replace(/^s_/, "").replace(/-\d\d$/, "")}</span>
                  <span className="session-round">{s.round_type}</span>
                  <span className="session-status">
                    {s.status === "ended" ? s.verdict || "graded pending" : "in progress"}
                  </span>
                  {s.status === "ended" && (
                    <button
                      className="report-button"
                      onClick={() => onOpenReport({ sessionId: s.session_id, solverSessionId: s.solver_session_id })}
                    >
                      View report
                    </button>
                  )}
                  {s.status === "in_progress" && (
                    <button
                      className="resume-button"
                      onClick={() => handleResume(s)}
                      disabled={resumingId === s.session_id}
                    >
                      {resumingId === s.session_id ? "Resuming..." : s.paused ? "Resume" : "Continue"}
                    </button>
                  )}
                  {s.status === "ended" && !s.solver_session_id && (
                    <button
                      className="solver-run-button"
                      onClick={() => handleRunSolver(s)}
                      disabled={solverRunningId === s.session_id}
                    >
                      {solverRunningId === s.session_id ? "Running senior reference..." : "Generate senior reference answer"}
                    </button>
                  )}
                  {s.solver_session_id && (
                    <span className="solver-badge">
                      Senior SDE reference available{" "}
                      <button
                        onClick={() =>
                          onOpenReport({ sessionId: s.solver_session_id, sourceSessionId: s.session_id })
                        }
                      >
                        View
                      </button>
                    </span>
                  )}
                  {solverErrorId?.id === s.session_id && (
                    <p className="error solver-error">{solverErrorId.message}</p>
                  )}
                </li>
              ))}
            {sessions.length === 0 && <li className="muted">No sessions yet.</li>}
          </ul>
        </>
      )}
    </div>
  );
}
