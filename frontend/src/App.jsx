import { useState } from "react";
import RoundSelector from "./components/RoundSelector";
import SessionView from "./components/SessionView";
import HistoryView from "./components/HistoryView";
import ReportView from "./components/ReportView";
import WeakPointsView from "./components/WeakPointsView";
import { api } from "./api";

export default function App() {
  const [view, setView] = useState("round-select"); // round-select | session | complete | history | report | weakpoints
  const [session, setSession] = useState(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);
  const [completion, setCompletion] = useState(null);
  const [reportTarget, setReportTarget] = useState(null);
  const [returnView, setReturnView] = useState("round-select");
  const [solverRunning, setSolverRunning] = useState(false);
  const [solverResult, setSolverResult] = useState(null);
  const [solverError, setSolverError] = useState(null);

  async function handleStart(roundType) {
    setStarting(true);
    setStartError(null);
    try {
      const started = await api.startSession(roundType);
      setSession(started);
      setView("session");
    } catch (e) {
      setStartError(e.message);
    } finally {
      setStarting(false);
    }
  }

  function handleEnded(result) {
    setCompletion(result);
    setView("complete");
  }

  function handleStartOver() {
    setSession(null);
    setCompletion(null);
    setSolverResult(null);
    setSolverError(null);
    setView("round-select");
  }

  function handleResume(sessionSummary) {
    setSession(sessionSummary);
    setView("session");
  }

  function handleOpenReport(target) {
    setReportTarget(target);
    setReturnView(view === "complete" ? "complete" : "history");
    setView("report");
  }

  async function handleRunSolver() {
    setSolverRunning(true);
    setSolverError(null);
    try {
      const result = await api.runSolverComparison(completion.session_id);
      setSolverResult(result);
    } catch (e) {
      setSolverError(e.message);
    } finally {
      setSolverRunning(false);
    }
  }

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <button className="wordmark" onClick={handleStartOver}>
            Interview Prep
          </button>
          {view !== "session" && (
            <nav className="topbar-nav">
              <button onClick={() => setView(view === "history" ? "round-select" : "history")}>
                {view === "history" ? "Close history" : "History"}
              </button>
              <button onClick={() => setView(view === "weakpoints" ? "round-select" : "weakpoints")}>
                {view === "weakpoints" ? "Close weak points" : "Weak points"}
              </button>
            </nav>
          )}
        </div>
      </header>

      <div className="app">
        {view === "round-select" && (
          <RoundSelector onStart={handleStart} loading={starting} error={startError} />
        )}

        {view === "session" && session && <SessionView session={session} onEnded={handleEnded} />}

        {view === "complete" && (
          <div className="complete-screen">
            <h2>Session complete</h2>
            {completion?.graded ? (
              <>
                <p>Verdict: {completion.verdict}</p>
                <button onClick={() => handleOpenReport({ sessionId: completion.session_id })}>
                  View report
                </button>

                {!solverResult && (
                  <button onClick={handleRunSolver} disabled={solverRunning}>
                    {solverRunning ? "Running senior reference candidate..." : "Generate senior reference answer"}
                  </button>
                )}
                {solverRunning && <p className="muted">This can take a few minutes.</p>}
                {solverError && <p className="error">{solverError}</p>}
                {solverResult && (
                  <>
                    <p className="muted">Reference verdict: {solverResult.verdict}</p>
                    <button
                      onClick={() =>
                        handleOpenReport({
                          sessionId: solverResult.session_id,
                          sourceSessionId: completion.session_id,
                        })
                      }
                    >
                      View reference report
                    </button>
                  </>
                )}
              </>
            ) : (
              <p className="error">Grading failed: {completion?.error || "unknown error"}</p>
            )}
            <button className="btn-primary" onClick={handleStartOver}>
              Start another round
            </button>
          </div>
        )}

        {view === "history" && (
          <HistoryView onBack={handleStartOver} onResume={handleResume} onOpenReport={handleOpenReport} />
        )}

        {view === "report" && reportTarget && (
          <ReportView {...reportTarget} onBack={() => setView(returnView)} />
        )}

        {view === "weakpoints" && <WeakPointsView onBack={handleStartOver} />}
      </div>
    </>
  );
}
