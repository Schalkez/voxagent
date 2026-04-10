---
description: how to scaffold a new dashboard feature for VoxAgent
---

1. **Determine the feature name**:
   - Folder name: `lowercase` (e.g., `autopilot`, `memory`, `voice-log`)
   - Component names: `PascalCase` (e.g., `AutopilotView`, `MemoryView`)
   - Hook names: `use{Feature}` (e.g., `useAutopilot`, `useMemory`)

2. **Create the feature directory tree**:
   ```bash
   FEATURE="feature_name"  # Replace with actual name
   BASE="voxagent/dashboard/src/features/$FEATURE"

   mkdir -p "$BASE/components/organisms"
   mkdir -p "$BASE/containers"
   mkdir -p "$BASE/hooks"
   mkdir -p "$BASE/types"
   mkdir -p "$BASE/constants"
   mkdir -p "$BASE/utils"
   ```

3. **Create type definitions** (`types/`):
   - `types/index.ts` — Barrel re-export ONLY
   - `types/{feature}.types.ts` — Domain/data types (API responses, models)
   - `types/components.types.ts` — Component prop types

4. **Create constants** (`constants/`):
   - `constants/index.ts` — Barrel re-export ONLY
   - `constants/ui.ts` — UI-related constants (labels, colors, sizes)
   - `constants/mocks.ts` — Mock/fallback data for development

5. **Create utils barrel** (`utils/`):
   - `utils/index.ts` — Barrel re-export ONLY

6. **Create the main hook** (`hooks/use{Feature}.ts`):
   - Owns all data fetching (API calls via `@shared/api`)
   - Owns all state logic (React state, derived data)
   - Returns typed data + actions for the container

7. **Create the container** (`containers/{Feature}View.tsx`):
   - Thin glue layer: calls hook, passes data to components
   - NO business logic — just orchestration
   - Named export only

8. **Create a placeholder organism** (`components/organisms/{Component}/{Component}.tsx`):
   - Pure UI component — receives data via props
   - Define Props interface above the component
   - Named export only

9. **Add barrel exports for each folder**:
   ```bash
   # Every folder must have index.ts that ONLY re-exports
   echo "export * from './{Feature}View';" > "$BASE/containers/index.ts"
   echo "export * from './use{Feature}';" > "$BASE/hooks/index.ts"
   ```

10. **Verify against conventions**:
    ```bash
    cat .claude/skills/voxagent-conventions/SKILL.md
    ```
    Check:
    - No relative parent imports (`../`) — use `@shared/*` or `@features/*`
    - No inline definitions in barrel files
    - Props interface exported from types/
    - Named exports everywhere (no default exports)

11. **Add the feature route** in `App.tsx`:
    ```tsx
    import { {Feature}View } from '@features/{feature}/containers';
    // Add to router config
    ```
