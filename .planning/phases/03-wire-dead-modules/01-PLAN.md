---
phase: 03-wire-dead-modules
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - agent/core/app.py
  - agent/core/brain.py
autonomous: true
requirements: [CR-04]
must_haves:
  truths:
    - "Autopilot runs as a background task during the main application loop"
    - "Brain can use Eyes to fetch screen context when required"
  artifacts:
    - path: "agent/core/app.py"
      provides: "Wired autopilot lifecycle"
    - path: "agent/core/brain.py"
      provides: "Vision-enabled intent routing"
  key_links:
    - from: "agent/core/app.py"
      to: "agent/core/autopilot.py"
      via: "asyncio background task"
    - from: "agent/core/brain.py"
      to: "agent/core/eyes.py"
      via: "context injection"
---

<objective>
Wire the currently dead Autopilot and Eyes modules into the main agent pipeline.

Purpose: Unlock the background processing and screen vision capabilities promised in the documentation.
Output: Active Autopilot task loop and Vision-aware Brain routing.
</objective>

<context>
@REVIEW.md
@agent/core/app.py
@agent/core/autopilot.py
@agent/core/brain.py
@agent/core/eyes.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Wire Autopilot into Application Lifecycle</name>
  <files>agent/core/app.py, agent/tests/test_app.py</files>
  <behavior>
    - Test: VoxAgentApp.start() launches autopilot.run() in background
    - Test: VoxAgentApp.stop() calls autopilot.stop()
    - Test: Autopilot instance is accessible via the app instance
  </behavior>
  <action>
  1. In `app.py`, import `Autopilot` from `core.autopilot`
  2. Instantiate `Autopilot` in `VoxAgentApp.__init__` (e.g., `self.autopilot = Autopilot()`)
  3. In `VoxAgentApp.start()`, create a background task:
     ```python
     self._bg_tasks.add(asyncio.create_task(self.autopilot.run()))
     ```
     *(Add `self._bg_tasks = set()` in init if not present to hold references and prevent GC)*
  4. In `VoxAgentApp.stop()`, call `await self.autopilot.stop()`
  5. Inject autopilot reference into pipeline components if needed (e.g., passing it so skills can register tasks), or just store on state.
  6. Add/update tests in `test_app.py` to verify this lifecycle.
  </action>
  <verify>
    <automated>cd agent && python -m pytest tests/test_app.py -x -v</automated>
  </verify>
  <done>Autopilot task starts and stops cleanly with the app</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Inject Vision Context via Eyes in Brain</name>
  <files>agent/core/brain.py, agent/tests/test_brain.py</files>
  <behavior>
    - Test: Brain can fetch screen context via Eyes if a screen-heavy action is requested
    - Test: (Optional) Fallback to normal behavior if Eyes not configured or vision disabled
  </behavior>
  <action>
  1. In `brain.py`, import `Eyes` from `core.eyes`
  2. In `Brain.__init__`, conditionally instantiate `Eyes`:
     ```python
     self.eyes = Eyes() if config.get("vision_enabled", False) else None
     ```
     *(Or pass configured instance, depending on injection pattern)*
  3. Modify `process(self, input_text: str)` or relevant routing method. If the user prompt hints at vision (e.g., "trên màn hình", "nhìn", "đọc"), try to fetch screen text/context if `self.eyes` is available:
     ```python
     screen_context = ""
     if self.eyes and any(keyword in input_text.lower() for keyword in ["màn hình", "screen", "đọc", "nhìn"]):
         try:
             # Just a simple example, adapt to exact Eyes API
             screen_text = await self.eyes.read_screen()
             screen_context = f"\n[Screen content: {screen_text}]"
         except Exception:
             pass
     ```
  4. Append this `screen_context` to the system prompt or user message sent to the LLM during Tier 1/2 routing.
  5. Add/update tests in `test_brain.py` to mock `Eyes` and verify context injection.
  </action>
  <verify>
    <automated>cd agent && python -m pytest tests/test_brain.py -x -v</automated>
  </verify>
  <done>Brain can conditionally extract screen content using Eyes and append to LLM context</done>
</task>

</tasks>

<verification>
- `ruff check agent/core/app.py agent/core/brain.py` passes
- All existing tests pass
- New tests for Autopilot lifecycle and Brain vision injection pass
</verification>

<success_criteria>
- VoxAgentApp successfully runs Autopilot in the background.
- Brain is capable of utilizing Eyes for vision context.
</success_criteria>
