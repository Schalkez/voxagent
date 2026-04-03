# 🤝 Contributing to VOXAGENT

Cảm ơn bạn đã quan tâm đến VOXAGENT! Mọi đóng góp đều được chào đón — từ báo lỗi, cải thiện docs, đến thêm tính năng mới.

---

## 📋 Trước khi bắt đầu

1. Đọc [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
2. Check [Issues](https://github.com/your-org/voxagent/issues) và [Discussions](https://github.com/your-org/voxagent/discussions) để tránh duplicate
3. Với tính năng lớn, hãy mở Discussion hoặc Issue trước để align về hướng đi

---

## 🚀 Dev Setup

### Yêu cầu

- Python 3.12+
- Git
- [uv](https://github.com/astral-sh/uv) (recommended) hoặc pip

### Cài đặt

```bash
# Fork repo trên GitHub, rồi clone fork của bạn
git clone https://github.com/YOUR_USERNAME/voxagent
cd voxagent

# Tạo virtual environment và cài dependencies
uv venv
source .venv/bin/activate  # Linux/macOS
# hoặc: .venv\Scripts\activate  # Windows

uv pip install -e ".[dev]"

# Cài pre-commit hooks
pre-commit install
```

### Kiểm tra setup

```bash
# Chạy toàn bộ tests
pytest

# Chạy với coverage
pytest --cov=voxagent --cov-report=term-missing

# Chạy linting
ruff check .
mypy voxagent/
```

---

## 🔄 Workflow

### 1. Tạo branch

```bash
git checkout -b feat/your-feature-name
# hoặc: fix/bug-description
# hoặc: docs/what-you-updated
```

### 2. Code

Xem [Code Style](#code-style) bên dưới.

### 3. Test

```bash
# Chạy tests liên quan đến thay đổi của bạn
pytest tests/test_your_module.py -v

# Với integration tests (cần setup providers)
pytest tests/integration/ -v --integration
```

### 4. Commit

```bash
# Dùng Conventional Commits format
git commit -m "feat(skills): thêm spotify skill"
git commit -m "fix(ears): sửa VAD timeout với câu ngắn"
git commit -m "docs(readme): cập nhật quick start"
```

**Commit types:** `feat` | `fix` | `docs` | `test` | `refactor` | `perf` | `chore`

### 5. Pull Request

- Điền đầy đủ PR template
- Ensure CI passes (tests + linting)
- Request review từ 1 maintainer
- Squash commits trước khi merge (nếu nhiều WIP commits)

---

## 💻 Code Style

### Python

```python
# ✅ Dùng type hints đầy đủ
async def transcribe(
    self,
    audio: bytes,
    language: str = "vi",
) -> TranscribeResult:
    ...

# ✅ Docstrings cho public API
class BaseSkill:
    """Base class cho tất cả VoxAgent skills.

    Subclass này và implement execute() để tạo skill mới.
    Xem SKILL_DEVELOPMENT_GUIDE.md để biết chi tiết.
    """
```

**Tools:** `ruff` (linting + formatting), `mypy` (type checking)

Config trong `pyproject.toml` — không cần cấu hình thêm.

### Async/await

VoxAgent dùng `asyncio` xuyên suốt. Mọi I/O (LLM calls, STT, TTS, file ops) phải async:

```python
# ✅ Đúng
async def chat(self, messages: list) -> str:
    async with aiohttp.ClientSession() as session:
        ...

# ❌ Sai — blocking I/O trong async context
async def chat(self, messages: list) -> str:
    response = requests.post(...)  # blocks event loop!
```

### Error handling

```python
# ✅ Raise ProviderError, không re-raise Exception raw
async def chat(self, messages) -> str:
    try:
        response = await self._client.chat(messages)
        return response.content
    except aiohttp.ClientError as e:
        raise ProviderError(
            provider=self.name,
            message=f"API request failed: {e}",
            retryable=True,
        ) from e
```

---

## 🧪 Testing Guidelines

### Unit tests (bắt buộc cho mọi code mới)

```python
# tests/test_brain.py
import pytest
from unittest.mock import AsyncMock, patch
from voxagent.core.brain import Brain

@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.chat.return_value = "Đã skip rồi nha"
    return provider

async def test_tier0_routing_skip(mock_provider):
    brain = Brain(providers={"tier1": mock_provider})
    result = await brain.process("skip")
    assert result.tier == 0
    mock_provider.chat.assert_not_called()  # Tier 0 không gọi LLM
```

### Mock providers

Dùng `MockLLMProvider`, `MockSTTProvider`, `MockTTSProvider` trong `tests/conftest.py` — đừng gọi API thật trong unit tests.

### Coverage target

- **Core modules:** ≥ 85%
- **Providers:** ≥ 70%
- **Skills:** ≥ 80%

---

## 📁 Các loại đóng góp

### 🐛 Báo lỗi

Dùng [bug report template](.github/ISSUE_TEMPLATE/bug_report.md). Cần include:
- OS + Python version
- Config profile đang dùng
- Logs từ `~/.voxagent/logs/voxagent.log`
- Steps to reproduce

### ✨ Tính năng mới

1. Mở Discussion để validate ý tưởng trước
2. Với tính năng lớn (> 200 LOC), tạo RFC draft trong Discussions
3. Implement và viết tests
4. Update docs nếu cần

### 🔌 Thêm Provider mới

1. Tạo file trong `voxagent/providers/{type}/your_provider.py`
2. Implement interface tương ứng (`LLMProvider`, `STTProvider`, `TTSProvider`, `VisionProvider`)
3. Thêm vào registry trong `voxagent/providers/registry.py`
4. Thêm tests trong `tests/test_providers.py`
5. Update [docs/providers.md](docs/providers.md)

### 🔌 Thêm Skill mới

Xem [SKILL_DEVELOPMENT_GUIDE.md](SKILL_DEVELOPMENT_GUIDE.md) đầy đủ.

Nhanh gọn:
1. Tạo `voxagent/skills/your_skill.py`, extend `BaseSkill`
2. Khai báo `skill.json` với permissions
3. Thêm tests
4. PR vào `main`

### 🌐 Hỗ trợ ngôn ngữ/nền tảng mới

- **Platform mới** (macOS, Linux): implement `SystemAutomation` interface trong `voxagent/platform/`
- **Ngôn ngữ mới**: thêm wake word model, kiểm tra STT accuracy, thêm TTS voice

---

## 📞 Cần giúp đỡ?

- 💬 [Discord #dev-help](https://discord.gg/voxagent)
- 📝 [GitHub Discussions](https://github.com/your-org/voxagent/discussions)
- 🐛 Tag issue với `good first issue` để bắt đầu dễ hơn

---

## 🏷️ Labels quan trọng

| Label | Ý nghĩa |
|-------|---------|
| `good first issue` | Phù hợp cho người mới |
| `help wanted` | Maintainer muốn cộng đồng pick up |
| `skill` | Liên quan đến skill system |
| `provider` | Thêm hoặc sửa provider |
| `platform` | macOS / Linux support |
| `blocked` | Đang chờ decision / dependency |

---

Cảm ơn đã đóng góp! 🙏
