const API_BASE = "http://127.0.0.1:8000";

async function request(path, options) {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "content-type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}

export const api = {
  startSession: (roundType) =>
    request("/sessions", { method: "POST", body: JSON.stringify({ round_type: roundType }) }),

  saveCheckpoint: (sessionId, text, inputMode) =>
    request(`/sessions/${sessionId}/checkpoints`, {
      method: "POST",
      body: JSON.stringify({ text, input_mode: inputMode }),
    }),

  pause: (sessionId) => request(`/sessions/${sessionId}/pause`, { method: "POST" }),

  resume: (sessionId) => request(`/sessions/${sessionId}/resume`, { method: "POST" }),

  attachDiagram: (sessionId, checkpointId) =>
    request(`/sessions/${sessionId}/diagram`, {
      method: "POST",
      body: JSON.stringify({ checkpoint_id: checkpointId }),
    }),

  endSession: (sessionId) => request(`/sessions/${sessionId}/end`, { method: "POST" }),

  getSession: (sessionId) => request(`/sessions/${sessionId}`),

  listSessions: () => request("/sessions"),

  getReport: (sessionId) => request(`/sessions/${sessionId}/report`),

  getTranscript: (sessionId) => request(`/sessions/${sessionId}/transcript`),

  getWeakpoints: (roundType) => request(`/weakpoints/${roundType}`),

  runSolverComparison: (sessionId) =>
    request(`/sessions/${sessionId}/solver-comparison`, { method: "POST" }),

  studyGuideUrl: (sessionId) => `${API_BASE}/sessions/${sessionId}/study-guide`,

  studyGuideExists: (sessionId) =>
    request(`/sessions/${sessionId}/study-guide/exists`).then((r) => r.exists),

  generateStudyGuide: (sessionId) =>
    request(`/sessions/${sessionId}/study-guide`, { method: "POST" }),
};
