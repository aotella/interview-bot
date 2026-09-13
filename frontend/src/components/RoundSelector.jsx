export default function RoundSelector({ onStart, loading, error }) {
  return (
    <div className="round-selector">
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
    </div>
  );
}
