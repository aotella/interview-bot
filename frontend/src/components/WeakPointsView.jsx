import { useEffect, useState } from "react";
import { api } from "../api";
import { humanizeDimension, rateTier } from "../format";

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

  // Weakest first - the whole point of this page is "what should I fix
  // next," so it shouldn't require scanning every row to find that out.
  // Dimensions with no tested opportunities yet can't be ranked, so they
  // sort to the bottom instead of interleaving with real data.
  const rows = data
    ? Object.entries(data).sort(([, a], [, b]) => {
        if (a.opportunities === 0 && b.opportunities === 0) return 0;
        if (a.opportunities === 0) return 1;
        if (b.opportunities === 0) return -1;
        return a.success_rate - b.success_rate;
      })
    : [];

  return (
    <div className="weakpoints-view">
      <button onClick={onBack} className="back-button">
        &larr; Back
      </button>
      <h2>Weak Points</h2>

      <div className="tab-bar">
        <button aria-pressed={roundType === "hld"} onClick={() => setRoundType("hld")}>
          HLD
        </button>
        <button aria-pressed={roundType === "lld_deepdive"} onClick={() => setRoundType("lld_deepdive")}>
          LLD + Deep-dive
        </button>
      </div>

      {loading && (
        <div className="skeleton-block">
          <div className="skeleton-line" style={{ width: "100%", height: "2.4rem" }} />
          <div className="skeleton-line" style={{ width: "100%", height: "2.4rem" }} />
          <div className="skeleton-line" style={{ width: "100%", height: "2.4rem" }} />
        </div>
      )}
      {error && (
        <div className="state-block state-block--error">
          <span className="state-block-icon">⚠️</span>
          <p className="error" style={{ margin: 0 }}>
            Couldn't load weak points: {error}
          </p>
        </div>
      )}

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
            {rows.map(([dimension, c]) => {
              const tier = c.opportunities > 0 ? rateTier(c.success_rate) : null;
              return (
                <tr key={dimension}>
                  <td>{humanizeDimension(dimension)}</td>
                  <td>{c.opportunities}</td>
                  <td>
                    {c.opportunities > 0 ? (
                      <div className="rate-cell">
                        <div className="rate-bar">
                          <div
                            className={`rate-bar-fill rate-bar-fill--${tier}`}
                            style={{ width: `${Math.round(c.success_rate * 100)}%` }}
                          />
                        </div>
                        <span>
                          {c.successes}/{c.opportunities} ({Math.round(c.success_rate * 100)}%)
                        </span>
                      </div>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>{c.success_streak}</td>
                </tr>
              );
            })}
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
