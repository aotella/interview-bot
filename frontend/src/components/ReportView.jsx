import { useEffect, useState } from "react";
import { api } from "../api";
import { humanizeDimension, scoreTier, verdictClass } from "../format";

function ReportBody({ report }) {
  return (
    <>
      <p>
        Verdict: <span className={verdictClass(report.verdict)}>{report.verdict}</span>
      </p>
      <span className="panel-label">Question</span>
      <p className="question-panel">{report.question}</p>

      <div className="dimension-grid">
        {report.dimensions.map((d) => {
          const tier = scoreTier(d.score, report.score_range);
          return (
            <div className={`dimension-card${tier ? ` dimension-card--${tier}` : ""}`} key={d.dimension}>
              <div className="dimension-card-heading">
                <h3>{humanizeDimension(d.dimension)}</h3>
                <span className={`score-badge${tier ? ` score-badge--${tier}` : ""}`}>
                  {d.score === null ? "Not tested" : `${d.score} / ${report.score_range[1]}`}
                </span>
              </div>
              <ul>
                {d.evidence.map((ev, i) => (
                  <li key={i}>
                    {ev.reason}
                    <span className="evidence-id">{ev.event_id}</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </>
  );
}

function TranscriptBody({ transcript }) {
  return (
    <>
      <span className="panel-label">Question</span>
      <p className="question-panel">{transcript.question}</p>
      <div className="transcript-turns">
        {transcript.turns.map((t, i) => (
          <div
            key={i}
            className={
              t.speaker === "candidate" ? "transcript-turn transcript-turn--candidate" : `transcript-turn inline-panel--${t.action}`
            }
          >
            <span className="transcript-turn-label">
              {t.speaker === "candidate" ? "Candidate" : t.action === "interject" ? "Interjection" : "Follow-up"}
            </span>
            {t.text}
          </div>
        ))}
        {transcript.turns.length === 0 && <p className="muted">No turns recorded.</p>}
      </div>
    </>
  );
}

function StudyGuideBody({ solverId }) {
  const [status, setStatus] = useState("checking"); // checking | missing | ready
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setStatus("checking");
    api
      .studyGuideExists(solverId)
      .then((exists) => setStatus(exists ? "ready" : "missing"))
      .catch((e) => setError(e.message));
  }, [solverId]);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      await api.generateStudyGuide(solverId);
      setStatus("ready");
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  }

  if (error) return <p className="error">{error}</p>;
  if (status === "checking") return <p className="muted">Checking...</p>;
  if (status === "ready") {
    return <iframe className="study-guide-frame" src={api.studyGuideUrl(solverId)} title="Study guide" />;
  }
  return (
    <div className="study-guide-empty">
      <p className="muted">
        Generates a one-time teaching page for this question &mdash; architecture, API design, storage and
        queueing trade-offs, and how they change at scale.
      </p>
      <button className="btn-primary" onClick={handleGenerate} disabled={generating}>
        {generating ? "Generating study guide..." : "Generate study guide"}
      </button>
    </div>
  );
}

const TAB_KIND = {
  mine: "report",
  "mine-answer": "transcript",
  solver: "report",
  "solver-answer": "transcript",
};

export default function ReportView({ sessionId, solverSessionId, sourceSessionId, onBack }) {
  const mineId = sourceSessionId || sessionId;
  const solverId = solverSessionId || (sourceSessionId ? sessionId : null);
  const hasSolver = Boolean(solverId);

  const [tab, setTab] = useState("mine"); // mine | mine-answer | solver | solver-answer | study
  const [report, setReport] = useState(null);
  const [transcript, setTranscript] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (tab === "study") return;

    const id = tab.startsWith("solver") ? solverId : mineId;
    const kind = TAB_KIND[tab];

    setLoading(true);
    setError(null);
    setReport(null);
    setTranscript(null);

    const request = kind === "transcript" ? api.getTranscript(id) : api.getReport(id);

    request
      .then(kind === "transcript" ? setTranscript : setReport)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tab, mineId, solverId]);

  return (
    <div className="report-view">
      <button onClick={onBack} className="back-button">
        &larr; Back
      </button>
      <h2>Report</h2>

      <div className="tab-bar">
        <button aria-pressed={tab === "mine"} onClick={() => setTab("mine")}>
          My answer
        </button>
        <button aria-pressed={tab === "mine-answer"} onClick={() => setTab("mine-answer")}>
          My conversation
        </button>
        {hasSolver && (
          <>
            <button aria-pressed={tab === "solver"} onClick={() => setTab("solver")}>
              Senior SDE reference
            </button>
            <button aria-pressed={tab === "solver-answer"} onClick={() => setTab("solver-answer")}>
              Reference answer
            </button>
            <button aria-pressed={tab === "study"} onClick={() => setTab("study")}>
              Study guide
            </button>
          </>
        )}
      </div>

      {tab === "study" ? (
        <StudyGuideBody solverId={solverId} />
      ) : (
        <>
          {loading && (
            <div className="skeleton-block">
              <div className="skeleton-line" style={{ width: "60%" }} />
              <div className="skeleton-line" style={{ width: "100%", height: "5rem" }} />
              <div className="skeleton-line" style={{ width: "100%", height: "4rem" }} />
            </div>
          )}
          {error && (
            <div className="state-block state-block--error">
              <span className="state-block-icon">⚠️</span>
              <p className="error" style={{ margin: 0 }}>
                Couldn't load this report: {error}
              </p>
            </div>
          )}
          {!loading && !error && TAB_KIND[tab] === "report" && report && <ReportBody report={report} />}
          {!loading && !error && TAB_KIND[tab] === "transcript" && transcript && (
            <TranscriptBody transcript={transcript} />
          )}
        </>
      )}
    </div>
  );
}
