# Draft: Resume Interrupted Generation Sessions

## Requirements (confirmed)
- User wants the local OmniVoice desktop app to continue interrupted generation sessions after failures such as power loss or app termination.
- Example target behavior: if a long script has generated only half its chunks, reopening the software should allow continuing that same session instead of starting over.
- Resume target is the existing Qt desktop app flow in `omnivoice_qt_app.py`.
- Recovery should focus on unfinished local desktop generation sessions, not cloud/remote execution.
- Recovery UX decision: do not auto-popup on launch; expose recoverable sessions in session history and let the user explicitly choose resume.
- User also wants a visible generation timer so they can monitor how long a job has been running.
- User also wants the app to reduce GPU spikes so it does not occasionally pin the GPU at 100%; selected approach: **soft throttle inside the app**.

## Technical Decisions
- Persist resumable session state at chunk granularity inside an app-managed session workspace rather than relying on in-memory final audio.
- Resume should rebuild the worker from persisted manifest + completed chunk files, then continue from the first unfinished chunk.
- Session persistence must cover both clone mode and design mode payloads.
- Final WAV assembly should happen after all chunks complete; partial chunk files remain the recovery source of truth during execution.
- Scope should include one unfinished-generation recovery system, not a full media library/history manager.
- Timer should be planned as part of the same generation/resume flow so elapsed time can continue across resumed sessions instead of resetting ambiguously.
- GPU cap interpretation: implement **best-effort soft throttling** in app code for CUDA runs, not a hard guarantee of exactly 99% utilization at every instant.
- Preferred throttle design should reduce load between chunks and/or after heavy CUDA work without depending on external NVIDIA driver tools.

## Research Findings
- Generation entry points are `OmniVoiceQtWindow._start_clone_generation()` and `_start_design_generation()`, which pass a payload into `_run_worker()`.
- `GenerationWorker.run()` already processes text chunk-by-chunk after `_split_text_chunks(text)`, making it the best place to persist progress and outputs.
- Current progress reporting exists, but current final output is only stored in memory and only saved to disk when the user manually exports a WAV.
- There is no existing settings/session persistence layer, no recovery manifest, and no recent-session/history system.
- Temporary audio extraction/trim uses OS temp files that are not currently tracked as resumable artifacts.
- The app already stores `started_at` in `_runtime_state` and uses `_elapsed_for_mode()` for post-run summaries, but there is no live on-screen elapsed timer during generation and no persisted elapsed-time metadata for resumed jobs.
- Current CUDA-related safeguards are minimal: `OMP_NUM_THREADS=1`, `torch.set_num_threads(1)`, and `torch.cuda.empty_cache()` after generation. There is no in-app utilization throttle or cooldown policy.
- The app calls `model.generate()` per chunk, so the safest best-effort throttle hook is around chunk boundaries and UI-configurable generation settings, not deep inside model internals.

## Open Questions
- Whether the timer should show only on the active generation screen, or also in the unfinished-session recovery list. Recommended default: both active screen and recovery list, with live elapsed time during runs and persisted cumulative elapsed time for interrupted sessions.
- Whether GPU soft-throttle should be always-on for CUDA or user-toggleable. Recommended default: always-on with conservative defaults, plus optional advanced settings later if needed.

## Scope Boundaries
- INCLUDE: session manifest design, chunk-level persistence, startup/session-history recovery flow, resume execution path, stale session cleanup rules, and QA/verification.
- INCLUDE: live elapsed generation timer and persisted elapsed-time metadata integrated with resume.
- INCLUDE: CUDA soft-throttle behavior inside app runtime to reduce sustained 100% spikes during long generation.
- EXCLUDE: remote sync, multi-machine recovery, cloud job orchestration, full project history browser beyond unfinished sessions, and model/training changes.
- EXCLUDE: external NVIDIA driver tuning, power-limit tooling, or OS-level GPU control panels.
