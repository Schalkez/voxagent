# FIX ROADMAP — Post-Review Hardening

> Generated from REVIEW.md findings (2026-04-07)
> Goal: Raise project score from 7.0 → 8.5+

---

## Phases

- [ ] **Phase 1: Security Hardening** — Fix critical security vulnerabilities (CR-03, CR-05, WR-06, WR-07)
- [ ] **Phase 2: Testing Integrity** — Honest coverage, remove gaming, add real tests (CR-01, CR-02)
- [ ] **Phase 3: Wire Dead Modules** — Connect Autopilot + Eyes to pipeline (CR-04)
- [ ] **Phase 4: Code Quality Fixes** — Dead code, async I/O, input validation (WR-01→WR-05)
- [ ] **Phase 5: Dashboard + Docs Polish** — Fix TS errors, create missing docs (WR-08, IN-02→IN-04)

---

## Phase Details

### Phase 1: Security Hardening
**Goal**: Eliminate all critical and high-severity security vulnerabilities
**Depends on**: Nothing
**Requirements**: CR-03, CR-05, WR-06, WR-07
**Success Criteria** (what must be TRUE):
  1. Terminal skill cannot execute arbitrary shell commands via injection
  2. API key comparison is timing-safe
  3. API server binds localhost by default
  4. Rate limit store has bounded memory usage
**Plans**: 1 plan, 2 tasks

---

### Phase 2: Testing Integrity
**Goal**: Coverage reflects real test quality — no gaming, no hiding
**Depends on**: Nothing (parallel with Phase 1)
**Requirements**: CR-01, CR-02
**Success Criteria** (what must be TRUE):
  1. Coverage omit patterns removed from pyproject.toml (except `*/tests/*` and `*/__pycache__/*`)
  2. Coverage threshold lowered to honest level (e.g., 60%) or raised via real tests
  3. Coverage boost tests either have meaningful assertions or are removed
  4. `pytest --cov` runs without omits and reports honest number
**Plans**: 1 plan, 3 tasks

---

### Phase 3: Wire Dead Modules
**Goal**: Autopilot + Eyes features work end-to-end as documented in README
**Depends on**: Nothing (parallel with Phase 1-2)
**Requirements**: CR-04
**Success Criteria** (what must be TRUE):
  1. VoxAgentApp.start() launches Autopilot as a background asyncio task
  2. Autopilot tasks can be registered and triggered during pipeline run
  3. Brain.process() can optionally invoke Eyes for screen context
  4. README use cases for autopilot + vision are functionally possible
**Plans**: 1 plan, 2 tasks

---

### Phase 4: Code Quality Fixes
**Goal**: Clean up dead code, fix async patterns, harden input handling
**Depends on**: Phase 1 (security fixes may touch same files)
**Requirements**: WR-01, WR-02, WR-03, WR-04, WR-05, IN-01, IN-04
**Success Criteria** (what must be TRUE):
  1. No dead code / unused expressions in production files
  2. SyncManager uses async I/O for all file operations
  3. Setup wizard handles invalid input gracefully
  4. Brain singleton reused in API server mode
  5. `ruff check .` passes, `vulture` reports no dead code
**Plans**: 1 plan, 3 tasks

---

### Phase 5: Dashboard + Docs Polish
**Goal**: Dashboard builds with zero TS errors, all referenced docs exist
**Depends on**: Nothing (parallel with all phases)
**Requirements**: WR-08, IN-02, IN-03
**Success Criteria** (what must be TRUE):
  1. `pnpm run build` completes with zero TypeScript errors
  2. `tsc --noEmit` reports zero errors
  3. CONTRIBUTING.md exists with contribution guidelines
  4. ARCHITECTURE.md exists with system design docs
  5. CI includes interrogate + vulture jobs
**Plans**: 1 plan, 3 tasks

---

## Progress Table

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 1. Security Hardening | 1/1 | Done | Yes |
| 2. Testing Integrity | 1/1 | Done | Yes |
| 3. Wire Dead Modules | 1/1 | Done | Yes |
| 4. Code Quality Fixes | 1/1 | Done | Yes |
| 5. Dashboard + Docs | 1/1 | Done | Yes |

---

## Requirement Coverage

| Finding | Phase | Status |
|---------|-------|--------|
| CR-01 Coverage Gaming | Phase 2 | Done |
| CR-02 Coverage Omits | Phase 2 | Done |
| CR-03 shell=True | Phase 1 | Done |
| CR-04 Dead Modules | Phase 3 | Done |
| CR-05 Timing Attack | Phase 1 | Done |
| WR-01 Dead Code | Phase 4 | Done |
| WR-02 Async I/O | Phase 4 | Done |
| WR-03 Magic Confidence | Phase 4 | Done |
| WR-04 Brain Singleton | Phase 4 | Done |
| WR-05 Input Validation | Phase 4 | Done |
| WR-06 Bind 0.0.0.0 | Phase 1 | Done |
| WR-07 Rate Limit | Phase 1 | Done |
| WR-08 TS Errors | Phase 5 | Done |
| IN-01 output.py | Phase 4 | Done |
| IN-02 CI Jobs | Phase 5 | Done |
| IN-03 Missing Docs | Phase 5 | Done |
| IN-04 Ruff Typo | Phase 4 | Done |

**Coverage: 17/17 findings mapped ✓**
