# Interview Prep Agent — Requirements

## Scope
Personal-use tool, single user, no auth/deployment concerns. Not a webapp in the
deployed sense — local script/app backed by OpenRouter.

## Rounds
- **HLD** (system design)
- **LLD / Deep-dive** (combined round type — low-level/OO design and personal-project
  deep-dive share a rubric)
- Behavioral and DSA are explicitly out of scope (deliberate cut, not an oversight)

## Rubrics
- Two separate rubrics: one for HLD, one shared for LLD/Deep-dive
- Each rubric produces per-dimension scores (kept even though verdict is binary)
- Rubric changes must be versioned (`rubric_version`) so trend data stays comparable

## Question sourcing
- Interviewer persona searches the web for questions at SDE3/SSE level
- Before use, the persona must evaluate whether a candidate question genuinely
  demands senior-level judgment (ambiguity, scale/trade-off reasoning, no single
  correct answer) — discard and re-search if it doesn't clear that bar
- No pre-built question bank (deliberately skipped — maintenance hassle)
- Each sourced question keeps a provenance record: source URL, discovery
  timestamp, target level, and the seniority evaluation that accepted it — for
  debugging/reproducibility, not a maintained bank

## Interviewer / grader separation
- Two distinct roles, separate prompts/configuration (can share a model
  initially, but responsibilities and prompts stay separate):
  - **Interviewer** — live interaction: questioning, follow-ups, deciding
    whether to interject, deciding whether a diagram would help
  - **Grader** — post-session only: rubric scoring, weak-point identification,
    SELECT/REJECT verdict
- The grader evaluates the raw transcript independently — it does not just
  trust the interviewer's in-session observations
- The rubric (scoring dimensions, thresholds, weak-point weights) is hidden
  from the session-facing interviewer persona and never shown to you during a
  live session, so you can't unconsciously optimize against it. You still see
  and edit the rubric outside of session context, since you're building it.
- Every meaningful score or weak-point claim in a report should be traceable
  to a specific transcript excerpt or event, not asserted vaguely

## Deep-dive input
- User feeds their resume; interviewer probes projects from it (distributed
  systems/sharding work etc.)

## Session structure
- No fixed cadence — user takes whichever round, whenever
- 1 hour per round (HLD and LLD/Deep-dive are separate sittings, not combined)
- Pausing is allowed mid-session, but is logged as a realism factor in the report
  (not neutral) — noted with rough duration/point in the round; recurring pauses
  across sessions become a tracked pattern, since real interviews don't pause

## In-session interjection
- Trigger: on-save only (no timer) — keeps checkpoint timing under user control,
  avoids clock-driven interruption of mid-thought reasoning
- Interviewer-judgment call on what counts as "going wrong" — technical or
  process errors both qualify, no fixed checklist
- If wrong: interject immediately (once the claim is complete, not mid-sentence)
- If fine: hold feedback until the user finishes speaking/typing
- The interviewer operates on a lightweight running state (round type,
  question, elapsed time, checkpoints so far, pause history, diagrams attached)
  rather than re-deriving context from the full transcript every turn — kept
  as a simple evolving object, not a separate state-management service, and
  without a parallel "tracked claims/suspected weaknesses" model (that's the
  grader's job post-session, not the interviewer's)
- Each checkpoint runs a simple loop: evaluate current state → decide
  continue / ask follow-up / interject → act

## Diagrams
- Optional, interviewer's call whether to prompt for one
- Applies to both HLD (system diagrams) and LLD/Deep-dive (class/sequence
  diagrams, interface sketches)
- A diagram improves the score only when it demonstrates useful reasoning or
  communication — existence of a diagram is not itself a bonus
- Metadata stored per diagram: path/reference, PNG/SVG type, checkpoint_id,
  whether volunteered or requested, timestamp — so the report can connect the
  diagram back to the surrounding transcript
- Tooling: drawing happens externally in Excalidraw/Obsidian (not inside the
  session UI); the plugin auto-exports PNG/SVG on save; the resulting image is
  attached into the session UI at a checkpoint, not embedded as a live canvas

## Grading standard
- Harsh, critical — binary reject/select as the headline verdict
- Calibrated to a generic "strong senior engineer" bar (not company-specific —
  deliberately deferred as too complex for now)
- Verdict delivered only after the full session is evaluated end-to-end (not
  mid-session)
- Per-dimension scores preserved underneath the binary verdict — this is what
  weak-point tracking and trend charts run on, so progress is visible even when
  the verdict itself stays harsh

## Weakness targeting ("gradually improving me")
- Weighted (not exclusive) sampling toward tagged weak points for next
  session's question selection
- Per weak-point tag, track simple counters filled in by the grader each
  session: `opportunities` (was this skill actually relevant/testable this
  session), `failures`, `successes`, `last_seen` — not just presence/absence
  in the last N sessions
- Decay happens primarily after repeated successful demonstrations, not
  merely after sessions where the topic didn't come up (a weakness that was
  never re-tested shouldn't quietly decay)

## UI
- Local, single-user web app (no auth) — hosts the **full live session**:
  question display, answer input (typed or Spokenly-dictated into the same
  field), interjections, save/checkpoint trigger, pause control
- Also serves as the browsing surface for session history/reports and for
  selecting/starting rounds
- Diagrams are not drawn inside the UI — see Diagrams section

## Storage
Two distinct artifacts, kept separate:
- **Raw transcript** (app-local, not in the Obsidian vault) — a typed event
  stream, not plain speaker/text records: events like `candidate_turn`,
  `interviewer_turn`, `checkpoint`, `interjection`, `pause_start`, `pause_end`,
  `diagram_attached`, each timestamped and tagged with a `checkpoint_id` where
  applicable. One `.jsonl` per session. This is what the grader actually reads.
  Immutable once the session ends — the authoritative evidence, never edited
  after the fact.
- **Markdown report** (Obsidian vault) — a derived artifact generated *from*
  the transcript after the session ends; never the source of truth. YAML
  frontmatter for machine-queryable fields (scores, weak-point counters,
  rubric_version, interviewer/grader/question-sourcing prompt versions, model
  ID, diagram links), prose critique with evidence pointers in the body;
  queried via Obsidian Dataview for trends
- Each evaluation is versioned as a **reproducibility tuple**: rubric_version,
  interviewer prompt version, grader prompt version, question-sourcing prompt
  version, model/provider/model ID — plain version strings bumped by hand when
  a prompt changes, not a config-management system
- Storage is structured so a past session *could* be re-graded later under a
  newer rubric/prompt without touching the original transcript or evaluation
  (new evaluation appended, old one kept) — this is a deferred capability, not
  something to build now; just don't design storage in a way that blocks it

## Model / consistency
- OpenRouter as backend, with per-task model routing
- Grading/scoring model should be pinned deliberately — model swaps are a known
  source of silent drift in both rubric scoring and "harshness" calibration, and
  at personal scale that drift would be indistinguishable from real progress/regression

## Voice input
- Spokenly for dictating verbal answers (behavioral-style delivery within
  HLD/LLD rounds); MCP server integration available if built on Claude Code
- Transcripts should be evaluated raw (not AI-cleaned) if communication clarity
  is ever part of scoring

## Still open / deferred
- None outstanding from this requirements pass — ready to move to design/
  implementation discussion when you are.
