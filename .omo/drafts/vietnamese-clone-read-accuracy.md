# Draft: Vietnamese Clone Read Accuracy

## Requirements (confirmed)
- User reports clone mode reads the voice correctly but skips/omits phrases from Vietnamese scripts.
- Example script: `D:\YOUTUBE\KÊNH 2 Hồ Sơ Ám Ảnh\SHORT 9\kich ban.txt`.
- User prefers writing scripts using commas only for ease.
- Priority selected: **Đúng chữ tối đa** — maximize exact text coverage, accepting slower generation and more segmented audio.

## Technical Decisions
- Plan must focus on robust Vietnamese comma-heavy clone reading, not generic UI redesign.
- Must account for existing local modifications already made during the session: Vietnamese normalization, comma pause insertion, chunk splitting, GPU throttling/cache cleanup.
- Target behavior: generated audio should not skip phrases such as `cuộn thép lên`, `sơ sẩy phát là nát con mẹ nó xe`, `Đặt nằm ngang mà xe xóc nhẹ một phát thôi`, and `vì miếng cơm manh áo nên phải liều thôi`.
- For Vietnamese profanity/slang pronunciation, use a **pronunciation-sensitive boundary list**, not text replacement. The list prevents chunk boundaries from falling next to high-risk words, but preserves the user's exact script text.
- Scope of word list: broad "Gen Z" slang/profanity variants, including accented and common unaccented/teencode forms.

## Research Findings
- Initial file example has entire script on one line with comma-separated clauses only.
- Current insertion point for boundary-sensitive slang/profanity handling is `GenerationWorker._split_text_chunks` in `omnivoice_qt_app.py`.
- Core text utilities live in `omnivoice/utils/text.py`; no existing slang dictionary file exists yet.
- Best design is an editable dictionary/list in text utilities plus chunker post-processing in the Qt worker.
- Test infrastructure: no unit test framework configured; verification should use compile checks, chunk simulation, and optional CLI/WER smoke tests.
- Generation starts from `OmniVoiceQtWindow._start_clone_generation()` / `_start_design_generation()` -> `_run_worker()` -> `GenerationWorker.run()` in `omnivoice_qt_app.py`.
- Generation already runs chunk-by-chunk; each chunk is produced inside `GenerationWorker.run()` after `_split_text_chunks(text)` and progress is emitted per chunk and per diffusion step.
- Current final audio is kept in memory and only written to disk when the user manually clicks save; this means crash/power loss currently loses all completed work.
- Current app state is effectively stateless across restarts: no settings store, no recent sessions, no recovery manifest, no auto-output directory.
- Temporary audio handling already uses OS temp files for extracted/trimmed reference audio, but those files are not tracked as resumable session artifacts.
- Best resume hook is a manifest + per-chunk persisted audio/session folder written during the worker loop, then detected on app startup.

## Open Questions
- Whether to add a UI toggle now or keep the boundary list always-on for Vietnamese clone/design text. Recommended default: always-on because it does not alter visible text.
- Whether crash recovery should resume automatically on app launch, or show a recovery dialog first. Recommended default: show recovery dialog with explicit Resume / Discard choices to avoid unintended duplicate audio generation.
- Whether resume scope should cover only the current desktop app's long-form generation flow, or also include saved exports/history browsing later. Recommended default: resume unfinished generation only; history browser can be a later feature.
- Whether partial chunks should be persisted into an app-managed session folder and final WAV assembled after completion. Recommended default: yes, because final output is not currently auto-saved and chunk-level persistence is the safest recovery path.

## Scope Boundaries
- INCLUDE: text preprocessing, Vietnamese chunking, clone generation flow, deterministic logging/evidence, QA with exact problematic script.
- EXCLUDE: changing model weights, fine-tuning OmniVoice, replacing model architecture, changing user's comma-only writing workflow.
- EXCLUDE: censoring profanity, rewriting profanity, translating slang, or changing user intent.

## New Requirements (resume feature)
- User wants a plan to update the software so interrupted sessions can continue after mid-run failures such as power loss.
- Example target behavior: if generation has completed only half of a script, reopening the app should allow continuing that exact work session instead of restarting from the beginning.
- Recovery should target unfinished local desktop app generation sessions, not remote/cloud execution.
- Resume target is the existing Qt desktop app flow in `omnivoice_qt_app.py`.
- Plan should introduce crash-safe persistence, startup detection of incomplete sessions, and a user-facing recovery flow.
