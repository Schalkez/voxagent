# VoxAgent Codebase Conventions

## 1. Language & Runtime

| Layer | Stack | Version |
|-------|-------|---------|
| Backend (Agent) | Python | 3.12+ (`target-version = "py312"`) |
| Frontend (Dashboard) | TypeScript + React | TS ~5.9, React 19+ |
| Formatter (Python) | ruff | `line-length = 100`, double quotes, spaces |
| Formatter (TS/CSS) | prettier | Default config via eslint-plugin-prettier |
| Linter (Python) | ruff (E, F, W, I, N, UP, B, A, SIM, ASYNC, PTH, RUF) | Strict rule set |
| Linter (TS) | typescript-eslint | strict + stylistic configs |
| Type Checker | mypy (`strict = true`) | `disallow_untyped_defs = true` |
| Package Manager (FE) | pnpm | Lockfile: `pnpm-lock.yaml` |

## 2. Project Structure & Module Boundaries

### Python Backend (`agent/`)

```
agent/
  core/          # Provider-agnostic domain logic (Brain, Ears, Eyes, Hands, Mouth, Memory, etc.)
  providers/     # LLM/STT/TTS/Vision — implements ABCs from providers/base.py
    stt/         # Speech-to-Text provider implementations
    tts/         # Text-to-Speech provider implementations
    vision/      # Vision provider implementations
  skills/        # All skills extend BaseSkill — discovered via registry
  system/        # OS-specific code (Windows/macOS/Linux), implements SystemAutomation ABC
  api/           # FastAPI REST layer
    routers/     # Route definitions per domain (providers, routing, skills, settings)
    schemas/     # Pydantic models + frozen dataclasses for request/response shapes
    services/    # Business logic backing the routers
    state/       # Shared application state (store)
  benchmarks/    # Performance benchmarks (bench_stt, bench_tiers)
  tests/         # All test files (flat directory, no sub-packages)
```

**Strict Boundary Rules:**
- `core/` NEVER imports concrete providers; it accesses them through `ProviderRegistry`.
- `providers/` implementations MUST inherit ABCs from `providers/base.py`.
- `skills/` implementations MUST inherit `BaseSkill` from `skills/base.py`.
- `system/` implementations MUST inherit `SystemAutomation` from `system/base.py`.
- Cross-layer imports flow downward: `api/ -> core/ -> providers/ (via registry)`.

### React Dashboard (`dashboard/src/`)

```
dashboard/src/
  features/          # Feature-sliced folders (dashboard, providers, routing, skills, settings, etc.)
    <feature>/
      components/    # Pure UI components (Atomic Design: atoms, molecules, organisms)
      containers/    # Thin glue connecting hooks to components (e.g., DashboardView.tsx)
      hooks/         # Data fetching & state logic (e.g., useDashboardStatus.ts)
      types/         # Feature-specific TypeScript interfaces
      constants/     # Feature-specific constants and mock data
      index.ts       # Barrel re-exports only
  shared/
    api/             # HTTP client (fetchApi generic function)
    components/      # Reusable UI primitives (atoms, molecules, organisms, templates)
    index.ts         # Barrel re-exports
```

## 3. Naming Conventions

### Python

| Element | Convention | Example |
|---------|-----------|---------|
| Module files | `snake_case.py` | `groq_provider.py`, `media_control.py` |
| Classes | `PascalCase` | `Brain`, `ProviderRegistry`, `MediaControlSkill` |
| Functions / Methods | `snake_case` | `load_config()`, `chat_with_tools()` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_INPUT_LENGTH`, `COMMAND_TIMEOUT_S`, `VK_MEDIA_PLAY_PAUSE` |
| Private members | Leading underscore | `self._running`, `self._db`, `_parse_tier()` |
| Type aliases | `PascalCase` | `VoxAgentConfig`, `SkillResult` |
| Logger instances | `logging.getLogger("voxagent.<module>")` | `logger = logging.getLogger("voxagent.brain")` |
| Boolean variables | `is_` / `has_` prefix (properties) | `is_active`, `is_loaded`, `_connected` |

### TypeScript / React

| Element | Convention | Example |
|---------|-----------|---------|
| Component files | `PascalCase/PascalCase.tsx` | `HeroCard/HeroCard.tsx` |
| Hook files | `camelCase.ts` | `useDashboardStatus.ts` |
| Type files | `kebab.types.ts` | `dashboard.types.ts`, `routing.types.ts` |
| Interfaces | `PascalCase` | `DashboardStatus`, `ProviderInfo` |
| Constants | `SCREAMING_SNAKE_CASE` | `POLL_INTERVAL_MS`, `API_BASE` |
| Components | Named exports, `React.FC` | `export const DashboardView: React.FC` |
| Hooks | `use` prefix, named export | `export function useDashboardStatus()` |

## 4. Import Conventions

### Python

- `from __future__ import annotations` at the top of every module (deferred evaluation).
- `TYPE_CHECKING` guard for circular/heavy imports: only used for type hints.
- Import order enforced by ruff isort: stdlib -> third-party -> first-party (`core`, `providers`, `system`, `skills`).
- Concrete providers are imported dynamically inside `try/except ImportError` blocks (graceful degradation).

```python
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

from core.config import VoxAgentConfig   # first-party

if TYPE_CHECKING:
    from providers.base import STTProvider
```

### TypeScript

- **BANNED**: Relative parent imports (`../`). ESLint rule enforces this.
- **REQUIRED**: Path aliases `@shared/*`, `@features/*` (configured in `vite.config.ts`).
- Barrel `index.ts` files MUST ONLY contain re-exports. No inline definitions.

```typescript
import { fetchApi } from '@shared/api/client';
import type { DashboardStatus } from '@features/dashboard/types';
```

## 5. Data Modeling

### Frozen Dataclasses (Python)

The project universally uses `@dataclass(frozen=True)` for immutable value objects:

```python
@dataclass(frozen=True)
class Intent:
    skill_name: str
    action: str
    params: dict[str, str]
    confidence: float
    tier_used: Tier
```

Used for: `Intent`, `SkillResult`, `SkillIntent`, `Message`, `ModelInfo`, `TranscribeResult`,
`WindowInfo`, `UIElement`, `ConversationEntry`, `SpeechConfig`, `EarsEvent`, `SkillPermission`,
`ActionResult`, `Notification`, `ProcessInfo`, and all config sub-objects (`ProviderConfig`,
`RoutingTierConfig`, `STTConfig`, `TTSConfig`, etc.).

**Mutable dataclasses** are used only for stateful objects: `VoxAgentConfig` (root config),
`AutopilotTask`, `Eyes` (has cache), `VoxAgentApp`.

### Pydantic Models (API Layer Only)

Used exclusively in `api/schemas/` for HTTP request validation:

```python
class SaveKeyRequest(BaseModel):
    api_key: str
```

### TypeScript Interfaces

Feature types use plain interfaces in dedicated `*.types.ts` files:

```typescript
export interface DashboardStatus {
  status: 'online' | 'offline' | 'error';
  listening: boolean;
  // ...
}
```

## 6. Error Handling Patterns

### Exception Hierarchy

```
VoxAPIException (HTTPException)       # Base domain error for API layer
  ProviderConfigError                 # Provider config invalid
  ProviderNotFoundError (api)         # Provider missing (HTTP 404)

ProviderNotFoundError (KeyError)      # Provider missing (core layer, non-HTTP)
```

### Catch Strategies

1. **Explicit exception tuples** — never bare `except:`. Always enumerate:
   ```python
   except (RuntimeError, OSError, TypeError, ValueError) as exc:
   ```

2. **Logged graceful degradation** — catch, log, return safe default:
   ```python
   except (NotImplementedError, OSError, RuntimeError) as e:
       logger.warning("Failed to get active window: %s", e)
       return WindowInfo(title="", process_name="", pid=0, bounds=(0, 0, 0, 0))
   ```

3. **Guard clauses / early returns** — flat control flow:
   ```python
   if self._db is None:
       return default
   ```

4. **`logger.exception()`** for unexpected failures (includes traceback).
5. **`logger.warning()`** for expected/recoverable failures.
6. **Catch blocks omit unused variable** in simple cases: `except ImportError: pass`.

### Error Propagation

- `core/` and `skills/` return result objects (`SkillResult`, `Intent`) with error fields instead of raising.
- `api/` raises `VoxAPIException` subclasses which are caught by the global exception handler.
- Provider failures propagate `ProviderNotFoundError` (KeyError subclass).

## 7. Async Patterns

- All I/O-bound operations are `async/await`.
- CPU-bound or blocking stdlib calls use `asyncio.to_thread()`:
  ```python
  result = await asyncio.to_thread(subprocess.run, cmd_args, ...)
  await asyncio.to_thread(self._capture_sync, region)
  ```
- Lazy imports of heavy libraries inside functions (e.g., `from PIL import ImageGrab` inside method body).
- `httpx.AsyncClient` for all HTTP calls with explicit timeout.

## 8. Security Conventions

- API keys stored in OS keyring (`keyring` library), NEVER in config files or env vars.
- `core/keyring_manager.py` wraps all keyring access behind `save_key()`, `get_key()`, `delete_key()`.
- `PromptGuard` in `core/safety.py` detects prompt injection via compiled regex patterns.
- Terminal command execution uses an allowlist (`ALLOWED_COMMAND_PREFIXES`), blocks dangerous shell chars, and applies Unicode normalization (`NFKC`) to prevent bypass.
- `DANGEROUS_ACTIONS` frozenset in Hands requires voice confirmation before execution.
- Permission system (`PermissionLevel.DANGEROUS`) blocks skills without explicit grants.
- `shell=False` enforced for subprocess execution.

## 9. Design Patterns

### Registry / Factory

- `ProviderRegistry`: Central factory for LLM/STT/TTS/Vision providers with instance caching and fallback chain.
- `SkillRegistry`: Singleton with `@register_skill` decorator for auto-registration. Plugin discovery via `pkgutil.walk_packages`.
- `system/factory.py`: Singleton factory for platform-specific `SystemAutomation` implementations.

### Strategy / Tiered Execution

- **Brain Tier System**: Tier 0 (keyword) -> Tier 1 (small LLM) -> Tier 2 (medium) -> Tier 3 (large/cloud). Cheapest first, escalate on failure.
- **Hands Execution Tiers**: A (Native API) -> B (App API) -> C (UI Automation) -> D (Keyboard). Skills declare supported tiers.
- **Eyes Layered Vision**: Layer 1 (UI tree) -> Layer 2 (OCR with 5s cache) -> Layer 3 (Vision LLM).

### Pipeline / Orchestrator

- Main pipeline: `EARS -> BRAIN -> HANDS -> MOUTH` (orchestrated by `VoxAgentApp._run_loop`).
- Each module is a single-responsibility orchestrator delegating to sub-components.
- `Ears` delegates to `AudioRecorder`, `WakeWordDetector`, `VoiceActivityDetector`, `AudioConverter`.

### Observer / Callback

- `Ears._event_callbacks`: list of callables notified on state changes via `_emit()`.

### Dependency Injection

- Providers injected via constructor: `Ears(stt_provider=...)`, `Mouth(tts_provider=...)`.
- `Hands` accepts optional `Mouth` and `Ears` for voice confirmation flow.
- `Brain` receives `ProviderRegistry` and skill list.

## 10. Docstring & Documentation

- **Every module** starts with a docstring explaining purpose and context.
- **Every public class** has a docstring with description.
- **Every public method** has a docstring with `Args:`, `Returns:`, and optionally `Raises:`.
- **Dataclass attributes** documented in the class docstring `Attributes:` section.
- Format: Google-style docstrings.
- Tool: `interrogate` enforces >= 80% docstring coverage.
- Section dividers use `# -- Section Name --` comments.

```python
"""BRAIN module: Smart tier routing and LLM orchestration.

Routes incoming text through a tiered system:
- Tier 0: Keyword pattern matching (no LLM, < 50ms)
- Tier 1: Small LLM for simple intents (1-3B params)
"""
```

## 11. Constants Organization

Constants are grouped at the top of each file, after imports, using `SCREAMING_SNAKE_CASE`:

```python
# -- Constants --
VAD_SILENCE_TIMEOUT_S: float = 1.5
MAX_RECORDING_S: int = 30
```

Immutable collections use `frozenset`:

```python
DANGEROUS_ACTIONS = frozenset({"shutdown", "restart", "delete_file", ...})
ALLOWED_COMMAND_PREFIXES = frozenset({"ls", "dir", "echo", ...})
```

## 12. Logging

- Hierarchical logger names: `voxagent.brain`, `voxagent.ears`, `voxagent.skills.media_control`.
- `%s` formatting (lazy evaluation): `logger.info("Transcription: '%s'", result.text)`.
- Levels: `DEBUG` for trace, `INFO` for operations, `WARNING` for recoverable errors, `ERROR` for failures.
- `logger.exception()` auto-includes stack trace.

## 13. Frontend Patterns

### Component Architecture (Atomic Design)

- **Atoms**: `Text`, `Badge`, `Dot`, `Icon`, `Input`, `Switch`, `Slider`, `Avatar`, `ProgressBar`
- **Molecules**: `Card`, `NavItem`, `Breadcrumb`, `StatusBadge`, `Select`
- **Organisms**: Feature-specific composites (`HeroCard`, `BentoGrid`, `TerminalLog`, `ProviderCard`)
- **Templates**: Layout wrappers (`MainLayout`)
- **Containers**: Thin glue components connecting hooks to organisms

### State Management

- No global state library; each feature uses local hooks (`useState`, `useCallback`, `useEffect`).
- Polling pattern with `setInterval` + cleanup in `useEffect`.
- Default state constants defined at module scope.

### API Communication

- Single generic `fetchApi<T>()` function in `@shared/api/client.ts`.
- API base URL from `VITE_API_URL` env var with `http://localhost:8642` fallback.
- Error handling: check `resp.ok`, throw `Error` with status + body text.

## 14. Configuration

- YAML-based config at `~/.voxagent/config.yaml`.
- 4 built-in profiles: `full_local`, `cloud_free`, `hybrid`, `budget_cloud`.
- Atomic writes via `NamedTemporaryFile` + `Path.replace()`.
- CORS origins from `CORS_ORIGINS` env var (comma-separated).
- FastAPI lifespan pattern for startup/teardown.
