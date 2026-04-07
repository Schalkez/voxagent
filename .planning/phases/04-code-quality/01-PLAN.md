---
phase: 04-code-quality
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - agent/skills/terminal.py
  - agent/core/sync.py
  - agent/core/brain.py
  - agent/api/server_mode.py
  - agent/core/app.py
  - agent/output.py
  - agent/pyproject.toml
autonomous: true
requirements: [WR-01, WR-02, WR-03, WR-04, WR-05, IN-01, IN-04]
must_haves:
  truths:
    - "No dead code or leftover files exist in the production source."
    - "Async methods do not block the event loop with synchronous file I/O."
    - "System configurations are applied correctly (e.g., singleton Brain, proper input handling)."
  artifacts:
    - path: "agent/core/sync.py"
      provides: "Non-blocking file operations"
    - path: "agent/api/server_mode.py"
      provides: "Singleton Brain usage"
  key_links:
    - from: "agent/api/server_mode.py"
      to: "agent/core/brain.py"
      via: "app.state injection"
---

<objective>
Refactor and harden general code quality across several modules based on minor warnings and code smells identified in REVIEW.md.

Purpose: Improve application resilience, performance (async non-blocking), and overall code cleanliness.
Output: Fixed minor bugs, converted I/O to async, removed dead code.
</objective>

<context>
@REVIEW.md
@agent/skills/terminal.py
@agent/core/sync.py
@agent/core/brain.py
@agent/api/server_mode.py
@agent/core/app.py
@agent/pyproject.toml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix Dead Code, Stubs, and Typos</name>
  <files>agent/skills/terminal.py, agent/output.py, agent/pyproject.toml</files>
  <action>
  1. **terminal.py**: Remove or fix the dead code expression statement at line 124 (`stdout[:200] if stdout else "(không có output)"`). Assign it to `stdout` to actually truncate, or log it:
     ```python
     stdout = stdout[:200] if stdout else "(không có output)"
     ```
  2. **output.py**: Delete this 52-byte unused stub file entirely.
  3. **pyproject.toml**: Fix the typo in the ruff configuration (`exclude = [..., ".agent/"]` -> `exclude = [..., "agent/.*", ".agents/"]` or remove it if unnecessary).
  </action>
  <verify>
    <automated>cd agent && ruff check skills/terminal.py pyproject.toml</automated>
  </verify>
  <done>Dead code in terminal.py is fixed/assigned, output.py is deleted, pyproject typo is corrected.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Convert SyncManager to Non-Blocking Async I/O</name>
  <files>agent/core/sync.py, agent/tests/test_sync.py</files>
  <behavior>
    - Test: register_device still creates JSON file successfully
    - Test: sync_preferences correctly reads and merges JSON async
    - Test: Calls use asyncio.to_thread rather than blocking
  </behavior>
  <action>
  In `agent/core/sync.py`, wrap all synchronous `Path.write_text` and `Path.read_text` operations within `asyncio.to_thread` or utilize `aiofiles`. Since this is a standard library context, `asyncio.to_thread` with a helper is preferred to avoid adding dependencies.

  Example modification for `register_device`:
  ```python
  def write_json_sync(path_obj, data):
      path_obj.write_text(json.dumps(data, indent=2), encoding="utf-8")

  await asyncio.to_thread(write_json_sync, device_file, {"device": asdict(device), "preferences": {}})
  ```
  Apply similar wrapping to `sync_preferences()`, `list_devices()`, and `remove_device()`.
  </action>
  <verify>
    <automated>cd agent && python -m pytest tests/test_sync.py -x -v</automated>
  </verify>
  <done>SyncManager uses asyncio.to_thread for all file-based I/O.</done>
</task>

<task type="auto">
  <name>Task 3: State Injection, Setup Validation, and Dynamic Confidence</name>
  <files>agent/api/server_mode.py, agent/core/app.py, agent/core/brain.py</files>
  <action>
  1. **Brain Confidence (`brain.py`)**:
     Update `Brain.process` routing logic to parse confidence dynamically instead of hardcoding `0.9` if possible. If an LLM is parsing intents, ask it to output a confidence score, or derive it heuristically. (If entirely heuristics-based, at least document the fixed fallback clearly rather than a magic number, or map keyword match to 1.0 and LLM match to 0.8).

  2. **Singleton Brain API (`server_mode.py`)**:
     Instead of initializing `Brain(registry, skills)` inside `execute_command`, define an `@app.on_event("startup")` or lifespan context manager in `api/server.py` that stores a `Brain` singleton on `app.state.brain`. Then, access `request.app.state.brain` in `execute_command`.

  3. **Setup Validation (`app.py`)**:
     In `_run_setup()`, fix the unsafe `int(choice) - 1` cast:
     ```python
     if choice.strip().isdigit():
         idx = int(choice) - 1
         # ... rest of logic
     else:
         print("Vui lòng nhập một số hợp lệ.")
         continue
     ```
  </action>
  <verify>
    <automated>cd agent && python -m pytest tests/test_api.py tests/test_app.py -x -v</automated>
  </verify>
  <done>Brain confidence is not a magic static 0.9 without reason, Brain is a singleton in API requests, and Setup UI gracefully handles non-integer input.</done>
</task>

</tasks>

<verification>
- `ruff check agent/` completes with 0 errors
- `pytest` suite passes without issues
- No blocking operations highlighted within the async event loop
</verification>

<success_criteria>
- Terminal output logic safely handles empty vs non-empty stdout
- File I/O is cleanly wrapped inside asyncio threads
- API performance does not degradation linearly with request instantiations
- User setup is crash-proof on invalid input
</success_criteria>
