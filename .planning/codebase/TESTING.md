# VoxAgent Testing Patterns

## 1. Framework & Tooling

| Tool | Purpose | Config Location |
|------|---------|-----------------|
| pytest 8.3+ | Test runner | `pyproject.toml [tool.pytest.ini_options]` |
| pytest-asyncio 0.24+ | Async test support | `asyncio_mode = "auto"` (global) |
| pytest-cov 6.0+ | Coverage reporting | `pyproject.toml [tool.coverage.*]` |
| unittest.mock | Mocking (stdlib) | Used directly, no third-party mock lib |
| FastAPI TestClient | API integration tests | `from fastapi.testclient import TestClient` |
| bandit 1.8+ | Security linting | `pyproject.toml [tool.bandit]` |
| interrogate 1.7+ | Docstring coverage | `fail-under = 80` |
| vulture 2.13+ | Dead code detection | `min_confidence = 70` |

### Pytest Configuration

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["../tests"]
asyncio_mode = "auto"
addopts = "-v --tb=short"
filterwarnings = ["ignore::DeprecationWarning"]
markers = [
    "slow: marks tests as slow",
    "integration: integration tests requiring external services",
    "platform: platform-specific tests",
]
```

Key: `asyncio_mode = "auto"` means `@pytest.mark.asyncio` is applied automatically
to all async test functions, though tests still use the explicit marker for clarity.

## 2. Test File Structure

### Directory Layout

```
agent/tests/
  conftest.py              # Global fixtures and module-level mocks
  test_api.py              # FastAPI endpoint integration tests
  test_app_compliance.py   # VoxAgentApp + Ears lifecycle tests
  test_audio.py            # Audio subsystem (recorder, VAD, wake word, converter)
  test_autopilot.py        # Autopilot task scheduling
  test_brain.py            # Brain intent routing (tier 0 + LLM)
  test_config.py           # Configuration load/save/profiles
  test_ears.py             # Ears state machine and dataclasses
  test_eyes.py             # Eyes module dataclasses and stubs
  test_hands.py            # Hands orchestration and skill dispatch
  test_llm_providers.py    # Provider model_info + health_check (all 7 LLM providers)
  test_memory.py           # SQLite CRUD operations
  test_mouth.py            # TTS output and response templates
  test_new_skills.py       # Phase 2 skills (terminal, file_manager, browser)
  test_providers.py        # Provider registry and fallback chain
  test_security_phase1.py  # Terminal command safety validation
  test_skills.py           # Built-in skills (media_control, app_launcher, system_control)
  test_system.py           # System automation factory and dataclasses
  test_coverage_boost.py   # Supplemental tests for coverage gaps
  test_final_coverage.py   # Final coverage push tests
  test_phase2_5.py         # Phase 2.5 feature tests
  test_push_80.py          # Coverage target tests
  test_remaining_features.py  # Remaining feature coverage
```

### Naming Convention

- Files: `test_<module_name>.py` — maps to the source module being tested.
- Classes: `Test<ComponentName>` — groups related tests for one class/concept.
- Methods: `test_<behavior_description>` — describes the expected behavior.
- Docstrings: Every test method has a one-line docstring explaining intent.

```python
class TestBrainTierZero:
    """Test Tier 0 keyword matching."""

    @pytest.mark.asyncio
    async def test_keyword_match_returns_correct_skill(self, brain: Brain) -> None:
        """Tier 0 should match keywords to skills."""
```

## 3. Test Organization Pattern

Tests are organized into **class-based groups**, each testing one logical unit:

```python
class TestProviderRegistryLLM:
    """Test LLM provider registration and retrieval."""

    def test_register_and_get(self) -> None: ...
    def test_get_unregistered_raises(self) -> None: ...
    def test_get_returns_cached_instance(self) -> None: ...

class TestFallbackChain:
    """Test LLM fallback chain logic."""

    @pytest.mark.asyncio
    async def test_fallback_returns_healthy_provider(self) -> None: ...
```

Common patterns per class:
- **Dataclass tests**: `test_frozen`, `test_defaults`, `test_fields`
- **Lifecycle tests**: `test_connect`, `test_close`, `test_stop`
- **CRUD tests**: `test_add_and_retrieve`, `test_update`, `test_get_missing_returns_default`
- **Error tests**: `test_get_unregistered_raises`, `test_invalid_raises`
- **Can-handle tests**: `test_can_handle_own_intent`, `test_rejects_other_skills`

## 4. Fixtures

### Global Fixtures (`conftest.py`)

The conftest performs **module-level mocking** of `keyring` before any imports:

```python
# Must happen before ANY test module import
mock_keyring_obj = MagicMock()
mock_keyring_obj.get_password.return_value = "mock-api-key"
mock_keyring_obj.set_password.return_value = None
mock_keyring_obj.delete_password.return_value = None
sys.modules["keyring"] = mock_keyring_obj

@pytest.fixture(autouse=True, scope="session")
def mock_keyring_fixture():
    """Provides access to the global keyring mock if needed."""
    return mock_keyring_obj
```

This is critical because providers import `keyring` at module level for API key access.

### Common Fixture Patterns

**Factory fixtures** that build configured test objects:

```python
@pytest.fixture
def brain() -> Brain:
    """Create a Brain instance with mock providers and skills."""
    registry = ProviderRegistry()
    registry.register_llm("mock", MockLLM)
    registry.register_llm("ollama", MockLLM)
    registry.set_fallback_chain(["mock", "ollama"])
    skills = [MockSkill()]
    return Brain(registry=registry, skills=skills, routing_config={})
```

**Async fixtures** with cleanup using `yield`:

```python
@pytest.fixture
async def memory(tmp_path):
    """Create a Memory instance connected to a temporary database."""
    db_path = str(tmp_path / "test_memory.db")
    mem = Memory()
    await mem.connect(db_path)
    yield mem
    await mem.close()
```

**TestClient fixture** for API tests:

```python
@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app with lifespan context."""
    with TestClient(app) as client:
        yield client
```

**Monkeypatch fixtures** for registry isolation:

```python
@pytest.fixture
def _mock_registry(monkeypatch):
    registry = SkillRegistry()
    monkeypatch.setattr(SkillRegistry, "_skills", {})
    registry.register(DummySkill)
    return registry
```

## 5. Mocking Strategies

### Mock Classes (Full ABC Implementation)

For provider testing, concrete mock classes implement the full ABC interface:

```python
class MockLLM(LLMProvider):
    """Mock LLM provider for testing."""

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        return "mock response"

    async def chat_with_tools(
        self, messages: list[Message], tools: list[dict[str, object]], **kwargs: object
    ) -> dict[str, object]:
        return {"tool": "media_control", "result": {"action": "play_pause"}}

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(name="mock", provider="mock")

    async def health_check(self) -> bool:
        return True
```

Variant mocks test different behaviors (e.g., `MockUnhealthyLLM` always returns `False` from `health_check`).

### Mock Skills (Minimal ABC Implementation)

```python
class DummySkill(BaseSkill):
    name = "dummy"
    description = "A dummy skill for testing"
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.APP_API]

    async def can_handle(self, intent: SkillIntent) -> bool:
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent):
        return SkillResult(success=True, data={"run": True}, tier_used=ExecutionTier.APP_API)
```

### `unittest.mock` Usage

| Mock Type | Used For | Example |
|-----------|----------|---------|
| `MagicMock()` | Sync objects/modules | `mock_keyring_obj = MagicMock()` |
| `AsyncMock()` | Async methods/providers | `stt.transcribe = AsyncMock(return_value=...)` |
| `@patch("module.path")` | Module-level patching | `@patch("core.app.load_config", return_value=...)` |
| `patch()` context manager | Scoped patching within test | `with patch("system.factory.get_system_automation"):` |
| `monkeypatch.setattr` | pytest-native attribute patching | `monkeypatch.setattr(SkillRegistry, "_skills", {})` |

### Keyring Mocking (Provider Tests)

Each provider test patches `get_key` at the provider module level:

```python
def test_model_info(self) -> None:
    with patch("providers.groq_provider.get_key", return_value="fake-key"):
        from providers.groq_provider import GroqProvider
        p = GroqProvider()
        info = p.get_model_info()
        assert info.provider == "groq"
```

### Heavy Dependency Mocking (Ears/Audio)

Multiple context managers mock audio subsystem components:

```python
with (
    patch("core.ears.AudioRecorder") as mock_recorder_cls,
    patch("core.ears.WakeWordDetector") as mock_ww_cls,
    patch("core.ears.VoiceActivityDetector") as mock_vad_cls,
):
    mock_recorder = mock_recorder_cls.return_value
    mock_recorder.stop = AsyncMock()
    ears = Ears(stt_provider=_make_mock_stt(), config=_make_config())
```

## 6. Async Testing

All async tests use `@pytest.mark.asyncio` (explicit marker despite `asyncio_mode = "auto"`):

```python
@pytest.mark.asyncio
async def test_fallback_returns_healthy_provider(self) -> None:
    """Should return the first healthy provider in the chain."""
    registry = ProviderRegistry()
    registry.register_llm("unhealthy", MockUnhealthyLLM)
    registry.register_llm("healthy", MockLLM)
    registry.set_fallback_chain(["unhealthy", "healthy"])
    provider = await registry.get_llm_with_fallback()
    assert isinstance(provider, MockLLM)
```

Class-level marking for entire async test classes:

```python
@pytest.mark.asyncio
class TestHandsOrchestration:
    async def test_hands_executes_registered_skill(self, _mock_registry): ...
    async def test_hands_returns_error_for_unknown_skill(self, _mock_registry): ...
```

## 7. API Integration Tests

Uses FastAPI `TestClient` with lifespan management for real server lifecycle:

```python
@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as client:
        yield client

class TestProviderEndpoints:
    def test_list_providers(self, client: TestClient) -> None:
        """GET /api/providers should return provider list."""
        response = client.get("/api/providers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_provider_has_required_fields(self, client: TestClient) -> None:
        """Each provider should have id, name, and status."""
        response = client.get("/api/providers")
        data = response.json()
        for provider in data:
            assert "id" in provider
            assert "name" in provider
            assert "status" in provider
```

Pattern: Test status codes, response structure, and field presence. No real API calls.

## 8. Testing Categories

### Unit Tests (Majority)

Test individual classes/functions in isolation with mocked dependencies:
- Dataclass immutability (`frozen=True` verified via `pytest.raises(AttributeError)`)
- Default values and field presence
- Return types and value correctness
- Error conditions and exception types
- State transitions

### Component Tests

Test module interactions with mocked external boundaries:
- `test_brain.py`: Brain + MockLLM + MockSkill (tests routing logic)
- `test_hands.py`: Hands + DummySkill + SkillRegistry (tests dispatch)
- `test_app_compliance.py`: VoxAgentApp + Ears lifecycle with all deps mocked

### Integration Tests (API)

- `test_api.py`: Full FastAPI app with real router wiring, mocked providers via lifespan.

### Security Tests

- `test_security_phase1.py`: Command safety validation (allowlist, blocked patterns, Unicode bypass).

## 9. Assertion Patterns

### Standard Assertions

```python
assert result.success is True              # Boolean identity
assert result.skill_name == "media_control"  # Equality
assert isinstance(provider, MockLLM)       # Type check
assert "ollama" in config.providers        # Membership
assert len(results) == 3                   # Collection size
assert result is not None                  # None check
assert a is b                              # Identity (singleton/caching)
```

### Exception Assertions

```python
# Basic exception check
with pytest.raises(ProviderNotFoundError):
    registry.get_llm("nonexistent")

# With message match
with pytest.raises(ValueError, match="Unknown profile"):
    load_profile("nonexistent_profile")

# Frozen dataclass mutation
with pytest.raises(AttributeError):
    intent.skill_name = "changed"  # type: ignore[misc]
```

### String Content Assertions

```python
assert "Anh muốn mở ứng dụng nào" in (result.tts_response or "")
assert "75" in (result.tts_response or "")
assert "blocked by safety filter" in str(result.error)
```

### Mock Assertions

```python
mock_tts.synthesize.assert_called_once_with("Xin chào", voice="vi-female", speed=1.0)
mock_tts.synthesize.assert_not_called()
mock_recorder.stop.assert_awaited_once()
mock_ww.load.assert_called_once()
callback.assert_called_once()
mock_auto.return_value.set_volume.assert_called_once_with(75)
```

## 10. Coverage Configuration

```toml
[tool.coverage.run]
source = ["core", "providers", "skills", "system"]
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
fail_under = 50
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
    "@abstractmethod",
]
```

### Coverage Targets

- **Goal**: >80% on `core/` and `skills/` (per CLAUDE.md).
- **CI minimum**: `fail_under = 50` (configured threshold).
- **Excluded from coverage**: `TYPE_CHECKING` blocks, `__main__` guards, abstract methods.
- **Supplemental test files** (`test_coverage_boost.py`, `test_push_80.py`, `test_final_coverage.py`) exist specifically to close coverage gaps.

### Coverage Source

Only source packages are measured: `core`, `providers`, `skills`, `system`. Tests and `api/` are excluded from source measurement.

## 11. Test Data Patterns

### Temporary Paths

pytest's built-in `tmp_path` fixture for file/database tests:

```python
async def test_connect_creates_tables(self, tmp_path) -> None:
    mem = Memory()
    db_path = str(tmp_path / "new.db")
    await mem.connect(db_path)
```

### Intent Factories

SkillIntent constructed inline with Vietnamese raw text:

```python
intent = SkillIntent(
    skill_name="media_control",
    action="play_pause",
    params={},
    raw_text="play music",
)
```

### Vietnamese Content

Tests use Vietnamese strings for response validation, reflecting the product's primary language:

```python
assert result == "Đã phát nhạc rồi nha"
assert result.tts_response == "Tôi không tìm thấy kỹ năng này."
```

## 12. Parametrized Tests

Used sparingly for profile testing:

```python
@pytest.mark.parametrize("profile_name", ["full_local", "cloud_free", "hybrid", "budget_cloud"])
def test_load_profile_returns_valid_config(self, profile_name: str) -> None:
    """Each profile should produce a valid VoxAgentConfig."""
    config = load_profile(profile_name)
    assert isinstance(config, VoxAgentConfig)
```

## 13. Key Principles

1. **No real network calls** — All external APIs (LLM, STT, TTS) are mocked.
2. **No real audio hardware** — AudioRecorder, microphone, speakers are mocked.
3. **No real OS keyring** — `keyring` module replaced with MagicMock at import time.
4. **Temporary databases** — SQLite tests use `tmp_path` for clean isolation.
5. **Type annotations on tests** — Return types (`-> None`) on all test methods.
6. **Docstrings on test methods** — One-line description of expected behavior.
7. **Fixture-per-test-class** — Fixtures scoped to the test class that uses them.
8. **Skills tested in isolation** — Each skill instantiated directly, not via registry in unit tests.
9. **Registry tests use fresh instances** — No shared singleton state between tests.
