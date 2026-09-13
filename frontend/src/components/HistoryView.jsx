import { useEffect, useState } from "react";
import { api } from "../api";
import { formatDuration, truncate, verdictClass } from "../format";

// A null score means "no transcript evidence for this dimension" (Flagged
// item 7), not a failing grade - averaging must exclude nulls, and a
// session where few dimensions were actually tested shouldn't be plotted
// as if its average were as reliable as a fully-tested session's.
function averageScore(scores) {
  if (!scores) return null;
  const values = Object.values(scores);
  const totalCount = values.length;
  const tested = values.filter((v) => v !== null && v !== undefined);
  const testedCount = tested.length;
  if (testedCount === 0) return { avg: null, testedCount, totalCount };
  const avg = tested.reduce((a, b) => a + b, 0) / testedCount;
  return { avg, testedCount, totalCount };
}

function ScoreTrend({ sessions }) {
  const graded = sessions
    .filter((s) => s.status === "ended" && s.scores && !s.source_session_id)
    .slice()
    .reverse() // oldest first for a left-to-right trend
    .map((s) => ({ session: s, ...averageScore(s.scores) }))
    // Same "half the dimensions" threshold HistoryView's backend counterpart
    // (report_generator's null-count warning) uses - a session with fewer
    // than half its dimensions actually tested isn't plotted at all rather
    // than shown as an equally-weighted point.
    .filter(({ avg, testedCount, totalCount }) => avg !== null && testedCount >= totalCount / 2);
  if (graded.length < 2) return null;

  const width = 400;
  const height = 80;
  const maxScore = 4;
  const coords = graded.map(({ avg }, i) => {
    const x = (i / (graded.length - 1)) * (width - 20) + 10;
    const y = height - 10 - (avg / maxScore) * (height - 20);
    return { x, y };
  });

  const latest = graded[graded.length - 1];

  return (
    <div>
      <span className="panel-label">Score trend ({graded.length} graded sessions)</span>
      <svg className="score-trend" viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="xMinYMid meet">
        <polyline
          points={coords.map(({ x, y }) => `${x},${y}`).join(" ")}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        />
        {coords.map(({ x, y }, i) => {
          const { testedCount, totalCount } = graded[i];
          const partial = testedCount < totalCount;
          return (
            <circle
              key={i}
              cx={x}
              cy={y}
              r={partial ? "2" : "3"}
              fill="currentColor"
              opacity={partial ? 0.6 : 1}
            >
              <title>{`avg over ${testedCount}/${totalCount} dimensions`}</title>
            </circle>
          );
        })}
      </svg>
      <p className="muted" style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
        Latest average: {latest.avg.toFixed(1)} / 4
      </p>
    </div>
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
      await onResume(s);
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

      {loading && (
        <div className="skeleton-block" style={{ marginTop: "1.5rem" }}>
          <div className="skeleton-line" style={{ width: "100%", height: "3.2rem" }} />
          <div className="skeleton-line" style={{ width: "100%", height: "3.2rem" }} />
          <div className="skeleton-line" style={{ width: "100%", height: "3.2rem" }} />
        </div>
      )}
      {error && (
        <div className="state-block state-block--error">
          <span className="state-block-icon">⚠️</span>
          <p className="error" style={{ margin: 0 }}>
            Couldn't load session history: {error}
          </p>
          <button onClick={() => { setLoading(true); refresh().catch((e) => setError(e.message)).finally(() => setLoading(false)); }}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && (
        <>
          <ScoreTrend sessions={sessions} />
          <ul className="session-list">
            {sessions
              .filter((s) => !s.source_session_id)
              .map((s) => (
                <li key={s.session_id} className="session-list-item">
                  <div className="session-list-item-main">
                    <span className="session-date">{s.session_id.replace(/^s_/, "").replace(/-\d\d$/, "")}</span>
                    <span className="session-round">{s.round_type}</span>
                    {s.status === "in_progress" && (
                      <span className="session-elapsed">{formatDuration(s.elapsed_seconds)} elapsed</span>
                    )}
                  </div>
                  {s.question && <span className="session-question">{truncate(s.question, 90)}</span>}
                  <span className="session-status">
                    {s.status === "ended" ? (
                      s.verdict ? <span className={verdictClass(s.verdict)}>{s.verdict}</span> : "graded pending"
                    ) : (
                      "in progress"
                    )}
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
