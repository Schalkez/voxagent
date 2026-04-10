---
description: how to review code changes against VoxAgent conventions
---

1. **Load the convention skills** — Read these FIRST before reviewing:
   ```bash
   cat .claude/skills/voxagent-conventions/SKILL.md
   cat .claude/skills/clean-code/SKILL.md
   cat .claude/skills/fastapi-async-patterns/SKILL.md
   ```

2. **Get the diff to review**:
   ```bash
   # For PR review:
   git diff main..HEAD

   # For staged changes:
   git diff --cached

   # For a specific commit:
   git show COMMIT_SHA
   ```

3. **Check each file against conventions** — For every changed file, verify:

   **Architecture (CRITICAL):**
   - Module boundaries respected? (core/ never imports concrete providers)
   - Execution tier priority followed? (Shell → API → UI → Mouse)
   - Provider-agnostic design in core/?

   **Naming (HIGH):**
   - `snake_case` for Python, `PascalCase` for React components?
   - No abbreviations? (`configuration` not `cfg`)
   - Boolean variables read as questions? (`is_active`, `has_permission`)
   - Constants in `SCREAMING_SNAKE_CASE`?

   **Types & Safety (HIGH):**
   - All functions have type hints?
   - No `Any` types? No bare `except:`?
   - Custom exceptions used? (`ProviderUnavailableError`, not `ValueError`)
   - Guard clauses at top?

   **SOLID (CRITICAL):**
   - Single Responsibility? (one function = one task)
   - Open/Closed? (extend via interfaces, don't modify)
   - Liskov Substitution? (providers are drop-in replacements)
   - Interface Segregation? (interfaces stay focused)
   - Dependency Inversion? (depend on abstractions)

   **Dashboard (if applicable):**
   - Components are pure UI only?
   - Business logic in hooks, not components?
   - No relative parent imports (`../`)?
   - Path aliases used (`@shared/*`, `@features/*`)?
   - Barrel exports correct?

4. **Run automated checks**:
   ```bash
   cd voxagent/agent
   ruff check .
   mypy core/ providers/ skills/ system/ --ignore-missing-imports
   ```

5. **Check test coverage** for new code:
   ```bash
   python -m pytest tests/ --cov=core --cov=providers --cov=skills --cov-report=term-missing
   ```

6. **Dashboard automated checks** (if applicable):
   ```bash
   cd voxagent/dashboard
   npx tsc --noEmit
   pnpm run lint
   ```

7. **Summarize findings** using this format:
   ```
   ✅ PASS / ⚠️ WARN / ❌ FAIL — file:line — rule-id — description
   ```
   Reference rule IDs from the skill files (e.g., `solid-srp`, `naming-intention`, `func-flat`).
