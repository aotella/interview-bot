import { useEffect, useState } from "react";
import { api } from "../api";

function ReportBody({ report }) {
  return (
    <>
      <p className={report.verdict === "REJECT" ? "error" : ""}>
        <strong>Verdict: {report.verdict}</strong>
      </p>
      <p className="question-panel">{report.question}</p>

      {report.dimensions.map((d) => (
        <div className="dimension-card" key={d.dimension}>
          <h3>
            {d.dimension} &mdash;{" "}
            {d.score === null ? "Not tested this session" : `${d.score}/${report.score_range[1]}`}
          </h3>
          <ul>
            {d.evidence.map((ev, i) => (
              <li key={i}>
                (<code>{ev.event_id}</code>) {ev.reason}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </>
  );
}

function TranscriptBody({ transcript }) {
  return (
    <>
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

      <div className="report-tabs">
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
          {loading && <p className="muted">Loading...</p>}
          {error && <p className="error">{error}</p>}
          {!loading && !error && TAB_KIND[tab] === "report" && report && <ReportBody report={report} />}
          {!loading && !error && TAB_KIND[tab] === "transcript" && transcript && (
            <TranscriptBody transcript={transcript} />
          )}
        </>
      )}
    </div>
  );
}
