# Interview Prep Agent — Design

Builds directly on `interview-prep-agent-requirements.md`. Monolithic, local,
single-user — no auth, no deployment, no DB server.

## Component breakdown

```
                        ┌────────────────────┐
                        │        UI           │  session view, history/report
                        │ (local web frontend)│  browser, round selector, pause
                        └─────────┬───────────┘
                                  │ HTTP (localhost only)
                        ┌─────────▼───────────┐
                        │   Session Engine     │  owns live session state,
                        │   (backend)          │  checkpoint loop, timers
                        └───┬─────┬─────┬──────┘
                            │     │     │
              ┌─────────────┘     │     └─────────────┐
              ▼                   ▼                    ▼
     ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐
     │ Question        │  │ Interviewer    │  │ Transcript Store  │
     │ Sourcing module │  │ Agent          │  │ (JSONL, append-   │
     │ (SearXNG MCP +  │  │ (live calls,   │  │  only, immutable  │
     │  seniority      │  │  per checkpoint)│ │  after session)   │
     │  filter)        │  └────────────────┘  └─────────┬─────────┘
     └────────┬────────┘                                │
              │                                          │ on session_end
              ▼                                          ▼
     ┌────────────────┐                        ┌──────────────────┐
     │ Weak-Point Store │◄──────────────────────│  Grader Agent     │
     │ (per round type, │       reads/writes    │ (post-session     │
     │  counters JSON)  │                        │  only, once)      │
     └──────────────────┘                        └─────────┬─────────┘
                                                             │
                                                             ▼
                                                   ┌──────────────────┐
                                                   │ Report Generator  │
                                                   │ → writes .md into │
                                                   │   Obsidian vault  │
                                                   └──────────────────┘
```

All model calls (interviewer, grader, question-sourcing seniority check) go
through a single **OpenRouter client** wrapper. Model selection is
role-specific (`models.interviewer`, `models.grader`,
`models.question_sourcing` in `config.py`) rather than one shared field —
the three roles can legitimately run different models, and an ambiguous
single field would make that unrepresentable. Reproducibility-tuple versions
(rubric, each prompt, each model) live in the same config.

## Session lifecycle

1. **Start** — user picks round type (HLD / LLD+Deep-dive) in the UI, hits
   Start. Session Engine calls Question Sourcing, which web-searches, runs the
   seniority filter, and (if it needs biasing toward a weak point) reads the
   Weak-Point Store for that round type to weight the search/selection.
   Writes `session_start` event with the accepted question + its provenance
   record.
2. **Live loop** — user types/dictates into the answer field (Spokenly types
   into it like any other field, no special integration needed). On
   **Save checkpoint**:
   - Session Engine appends a `candidate_turn` event
   - Interviewer Agent is called with the lightweight running state (round
     type, question, elapsed time, checkpoints so far, pause history,
     diagrams attached — *not* a parallel claims/weakness tracker) plus the
     new turn
   - Interviewer returns one of `continue | follow_up | interject` — defined
     precisely so `follow_up` never becomes an implicit soft-pedal of a real
     mistake:
     - `continue`: reasoning is acceptable, no intervention
     - `follow_up`: reasoning is acceptable, interviewer probes deeper
     - `interject`: a material technical or process mistake occurred;
       interviewer intervenes immediately once the current thought completes
   - Session Engine appends `interviewer_turn` with that decision; UI shows
     the interjection/follow-up only if the decision wasn't `continue`
3. **Diagram attach** — user uploads an exported PNG/SVG at any point;
   `diagram_attached` event recorded with checkpoint_id, volunteered/requested,
   timestamp
4. **Pause/resume** — `pause_start` / `pause_end` events; elapsed-time display
   excludes paused duration
5. **End** (1 hour elapses, or user ends manually) — `session_end` event
   written with wall-clock, active, and paused durations. Transcript file
   becomes immutable: the application-level invariant is that no code path
   ever writes to a finalized transcript — this is the real guarantee, not the
   filesystem; a read-only chmod on the file is a cheap secondary safeguard,
   not the mechanism itself.
6. **Grading** — Grader Agent runs once, reads the full transcript file fresh
   (not the interviewer's in-session state) plus the actual diagram images
   referenced in it (not just their paths — the grader needs to see what's
   drawn, not just that something was attached), scores against the hidden
   rubric, and returns **structured output**: per-dimension scores each with
   an evidence list pointing at specific transcript event IDs, plus the
   overall verdict and weak-point outcomes. The report generator consumes
   this structure directly rather than inferring anything from free-form prose.
7. **Weak-Point Store update** — for each rubric dimension/tag: increment
   `opportunities` if it was actually testable this session, `failures` or
   `successes` accordingly, update `last_seen`
8. **Report generation** — reads transcript + grader output, writes the
   markdown report (frontmatter + evidence-linked prose) into the Obsidian
   vault path. UI shows a simple "session complete" confirmation; you read the
   actual report in Obsidian.

## Data shapes

**Transcript event stream** (`data/transcripts/{session_id}.jsonl`, one JSON
object per line):

```json
{"event": "session_start", "session_id": "s_2026-09-10-01", "round_type": "hld", "question": "...", "question_provenance": {"source_urls": ["...", "..."], "discovered_at": "...", "seniority_eval": "..."}, "timestamp": "..."}
{"event": "candidate_turn", "checkpoint_id": "cp_1", "text": "...", "input_mode": "typed|voice", "timestamp": "..."}
{"event": "interviewer_turn", "checkpoint_id": "cp_1", "action": "continue|follow_up|interject", "text": "...", "timestamp": "..."}
{"event": "pause_start", "timestamp": "..."}
{"event": "pause_end", "duration_seconds": 480, "timestamp": "..."}
{"event": "diagram_attached", "checkpoint_id": "cp_3", "path": "...", "file_type": "png|svg", "volunteered": true, "timestamp": "..."}
{"event": "session_end", "wall_clock_seconds": 3900, "active_seconds": 3540, "paused_seconds": 360, "timestamp": "..."}
```

**Grader output** (structured, consumed directly by the report generator —
not inferred from prose):

```json
{
  "verdict": "REJECT",
  "dimensions": [
    {"dimension": "capacity_estimation", "score": 1, "evidence": [
      {"event_id": "cp_1_candidate_turn", "reason": "never estimated QPS or storage before designing"}
    ]}
  ],
  "weak_point_outcomes": [
    {"tag": "capacity_estimation", "outcome": "failure"},
    {"tag": "tradeoff_articulation", "outcome": "success"},
    {"tag": "concurrency_deep_dive", "outcome": "neutral"}
  ]
}
```

**Report frontmatter** (Obsidian vault) — `scores` keys are whatever
dimensions the active rubric for that `round_type` defines; the report
generator reads them from the rubric config rather than hardcoding HLD/LLD
field names, so an HLD report can never end up with LLD dimensions or vice
versa:

```yaml
---
session_id: s_2026-09-10-01
date: 2026-09-10
round_type: hld
question: "Design a rate limiter"
verdict: REJECT
scores:
  requirements_clarification: 2
  capacity_estimation: 1
  high_level_design: 4
  deep_dive: 3
  tradeoffs_stated: 2
  failure_modes: 2
weak_points: [skipped-capacity-estimation, jumped-to-design-early]
diagrams: ["[[rate-limiter-2026-09-10.excalidraw]]"]
pauses: {count: 1, total_seconds: 480}
durations: {wall_clock_seconds: 3900, active_seconds: 3540, paused_seconds: 360}
rubric_version: hld_v1
interviewer_prompt_version: v1
grader_prompt_version: v1
question_sourcing_version: v1
models:
  interviewer: anthropic/claude-sonnet-4.6
  grader: anthropic/claude-sonnet-4.6
  question_sourcing: anthropic/claude-sonnet-4.6
---
```

**Weak-point store** (`data/weakpoints/hld.json`, `data/weakpoints/lld_deep_dive.json`) —
each opportunity resolves to exactly one outcome (`success | failure | neutral`,
where `neutral` covers "tested but not cleanly gradable"), so
`opportunities == successes + failures + neutral` always holds. Decay applies
only after a run of successes for that tag; a new failure resets the streak:

```json
{
  "capacity_estimation": {"opportunities": 5, "successes": 1, "failures": 3, "neutral": 1, "success_streak": 0, "last_seen": "2026-09-01"},
  "tradeoff_articulation": {"opportunities": 4, "successes": 3, "failures": 1, "neutral": 0, "success_streak": 2, "last_seen": "2026-09-08"}
}
```

## Configuration

Machine-specific paths and secrets are env vars, loaded once in `config.py`
— never hardcoded or committed:

- `OBSIDIAN_VAULT_PATH` — where the report generator writes markdown reports
- `EXCALIDRAW_EXPORT_PATH` — folder the "Attach latest diagram" button checks
- `OPENROUTER_API_KEY` — used by the OpenRouter client for all three roles

Role-specific model IDs and prompt/rubric versions (the reproducibility
tuple) stay in `config.py` itself rather than env vars — they're part of the
app's versioned behavior, not per-machine setup.

## Folder layout

```
interview-prep-agent/
  backend/
    app.py                    # HTTP entry point, routes
    session_engine.py         # session lifecycle, checkpoint loop
    interviewer_agent.py
    grader_agent.py
    question_sourcing.py
    report_generator.py
    weakpoint_store.py
    openrouter_client.py
    config.py                 # role-specific model IDs (interviewer/grader/
                               # question_sourcing) + prompt versions per role
    prompts/
      interviewer_hld_v1.md
      interviewer_lld_deepdive_v1.md
      grader_hld_v1.md
      grader_lld_deepdive_v1.md
      question_sourcing_v1.md
    rubrics/
      hld_v1.yaml              # dimensions + score range + anchor meanings
      lld_deepdive_v1.yaml     # (anchor definitions detailed in prompt-design pass)
  frontend/
    (session view, history/report browser, round selector)
  data/
    transcripts/{session_id}.jsonl
    weakpoints/{round_type}.json
    diagrams/{session_id}/            # attached checkpoint images
  # Obsidian vault path is external/configured, not inside this repo
```

## Settled technical decisions

1. **Question sourcing search** — SearXNG via MCP; the model calls it as a
   tool during question sourcing, results feed the seniority filter
2. **Backend** — FastAPI (Python); OpenRouter calls, agent logic, transcript/
   report/weak-point handling all live here
3. **Frontend** — Node-based (React/Vite), single local dev server, no
   deployment step needed — see UI design principles below
4. **Diagram attach** — a single **"Attach latest diagram"** button in the
   session UI: on click, backend checks the configured Excalidraw export
   folder's most-recently-modified file and attaches it to the current
   checkpoint. No file-browser dialog, no background filesystem watcher
   process. The model only ever sees the image at the moment of attach — same
   as a manual upload would — so this adds no extra model calls or continuous
   evaluation, just removes the "leave the app to browse files" step.

## UI design principles

Session UI is built around minimizing flow-breaking and competing-attention
moments, not just visual simplicity:

- One thing on screen at a time during a live session — question pinned at
  top, one large answer input, one Save Checkpoint button. No sidebar or
  secondary panels visible while a session is active.
- Interjections/follow-ups render as a distinctly-colored **inline** panel
  directly below the answer box, never a modal/popup — noticeable without
  stealing focus.
- Elapsed time shown quietly (small, corner), not a countdown — avoids
  clock-anxiety while still giving time awareness.
- No pre-session config screens — round selection is a single click (two
  round types), straight into the question after that.
- History view is a plain chronological list + a simple score-trend line, not
  a dashboard. The full report itself lives in Obsidian; the web UI doesn't
  duplicate it, so it stays uncluttered.
