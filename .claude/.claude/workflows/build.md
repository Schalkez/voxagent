---
description: how to build VoxAgent for production (backend + frontend)
---

## Python Backend

1. Navigate to the agent directory:
   ```bash
   cd voxagent/agent
   ```

2. Create and activate virtual environment (if not exists):
   ```bash
   python -m venv .venv && .venv/Scripts/activate
   ```

3. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Run type checking:
   ```bash
   mypy core/ providers/ skills/ system/ --ignore-missing-imports
   ```

5. Run tests with coverage:
   ```bash
   python -m pytest tests/ -v --cov=core --cov=providers --cov=skills --cov-report=term-missing
   ```

6. Verify coverage meets threshold (80%):
   ```bash
   python -m pytest tests/ --cov=core --cov=providers --cov=skills --cov-fail-under=80 -q
   ```

## React Dashboard

7. Navigate to the dashboard directory:
   ```bash
   cd voxagent/dashboard
   ```

8. Install dependencies:
   ```bash
   pnpm install --frozen-lockfile
   ```

9. TypeScript type check:
   ```bash
   npx tsc --noEmit
   ```

10. Lint check:
    ```bash
    pnpm run lint
    ```

11. Build for production:
    ```bash
    pnpm run build
    ```

12. Verify build output:
    ```bash
    ls -la dist/
    ```
