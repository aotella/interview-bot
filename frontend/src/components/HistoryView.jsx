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
    .filter((s) => s.status === "ended" && s.scores)
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

export default function HistoryView({ onBack }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .listSessions()
      .then(setSessions)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

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
            {sessions.map((s) => (
              <li key={s.session_id} className="session-list-item">
                <span className="session-date">{s.session_id.replace(/^s_/, "").replace(/-\d\d$/, "")}</span>
                <span className="session-round">{s.round_type}</span>
                <span className="session-status">
                  {s.status === "ended" ? s.verdict || "graded pending" : "in progress"}
                </span>
              </li>
            ))}
            {sessions.length === 0 && <li className="muted">No sessions yet.</li>}
          </ul>
        </>
      )}
    </div>
  );
}
