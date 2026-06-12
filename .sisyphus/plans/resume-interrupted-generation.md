# Resume Interrupted Generation Sessions

## TL;DR
> **Summary**: Add a local, crash-safe unfinished-session recovery system to the Qt desktop app so long generation jobs can continue after power loss or forced shutdown without regenerating completed chunks.
> **Deliverables**:
> - Versioned session manifest + per-session workspace
> - Chunk-level persisted audio artifacts
> - Explicit “unfinished sessions” recovery UI with Resume/Delete actions
> - Live generation timer + persisted cumulative elapsed time for resumed jobs
> - CUDA soft-throttle policy to reduce 100% utilization spikes during long runs
> - Resume-aware worker path for clone + design modes
> - Automated verification for manifest integrity, resume behavior, and edge cases
> **Effort**: Medium
> **Parallel**: YES - 2 waves
> **Critical Path**: 1 → 2 → 3 → 5 → 7

## Context
### Original Request
Update the software so interrupted work sessions can continue later. Example: if the app generated only half a script before power loss, reopening the app should let the user continue that exact session instead of starting over.

### Interview Summary
- Recovery target is the existing local Qt desktop app in `omnivoice_qt_app.py`.
- Recovery is only for unfinished local generation sessions.
- UX decision: **no auto-resume and no startup recovery popup**.
- Recovery must be user-initiated from a session-history/recovery surface.
- Scope is unfinished-generation recovery, not cloud sync and not a full media library.
- User also wants a visible timer showing how long generation has been running.
- User also wants the app to avoid occasional 100% GPU spikes that make the machine unstable.

### Metis Review (gaps addressed)
- Use a **versioned manifest schema** and **atomic writes** for manifest + chunk artifacts.
- Copy clone-mode reference audio into the session folder; do not rely on OS temp files for resumable inputs.
- Keep the UI narrow: unfinished-session recovery list with Resume/Delete only.
- Define precise status transitions: `running`, `interrupted`, `failed`, `cancelled`, `completed`, `invalid`.
- Handle corrupt manifest / missing chunk / missing reference audio / disk-write failures explicitly.
- Integrate the timer into the same session state so resumed jobs show cumulative elapsed time rather than resetting misleadingly.
- GPU load policy is **best-effort soft throttling inside app code**, not a hard guarantee of exactly 99% utilization at every instant.
- Throttling must stay inside the Qt app/runtime path and must NOT depend on NVIDIA driver tools, `nvidia-smi`, MSI Afterburner, or OS power-limit utilities.

## Work Objectives
### Core Objective
Make long-running clone/design generation resumable after app interruption by persisting enough local state during generation to restart from the first unfinished chunk.

### Deliverables
- A local session workspace root for resumable jobs.
- A `SessionManager`-style helper responsible for creating, reading, validating, updating, and deleting session folders/manifests.
- A resume-capable worker flow integrated into the existing `_start_*` → `_run_worker()` → `GenerationWorker.run()` path.
- A recovery/history UI surface listing unfinished sessions and allowing explicit Resume/Delete.
- A live elapsed timer on the active generation UI plus persisted elapsed metadata shown for unfinished sessions.
- A CUDA soft-throttle mechanism that reduces sustained full-load spikes without breaking resume, cancel, or output correctness.
- Automated tests or scriptable checks for manifest integrity, resume correctness, and failure handling.

### Definition of Done (verifiable conditions with commands)
- `python -m py_compile omnivoice_qt_app.py` succeeds.
- Automated checks verify that a simulated interrupted session resumes from the first incomplete chunk rather than regenerating completed chunks.
- Automated checks verify that unfinished sessions appear in recovery/history data and are not auto-resumed on app startup.
- Automated checks verify that the elapsed timer updates while generation is running and that resumed sessions continue from persisted cumulative elapsed time.
- Automated checks verify that CUDA throttle hooks run only on CUDA paths and introduce bounded inter-chunk cooldown behavior without affecting correctness.
- Automated checks verify clone-mode resume still works after the original temp reference file is removed, using the copied session-local reference audio.
- Automated checks verify corrupt manifest or missing chunk files do not crash the app.

### Must Have
- Local-only persistence.
- One folder per session using generated session IDs, not user text.
- Manifest schema versioning.
- Atomic writes for manifest and chunk audio artifacts.
- Clone + design mode support.
- Explicit Resume/Delete actions.
- No data loss for completed chunks after crash.
- Visible elapsed-time display during active generation and persisted elapsed-time metadata for recovery.
- CUDA soft-throttle active during long generation jobs with conservative defaults.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Must NOT auto-popup a recovery modal on launch.
- Must NOT auto-resume any session on launch.
- Must NOT build cloud sync, multi-device sync, or remote queueing.
- Must NOT turn recovery UI into a full media library/history browser.
- Must NOT require users to manually browse filesystem folders.
- Must NOT rely on OS temp files for resumable reference audio.
- Must NOT rewrite the core generation algorithm beyond the minimal hooks needed for persistence/resume.
- Must NOT show a timer that silently resets on resume without telling the truth about total elapsed runtime.
- Must NOT claim a mathematically exact 99% GPU cap when the implementation is only best-effort app-side throttling.
- Must NOT add dependencies on external GPU control tools or vendor-specific tuning software.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: **tests-after** using Python test scripts / targeted harnesses, because no app-level test framework exists today.
- QA policy: Every task includes agent-executed scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.

Wave 1: foundation + persistence contracts
- T1 session workspace root + schema
- T2 session manager helper
- T3 durable clone reference/input capture
- T4 recovery list data model / filtering
- T5 elapsed-time model for live + resumed jobs

Wave 2: runtime integration + UI + verification
- T6 worker chunk persistence + atomic updates
- T7 resume execution path
- T8 CUDA soft-throttle policy in generation runtime
- T9 unfinished-session recovery UI + live timer display
- T10 cleanup / retention / invalid-session handling
- T11 automated verification harness

### Dependency Matrix (full, all tasks)
- T1: no blockers
- T2: blocked by T1
- T3: blocked by T1
- T4: blocked by T2
- T5: blocked by T2
- T6: blocked by T2, T3, T5
- T7: blocked by T2, T5, T6
- T8: blocked by T5, T6
- T9: blocked by T4, T5, T7
- T10: blocked by T2, T4
- T11: blocked by T6, T7, T8, T9, T10
- F1-F4: blocked by T1-T11

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 5 tasks → quick / unspecified-high
- Wave 2 → 6 tasks → unspecified-high / deep / visual-engineering
- Final Verification → 4 review tasks → oracle / unspecified-high / deep

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. Define resumable session storage contract

  **What to do**: Introduce a single app-managed sessions root and a versioned folder layout for resumable jobs. Define the folder structure, naming, manifest file name, chunk subfolder, reference-audio subfolder, and final-output artifact path. The chosen root must be stable across restarts on Windows and local-only; prefer a dedicated app data location over the repo root or OS temp. Define manifest statuses and allowed transitions: `running` → `completed`; `running`/`failed write`/abrupt shutdown` -> recover as `interrupted`; `cancelled`; `failed`; `invalid` for unreadable/corrupt sessions discovered during scan.
  **Must NOT do**: Must NOT use user text as folder name. Must NOT store resumable artifacts only in `%TEMP%`. Must NOT add database/ORM.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: bounded filesystem/schema design grounded in existing desktop app.
  - Skills: `[]` - no special domain skill needed.
  - Omitted: `[nodejs-best-practices, frontend-design]` - not relevant to local PySide persistence.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T2, T3, T5 | Blocked By: none

  **References**:
  - Pattern: `omnivoice_qt_app.py:1766-1788` - current clone reference preprocessing writes temp WAVs and needs a durable replacement for resumable jobs.
  - Pattern: `omnivoice_qt_app.py:1858-1861` - `_runtime_state` is currently in-memory only.
  - Pattern: `omnivoice_qt_app.py:2212-2218` - final output save is manual today; resumable storage must exist independently.
  - External: `https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid` - if using Windows app-data conventions.

  **Acceptance Criteria**:
  - [ ] A documented session folder schema exists in code comments or helper docstrings and is used consistently by persistence code.
  - [ ] New session IDs are generated independently of user text and produce filesystem-safe paths.
  - [ ] Resumable sessions root survives app restart and does not rely on temp directories.

  **QA Scenarios**:
  ```
  Scenario: Session path contract is stable
    Tool: Bash
    Steps: Run a script/harness that creates a new session record twice and prints both resolved roots and session folder names.
    Expected: Both sessions use the same stable root; folder names are generated IDs, not text snippets.
    Evidence: .sisyphus/evidence/task-1-session-root.txt

  Scenario: Invalid user text cannot break folder naming
    Tool: Bash
    Steps: Run the same harness with text containing `<>:"/\\|?*` and non-ASCII Vietnamese.
    Expected: Session folder creation still succeeds because folder name is generated from session ID, not raw text.
    Evidence: .sisyphus/evidence/task-1-invalid-filename.txt
  ```

  **Commit**: YES | Message: `feat(session): define resumable storage contract` | Files: `omnivoice_qt_app.py`, new helper module(s)

- [ ] 2. Add a SessionManager helper with versioned manifest I/O

  **What to do**: Implement a focused helper class/module responsible for creating session folders, writing the initial manifest, atomically updating manifest state, validating discovered sessions, resolving chunk paths, resolving copied reference-audio paths, and deleting sessions. Manifest must include at least: `schema_version`, `session_id`, `mode`, `status`, `created_at`, `updated_at`, `text`, `text_preview`, `chunk_plan`, `completed_chunk_indexes` or per-chunk statuses, generation config snapshot, artifacts paths, and error metadata. Include forward-compat behavior for unknown schema versions: mark unreadable/unsupported sessions as `invalid` and do not crash the app.
  **Must NOT do**: Must NOT embed UI behavior into SessionManager. Must NOT silently ignore JSON corruption without marking session invalid.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: persistence logic, validation, atomic writes, and schema/version handling.
  - Skills: `[]`
  - Omitted: `[frontend-design]` - not a UI design task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: T4, T5, T6, T8 | Blocked By: T1

  **References**:
  - Pattern: `omnivoice_qt_app.py:579` - current runtime state is a transient dict only.
  - Pattern: `omnivoice_qt_app.py:294-297` - worker signal contract indicates where session events will integrate.
  - Pattern: `omnivoice_qt_app.py:411-537` - manifest updates must align with worker lifecycle.

  **Acceptance Criteria**:
  - [ ] Initial manifest creation writes valid JSON with `schema_version` and `status`.
  - [ ] Manifest updates use atomic replace semantics (`tmp` write then replace), leaving valid JSON after simulated interruption points.
  - [ ] Unsupported/corrupt manifests are classified as invalid without crashing the scanner.

  **QA Scenarios**:
  ```
  Scenario: Manifest create and update remain valid JSON
    Tool: Bash
    Steps: Run a Python harness that creates a session, updates progress for chunk 0, reloads the manifest, and validates required keys.
    Expected: JSON parses successfully before and after updates; required fields are present.
    Evidence: .sisyphus/evidence/task-2-manifest-valid.txt

  Scenario: Corrupt manifest is isolated
    Tool: Bash
    Steps: Write an invalid `manifest.json` into one fake session folder, then run the discovery/validation harness across the sessions root.
    Expected: The corrupt session is flagged `invalid` or skipped according to design; valid sessions still load.
    Evidence: .sisyphus/evidence/task-2-corrupt-manifest.txt
  ```

  **Commit**: YES | Message: `feat(session): add session manager and manifest io` | Files: helper module(s), `omnivoice_qt_app.py`

- [ ] 3. Persist resumable inputs for clone and design sessions

  **What to do**: Capture all data required to resume before generation starts. For clone mode, copy the trimmed reference WAV produced by `_prepare_reference_audio()` into the session folder and store that durable path in the manifest. Persist the input text, text preview, language, speed, duration, chunking inputs, transcript/ref_text, and generation config snapshot. For design mode, persist the same runtime inputs except clone artifacts. Ensure resume does not depend on `self.current_processed_ref` or transient OS temp paths surviving reboot.
  **Must NOT do**: Must NOT keep resumable clone sessions pointing at the temp file returned by `tempfile.NamedTemporaryFile(...)`. Must NOT omit any worker-required payload fields from the persisted snapshot.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: clear hook points in `_prepare_reference_audio()` and `_start_*_generation()`.
  - Skills: `[]`
  - Omitted: `[accessibility]` - no a11y changes here.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T5, T6 | Blocked By: T1

  **References**:
  - Pattern: `omnivoice_qt_app.py:1766-1788` - `_prepare_reference_audio()` currently emits temp WAVs.
  - Pattern: `omnivoice_qt_app.py:1793-1821` - clone payload fields to persist.
  - Pattern: `omnivoice_qt_app.py:1831-1846` - design payload fields to persist.
  - Pattern: `omnivoice_qt_app.py:2145-2152` - runtime summary enumerates the current payload surface.

  **Acceptance Criteria**:
  - [ ] Starting a clone session copies the processed reference WAV into a session-local path before worker execution.
  - [ ] Deleting the original temp reference file does not make the session unrecoverable.
  - [ ] Persisted payload data is sufficient to reconstruct the worker payload for both clone and design modes.

  **QA Scenarios**:
  ```
  Scenario: Clone session keeps durable reference audio
    Tool: Bash
    Steps: Start a clone-session harness, capture the generated session folder, delete the original temp WAV, and reload session metadata.
    Expected: Session still points to a session-local reference WAV that exists.
    Evidence: .sisyphus/evidence/task-3-durable-ref.txt

  Scenario: Design session snapshot is reconstructable
    Tool: Bash
    Steps: Create a design session snapshot and run a reconstruction helper that rebuilds the worker payload from manifest data.
    Expected: Reconstructed payload contains text, language, config, instruct, speed, duration, and chunk settings.
    Evidence: .sisyphus/evidence/task-3-design-payload.txt
  ```

  **Commit**: YES | Message: `feat(session): persist resumable generation inputs` | Files: `omnivoice_qt_app.py`, helper module(s)

- [ ] 4. Implement unfinished-session discovery and filtering

  **What to do**: Build a discovery layer that scans the session root, validates manifests, and returns a list of unfinished recoverable sessions for the UI. By default, list only statuses relevant to the recovery surface: `interrupted`, optionally `failed` if resumable, and optionally `cancelled` only if product behavior explicitly keeps cancellations resumable. Completed sessions must not clutter the unfinished list. Invalid/corrupt sessions must be safely classified so the app stays usable.
  **Must NOT do**: Must NOT turn this into a generic history browser for every past job. Must NOT list completed sessions in the unfinished recovery view.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: bounded data filtering on top of SessionManager.
  - Skills: `[]`
  - Omitted: `[frontend-design]` - no UI composition yet.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T7, T8 | Blocked By: T2

  **References**:
  - Pattern: `omnivoice_qt_app.py:555-579` - no current history/session state exists, so recovery list must be introduced cleanly.
  - Pattern: `omnivoice_qt_app.py:2155-2167` - runtime metadata available for previews/progress summaries.

  **Acceptance Criteria**:
  - [ ] Discovery returns unfinished sessions with enough metadata for identification: timestamp, mode, progress, text preview.
  - [ ] Completed sessions are excluded from the unfinished recovery list.
  - [ ] Invalid/corrupt sessions do not crash discovery.

  **QA Scenarios**:
  ```
  Scenario: Only unfinished sessions appear
    Tool: Bash
    Steps: Seed one `completed`, one `interrupted`, and one `invalid` session manifest, then run the discovery harness.
    Expected: The returned recovery list contains the interrupted session only; invalid is quarantined or flagged separately; completed is omitted.
    Evidence: .sisyphus/evidence/task-4-discovery-filter.txt

  Scenario: Multiple unfinished sessions are ordered predictably
    Tool: Bash
    Steps: Seed at least three interrupted sessions with different timestamps and run discovery.
    Expected: Output ordering matches the plan’s chosen sort rule, e.g. most recently updated first.
    Evidence: .sisyphus/evidence/task-4-ordering.txt
  ```

  **Commit**: YES | Message: `feat(session): add unfinished session discovery` | Files: helper module(s), `omnivoice_qt_app.py`

- [ ] 5. Add a cumulative elapsed-time model for active and resumed jobs

  **What to do**: Introduce explicit elapsed-time tracking for generation sessions. Reuse the current `started_at` / `_elapsed_for_mode()` concept, but upgrade it so the app can display a live timer while generation is running and preserve cumulative elapsed time across interruptions. Persist timing metadata in the session manifest, including at minimum current run start time, cumulative elapsed seconds from prior runs, and last updated timestamp. Define the display rule clearly: the active generation UI shows a live cumulative timer; unfinished sessions in recovery view show the last persisted elapsed duration. On resume, the live timer must continue from previously accumulated time rather than resetting to zero.
  **Must NOT do**: Must NOT treat resumed jobs as brand-new jobs with elapsed time reset to zero. Must NOT display ambiguous time that mixes wall-clock downtime after a crash into active generation time unless that is explicitly intended.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: builds on existing `_runtime_state.started_at` and `_elapsed_for_mode()` without changing the generation algorithm.
  - Skills: `[]`
  - Omitted: `[frontend-design]` - behavior/state first, not visual styling.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: T6, T7, T8, T10 | Blocked By: T2

  **References**:
  - Pattern: `omnivoice_qt_app.py:1858-1861` - current runtime state already stores `started_at`.
  - Pattern: `omnivoice_qt_app.py:2155-2159` - `_elapsed_for_mode()` already computes current elapsed time from `started_at`.
  - Pattern: `omnivoice_qt_app.py:1973-2001` - completion summary already displays elapsed seconds after success.
  - Pattern: `omnivoice_qt_app.py:2037-2066` - cancellation/error summaries already use elapsed time after interruption.

  **Acceptance Criteria**:
  - [ ] Active generation UI shows a live elapsed timer while a job is running.
  - [ ] Session manifest stores cumulative elapsed-time metadata sufficient for resumed jobs.
  - [ ] Resumed jobs continue the live timer from prior accumulated active runtime, not from zero.

  **QA Scenarios**:
  ```
  Scenario: Live timer increments during active generation
    Tool: Bash
    Steps: Launch a deterministic fake-generation harness, sample timer text/state at two different moments during the same run.
    Expected: The later sample shows a larger elapsed time than the earlier sample.
    Evidence: .sisyphus/evidence/task-5-live-timer.txt

  Scenario: Resume preserves cumulative elapsed time
    Tool: Bash
    Steps: Seed an interrupted session with persisted elapsed seconds, resume it, and sample the live timer immediately after resume starts.
    Expected: The displayed elapsed time starts from at least the persisted cumulative value, not near zero.
    Evidence: .sisyphus/evidence/task-5-resume-timer.txt
  ```

  **Commit**: YES | Message: `feat(session): add cumulative generation timer model` | Files: `omnivoice_qt_app.py`, helper module(s)

- [ ] 6. Persist chunk outputs and state during GenerationWorker.run

  **What to do**: Extend `GenerationWorker.run()` so each chunk is treated as an independently persisted unit. Before generation, compute the chunk plan once and register it in the manifest. During the chunk loop, after each chunk succeeds, write the chunk audio to a deterministic path such as `chunks/0000.wav`, then atomically update manifest status/progress only after the file exists. On startup recovery, the persisted chunks must be the source of truth for already-finished work. If the app exits while a chunk is being generated or written, the session must remain recoverable from the last fully completed chunk.
  **Must NOT do**: Must NOT mark a chunk complete before its audio file exists. Must NOT keep completed chunks only in RAM. Must NOT break existing progress signaling.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: high-risk integration inside the worker lifecycle with filesystem durability.
  - Skills: `[]`
  - Omitted: `[review-work]` - not for implementation itself.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: T7, T10 | Blocked By: T2, T3, T5

  **References**:
  - Pattern: `omnivoice_qt_app.py:411-537` - exact worker execution loop and progress emissions.
  - Pattern: `omnivoice_qt_app.py:460-492` - existing chunk loop and append-only in-memory behavior.
  - Pattern: `omnivoice_qt_app.py:494-534` - final concatenation and success emission path.
  - Pattern: `omnivoice_qt_app.py:308-316` - cancellation checks must stay safe.

  **Acceptance Criteria**:
  - [ ] Each completed chunk produces a persisted chunk WAV file before manifest marks it completed.
  - [ ] Simulated interruption after chunk N leaves a valid manifest and chunk files `0..N` recoverable.
  - [ ] Existing progress updates still emit meaningful chunk progress during normal generation.

  **QA Scenarios**:
  ```
  Scenario: Simulated crash after first completed chunk
    Tool: Bash
    Steps: Run a fake-model harness that generates chunk 0, persists it, then raises a controlled exception before chunk 1 completes.
    Expected: `chunks/0000.wav` exists, manifest remains valid JSON, and chunk 0 is the last completed chunk.
    Evidence: .sisyphus/evidence/task-5-crash-after-chunk.txt

  Scenario: Mid-write safety preserves last good chunk
    Tool: Bash
    Steps: Simulate a write failure while persisting chunk 1.
    Expected: Chunk 1 is not marked complete; chunk 0 remains complete and resumable.
    Evidence: .sisyphus/evidence/task-5-write-failure.txt
  ```

  **Commit**: YES | Message: `feat(session): persist chunk outputs during generation` | Files: `omnivoice_qt_app.py`, helper module(s)

- [ ] 7. Add resume-aware worker bootstrap and final reconstruction

  **What to do**: Extend the worker bootstrap so a resumed session can be rebuilt from the manifest instead of from live UI state alone. Resume must load the stored payload/config, validate required artifacts, load already-completed chunk audio from disk, and continue from the first incomplete chunk only. On successful completion, reconstruct the final audio in correct chunk order from persisted + newly generated chunks, then continue through the normal success path (`self.audio_output`, play button, manual save). If a completed chunk is missing on disk, apply the chosen rule consistently: mark it incomplete and regenerate from that chunk index.
  **Must NOT do**: Must NOT regenerate already-completed chunks in the happy path. Must NOT bypass the normal success/save flow after resume.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: this is the core resume behavior and must reconcile persisted and live generation outputs.
  - Skills: `[]`
  - Omitted: `[nodejs-backend-patterns]` - irrelevant.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: T8, T10 | Blocked By: T2, T5, T6

  **References**:
  - Pattern: `omnivoice_qt_app.py:1848-1951` - `_run_worker()` bootstrap path.
  - Pattern: `omnivoice_qt_app.py:1964-2031` - `_on_worker_success()` normal post-generation behavior to preserve.
  - Pattern: `omnivoice_qt_app.py:2212-2218` - manual save behavior must remain intact.

  **Acceptance Criteria**:
  - [ ] Resume starts generation from the first incomplete chunk only.
  - [ ] Final combined output after resume contains earlier persisted chunks plus newly generated chunks in order.
  - [ ] Normal play/save UI continues working after resumed completion.

  **QA Scenarios**:
  ```
  Scenario: Resume skips completed chunks
    Tool: Bash
    Steps: Seed a resumable session with 3 chunks where chunk 0 is complete, then run resume using a fake backend that logs every generated chunk index.
    Expected: Backend is called only for chunks 1 and 2; final reconstructed audio includes 0,1,2 in order.
    Evidence: .sisyphus/evidence/task-6-resume-skip.txt

  Scenario: Missing completed chunk regenerates from first broken index
    Tool: Bash
    Steps: Mark chunk 0 complete in manifest but delete `chunks/0000.wav`, then run resume.
    Expected: Resume detects inconsistency and regenerates from chunk 0 according to the documented rule.
    Evidence: .sisyphus/evidence/task-6-missing-chunk.txt
  ```

  **Commit**: YES | Message: `feat(session): resume unfinished generation sessions` | Files: `omnivoice_qt_app.py`, helper module(s)

- [ ] 8. Add CUDA soft-throttle policy to generation runtime

  **What to do**: Implement a conservative, best-effort GPU soft-throttle inside the Qt app runtime for CUDA generation. The throttle must activate only when the model device resolves to CUDA and must reduce full-load spikes without depending on external NVIDIA tools. Preferred design: introduce a small configurable cooldown between completed chunks, optional micro-cooldown after especially long chunks, and lightweight cache/yield points that do not change output semantics. Keep defaults conservative and always-on for CUDA unless later exposed in advanced settings. The mechanism must NOT pretend to enforce an exact 99% cap; its contract is to reduce sustained 100% spikes and improve machine responsiveness.
  **Must NOT do**: Must NOT shell out to `nvidia-smi` or require MSI Afterburner/driver utilities. Must NOT sleep inside inner model math loops if that requires invasive model surgery. Must NOT change generated text/audio content beyond timing/cooldown between chunks.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: runtime performance control around GPU-heavy generation with correctness constraints.
  - Skills: `[]`
  - Omitted: `[frontend-design]` - not a UI-first task.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: T11 | Blocked By: T5, T6

  **References**:
  - Pattern: `omnivoice_qt_app.py:399-447` - chunk loop in `GenerationWorker.run()` is the safest throttle insertion point.
  - Pattern: `omnivoice_qt_app.py:454-459` - existing post-generation CUDA cleanup already touches `torch.cuda.empty_cache()`.
  - Pattern: `omnivoice_qt_app.py:1790-1796` - app already applies CPU-thread limiting via `OMP_NUM_THREADS` and `torch.set_num_threads(1)`.

  **Acceptance Criteria**:
  - [ ] Soft-throttle logic runs only on CUDA generation paths.
  - [ ] Throttle introduces bounded cooldown/yield behavior around chunk boundaries without breaking cancel/resume logic.
  - [ ] Normal generation output ordering and resume correctness remain unchanged.

  **QA Scenarios**:
  ```
  Scenario: CUDA throttle hook activates only for CUDA sessions
    Tool: Bash
    Steps: Run a fake or monkeypatched generation harness once with device reported as `cuda` and once as `cpu`, logging throttle invocations.
    Expected: Throttle activity is recorded for CUDA only; CPU path shows no throttle hook.
    Evidence: .sisyphus/evidence/task-8-cuda-throttle-scope.txt

  Scenario: Resume remains correct with throttle enabled
    Tool: Bash
    Steps: Run the resume harness with CUDA-throttle settings enabled across a multi-chunk interrupted session.
    Expected: Resume still skips completed chunks and final output ordering is unchanged.
    Evidence: .sisyphus/evidence/task-8-cuda-throttle-resume.txt
  ```

  **Commit**: YES | Message: `perf(cuda): add soft throttle for generation spikes` | Files: `omnivoice_qt_app.py`

- [ ] 9. Add explicit recovery/history UI and live timer display

  **What to do**: Add a minimal unfinished-session recovery surface to the Qt app and expose the new timer in the active generation UI. The recovery surface must allow users to inspect unfinished sessions and choose Resume/Delete explicitly. Each recovery item must include enough metadata to distinguish sessions: mode, created/updated time, progress `completed/total`, persisted elapsed time, text preview, and relevant clone/design summary. The active generation UI must show a live elapsed timer that updates while the worker runs. Launch behavior must remain quiet: no modal popup and no auto-resume.
  **Must NOT do**: Must NOT auto-open a modal recovery popup on app startup. Must NOT expose completed sessions in this view. Must NOT balloon into waveform previews, search, tags, or a media library. Must NOT show different elapsed-time semantics between active view and recovery list.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` - Reason: focused desktop UI addition with clear UX guardrails.
  - Skills: `[]`
  - Omitted: `[frontend-design]` - useful for web polish, but this is a narrow PySide recovery surface rather than a design-heavy web task.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: T11 | Blocked By: T4, T5, T7

  **References**:
  - Pattern: `omnivoice_qt_app.py:555-579` - main window runtime state where recovery surface will attach.
  - Pattern: `omnivoice_qt_app.py:1953-1961` - progress/status language to mirror.
  - Pattern: `omnivoice_qt_app.py:2124-2153` - runtime summary formatting to reuse for compact metadata.
  - Pattern: `omnivoice_qt_app.py:2155-2159` - current elapsed-time helper to extend for live display.

  **Acceptance Criteria**:
  - [ ] App startup does not auto-popup or auto-resume even when unfinished sessions exist.
  - [ ] Recovery UI lists unfinished sessions with metadata including persisted elapsed time and working Resume/Delete actions.
  - [ ] Active generation screen shows a live elapsed timer while a job is running.
  - [ ] Resume action uses manifest-backed data; Delete action removes session files and updates the view.

  **QA Scenarios**:
  ```
  Scenario: Relaunch stays quiet but recovery list is available
    Tool: Bash
    Steps: Seed an unfinished session, launch the app in an automated harness or direct UI-state test, and inspect startup behavior plus recovery-list population.
    Expected: No recovery modal appears and no worker starts automatically; the unfinished session is present when the recovery surface loads with persisted elapsed time shown.
    Evidence: .sisyphus/evidence/task-7-no-autopopup.txt

  Scenario: Delete action removes unfinished session
    Tool: Bash
    Steps: Seed an unfinished session, invoke the delete path programmatically or through scripted UI interaction, then rescan recovery data.
    Expected: Session folder is removed and the recovery list no longer contains it.
    Evidence: .sisyphus/evidence/task-7-delete-session.txt

  Scenario: Active timer is visible during generation
    Tool: Bash
    Steps: Start a fake generation run and query the active UI state twice while the worker is still running.
    Expected: The timer control/text exists and shows increasing elapsed time.
    Evidence: .sisyphus/evidence/task-7-active-timer.txt
  ```

  **Commit**: YES | Message: `feat(ui): add unfinished session recovery list` | Files: `omnivoice_qt_app.py`, helper module(s)

- [ ] 10. Define cancellation, failure, cleanup, and retention behavior

  **What to do**: Make session lifecycle rules explicit and implement them consistently. Cancellation should not accidentally appear as a crash unless that is the chosen product behavior; recommended default is `cancelled` and excluded from unfinished recovery unless intentionally marked resumable later. Failed sessions due to transient write/model errors may remain resumable only if required artifacts are intact; otherwise mark them unrecoverable/invalid. Add safe cleanup helpers for completed, invalid, and deleted sessions. Ensure repeated crashes/resumes update `updated_at` and status predictably.
  **Must NOT do**: Must NOT leave cancelled sessions ambiguously mixed with interrupted ones. Must NOT keep invalid junk sessions permanently visible.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: policy implementation on top of the persistence layer.
  - Skills: `[]`
  - Omitted: `[seo]` - irrelevant.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: T11 | Blocked By: T2, T4

  **References**:
  - Pattern: `omnivoice_qt_app.py:2034-2080` - current cancellation/error flow in HEAD version.
  - Pattern: `omnivoice_qt_app.py:308-316` - cancellation signal inside worker.
  - Pattern: `omnivoice_qt_app.py:2067-2073` - existing logging paths for cancel/error states.

  **Acceptance Criteria**:
  - [ ] Cancellation, interruption, failure, completion, and invalid-session states are distinguishable in manifest data.
  - [ ] Cancelled sessions follow the chosen visibility rule consistently.
  - [ ] Delete/cleanup removes manifest, chunk audio, and copied reference audio.

  **QA Scenarios**:
  ```
  Scenario: User cancellation is not mistaken for crash recovery
    Tool: Bash
    Steps: Run a generation harness, trigger cancellation through the worker path, then scan unfinished recovery sessions.
    Expected: Session is marked `cancelled` and is excluded from unfinished recovery if using the recommended default.
    Evidence: .sisyphus/evidence/task-8-cancelled-policy.txt

  Scenario: Cleanup removes all artifacts
    Tool: Bash
    Steps: Create a fake interrupted session with manifest, chunk files, and copied reference audio, then invoke delete/cleanup.
    Expected: Session folder and all nested artifacts are removed.
    Evidence: .sisyphus/evidence/task-8-cleanup.txt
  ```

  **Commit**: YES | Message: `feat(session): finalize session lifecycle rules` | Files: helper module(s), `omnivoice_qt_app.py`

- [ ] 11. Add an automated crash/resume + timer verification harness

  **What to do**: Create a lightweight automated verification layer for the new recovery feature. Because the repo lacks app-level tests, add a scriptable harness or test module that monkeypatches/fakes generation so chunk completion, interruption, corruption, resume behavior, timer behavior, and CUDA soft-throttle behavior can be exercised deterministically without long GPU runs. Cover at minimum: new session creation, chunk persistence, crash after first chunk, resume skip behavior, no auto-popup/auto-resume at startup, durable clone reference audio, corrupt manifest handling, delete cleanup, live timer increment, cumulative timer continuity after resume, and CUDA-only throttle activation.
  **Must NOT do**: Must NOT rely on manual visual testing as the only proof. Must NOT require actual long real-model inference for every verification scenario.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: requires careful design of deterministic test seams around an app with no existing UI test framework.
  - Skills: `[]`
  - Omitted: `[playwright]` - desktop Qt app, not a browser task.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: F1-F4 | Blocked By: T5, T6, T7, T8

  **References**:
  - Pattern: `omnivoice_qt_app.py:411-537` - worker core to fake/monkeypatch.
  - Pattern: `omnivoice_qt_app.py:1953-2031` - success/status path to assert after resume.
  - Pattern: `omnivoice_qt_app.py:2235-2247` - existing log stream hook may help assert progress behavior.

  **Acceptance Criteria**:
  - [ ] A repeatable automated harness exists and runs locally without human clicking.
  - [ ] The harness covers happy-path resume, timer continuity, CUDA-throttle scope, and at least the documented edge/failure cases.
  - [ ] Evidence artifacts are generated for each required recovery scenario.

  **QA Scenarios**:
  ```
  Scenario: End-to-end fake resume verification
    Tool: Bash
    Steps: Run the automated harness covering create -> crash-after-chunk-0 -> relaunch/discover -> explicit resume -> complete.
    Expected: Harness exits successfully and records that only unfinished chunks were generated on resume.
    Evidence: .sisyphus/evidence/task-9-end-to-end.txt

  Scenario: Corrupt session scan remains stable
    Tool: Bash
    Steps: Run the harness against a sessions root containing both valid and invalid manifests.
    Expected: Valid sessions remain recoverable; corrupt sessions are quarantined/flagged without crashing the process.
    Evidence: .sisyphus/evidence/task-9-invalid-scan.txt

  Scenario: Timer continuity after resume
    Tool: Bash
    Steps: Run a harness that persists elapsed time, resumes the session, and samples the active timer shortly after resume begins.
    Expected: Timer starts from the accumulated elapsed baseline and continues increasing.
    Evidence: .sisyphus/evidence/task-9-timer-continuity.txt

  Scenario: CUDA throttle scope stays bounded
    Tool: Bash
    Steps: Run the harness with a mocked CUDA path and inspect recorded throttle calls/counts across a 3-chunk run.
    Expected: Throttle events appear at the planned chunk boundaries only and do not alter chunk count/order semantics.
    Evidence: .sisyphus/evidence/task-9-cuda-throttle-harness.txt
  ```

  **Commit**: YES | Message: `test(session): add crash resume verification harness` | Files: test/harness files, helper module(s), `omnivoice_qt_app.py`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Prefer one commit per numbered task when the codebase changes are logically isolated.
- If T5 and T6 are tightly coupled in practice, they may be combined into one implementation commit **only if** the combined diff stays reviewable and the message clearly describes persistence + resume integration.
- Keep test/harness additions separate from core runtime integration when possible.

## Success Criteria
- Users can reopen the app after interruption and explicitly resume unfinished clone/design jobs from a recovery list.
- Already-completed chunks are reused from disk and not regenerated unnecessarily.
- Clone-mode resume remains possible after restart because reference audio is copied into the session workspace.
- Recovery introduces no startup popup and no automatic resume behavior.
- Corrupt or incomplete session artifacts never crash the app.
