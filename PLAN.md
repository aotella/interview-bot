# Interview Prep Agent — Implementation Plan

## Context primer

This is a personal-use, single-user, local tool that runs mock HLD and
LLD/Deep-dive system-design interviews. An "interviewer" agent runs a live
checkpoint loop (continue / follow-up / interject) against candidate answers;
a separate "grader" agent evaluates the finished transcript against a hidden
rubric, producing a binary verdict, per-dimension scores, and weak-point
tracking that biases future question selection. Sessions are stored as
immutable JSONL transcripts locally, with a derived Markdown report written
into an Obsidian vault. Backend is FastAPI/Python, frontend is React/Vite,
model calls go through OpenRouter.

Source of truth (read these before touching this plan):
- `interview-prep-agent-requirements.md`
- `interview-prep-agent-design.md`

**Status: Phase 1 — Project scaffold & config — complete. Phase 2 — Data
layer — not started.**
(Update this line every time a phase completes. Next session: start here,
re-read this primer and the current phase's checklist state before making
any changes.)

## Working agreements

- Tasks are sized to finish and verify in one sitting. If a task can't be
  verified without also building a later phase, it's too big — split it.
- Commit after each completed task or small task group. Commit messages
  describe what became true ("weak-point store rejects inconsistent
  counters"), not which files changed.
- Don't build ahead of the current phase: no wiring the frontend to endpoints
  that don't exist yet, no schema fields added "for later" that no phase
  currently uses.
- If a design decision turns out ambiguous *during* implementation (not
  before — this isn't for re-litigating settled decisions), stop and add it
  to Flagged for decision below rather than silently picking one.
- Testing matches the project's scale: no heavy test infra, but every
  invariant the design doc calls correctness-critical (event schema
  validity, transcript immutability, weak-point counter consistency,
  rubric/report dimension matching) gets a real automated check, not a
  manual eyeball — a silent break there corrupts data the whole project
  depends on.

## Flagged for decision

These are gaps the design doc leaves open that this plan deliberately does
NOT resolve — each blocks part of a phase below from being "real" (as
opposed to stubbed) until decided.

1. **Rubric anchor/scoring content.** Neither doc specifies what earns a 1
   vs. a 4 on any dimension. This is evaluative content, not architecture —
   needs a dedicated authoring pass, not an invented placeholder. Blocks:
   Phase 2's rubric YAML files (stub with TODO anchors), and blocks the
   grader from being meaningfully calibrated in Phase 4.
2. **LLD/Deep-dive rubric dimension list.** HLD has an implied 6-dimension
   list (via the report frontmatter example in the design doc); LLD/Deep-dive
   has zero worked example anywhere, despite being a combined round type
   (low-level/OO design + resume-driven project deep-dive). Do not invent
   this by analogy to HLD. Blocks: Phase 2's `lld_deepdive_v1.yaml`.
3. **Weak-point tag taxonomy vs. rubric dimensions.** The design doc's two
   worked examples are inconsistent: report frontmatter's `weak_points` uses
   kebab-case narrative phrases (`skipped-capacity-estimation`), while
   grader-output/weak-point-store examples use snake_case dimension-like
   keys (`capacity_estimation`, `tradeoff_articulation`,
   `concurrency_deep_dive` — the last isn't even in HLD's implied dimension
   list). Unclear whether weak-point tags ARE the rubric dimension set or a
   separate, finer-grained vocabulary. Blocks: Phase 2's weak-point store
   schema, Phase 4's grader-output schema, and the report generator's
   `weak_points` field mapping — get this wrong and all three need rework.
4. **SearXNG MCP setup.** Neither doc says whether a local SearXNG
   instance/MCP server already exists, needs to be stood up, or is external
   infra to point at — no connection config (URL, auth, transport) given.
   Blocks: Phase 3's SearXNG wiring task.
5. **Grader structured-output enforcement mechanism.** The design doc says
   the grader "returns structured output" but not how that's enforced —
   OpenRouter JSON-schema/tool-calling mode, a parse-and-retry loop, or
   something else. Affects reliability/error-handling design. Blocks: Phase
   4's grader agent implementation detail (not the schema itself).
6. **Diagram image handling for the grader.** The grader must see actual
   image bytes ("what's drawn," not just paths), but size limits, how
   multiple diagrams per session get batched into one grading call, and
   fallback behavior on a failed image load aren't specified. Blocks: Phase
   4/5's grader-agent diagram handling.

---

## Phase 1 — Project scaffold & config

**Goal:** Repo skeleton, config loading, and an importable (but not yet
wired) OpenRouter client exist, so every later phase has somewhere to live.

**Tasks**
- [x] Create folder layout: `backend/`, `backend/prompts/`, `backend/rubrics/`,
      `frontend/`, `data/transcripts/`, `data/weakpoints/`, `data/diagrams/`
- [x] Add `.gitignore` covering `data/`, `.env`, `__pycache__/`,
      `node_modules/`, `dist/`
- [x] Create `backend/config.py`: loads `OBSIDIAN_VAULT_PATH`,
      `EXCALIDRAW_EXPORT_PATH`, `OPENROUTER_API_KEY` from env once; raises
      loudly at import time if any is missing; defines `models.interviewer`,
      `models.grader`, `models.question_sourcing`; defines the
      reproducibility-tuple version fields (`rubric_version` per round type,
      `interviewer_prompt_version`, `grader_prompt_version`,
      `question_sourcing_prompt_version`)
- [x] Create `backend/openrouter_client.py` as a thin wrapper exposing a
      `complete(role, messages, **kwargs)`-shaped interface; real HTTP call
      raises `NotImplementedError` for now (real wiring is Phase 3)
- [x] Add `backend/requirements.txt` or `pyproject.toml` (fastapi, pydantic,
      httpx, pyyaml, python-dotenv) — no server code yet
- [x] Add `.env.example` documenting the three required env vars

**Definition of done**
- Repo tree matches the layout above
- Importing `config` succeeds with a fully populated `.env`, fails with a
  clear error when any of the three vars is missing
- `openrouter_client` imports cleanly; calling `complete()` raises
  `NotImplementedError`, not an import error
- `.env` is gitignored, not committed

**Verification**
- `find backend frontend data -type d` — matches the layout above
- `python -c "from backend import config"` with full `.env` → succeeds,
  prints resolved model IDs/versions
- Unset `OPENROUTER_API_KEY`, re-run → raises a descriptive error
- `git status` shows `.env` ignored, `.env.example` tracked

---

## Phase 2 — Data layer

**Goal:** Transcript event schema, weak-point store, and rubric config exist
with their invariants enforced by real, checked code — before any agent or
UI touches them.

**Tasks**
- [ ] Define an event_id scheme and add it as a required field on every
      event type: monotonic per-session sequence number formatted as
      `f"{session_id}_{seq:04d}"`, assigned by the transcript writer at
      append time (not by the caller) so it can never collide, including
      across multiple events at the same checkpoint_id (e.g. an edited
      candidate_turn)
- [ ] Define pydantic models (or JSON Schema) for each transcript event type
      in `backend/schemas.py`: `session_start`, `candidate_turn`,
      `interviewer_turn`, `pause_start`, `pause_end`, `diagram_attached`,
      `session_end` — fields per the design doc's example JSONL, plus the
      `event_id` field defined above
- [ ] Implement an append-only transcript writer
      (`data/transcripts/{session_id}.jsonl`) in `backend/session_engine.py`
      (or a dedicated `transcript_store.py`) that:
  - validates and appends one JSON object per line
  - refuses to append anything once `session_end` has been written for that
    session_id (application-level immutability guarantee)
  - chmods the file read-only after `session_end` as the secondary
    safeguard the design doc calls for
- [ ] Implement `backend/weakpoint_store.py`: read/write
      `data/weakpoints/{round_type}.json`; enforce
      `opportunities == successes + failures + neutral` on every write
      (raise if violated); `success_streak` resets to 0 on any failure,
      increments on success; `last_seen` updates only when `opportunities`
      increments — **tag vocabulary here depends on Flagged item 3**
- [ ] Author `backend/rubrics/hld_v1.yaml` with the 6 dimensions implied by
      the design doc's frontmatter example; mark anchor text as TODO
      (**Flagged item 1**)
- [ ] Author `backend/rubrics/lld_deepdive_v1.yaml` — do not invent the
      dimension list by analogy to HLD; stub with an explicit TODO block
      until Flagged item 2 is resolved
- [ ] Write a rubric loader that reads dimension names from YAML rather than
      hardcoding HLD/LLD field names (this is what report generation later
      depends on)
- [ ] Write pytest tests: valid event round-trip, rejected write after
      `session_end`, weak-point invariant enforcement (including a
      deliberately-broken update raising), rubric loader returning the
      correct dimension set per round_type

**Definition of done**
- All event types construct, validate, and append correctly to a `.jsonl`
- Every appended event carries a unique, monotonically increasing
  `event_id`; two events at the same checkpoint_id still get distinct IDs
- Appending anything after `session_end` raises, and the file is unchanged
- A weak-point update with `opportunities != successes+failures+neutral`
  raises
- Both rubric YAMLs load with visibly distinct, non-hardcoded dimension sets
- `pytest` suite for this phase passes

**Verification**
- `pytest backend/tests/test_schemas.py backend/tests/test_weakpoint_store.py backend/tests/test_rubric_loader.py -v`
- Append several events including two at the same checkpoint_id; assert all
  `event_id`s are unique and increasing
- Manually append a `session_end` event to a test transcript, then attempt
  one more append → exception raised, `wc -l` on the file unchanged
- Manually construct a mismatched weak-point counter update → raises
- Load `hld_v1.yaml` → dimension keys equal
  `{requirements_clarification, capacity_estimation, high_level_design, deep_dive, tradeoffs_stated, failure_modes}`

---

## Phase 3 — External integrations

**Goal:** OpenRouter client makes a real successful call; SearXNG MCP is
wired so question sourcing has a real search tool — both testable in
isolation, no agent logic yet.

**Tasks**
- [ ] Implement real HTTP call logic in `openrouter_client.py`: request
      construction, auth header from `config.OPENROUTER_API_KEY`, response
      parsing, error handling for rate limit/timeout/malformed response
- [ ] `complete(role=..., messages=...)` resolves the model ID from
      `config.models.<role>` so callers never hardcode a model string
- [ ] Resolve **Flagged item 4** (SearXNG MCP connection details) before
      wiring; document the decision in this file once made
- [ ] Add `backend/scripts/smoke_openrouter.py`: calls `complete()` for all
      three roles with a trivial prompt, prints responses
- [ ] Add `backend/scripts/smoke_searxng.py`: calls the SearXNG MCP search
      tool with a fixed query, prints raw results

**Definition of done**
- A real OpenRouter call succeeds for all three roles, returns parsed text
- A real SearXNG MCP search succeeds, returns result objects with at least
  title/url/snippet
- Both fail with clear, actionable errors on bad auth/config — no silent
  hangs, no raw library stack traces surfacing to the caller

**Verification**
- `python -m backend.scripts.smoke_openrouter` → non-empty completions for
  all three roles
- `python -m backend.scripts.smoke_searxng --query "distributed rate limiter design interview"`
  → at least one result with a URL
- Temporarily break `OPENROUTER_API_KEY` → clear auth error, not a raw
  httpx traceback

---

## Phase 4 — Agent logic (question sourcing, interviewer, grader)

**Goal:** All three agent roles work as directly-callable functions/CLIs,
independently testable without the session engine or UI.

**Tasks**
- [ ] Author `backend/prompts/interviewer_hld_v1.md` and
      `interviewer_lld_deepdive_v1.md`: encode the
      `continue | follow_up | interject` contract, "interject only once the
      current thought completes," and confirm the rubric is never included
      in this prompt's context (hidden-rubric requirement)
- [ ] Author `backend/prompts/grader_hld_v1.md` and
      `grader_lld_deepdive_v1.md`: instruct structured output matching the
      grader-output shape (per-dimension scores + evidence event IDs +
      verdict + weak_point_outcomes) — enforcement mechanism per
      **Flagged item 5**
- [ ] Author `backend/prompts/question_sourcing_v1.md`: encode the
      seniority bar (ambiguity, scale/trade-off reasoning, no single correct
      answer) as an explicit accept/reject check; require a provenance
      record (source URLs, discovered_at, target_level, seniority_eval)
- [ ] Implement `backend/question_sourcing.py`: calls SearXNG MCP, runs the
      seniority filter, loops re-search on reject, capped at 5 attempts; on
      exhausting the cap, fails session start with a clear, specific error
      (not a silent hang or an unbounded loop) — document this cap choice in
      a code comment. Reads the Weak-Point Store for the target round type
      and computes a sampling weight per tag from `failures`,
      `success_streak`, and `last_seen` (e.g. higher recent-failure count
      and a reset/low `success_streak` increase weight; a long
      `success_streak` decays it toward zero, per the design doc's decay
      rule). Uses the resulting weights to bias which tag(s) the
      search/selection targets for this session — this must measurably
      change question selection, not just read the store for logging.
      Returns question + provenance record matching `session_start`'s shape
- [ ] Implement `backend/interviewer_agent.py`: takes the lightweight
      running state (round type, question, elapsed time, checkpoints so
      far, pause history, diagrams attached) + new candidate turn; returns
      `continue|follow_up|interject` + text matching `interviewer_turn`
- [ ] Implement `backend/grader_agent.py`: takes the full transcript (read
      fresh from file) + referenced diagram image bytes per **Flagged item
      6**; applies the rubric loaded from `rubrics/{round_type}_{version}.yaml`;
      returns structured output matching the grader-output shape, with each
      evidence entry's `event_id` set to a real `event_id` value from the
      transcript being graded, never invented
- [ ] Add dev CLIs: `backend/scripts/dev_question_sourcing.py`,
      `dev_interviewer_turn.py`, `dev_grade_transcript.py` for direct
      invocation with hand-crafted inputs
- [ ] Write pytest tests feeding a hand-authored fixture transcript into the
      grader, asserting output validates against the schema AND that every
      evidence `event_id` exactly matches an `event_id` present in the
      fixture transcript

**Definition of done**
- Question sourcing CLI produces a real accepted question with a fully
  populated provenance record from a live search
- Given a weak-point store where tag X has recent failures and a reset
  streak, and tag Y has a long success_streak, running question sourcing
  repeatedly favors tag X over tag Y at a rate clearly above chance —
  proven by a test, not eyeballed
- Interviewer CLI, given a hand-crafted running-state + turn, returns a
  valid decision
- Grader CLI, given a fixture transcript, returns a verdict where every
  evidence `event_id` exactly matches an event_id value present in the
  fixture transcript (not merely a plausible-looking string)
- Grepping the assembled interviewer prompt/messages for rubric dimension
  names returns zero matches

**Verification**
- `python -m backend.scripts.dev_question_sourcing --round hld` → output has
  `source_urls`, `discovered_at`, `target_level`, `seniority_eval` populated
- A test fixture with two weak-point stores (one skewed toward tag X, one
  toward tag Y) drives question sourcing N times each; assert the tag
  distribution flips accordingly between the two runs
- `python -m backend.scripts.dev_interviewer_turn --fixture fixtures/turn_ok.json`
  vs. `fixtures/turn_bad.json` → decision differs appropriately
- `pytest backend/tests/test_grader_agent.py -v` — includes the assertion
  that every evidence `event_id` exactly matches an `event_id` present in
  the fixture transcript
- Grep assembled interviewer prompt for each rubric dimension name from
  `hld_v1.yaml` — zero matches

---

## Phase 5 — Session engine (full lifecycle)

**Goal:** Question sourcing, interviewer, grader, transcript store,
weak-point store, and report generator are wired into the complete session
lifecycle via direct function calls — no HTTP/UI yet.

**Tasks**
- [ ] Implement lifecycle functions in `backend/session_engine.py`:
      `start_session(round_type)`, `save_checkpoint(session_id, text, input_mode)`,
      `attach_diagram(session_id, checkpoint_id)` (checks
      `EXCALIDRAW_EXPORT_PATH` for the most-recently-modified file, copies it
      into `data/diagrams/{session_id}/`, appends `diagram_attached`),
      `pause(session_id)` / `resume(session_id)` (tracks paused duration,
      excluded from elapsed time), `end_session(session_id)` (appends
      `session_end` with wall_clock/active/paused durations, finalizes
      immutability)
- [ ] Implement `backend/report_generator.py`: reads transcript + grader
      structured output; writes Markdown into `OBSIDIAN_VAULT_PATH` with
      frontmatter (scores keyed from the round's rubric dimensions,
      weak_points, diagrams, pauses, durations, full reproducibility tuple,
      model IDs) + evidence-linked prose body; scores keys loaded from the
      rubric config, never hardcoded
- [ ] Wire grading + weak-point update into `end_session`: on
      `session_end`, call the grader once, persist its structured output,
      update the weak-point store per outcome, then call the report
      generator
- [ ] Add `backend/scripts/dev_full_session_dry_run.py`: drives a full fake
      session end-to-end via direct engine calls — start → 2-3 checkpoints →
      one pause/resume → one diagram attach → end → grade → weak-point
      update → report write

**Definition of done**
- A full session runs start-to-finish via direct Python calls, producing an
  immutable `.jsonl` transcript, an updated weak-point JSON file, and a
  Markdown report in the configured vault path
- Report frontmatter's `scores` keys exactly equal the active rubric's
  dimension list for that round_type — checked programmatically
- Any transcript write attempted after `end_session` fails (same invariant
  from Phase 2, now exercised through the real lifecycle)
- `active_seconds + paused_seconds == wall_clock_seconds` on `session_end`

**Verification**
- `python -m backend.scripts.dev_full_session_dry_run --round hld` →
  completes without error, prints transcript/weak-point/report paths
- `cat data/transcripts/{session_id}.jsonl | python -c "import json,sys; [json.loads(l) for l in sys.stdin]"`
  → every line valid JSON, last line is `session_end`
- Assert `active_seconds + paused_seconds == wall_clock_seconds` against the
  produced `session_end` event
- Diff report frontmatter `scores` keys against `rubrics/hld_v1.yaml`
  dimension keys — assert set equality
- Attempt a post-`session_end` append through the engine → rejected

---

## Phase 6 — Backend API surface

**Goal:** Session engine is exposed over local-only HTTP via FastAPI.

**Tasks**
- [ ] Implement `backend/app.py`, bound to `127.0.0.1` only:
      `POST /sessions` (start), `POST /sessions/{id}/checkpoints` (save
      checkpoint), `POST /sessions/{id}/diagram` (attach latest),
      `POST /sessions/{id}/pause`, `POST /sessions/{id}/resume`,
      `POST /sessions/{id}/end`, `GET /sessions` (history list),
      `GET /sessions/{id}` (session summary — verdict/score summary, not
      the full report, since the UI doesn't duplicate Obsidian)
- [ ] Response shapes carry only what the UI needs: elapsed time, latest
      interviewer decision/text (only when not `continue`), pause state,
      checkpoint count
- [ ] Add pydantic request validation and clear 4xx/5xx error responses
- [ ] Add a dev run script/command (`uvicorn backend.app:app --reload`)

**Definition of done**
- All routes map 1:1 to `session_engine` functions — no duplicated business
  logic in `app.py`
- Server binds only to localhost; CORS scoped to the frontend dev origin,
  not wildcard
- `GET /sessions/{id}` after completion shows verdict/score summary without
  dumping the full transcript/report

**Verification**
- `uvicorn backend.app:app --port 8000`, then:
  `curl -X POST localhost:8000/sessions -d '{"round_type":"hld"}' -H 'content-type: application/json'`
  → returns session_id + question
  `curl -X POST localhost:8000/sessions/{id}/checkpoints -d '{...}'` →
  returns interviewer decision
  `curl -X POST localhost:8000/sessions/{id}/pause` → confirms pause state;
  `curl -X POST localhost:8000/sessions/{id}/resume` → confirms resume and
  that paused duration was recorded
  `curl -X POST localhost:8000/sessions/{id}/end` → confirmation; then
  `curl localhost:8000/sessions/{id}` shows verdict
- Confirm server bind address is `127.0.0.1`, not `0.0.0.0`

---

## Phase 7 — Frontend

**Goal:** Minimal live-session UI first, verified against the running
backend, then pause/diagram-attach/history layered in — following the UI
design principles in the design doc.

**Tasks**
- [ ] Scaffold Node/Vite/React app under `frontend/`
- [ ] Round-selector screen: two buttons (HLD / LLD+Deep-dive), single click
      straight into the question — no config screen
- [ ] Core session view: question pinned at top, one large answer input
      (typed or Spokenly-dictated — same field, no special integration),
      one Save Checkpoint button, no sidebar/secondary panels visible
- [ ] Confirm the answer input is a plain, standard-focusable text element
      (native `<textarea>` or equivalent) — not a rich-text/contenteditable
      component that could intercept or mangle OS-level dictation input
- [ ] Inline interjection/follow-up panel: distinctly colored, directly
      below the answer box, never a modal — shown only when decision !=
      `continue`
- [ ] Quiet elapsed-time display (small, corner, not a countdown)
- [ ] Pause control (button + visible pause state)
- [ ] "Attach latest diagram" button wired to `POST /sessions/{id}/diagram`
- [ ] History view: plain chronological list + simple score-trend line
      (not a dashboard), pulling from `GET /sessions`
- [ ] Wire all actions to the Phase 6 API; minimal loading/error states

**Definition of done**
- A full round completes through the UI alone: pick round → see question →
  answer/checkpoint → inline interjections appear only when warranted →
  pause/resume → attach a diagram → end → "session complete" confirmation
- History view lists past sessions and renders a score trend without
  touching Obsidian
- No modals, no secondary panels mid-session, elapsed time non-intrusive

**Verification**
- Manual run-through with backend running: `npm run dev`, walk one full HLD
  session in the browser, confirm each UI principle bullet holds
- With Spokenly running, focus the answer input and dictate a short test
  phrase — confirm the transcribed text lands in the field exactly as it
  would in any other native text field, with no formatting/structure loss
- Devtools network tab: diagram-attach calls fire only on button click, no
  polling/watcher
- History view renders correctly after ≥2 completed sessions exist

---

## Phase 8 — End-to-end pass

**Goal:** One real, full-length session runs through the entire pipeline via
the actual UI; both output artifacts (Obsidian report, weak-point store) are
confirmed correct and mutually consistent.

**Tasks**
- [ ] Point `OBSIDIAN_VAULT_PATH` at a real (or throwaway test) vault
- [ ] Point `EXCALIDRAW_EXPORT_PATH` at a working Excalidraw/Obsidian
      auto-export setup and confirm it exports outside the app first
- [ ] Run one complete real HLD or LLD/Deep-dive session through the
      frontend: real question sourcing, real answers, at least one
      deliberate mistake (to trigger `interject`), at least one pause, at
      least one diagram attach
- [ ] Let it run to `session_end`; confirm grading, weak-point update, and
      report generation all fire automatically
- [ ] Cross-check transcript, weak-point store diff, and Obsidian report
      together for internal consistency

**Definition of done**
- Transcript `.jsonl` is complete, well-formed, immutable, and contains
  events for every real action taken
- Weak-point store shows exactly the counter deltas implied by the grader's
  `weak_point_outcomes` for that session, still satisfying
  `opportunities == successes+failures+neutral`
- Obsidian report's frontmatter `scores` keys match the round's rubric
  dimensions, correct reproducibility tuple, correct diagram link(s),
  correct pause/duration numbers, and prose evidence pointers that resolve
  to real transcript event IDs
- Report is queryable via a basic Obsidian Dataview query

**Verification**
- `wc -l data/transcripts/{session_id}.jsonl` and manually diff event
  count/types against what was actually done
- Script a diff of the weak-point store before/after; assert the delta
  matches the grader's `weak_point_outcomes` exactly, summed by tag
- Open the report in Obsidian, confirm frontmatter renders, run a Dataview
  query (e.g. list sessions where `round_type = hld`) and confirm the new
  session appears
- For each `evidence[].event_id` used in this real session's grading, look
  up the exact `event_id` in the transcript's parsed events and confirm it
  exists — use the same parsing path Phase 2's tests use, not grep, since
  `event_id` is now a structured field
