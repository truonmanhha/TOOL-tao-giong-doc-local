# Plan: Lightweight UI Optimization for OmniVoice

## TL;DR
> **Summary**: Extract and modernize the UI styling of OmniVoice local app without increasing RAM/CPU usage.
> **Deliverables**: External `style.qss`, removal of inline `setStyleSheet`, responsive layout margins, and modernized custom widget colors.
> **Effort**: Short
> **Parallel**: NO (Sequential UI refactoring to prevent merge conflicts in the God Class)
> **Critical Path**: Task 1 (Extract QSS) → Task 2 (Responsive Layout) → Task 3 (Custom Widgets & Popups)

## Context
### Original Request
- "đẹp nhưng phải nhẹ hơn nha , đảm bảo ăn ram ít nhất có thể" (Beautiful but extremely lightweight, minimize RAM usage).
- User prefers a "Modern, soft" style (Dark theme, rounded corners, accent colors).
- User explicitly rejected Toast notifications; wants to keep the old `QMessageBox` but style it.

### Interview Summary
- App must remain a native desktop PySide6 app.
- UI runs alongside PyTorch; saving RAM/VRAM is critical.
- `OmniVoiceQtWindow` is currently a monolithic God Class (~1,700 lines). We will *not* refactor the Python architecture to avoid scope creep, only the styling.

### Metis Review (gaps addressed)
- **Guardrail**: FORBID `QGraphicsDropShadowEffect`, `QPropertyAnimation`, or any complex Qt rendering effects. Use QSS borders and gradients to simulate depth.
- **Guardrail**: `style.qss` must be loaded robustly (using `os.path.dirname(__file__)`), not dependent on the Current Working Directory (CWD).
- **Guardrail**: Do not add new Python dependencies or heavy asset files (images/fonts).
- **Guardrail**: Maintain exact existing behavior for Popups (`QMessageBox`).

## Work Objectives
### Core Objective
Modernize the PySide6 UI aesthetically while strictly enforcing zero-impact on CPU/RAM.

### Deliverables
1. `omnivoice_qt_app.py` with stripped inline styles and normalized margins.
2. A new `style.qss` file containing the complete "Modern, soft" dark theme.

### Definition of Done (verifiable conditions with commands)
- Zero instances of `QGraphicsDropShadowEffect`.
- App launches successfully and applies `style.qss` dynamically.
- `TrimRangeSelector` uses theme-consistent colors instead of hardcoded hex values.

### Must Have
- Fallback logic: If `style.qss` fails to load, the app must still run (print warning, don't crash).
- Robust QSS path resolution (`os.path.join(os.path.dirname(__file__), 'style.qss')`).

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- NO architectural refactoring of `OmniVoiceQtWindow` (do not split the file).
- NO Toast notification systems.
- NO animations, opacity effects, or blur effects.
- NO heavy external assets (fonts, large images).

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: none (no existing test framework). Agent-executed smoke tests via `python -c "import ..."` and CLI dry-runs.
- QA policy: Every task has agent-executed scenarios.
- Evidence: .sisyphus/evidence/task-{N}-{slug}.{ext}

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Sequential execution is required here because all changes target the same `omnivoice_qt_app.py` file.

Wave 1: Extraction & Layout
Wave 2: Custom Components & Polish

### Dependency Matrix (full, all tasks)
Task 1 (Extract QSS) blocks Task 2 (Responsive Margins) blocks Task 3 (Widget Polish)

### Agent Dispatch Summary (wave → task count → categories)
Wave 1 → 2 tasks → visual-engineering
Wave 2 → 1 task → visual-engineering

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. Extract Global Styles to style.qss and Remove Inline `setStyleSheet`

  **What to do**: 
  - Create `style.qss` in the same directory as `omnivoice_qt_app.py`.
  - Move the massive QSS string from `_apply_style` into `style.qss`.
  - Find all `setStyleSheet` calls in `omnivoice_qt_app.py` (header, title, subtitle, runtime_badge, device_combo, tabs, clone_generate_btn) and move them to `style.qss` using object names (e.g., `header.setObjectName("HeaderFrame")`).
  - Update `_apply_style` to read from `os.path.join(os.path.dirname(__file__), 'style.qss')`. Add a `try/except` block to gracefully fallback if the file is missing.
  - Ensure the style implements the "Modern, soft" dark theme (rounded corners, dark background, accent colors, subtle borders instead of shadows).

  **Must NOT do**: 
  - Do not use `QGraphicsDropShadowEffect`.
  - Do not change any Python logic outside of UI initialization.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` - Reason: UI styling and QSS extraction.
  - Skills: `[]`
  - Omitted: `[frontend-design]` - Not a web frontend task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [2, 3] | Blocked By: []

  **References**:
  - Pattern: `omnivoice_qt_app.py:500` - Current `_apply_style` location.

  **Acceptance Criteria**:
  - [ ] App launches without crashing.
  - [ ] `setStyleSheet` is only used for dynamic states (like progress bars) or is completely removed.

  **QA Scenarios**:
  ```
  Scenario: Load external QSS successfully
    Tool: Bash
    Steps: python -c "from omnivoice_qt_app import OmniVoiceQtWindow; from PySide6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); win = OmniVoiceQtWindow(); print('UI Loaded')"
    Expected: "UI Loaded" printed, no traceback.
    Evidence: .sisyphus/evidence/task-1-load-qss.txt

  Scenario: Fallback if QSS is missing
    Tool: Bash
    Steps: Rename style.qss to style_temp.qss. Run the same python command. Rename it back.
    Expected: "UI Loaded" printed, no traceback (handled gracefully).
    Evidence: .sisyphus/evidence/task-1-missing-qss.txt
  ```
  **Commit**: YES | Message: `style(ui): extract inline styles to style.qss` | Files: [omnivoice_qt_app.py, style.qss]

- [ ] 2. Remove Hardcoded Margins for Responsive Layout

  **What to do**: 
  - Search for `setContentsMargins`, `setSpacing`, `setMinimumHeight`, `setMaximumHeight`, and fixed `resize()` calls in `omnivoice_qt_app.py`.
  - Remove overly restrictive hardcoded layout constraints so the app can scale gracefully.
  - Control layout padding/margins via QSS where possible, or use standard Qt default spacings.

  **Must NOT do**: 
  - Do not break the visual hierarchy. If removing a margin causes elements to overlap, use `addStretch()` or standard QSpacerItem.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` - Reason: PySide6 Layout adjustments.
  - Skills: `[]`

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [3] | Blocked By: [1]

  **References**:
  - Pattern: `omnivoice_qt_app.py` - Look inside `_build_ui`, `_build_clone_page`, `_build_design_page`.

  **Acceptance Criteria**:
  - [ ] Layout spacing is no longer hardcoded with excessive arbitrary numbers.

  **QA Scenarios**:
  ```
  Scenario: Verify hardcoded margins are reduced
    Tool: Bash
    Steps: grep -c "setContentsMargins" omnivoice_qt_app.py
    Expected: Count should be significantly lower than the baseline (~25).
    Evidence: .sisyphus/evidence/task-2-margins.txt
  ```
  **Commit**: YES | Message: `style(ui): remove hardcoded layout constraints` | Files: [omnivoice_qt_app.py]

- [ ] 3. Polish Custom Widgets and QMessageBox

  **What to do**: 
  - Modify `TrimRangeSelector` in `omnivoice_qt_app.py` to use theme-aware colors (or define its colors at the top of the class so they match the new dark theme) instead of hardcoded hex values.
  - Add QSS rules in `style.qss` targeting `QMessageBox` and `QPushButton` inside it to ensure error/info popups look modern and match the app theme.

  **Must NOT do**: 
  - Do not change `TrimRangeSelector` interaction logic (mouse events).

  **Recommended Agent Profile**:
  - Category: `visual-engineering` - Reason: Custom Qt painting and specific widget styling.
  - Skills: `[]`

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [] | Blocked By: [1, 2]

  **References**:
  - Pattern: `omnivoice_qt_app.py:133` - `TrimRangeSelector` class.

  **Acceptance Criteria**:
  - [ ] `TrimRangeSelector` does not contain hardcoded `#` hex colors inside `paintEvent`.
  - [ ] `QMessageBox` has styling defined in `style.qss`.

  **QA Scenarios**:
  ```
  Scenario: Verify no hardcoded hex in paintEvent
    Tool: Bash
    Steps: awk '/def paintEvent/,/def mousePressEvent/' omnivoice_qt_app.py | grep "#[0-9a-fA-F]"
    Expected: No matches (or handled via variables).
    Evidence: .sisyphus/evidence/task-3-trim-colors.txt
  ```
  **Commit**: YES | Message: `style(ui): theme custom widgets and message boxes` | Files: [omnivoice_qt_app.py, style.qss]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high
- [ ] F4. Scope Fidelity Check — deep
## Commit Strategy
Atomic commits after each visual engineering task.
## Success Criteria
- Modern, rounded dark theme applied.
- Zero increase in RAM usage via heavy Qt effects.
- No `setStyleSheet` clutter in Python code.