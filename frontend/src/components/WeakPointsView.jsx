import { useEffect, useState } from "react";
import { api } from "../api";

export default function WeakPointsView({ onBack }) {
  const [roundType, setRoundType] = useState("hld");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .getWeakpoints(roundType)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [roundType]);

  const rows = data
    ? Object.entries(data).sort(([a], [b]) => a.localeCompare(b))
    : [];

  return (
    <div className="weakpoints-view">
      <button onClick={onBack} className="back-button">
        &larr; Back
      </button>
      <h2>Weak Points</h2>

      <div className="round-buttons">
        <button aria-pressed={roundType === "hld"} onClick={() => setRoundType("hld")}>
          HLD
        </button>
        <button aria-pressed={roundType === "lld_deepdive"} onClick={() => setRoundType("lld_deepdive")}>
          LLD + Deep-dive
        </button>
      </div>

      {loading && <p className="muted">Loading...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && (
        <table className="weakpoints-table">
          <thead>
            <tr>
              <th>Dimension</th>
              <th>Opportunities</th>
              <th>Success rate</th>
              <th>Current streak</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([dimension, c]) => (
              <tr key={dimension}>
                <td>{dimension}</td>
                <td>{c.opportunities}</td>
                <td>
                  {c.opportunities > 0
                    ? `${c.successes}/${c.opportunities} (${Math.round(c.success_rate * 100)}%)`
                    : "—"}
                </td>
                <td>{c.success_streak}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  No data yet for this round type.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
