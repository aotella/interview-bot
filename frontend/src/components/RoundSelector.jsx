export default function RoundSelector({ onStart, loading, error }) {
  return (
    <div className="round-selector">
      <h1>Interview Prep</h1>
      <div className="round-buttons">
        <button disabled={loading} onClick={() => onStart("hld")}>
          High-Level Design
        </button>
        <button disabled={loading} onClick={() => onStart("lld_deepdive")}>
          LLD + Deep-Dive
        </button>
      </div>
      {loading && <p className="muted">Finding your question...</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
