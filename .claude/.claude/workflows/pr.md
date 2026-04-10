---
description: how to create a well-formatted pull request for VoxAgent
---

1. **Verify all checks pass** before creating the PR:
   ```bash
   cd voxagent/agent
   ruff check . && ruff format --check .
   mypy core/ providers/ skills/ system/ --ignore-missing-imports
   python -m pytest tests/ -v --tb=short
   ```

2. **Dashboard checks** (if dashboard files changed):
   ```bash
   cd voxagent/dashboard
   npx tsc --noEmit
   pnpm run lint
   pnpm run build
   ```

3. **Review your changes**:
   ```bash
   git log --oneline main..HEAD
   git diff --stat main..HEAD
   git diff main..HEAD
   ```

4. **Determine PR type** from your commits:
   - `feat:` commits → Feature PR
   - `fix:` commits → Bug fix PR
   - `refactor:` commits → Refactoring PR
   - `docs:` commits → Documentation PR
   - Mixed → Use the most significant type

5. **Push your branch** (if not already pushed):
   ```bash
   git push -u origin HEAD
   ```

6. **Create the PR** using gh CLI:
   ```bash
   gh pr create --title "type: short description" --body "$(cat <<'EOF'
   ## Summary
   - What this PR does and why

   ## Changes
   - List of specific changes made
   - File-by-file if helpful

   ## Testing
   - [ ] Unit tests pass
   - [ ] Type checks pass
   - [ ] Lint checks pass
   - [ ] Manual testing done (describe what you tested)

   ## Screenshots
   (if UI changes, add before/after screenshots)
   EOF
   )"
   ```

7. **Verify the PR**:
   ```bash
   gh pr view --web
   ```
