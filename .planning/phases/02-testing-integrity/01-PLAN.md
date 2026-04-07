---
phase: 02-testing-integrity
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - agent/pyproject.toml
  - agent/tests/test_coverage_boost.py
  - agent/tests/test_push_80.py
  - agent/tests/test_final_coverage.py
autonomous: true
requirements: [CR-01, CR-02]
must_haves:
  truths:
    - "Coverage omit patterns only exclude tests/ and __pycache__/"
    - "All existing tests have meaningful assertions"
    - "pytest --cov reports honest coverage without artificial inflation"
  artifacts:
    - path: "agent/pyproject.toml"
      provides: "Honest coverage config"
    - path: "agent/tests/test_coverage_boost.py"
      provides: "Behavioral tests (rewritten)"
  key_links:
    - from: "pyproject.toml"
      to: "coverage.run"
      via: "omit patterns reduced"
---

<objective>
Remove coverage gaming and report honest test metrics.

Purpose: Ensure test suite actually validates behavior, not just line count.
Output: Honest coverage config, rewritten shallow tests, new integration markers.
</objective>

<context>
@REVIEW.md
@agent/pyproject.toml
@agent/tests/test_coverage_boost.py
@agent/tests/test_push_80.py
@agent/tests/test_final_coverage.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Remove Coverage Omits, Add Integration Markers</name>
  <files>agent/pyproject.toml</files>
  <action>
  1. In `[tool.coverage.run]` section, reduce omit to essentials only:
     ```toml
     omit = [
         "*/tests/*",
         "*/__pycache__/*",
     ]
     ```

  2. Lower `fail_under` to 50 (honest baseline):
     ```toml
     fail_under = 50
     ```

  3. In `[tool.pytest.ini_options]` markers, ensure `integration` marker exists (it does)

  4. Add `filterwarnings` to suppress integration test noise:
     ```toml
     filterwarnings = ["ignore::DeprecationWarning"]
     ```
  </action>
  <verify>
    <automated>cd agent && python -m pytest tests/ --co -q | head -5</automated>
  </verify>
  <done>Coverage config has only 2 omit patterns, fail_under at 50</done>
</task>

<task type="auto">
  <name>Task 2: Audit and Fix Shallow Tests</name>
  <files>agent/tests/test_coverage_boost.py, agent/tests/test_push_80.py, agent/tests/test_final_coverage.py</files>
  <action>
  Audit all 3 coverage-gaming test files. For each test:

  1. **Has assertions** → Keep as-is
  2. **Loops/calls without assertions** → Add meaningful assertions:
     - Assert return types
     - Assert state changes
     - Assert error handling behavior
  3. **Pure import coverage** → Convert to `@pytest.mark.integration` if they need hardware/API, or add behavioral assertions

  Specific fixes needed:
  - `test_play_earcon_with_various_sounds`: Assert `play_earcon` returns None (no error)
  - Tests that just instantiate classes: Assert properties, assert method contracts
  - Tests that call methods: Assert return values match expected types

  Do NOT delete tests — fix them. Every test should have at least one `assert`.
  </action>
  <verify>
    <automated>cd agent && python -m pytest tests/test_coverage_boost.py tests/test_push_80.py tests/test_final_coverage.py -x -v 2>&1 | tail -20</automated>
  </verify>
  <done>All tests in the 3 files have meaningful assertions, no assertion-free loops</done>
</task>

<task type="auto">
  <name>Task 3: Run Honest Coverage Report</name>
  <files>None (verification only)</files>
  <action>
  Run full test suite with new coverage config and capture honest baseline:

  ```bash
  cd agent
  python -m pytest tests/ --cov --cov-report=term-missing -x
  ```

  Document the honest coverage number. If below 50%, no action needed (just honest reporting). If tests fail due to missing imports for excluded modules, mark those tests as `@pytest.mark.integration`.
  </action>
  <verify>
    <automated>cd agent && python -m pytest tests/ --cov --cov-report=term-missing -x 2>&1 | tail -30</automated>
  </verify>
  <done>Honest coverage number documented, all tests pass, no artificial inflation</done>
</task>

</tasks>

<verification>
- `python -m pytest tests/ --cov -x` passes
- Coverage report shows real numbers without 1,027 LOC excluded
- Every test has at least one `assert` statement
</verification>

<success_criteria>
- Coverage omit reduced to 2 patterns (tests + pycache only)
- fail_under set to honest baseline
- All 3 gaming test files audited and fixed
- Honest coverage number reported
</success_criteria>
