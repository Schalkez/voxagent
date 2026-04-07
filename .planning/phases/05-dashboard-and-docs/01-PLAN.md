---
phase: 05-dashboard-and-docs
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - dashboard/src/features/settings/components/organisms/AudioSettingsCard/AudioSettingsCard.tsx
  - dashboard/src/features/settings/components/organisms/SecurityCard/SecurityCard.tsx
  - dashboard/src/features/settings/containers/SettingsView.tsx
  - dashboard/src/features/settings/hooks/useSettings.ts
  - .github/workflows/ci.yml
  - CONTRIBUTING.md
  - ARCHITECTURE.md
autonomous: true
requirements: [WR-08, IN-02, IN-03]
must_haves:
  truths:
    - "Dashboard compiles cleanly with zero TypeScript errors"
    - "CI tests docstring coverage and dead code using interrogate and vulture"
    - "Documentation clearly guides contributions and system architecture"
  artifacts:
    - path: "CONTRIBUTING.md"
      provides: "Developer guidelines"
    - path: "ARCHITECTURE.md"
      provides: "High-level system design"
    - path: "dashboard/tsc_errors.log"
      provides: "Clean empty state (via build execution)"
  key_links:
    - from: ".github/workflows/ci.yml"
      to: "interrogate & vulture"
      via: "automated checks"
---

<objective>
Polish the frontend build by resolving all TypeScript type-safety errors and finalize project documentation and continuous integration rules.

Purpose: Bring the project fully to production-grade 100% type safety and maintainability.
Output: Zero TS errors in Dashboard, 2 new documentation files, updated CI config.
</objective>

<context>
@REVIEW.md
@dashboard/tsc_errors.log
@.github/workflows/ci.yml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Resolve TypeScript Build Errors</name>
  <files>dashboard/src/features/settings/components/**/*.tsx, dashboard/src/features/settings/hooks/*.ts</files>
  <action>
  Fix the 17 identified TypeScript errors:
  1. Fix implicit `any` parameter types by explicitly declaring types (e.g. `(e: React.ChangeEvent<HTMLInputElement>)`, `(opt: string)` or `(opt: SelectOption)`).
  2. Map missing imports (e.g. `@/shared/components/atoms/Input`, `../../types`, `@tanstack/react-query`) to their correct actual paths. Look at `tsconfig.app.json` for path aliases, and verify whether those UI components natively exist.
  3. Ensure `useSettings.ts` explicitly types the `data` parameter in success handlers or default states.
  </action>
  <verify>
    <automated>cd dashboard && pnpm run type-check || pnpm tsc --noEmit</automated>
  </verify>
  <done>Zero TS errors reported by the TypeScript compiler</done>
</task>

<task type="auto">
  <name>Task 2: Add Interrogate and Vulture to CI Pipeline</name>
  <files>.github/workflows/ci.yml</files>
  <action>
  In `.github/workflows/ci.yml`, within the `lint` job (or dedicated `quality` job):
  1. Add dependencies to the pip install step: `pip install ruff interrogate vulture`
  2. Add the `interrogate` step:
     ```yaml
     - run: interrogate -v -c pyproject.toml .
     ```
  3. Add the `vulture` step:
     ```yaml
     - run: vulture core/ providers/ skills/ system/ --min-confidence 80
     ```
  (Adjust vulture targets based on the specific directory structure inside `agent/`)
  </action>
  <verify>
    <automated>cat .github/workflows/ci.yml | grep -E "interrogate|vulture"</automated>
  </verify>
  <done>CI cleanly reports docstring metrics and dead code scans</done>
</task>

<task type="auto">
  <name>Task 3: Create Missing Documentation Artifacts</name>
  <files>CONTRIBUTING.md, ARCHITECTURE.md</files>
  <action>
  Create two markdown files at the root of the project:

  1. **CONTRIBUTING.md**
     - Section on Environment Setup (Python 3.12, pnpm)
     - Coding Standards (Ruff, Mypy, TS Strict mode)
     - Pull Request guidelines
     - Branch naming conventions

  2. **ARCHITECTURE.md**
     - Detail the pipeline: EARS (STT) -> BRAIN (Intent/Routing) -> HANDS (Execution Tiers) -> MOUTH (TTS)
     - Detail Provider abstraction (Strategy Pattern based classes)
     - Detail Dashboard interactions (Server mode API integration)
     - Data flow diagram leveraging Mermaid syntax
  </action>
  <verify>
    <automated>ls -la CONTRIBUTING.md ARCHITECTURE.md</automated>
  </verify>
  <done>Rich markdown documents exist detailing how to contribute and how the system works.</done>
</task>

</tasks>

<verification>
- `cd dashboard && pnpm tsc --noEmit` returns no output
- The documentation accurately reflects the codebase
</verification>

<success_criteria>
- Dashboard compiles perfectly
- Codebase docstring and zombie code tools are enforced
- Contributors and standard visitors understand the repository
</success_criteria>
