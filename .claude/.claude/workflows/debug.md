---
description: how to systematically debug issues in VoxAgent
---

Follow these 8 steps in order. Do NOT skip steps.

1. **Reproduce** — Run the exact failing command or test with verbose output:
   ```bash
   # For Python tests:
   python -m pytest tests/test_MODULE.py -v -s --tb=long -k "test_name"
   
   # For runtime errors:
   python -m core.app --debug 2>&1
   
   # For dashboard:
   cd voxagent/dashboard && pnpm run dev 2>&1
   ```

2. **Isolate the layer** — Determine which module boundary the bug lives in:
   - `core/` — Pipeline logic (ears, brain, hands, mouth)
   - `providers/` — LLM/STT/TTS provider integration
   - `skills/` — Skill execution logic
   - `system/` — OS-specific automation
   - `api/` — FastAPI endpoints
   - `dashboard/` — React frontend

3. **Read the traceback** — Identify the exact file, line number, and exception type.
   Note the chain of calls from bottom to top. Focus on the FIRST frame in YOUR code (ignore library frames).

4. **Check recent changes** — Look at what changed:
   ```bash
   git log --oneline -10
   git diff HEAD~3 -- voxagent/agent/MODULE/
   ```

5. **Add targeted logging** — Use the `logging` module, never `print()`:
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.debug("Variable state: %s", variable)
   ```

6. **Run minimal reproduction** — Create the smallest test case:
   ```python
   # Quick one-liner to test a specific function:
   python -c "from MODULE import function; print(function(args))"
   ```

7. **Fix and verify** — Apply the fix, then run:
   ```bash
   # Run the specific failing test
   python -m pytest tests/test_MODULE.py -v -k "test_name"
   
   # Run the full suite to check for regressions
   python -m pytest tests/ -v --tb=short
   ```

8. **Check regressions** — Ensure no new issues:
   ```bash
   ruff check .
   mypy core/ providers/ skills/ system/ --ignore-missing-imports
   ```
