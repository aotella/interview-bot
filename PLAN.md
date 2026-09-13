# Interview Prep Agent — Implementation Plan

## Context primer

This is a personal-use, single-user, local tool that runs mock HLD and
LLD/Deep-dive system-design interviews. An "interviewer" agent runs a live
checkpoint loop (continue / follow-up / interject) against candidate answers;
a separate "grader" agent evaluates the finished transcript against a hidden
rubric, producing a binary verdict, per-dimension scores, and weak-point
tracking that biases future question selection. Sessions are stored as
immutable JSONL transcripts locally, with a derived JSON report record
(`data/reports/{session_id}.json`) as the sole persisted report - Obsidian
was dropped in Phase 10, see below. Backend is FastAPI/Python, frontend is
React/Vite, model calls go through OpenRouter.

Source of truth (read these before touching this plan):
- `interview-prep-agent-requirements.md`
- `interview-prep-agent-design.md`

**Status (updated 2026-09-13):** Phase 7's original browser-click-through
caveat is superseded by events, not by a dedicated verification pass: the
user ran real HLD/LLD sessions through the UI starting 2026-09-12 (that's
what drove Phase 9's post-launch feature pass below), so the core session
flow, history view, and diagram attach are confirmed working in practice.
Phase 8 as a distinct "end-to-end pass" phase was never formally run or
closed out — treat it as folded into the Phase 9/10/11 real-usage-driven
passes rather than a separate remaining task. Current phase is Phase 11
(below) plus Flagged item 1 just resolved (rubric anchors authored,
`hld_v2`/`lld_deepdive_v2`). Next session: re-grade or at least spot-check
a real transcript against the new v2 anchors to sanity-check the
calibration before trusting weak-point data accumulated under it.

**Phase 9 — Post-launch feature pass (2026-09-12):** after running the
first real HLD round, review of its transcript drove four additions on top
of Phase 7:
1. **Report duplication principle reversed.** Phase 6/7 deliberately kept
   `get_session_summary` from returning the full report ("the UI doesn't
   duplicate Obsidian") — the user explicitly asked to see the graded
   assessment (verdict, per-dimension scores, evidence) in the web UI. Added
   `report_generator.generate_report` now also writes a JSON sidecar
   (`data/reports/{session_id}.json`, the raw `GraderOutput`) alongside the
   Markdown; `session_engine.get_session_report` + `GET
   /sessions/{id}/report` + a new `ReportView` component serve it.
   `get_session_summary`'s docstring updated accordingly — full detail now
   lives behind the report endpoint, not withheld entirely.
2. **Weak-points UI added.** `weakpoint_store` already accumulated
   per-dimension counters with nothing surfacing them. Added
   `session_engine.get_weakpoints` (adds a derived `success_rate`) + `GET
   /weakpoints/{round_type}` + a new `WeakPointsView` component. Purely
   additive read path, no invariant/architecture change.
3. **LLD rubric dimension list authored** — see Flagged item 2's resolution
   above.
4. **Solver-agent concept introduced.** A fourth agent role, `solver`
   (`backend/solver_agent.py`, `backend/prompts/solver_{hld,lld_deepdive}_v1.md`,
   `config.models.solver`, `config.solver_prompt_version`), plays a strong
   SDE3/Senior candidate answering the same live interviewer for the same
   question a completed session was asked — batch/offline, no live
   streaming, one blocking HTTP call
   (`session_engine.run_solver_comparison`, `POST
   /sessions/{id}/solver-comparison`). Its session is linked back via a new
   `source_session_id` field on `SessionStartEvent` and a new `"solver"`
   value on `CandidateTurnEvent.input_mode`, capped at `MAX_SOLVER_TURNS =
   25` turns. It is graded identically to a real session but explicitly
   excluded from weak-point tracking (`end_session` checks
   `source_session_id` before calling `weakpoint_store.record_outcome`) —
   that tracker measures the human's own performance only. `HistoryView`
   surfaces it as a badge/link on the source session's row (not its own
   top-level row); `ReportView` shows both reports as two tabs when either
   is opened for a session with a linked pair.

**Phase 10 — Obsidian dropped, scrollback added (2026-09-12):**
1. **Obsidian vault write removed.** User confirmed no Dataview/cross-linking
   use of the vault, so the only things it gave beyond what the web UI
   already covers didn't apply. `report_generator.generate_report` no longer
   writes Markdown or touches `OBSIDIAN_VAULT_PATH` at all — the JSON record
   at `data/reports/{session_id}.json` is now the sole persisted report.
   Since the Markdown frontmatter used to carry fields `GraderOutput` never
   had (pauses, durations, diagram filenames, the full reproducibility
   tuple), a new `report_generator.SessionReportRecord` model absorbs all of
   it so none of that metadata was silently lost in the move.
   `OBSIDIAN_VAULT_PATH` removed from `config._REQUIRED_ENV_VARS` and
   `.env.example`; `report_generator.read_report_frontmatter` deleted;
   `session_engine.get_session_summary` now reads `read_report_json`
   instead. `interview-prep-agent-design.md`/`requirements.md`'s
   Obsidian-centric sections (the architecture diagram box, "Markdown report
   (Obsidian vault)", "queryable via Obsidian Dataview") are superseded by
   this entry and intentionally left unedited as the original historical
   spec, same treatment as Phase 9's report-duplication reversal.
2. **`SessionView` gained a chat scrollback.** Previously each saved answer
   cleared the textarea with no way to see prior answers mid-session. Now
   fetches the session's transcript on mount (`GET /sessions/{id}/transcript`,
   already built for `ReportView`'s reference-answer tab) and appends turns
   optimistically as they're saved, auto-scrolling to the latest.
3. **`ReportView` gained a "My conversation" tab.** Same gap the solver side
   had before "Reference answer" existed - your own critique tab showed
   evidence citations but never the actual conversation. Available on every
   ended session (not gated behind a solver link, since the transcript
   endpoint works for any session_id), alongside the existing solver-side
   tabs when a linked solver run exists.

**Phase 11 — Study-guide agent (undated, backfilled into this plan
2026-09-13):** a fifth agent role, `study_guide`
(`backend/study_guide_agent.py`,
`backend/prompts/study_guide_{hld,lld_deepdive}_v1.md`,
`config.models.study_guide`, `config.study_guide_prompt_version`), was
built and wired but never logged here — this entry backfills it so the
plan stays the source of truth. Generates a one-time cached HTML study
guide grounded in a session's transcript (`session_engine.generate_study_guide`,
`POST /sessions/{id}/study-guide`, cached to
`data/study_guides/{session_id}.html`, `GET`/`exists` endpoints for
read-back); intended to be called on a solver-comparison session so the
teaching material is grounded in a strong reference answer, and if the
session has a `source_session_id`, that source session's failed rubric
dimensions (from its report's `weak_point_outcomes`) are passed in to
weight the guide toward those topics. `ReportView` surfaces it as a
"Study guide" tab (iframe) with a generate button when none exists yet.
No tests exist for `study_guide_agent.py` (`test_solver_agent.py` exists
for the solver role; there is no equivalent `test_study_guide_agent.py`) —
flagged here as a gap, not fixed in this pass.

**Model choice note (2026-09-10):** `config.py`'s model IDs were changed
from `anthropic/claude-sonnet-4.6` to `z-ai/glm-5.3-flash` for all three
roles. Reason: the user's OpenRouter key is scoped to an org workspace
(`bbps`) whose guardrail blocks Anthropic models; `z-ai/glm-5.3-flash` is
allowed and was confirmed working live for interviewer, grader, and
question_sourcing. Requirements.md's "grading model should be pinned
deliberately" note still applies going forward — don't swap this again
without updating `grader_prompt_version`/`rubric_version` expectations if
grading behavior visibly shifts.
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

1. ~~**Rubric anchor/scoring content.**~~ **Resolved 2026-09-13:** authored
   full 1-4 anchor text for all 6 dimensions in both rubrics, calibrated to
   a senior/staff bar (3 = hire at that level on this dimension, 4 = depth
   that stands out even among senior candidates, 1-2 = fell short of the
   bar on this dimension specifically, not "said nothing"). Files renamed
   `hld_v1.yaml` → `hld_v2.yaml` and `lld_deepdive_v1.yaml` →
   `lld_deepdive_v2.yaml` (`version:` field and `config.rubric_version`
   bumped to match) — the anchor text IS the grading criteria, so per the
   reproducibility tuple's own purpose, sessions graded under v1's TODO
   placeholders are not comparable to sessions graded under v2's real
   anchors and must stay distinguishable. All of Phase 9/10's real
   sessions were graded under v1 (recorded as such in their
   `data/reports/*.json`, left untouched as historical record) — treat
   those scores as provisional/uncalibrated, not a baseline to compare
   future v2-graded sessions against.
2. ~~**LLD/Deep-dive rubric dimension list.**~~ **Resolved 2026-09-12:**
   authored as part of the post-launch feature pass below — 6 dimensions
   tailored to both halves of the round (`requirements_clarification`,
   `class_and_interface_design`, `concurrency_and_edge_cases`,
   `extensibility_tradeoffs`, `deep_dive_depth`, `communication_of_tradeoffs`),
   not invented by analogy to HLD's names. `lld_deepdive_v1.yaml` now has a
   real dimension list and grading/report/weak-point code paths are usable
   end-to-end for this round type. Anchor *content* (Flagged item 1) is
   still open for both rubrics.
3. ~~**Weak-point tag taxonomy vs. rubric dimensions.**~~ **Resolved
   2026-09-10:** weak-point tags ARE the rubric dimension names, exactly —
   no separate finer-grained vocabulary. `concurrency_deep_dive` in the
   design doc's grader-output example was not an intentional third
   vocabulary; treat it as illustrative, not literal. Grader-output
   `weak_point_outcomes[].tag` and the weak-point store's keys must equal
   `rubric_loader.load_rubric(round_type).dimension_names()` for that round.
   The report frontmatter's kebab-case `weak_points` example
   (`skipped-capacity-estimation`) is a human-readable rendering the report
   generator derives from the tag + outcome, not a separate stored value.
4. ~~**SearXNG MCP setup.**~~ **Resolved 2026-09-10:** a SearXNG instance is
   already running locally at `http://localhost:10999` with its JSON API
   enabled. Question sourcing calls it directly over HTTP
   (`GET /search?format=json`) rather than through a separate MCP server
   process — no other MCP consumer exists to justify that layer. Configured
   via the new optional `SEARXNG_URL` env var (default
   `http://localhost:10999`). See `backend/searxng_client.py`.
5. ~~**Grader structured-output enforcement mechanism.**~~ **Resolved
   2026-09-10 (architectural call, not evaluative content — mine to make):**
   parse-and-retry, not provider-specific JSON-schema/tool-calling mode —
   keeps the grader provider-agnostic since `config.models.grader` could
   point at any OpenRouter model. The prompt instructs the model to return
   one JSON object matching the grader-output schema; the response is
   parsed and validated against a pydantic model, with up to 3 attempts
   (each retry re-sends the original request plus the previous invalid
   output and the validation error) before raising a clear
   `GraderOutputError` — never a silent fallback to unstructured text.
6. **Diagram image handling for the grader.** **Resolved 2026-09-10
   (architectural call): grader_agent.py takes pre-loaded image bytes as
   input (list of `{checkpoint_id, path, media_type, data}`) — it does not
   itself touch the filesystem, keeping Phase 4 testable without Phase 5's
   session engine. All diagrams referenced by a session's
   `diagram_attached` events are batched into the single grading call as
   separate image content blocks, capped at 5 diagrams and 5MB each (a
   session realistically has at most a handful). A diagram that fails to
   load (missing file, over the cap) is dropped from the image blocks and
   replaced with a text note in the prompt ("diagram at {path} for
   checkpoint {checkpoint_id} could not be loaded") rather than aborting
   the whole grading call — one bad image shouldn't block grading the rest
   of the session.**

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
- [x] Define an event_id scheme and add it as a required field on every
      event type: monotonic per-session sequence number formatted as
      `f"{session_id}_{seq:04d}"`, assigned by the transcript writer at
      append time (not by the caller) so it can never collide, including
      across multiple events at the same checkpoint_id (e.g. an edited
      candidate_turn)
- [x] Define pydantic models (or JSON Schema) for each transcript event type
      in `backend/schemas.py`: `session_start`, `candidate_turn`,
      `interviewer_turn`, `pause_start`, `pause_end`, `diagram_attached`,
      `session_end` — fields per the design doc's example JSONL, plus the
      `event_id` field defined above
- [x] Implement an append-only transcript writer
      (`data/transcripts/{session_id}.jsonl`) in `backend/session_engine.py`
      (or a dedicated `transcript_store.py`) that:
  - validates and appends one JSON object per line
  - refuses to append anything once `session_end` has been written for that
    session_id (application-level immutability guarantee)
  - chmods the file read-only after `session_end` as the secondary
    safeguard the design doc calls for
- [x] Implement `backend/weakpoint_store.py`: read/write
      `data/weakpoints/{round_type}.json`; enforce
      `opportunities == successes + failures + neutral` on every write
      (raise if violated); `success_streak` resets to 0 on any failure,
      increments on success; `last_seen` updates only when `opportunities`
      increments — **tag vocabulary here depends on Flagged item 3** (tags
      are treated as opaque strings here; which vocabulary callers use is
      still unresolved)
- [x] Author `backend/rubrics/hld_v1.yaml` with the 6 dimensions implied by
      the design doc's frontmatter example; mark anchor text as TODO
      (**Flagged item 1**)
- [x] Author `backend/rubrics/lld_deepdive_v1.yaml` — do not invent the
      dimension list by analogy to HLD; stub with an explicit TODO block
      until Flagged item 2 is resolved
- [x] Write a rubric loader that reads dimension names from YAML rather than
      hardcoding HLD/LLD field names (this is what report generation later
      depends on)
- [x] Write pytest tests: valid event round-trip, rejected write after
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
- [x] Implement real HTTP call logic in `openrouter_client.py`: request
      construction, auth header from `config.OPENROUTER_API_KEY`, response
      parsing, error handling for rate limit/timeout/malformed response
- [x] `complete(role=..., messages=...)` resolves the model ID from
      `config.models.<role>` so callers never hardcode a model string
- [x] Resolve **Flagged item 4** (SearXNG MCP connection details) before
      wiring; document the decision in this file once made
- [x] Add `backend/scripts/smoke_openrouter.py`: calls `complete()` for all
      three roles with a trivial prompt, prints responses
- [x] Add `backend/scripts/smoke_searxng.py`: calls the SearXNG MCP search
      tool with a fixed query, prints raw results

**Definition of done**
- A real OpenRouter call succeeds for all three roles, returns parsed text
  — **verified 2026-09-10** with a real key and `z-ai/glm-5.3-flash`
  (`python -m backend.scripts.smoke_openrouter` → "pong" for all three
  roles); also verified the error path earlier (bad key → clean 401)
- A real SearXNG search succeeds, returns result objects with at least
  title/url/snippet — verified live against the local instance
- Both fail with clear, actionable errors on bad auth/config — no silent
  hangs, no raw library stack traces surfacing to the caller — verified for
  both (bad OpenRouter key → 401 message; unreachable SearXNG URL →
  connection-refused message)

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
- [x] Author `backend/prompts/interviewer_hld_v1.md` and
      `interviewer_lld_deepdive_v1.md`: encode the
      `continue | follow_up | interject` contract, "interject only once the
      current thought completes," and confirm the rubric is never included
      in this prompt's context (hidden-rubric requirement)
- [x] Author `backend/prompts/grader_hld_v1.md` and
      `grader_lld_deepdive_v1.md`: instruct structured output matching the
      grader-output shape (per-dimension scores + evidence event IDs +
      verdict + weak_point_outcomes) — enforcement mechanism per
      **Flagged item 5**
- [x] Author `backend/prompts/question_sourcing_v1.md`: encode the
      seniority bar (ambiguity, scale/trade-off reasoning, no single correct
      answer) as an explicit accept/reject check; require a provenance
      record (source URLs, discovered_at, target_level, seniority_eval)
- [x] Implement `backend/question_sourcing.py`: calls SearXNG (direct HTTP,
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
- [x] Implement `backend/interviewer_agent.py`: takes the lightweight
      running state (round type, question, elapsed time, checkpoints so
      far, pause history, diagrams attached) + new candidate turn; returns
      `continue|follow_up|interject` + text matching `interviewer_turn`
- [x] Implement `backend/grader_agent.py`: takes the full transcript (read
      fresh from file) + referenced diagram image bytes per **Flagged item
      6**; applies the rubric loaded from `rubrics/{round_type}_{version}.yaml`;
      returns structured output matching the grader-output shape, with each
      evidence entry's `event_id` set to a real `event_id` value from the
      transcript being graded, never invented
- [x] Add dev CLIs: `backend/scripts/dev_question_sourcing.py`,
      `dev_interviewer_turn.py`, `dev_grade_transcript.py` for direct
      invocation with hand-crafted inputs
- [x] Write pytest tests feeding a hand-authored fixture transcript into the
      grader, asserting output validates against the schema AND that every
      evidence `event_id` exactly matches an `event_id` present in the
      fixture transcript

**Definition of done**
- Question sourcing CLI produces a real accepted question with a fully
  populated provenance record from a live search — **verified live
  2026-09-10**: `dev_question_sourcing --round hld` returned a genuinely
  ambiguous, scale/trade-off-driven rate-limiter question with populated
  `source_urls`, `discovered_at`, `target_level`, and a well-reasoned
  `seniority_eval` explaining why it clears the bar
- Given a weak-point store where tag X has recent failures and a reset
  streak, and tag Y has a long success_streak, running question sourcing
  repeatedly favors tag X over tag Y at a rate clearly above chance —
  proven by test (`test_question_sourcing.py`, three tests, all passing)
- Interviewer CLI, given a hand-crafted running-state + turn, returns a
  valid decision — **verified live 2026-09-10**: `fixtures/turn_ok.json`
  (solid requirements + estimation) → `follow_up`; `fixtures/turn_bad.json`
  (no clarification, no estimation, dismissed caching) → `interject`,
  correctly differentiating the two
- Grader CLI, given a fixture transcript, returns a verdict where every
  evidence `event_id` exactly matches an event_id value present in the
  fixture transcript (not merely a plausible-looking string) — verified by
  test with a mocked model response, AND live 2026-09-10 against a
  hand-built 5-event transcript: correct verdict (REJECT), all 6 HLD
  dimensions scored, every evidence event_id real, weak_point_outcomes
  tags exactly matched rubric dimension names
- Grepping the assembled interviewer prompt/messages for rubric dimension
  names returns zero matches — verified by test and by manual grep of both
  prompt files against all 6 HLD dimension names

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
- [x] Implement lifecycle functions in `backend/session_engine.py`:
      `start_session(round_type)`, `save_checkpoint(session_id, text, input_mode)`,
      `attach_diagram(session_id, checkpoint_id)` (checks
      `EXCALIDRAW_EXPORT_PATH` for the most-recently-modified file, copies it
      into `data/diagrams/{session_id}/`, appends `diagram_attached`),
      `pause(session_id)` / `resume(session_id)` (tracks paused duration,
      excluded from elapsed time), `end_session(session_id)` (appends
      `session_end` with wall_clock/active/paused durations, finalizes
      immutability). No parallel in-memory session-state object — the
      lightweight running state the interviewer needs is reconstructed
      fresh from the transcript on every checkpoint.
- [x] Implement `backend/report_generator.py`: reads transcript + grader
      structured output; writes Markdown into `OBSIDIAN_VAULT_PATH` with
      frontmatter (scores keyed from the round's rubric dimensions,
      weak_points, diagrams, pauses, durations, full reproducibility tuple,
      model IDs) + evidence-linked prose body; scores keys loaded from the
      rubric config, never hardcoded
- [x] Wire grading + weak-point update into `end_session`: on
      `session_end`, call the grader once, persist its structured output,
      update the weak-point store per outcome, then call the report
      generator
- [x] Add `backend/scripts/dev_full_session_dry_run.py`: drives a full fake
      session end-to-end via direct engine calls — start → 2-3 checkpoints →
      one pause/resume → one diagram attach → end → grade → weak-point
      update → report write

**Definition of done**
- A full session runs start-to-finish via direct Python calls, producing an
  immutable `.jsonl` transcript, an updated weak-point JSON file, and a
  Markdown report in the configured vault path — **verified live
  2026-09-10** with `dev_full_session_dry_run --round hld` (run against
  throwaway vault/excalidraw paths, not the real ones, to avoid polluting
  real Obsidian/weak-point data with fake dry-run content — see note below)
- Report frontmatter's `scores` keys exactly equal the active rubric's
  dimension list for that round_type — checked programmatically (enforced
  in `report_generator.generate_report`, which raises if they don't match)
  and confirmed live: both sets equal
  `{capacity_estimation, deep_dive, failure_modes, high_level_design, requirements_clarification, tradeoffs_stated}`
- Any transcript write attempted after `end_session` fails (same invariant
  from Phase 2, now exercised through the real lifecycle) — verified by
  test and live
- `active_seconds + paused_seconds == wall_clock_seconds` on `session_end`
  — verified live (161 + 0 == 161) and by test

**Note on `data/transcripts/` and `data/weakpoints/`:** unlike
`OBSIDIAN_VAULT_PATH`/`EXCALIDRAW_EXPORT_PATH`, these paths are NOT env-
configurable (by design — app-local storage, not per-machine config), so
`dev_full_session_dry_run` always writes real transcript/weak-point files
under this repo's `data/`. The live verification run's fake transcript and
weak-point entries were deleted afterward so they don't bias real future
question selection; only the Obsidian report was redirected to a throwaway
path via env override. Keep this in mind before re-running the dry-run
script - it always writes real (fake-content) rows to `data/transcripts/`
and `data/weakpoints/{round_type}.json` unless you clean up after.

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
- [x] Implement `backend/app.py`, bound to `127.0.0.1` only:
      `POST /sessions` (start), `POST /sessions/{id}/checkpoints` (save
      checkpoint), `POST /sessions/{id}/diagram` (attach latest),
      `POST /sessions/{id}/pause`, `POST /sessions/{id}/resume`,
      `POST /sessions/{id}/end`, `GET /sessions` (history list),
      `GET /sessions/{id}` (session summary — verdict/score summary, not
      the full report, since the UI doesn't duplicate Obsidian). Added
      `session_engine.get_session_summary`/`list_sessions` (read-side
      query functions the routes call into) and
      `report_generator.read_report_frontmatter` (reads verdict/scores back
      from the already-written report instead of duplicating grader-output
      storage).
- [x] Response shapes carry only what the UI needs: elapsed time, latest
      interviewer decision/text (only when not `continue`), pause state,
      checkpoint count
- [x] Add pydantic request validation and clear 4xx/5xx error responses
      (422 on bad request body via FastAPI/pydantic; `SessionEngineError`
      → 400 globally, 404 specifically for "no such session" on
      `GET /sessions/{id}`; `QuestionSourcingError` → 502)
- [x] Add a dev run script/command (`uvicorn backend.app:app --reload`,
      or `python -m backend.app` which calls `uvicorn.run(..., host="127.0.0.1")`)

**Definition of done**
- All routes map 1:1 to `session_engine` functions — no duplicated business
  logic in `app.py`
- Server binds only to localhost; CORS scoped to the frontend dev origin,
  not wildcard — **verified live**: `lsof` showed `TCP localhost:8000
  (LISTEN)`, not `0.0.0.0`
- `GET /sessions/{id}` after completion shows verdict/score summary without
  dumping the full transcript/report — verified live

**Verification**
- `uvicorn backend.app:app --port 8000`, then the full curl sequence —
  **run live 2026-09-10** against throwaway vault/excalidraw paths (same
  real-data-pollution caveat as Phase 5's dry run; cleaned up afterward):
  start → real question with full provenance; checkpoint → real
  `follow_up` decision; pause → `{"paused": true}`; resume →
  `{"paused": false, "duration_seconds": ...}`; diagram attach → path
  returned; `GET /sessions/{id}` mid-session → correct in-progress summary
  with `latest_interviewer_text` populated; end → `{"graded": true,
  "verdict": "REJECT", "report_path": ...}`; `GET /sessions/{id}`
  post-end → verdict + scores, no transcript/report body; `GET /sessions`
  → chronological history with both sessions
- Confirmed server bind address is `127.0.0.1`, not `0.0.0.0`
- 4 new `TestClient`-based unit tests (`test_app.py`, mocked
  `session_engine`) cover request validation (422) and error-code mapping
  (404 unknown session, 400 on `SessionEngineError`) without needing a live
  model call — 21 tests passing overall

---

## Phase 7 — Frontend

**Goal:** Minimal live-session UI first, verified against the running
backend, then pause/diagram-attach/history layered in — following the UI
design principles in the design doc.

**Tasks**
- [x] Scaffold Node/Vite/React app under `frontend/`
- [x] Round-selector screen: two buttons (HLD / LLD+Deep-dive), single click
      straight into the question — no config screen
- [x] Core session view: question pinned at top, one large answer input
      (typed or Spokenly-dictated — same field, no special integration),
      one Save Checkpoint button, no sidebar/secondary panels visible
- [x] Confirm the answer input is a plain, standard-focusable text element
      (native `<textarea>` or equivalent) — not a rich-text/contenteditable
      component that could intercept or mangle OS-level dictation input
      (`SessionView.jsx`'s `.answer-input` is a plain `<textarea>`, no
      contenteditable/rich-text library anywhere in the tree)
- [x] Inline interjection/follow-up panel: distinctly colored, directly
      below the answer box, never a modal — shown only when decision !=
      `continue`
- [x] Quiet elapsed-time display (small, corner, not a countdown) - client-
      side timer (not polling `GET /sessions/{id}`), paused while the
      session is paused
- [x] Pause control (button + visible pause state)
- [x] "Attach latest diagram" button wired to `POST /sessions/{id}/diagram`
- [x] History view: plain chronological list + simple score-trend line
      (inline SVG polyline of average score per graded session, not a
      charting library or dashboard), pulling from `GET /sessions`
- [x] Wire all actions to the Phase 6 API; minimal loading/error states

**Definition of done**
- A full round completes through the UI alone: pick round → see question →
  answer/checkpoint → inline interjections appear only when warranted →
  pause/resume → attach a diagram → end → "session complete" confirmation
  — **implemented, builds cleanly, but NOT run through an actual browser
  this session** (see status note above) - code review confirms the flow
  wires together correctly (response field names match the Phase 6 API
  exactly), but this is not the same as observed behavior
- History view lists past sessions and renders a score trend without
  touching Obsidian — implemented, not visually verified
- No modals, no secondary panels mid-session, elapsed time non-intrusive —
  implemented (single-view component tree, no modal library used, history
  link hidden during `view === "session"`), not visually verified

**Verification**
- Manual run-through with backend running: `npm run dev`, walk one full HLD
  session in the browser, confirm each UI principle bullet holds — **NOT
  DONE. You'll need to do this yourself**: both servers are running
  (frontend http://localhost:5173, backend http://127.0.0.1:8000 using
  your real `.env`, so a real session you run through the UI will write a
  real report to your vault and update your real weak-point store - same
  as Phase 8's real pass, so this doubles as that if you want it to)
- With Spokenly running, focus the answer input and dictate a short test
  phrase — confirm the transcribed text lands in the field exactly as it
  would in any other native text field, with no formatting/structure loss
  — **NOT DONE, needs you** (Spokenly isn't something this session can
  drive)
- Devtools network tab: diagram-attach calls fire only on button click, no
  polling/watcher — **NOT DONE, needs a browser**; code review confirms no
  `setInterval`/polling calls `api.attachDiagram` anywhere, only the button
  handler does
- History view renders correctly after ≥2 completed sessions exist — **NOT
  DONE, needs a browser**

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
