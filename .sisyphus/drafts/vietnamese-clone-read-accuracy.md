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

## Open Questions
- Whether to add a UI toggle now or keep the boundary list always-on for Vietnamese clone/design text. Recommended default: always-on because it does not alter visible text.

## Scope Boundaries
- INCLUDE: text preprocessing, Vietnamese chunking, clone generation flow, deterministic logging/evidence, QA with exact problematic script.
- EXCLUDE: changing model weights, fine-tuning OmniVoice, replacing model architecture, changing user's comma-only writing workflow.
- EXCLUDE: censoring profanity, rewriting profanity, translating slang, or changing user intent.
