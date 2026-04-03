# 🔌 VOXAGENT Skill Development Guide

Hướng dẫn tạo skills (plugins) cho VoxAgent — từ skill đơn giản đến skill nâng cao có vision và autopilot.

---

## 1. Skill là gì?

Skill là module mở rộng giúp VoxAgent thực hiện một nhóm tác vụ cụ thể. Ví dụ:
- `media_control` — play, pause, skip nhạc
- `browser_control` — điều hướng browser, skip ads
- `terminal` — chạy git, npm, python commands

Mỗi skill có thể được trigger bởi:
- **Tier 0:** keyword matching (nhanh nhất, không cần LLM)
- **Tier 1–3:** LLM detect intent và route vào skill

---

## 2. Tạo skill đầu tiên

### Bước 1: Tạo file skill

```python
# voxagent/skills/my_skill.py

from voxagent.skills.base import BaseSkill, SkillResult, SkillContext
from voxagent.platform import get_platform


class MySkill(BaseSkill):
    # === Metadata (bắt buộc) ===
    name = "my_skill"
    description = """
    Mô tả skill cho LLM hiểu khi nào nên dùng.
    Càng rõ ràng càng tốt. Ví dụ:
    'Dùng khi user muốn X, Y, hoặc Z.
     Không dùng khi A hoặc B.'
    """

    # Tier 0 keywords (không cần LLM)
    keywords = ["từ khoá", "keyword", "trigger word"]

    # Tier tối thiểu cần để chạy skill này
    min_tier = 0

    # Platforms hỗ trợ
    os_support = ["windows", "macos", "linux"]  # hoặc chỉ ["windows"]

    def execute(self, intent: dict, context: SkillContext) -> SkillResult:
        # Logic chính ở đây

        # Ví dụ: lấy parameter từ intent
        target = intent.get("params", {}).get("target", "default")

        # Thực hiện action
        try:
            # ... code của bạn ...
            return SkillResult(
                success=True,
                tts_response=f"Đã làm xong {target} rồi nha",
                data={"result": "some data"}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                tts_response=f"Không làm được vì {str(e)}",
                error=str(e)
            )
```

### Bước 2: Tạo skill manifest

```json
// voxagent/skills/my_skill.json
{
  "name": "my_skill",
  "version": "1.0.0",
  "display_name": "My Skill",
  "description": "Mô tả ngắn cho người dùng thấy",
  "author": "Your Name",
  "license": "Apache-2.0",
  "min_voxagent_version": "0.1.0",
  "os_support": ["windows", "macos", "linux"],
  "permissions": [
    "filesystem:read"
  ],
  "dependencies": {
    "python": ["requests>=2.28.0"],
    "system": []
  }
}
```

**Danh sách permissions hợp lệ:**

| Permission | Mô tả |
|-----------|-------|
| `filesystem:read` | Đọc files/directories |
| `filesystem:write` | Tạo/sửa/xóa files |
| `process:list` | Liệt kê running processes |
| `process:launch` | Mở application |
| `process:kill` | Tắt process |
| `browser:control` | Điều khiển browser |
| `browser:history` | Đọc browser history |
| `network:request` | Gọi HTTP APIs |
| `system:volume` | Thay đổi âm lượng |
| `system:display` | Thay đổi độ sáng, resolution |
| `system:power` | Shutdown, restart, sleep |
| `screen:read` | Chụp và đọc màn hình |
| `clipboard:read` | Đọc clipboard |
| `clipboard:write` | Ghi vào clipboard |

### Bước 3: Đăng ký skill

```python
# voxagent/skills/__init__.py — thêm vào danh sách
from .my_skill import MySkill

BUILTIN_SKILLS = [
    MediaControlSkill,
    BrowserControlSkill,
    # ...
    MySkill,  # thêm dòng này
]
```

### Bước 4: Viết tests

```python
# tests/test_skills.py

import pytest
from voxagent.skills.my_skill import MySkill

class TestMySkill:
    def setup_method(self):
        self.skill = MySkill()

    def test_handles_keyword(self):
        assert self.skill.can_handle_keyword("từ khoá")

    def test_execute_success(self):
        intent = {"params": {"target": "something"}}
        result = self.skill.execute(intent, context={})
        assert result.success
        assert "xong" in result.tts_response

    def test_execute_error_handling(self):
        intent = {"params": {"target": None}}
        result = self.skill.execute(intent, context={})
        # Should not raise, should return SkillResult with error
        assert result is not None
```

---

## 3. SkillResult — Chi tiết

```python
@dataclass
class SkillResult:
    success: bool = True

    # Text để TTS đọc cho user
    tts_response: str = ""

    # Data trả về (cho chaining, autopilot, v.v.)
    data: dict = field(default_factory=dict)

    # Nếu có lỗi
    error: Optional[str] = None

    # User đã cancel (vd: không confirm action nguy hiểm)
    cancelled: bool = False

    # Tạo autopilot task từ skill result
    autopilot_task: Optional[AutopilotTask] = None

    # Cần thêm info từ user trước khi tiếp tục
    needs_clarification: Optional[str] = None
```

---

## 4. Skill nâng cao

### Skill với Vision (đọc màn hình)

```python
class ScreenReaderSkill(BaseSkill):
    name = "screen_reader"
    keywords = ["đọc màn hình", "screen có gì", "trên màn hình"]
    min_tier = 1

    def execute(self, intent: dict, context: SkillContext) -> SkillResult:
        eyes = context.eyes

        # Layer 1: Thử UI Automation trước (nhanh + free)
        active_window = eyes.get_active_window()
        if active_window.text_content:
            summary = context.llm.summarize(active_window.text_content)
            return SkillResult(success=True, tts_response=summary)

        # Layer 2: OCR nếu Layer 1 không đủ
        ocr_text = eyes.ocr_region(region="center")
        if ocr_text:
            summary = context.llm.summarize(ocr_text)
            return SkillResult(success=True, tts_response=summary)

        # Layer 3: Vision LLM (tốn nhất — dùng cuối cùng)
        screenshot = eyes.capture_region(region="center", max_size=(800, 600))
        analysis = context.vision.analyze(
            image=screenshot,
            prompt="Mô tả ngắn gọn nội dung chính trên màn hình bằng tiếng Việt"
        )
        return SkillResult(success=True, tts_response=analysis)
```

### Skill với Memory (lưu state)

```python
class CodeReviewerSkill(BaseSkill):
    name = "code_reviewer"
    keywords = ["cursor xong chưa", "check code", "review code"]
    min_tier = 2

    def execute(self, intent: dict, context: SkillContext) -> SkillResult:
        memory = context.memory

        # Đọc state từ lần trước
        last_check = memory.skill_get(self.name, "last_cursor_state")

        # Check Cursor window
        cursor_window = context.eyes.find_window("Cursor")
        if not cursor_window:
            return SkillResult(
                success=False,
                tts_response="Không thấy Cursor đang chạy"
            )

        current_state = context.eyes.ocr_region(
            window=cursor_window,
            region="output_panel"
        )

        # So sánh với state cũ
        if current_state == last_check:
            return SkillResult(
                success=True,
                tts_response="Cursor vẫn đang chạy, chưa xong"
            )

        # LLM đánh giá kết quả
        evaluation = context.llm.chat([
            {"role": "user", "content": f"Code output này đã hoàn thành chưa?\n{current_state}"}
        ])

        # Lưu state mới
        memory.skill_set(self.name, "last_cursor_state", current_state)

        return SkillResult(
            success=True,
            tts_response=evaluation,
            data={"completed": "100%" in current_state}
        )
```

### Skill tạo Autopilot Task

```python
class AutoPromptSkill(BaseSkill):
    name = "auto_prompt"
    description = "Tự động prompt Cursor khi idle. Dùng khi user muốn VoxAgent theo dõi và tiếp tục task tự động."
    min_tier = 2

    def execute(self, intent: dict, context: SkillContext) -> SkillResult:
        follow_up_prompt = intent.get("params", {}).get("prompt", "tiếp tục")

        # Tạo autopilot task — chạy nền
        task = AutopilotTask(
            trigger=TriggerType.IDLE_BASED,
            condition=lambda: self._is_cursor_idle(context),
            actions=[
                lambda: self._check_and_prompt(context, follow_up_prompt)
            ],
            repeat=True,
            max_retries=10,
        )

        return SkillResult(
            success=True,
            tts_response="Rồi, tôi sẽ theo dõi và tự prompt khi Cursor xong",
            autopilot_task=task
        )

    def _is_cursor_idle(self, context) -> bool:
        cursor = context.eyes.find_window("Cursor")
        return cursor and cursor.cpu_usage < 5.0

    def _check_and_prompt(self, context, prompt: str):
        output = context.eyes.ocr_region(window="Cursor", region="output")
        is_done = "100%" in output or "completed" in output.lower()

        if not is_done:
            context.hands.keyboard.type(prompt)
            context.hands.keyboard.press("enter")
        else:
            context.mouth.speak("Cursor đã xong 100% rồi nha!")
            return "DONE"  # Stop autopilot loop
```

---

## 5. Async Skills

Với skills cần I/O nặng (API calls, database, v.v.), dùng async:

```python
class WebSearchSkill(BaseSkill):
    name = "web_search"
    min_tier = 2

    # Khai báo là async skill
    is_async = True

    async def execute_async(
        self,
        intent: dict,
        context: SkillContext
    ) -> SkillResult:
        query = intent.get("params", {}).get("query", "")

        async with aiohttp.ClientSession() as session:
            results = await search_web(session, query)

        summary = await context.llm.summarize_async(results[:3])
        return SkillResult(success=True, tts_response=summary)
```

---

## 6. Platform-specific Skills

Nếu skill chỉ chạy được trên một số OS:

```python
class WindowsNotificationSkill(BaseSkill):
    name = "windows_notifications"
    os_support = ["windows"]  # Chỉ Windows

    def execute(self, intent, context) -> SkillResult:
        import win32api  # Safe vì chỉ load trên Windows
        ...
```

VoxAgent tự động disable skill nếu OS không hỗ trợ và báo user biết.

---

## 7. Testing Best Practices

```python
# Dùng mock để không cần real providers
from tests.mocks import MockEyes, MockLLM, MockHands

def test_my_skill_with_mocks():
    skill = MySkill()
    context = SkillContext(
        eyes=MockEyes(active_window_title="Chrome"),
        llm=MockLLM(response="kết quả mock"),
        hands=MockHands(),
        memory=MemoryStore(":memory:"),  # in-memory SQLite
    )
    result = skill.execute(intent={}, context=context)
    assert result.success
```

---

## 8. Publish lên Skill Marketplace

Khi skill ổn định và tested:

1. Tạo repository riêng: `voxagent-skill-{tên-skill}`
2. Đảm bảo có `skill.json`, README, tests
3. Tag release: `git tag v1.0.0`
4. Submit PR vào [voxagent-skills-registry](https://github.com/your-org/voxagent-skills-registry)

Maintainer sẽ review `skill.json` permissions và code trước khi approve.

---

## 9. Ví dụ hoàn chỉnh: YouTube Ad Skipper

```python
# voxagent/skills/youtube_ad_skipper.py

from voxagent.skills.base import BaseSkill, SkillResult, SkillContext


class YouTubeAdSkipper(BaseSkill):
    name = "youtube_ad_skipper"
    description = "Skip quảng cáo YouTube. Dùng khi user nói skip, bỏ qua, hay skip ad."
    keywords = ["skip", "bỏ quảng cáo", "skip ad", "bỏ ad"]
    min_tier = 0
    os_support = ["windows", "macos", "linux"]

    def execute(self, intent: dict, context: SkillContext) -> SkillResult:
        eyes = context.eyes
        hands = context.hands

        # Kiểm tra YouTube có đang mở không
        window = eyes.get_active_window()
        if "YouTube" not in (window.title or ""):
            return SkillResult(
                success=False,
                tts_response="Không thấy YouTube đang mở"
            )

        # Layer 1: UI Automation — tìm nút Skip
        skip_button = eyes.find_element(role="button", name_pattern="Skip Ad*")
        if skip_button:
            hands.click(skip_button)
            return SkillResult(
                success=True,
                tts_response="Đã skip quảng cáo rồi nha"
            )

        # Layer 2: Keyboard shortcut fallback
        hands.keyboard.hotkey("tab")
        hands.keyboard.press("enter")
        return SkillResult(
            success=True,
            tts_response="Đã thử skip rồi"
        )
```

```json
// voxagent/skills/youtube_ad_skipper.json
{
  "name": "youtube_ad_skipper",
  "version": "1.0.0",
  "display_name": "YouTube Ad Skipper",
  "description": "Tự động skip quảng cáo YouTube bằng giọng nói",
  "author": "Your Name",
  "license": "Apache-2.0",
  "min_voxagent_version": "0.1.0",
  "os_support": ["windows", "macos", "linux"],
  "permissions": [
    "screen:read",
    "browser:control"
  ],
  "dependencies": {
    "python": [],
    "system": []
  }
}
```

---

## 10. Checklist trước khi PR

- [ ] `skill.json` có đầy đủ fields
- [ ] Permissions khai báo đúng (không khai báo thừa)
- [ ] Tests đạt coverage ≥ 80%
- [ ] Không có blocking I/O trong sync methods
- [ ] Graceful error handling (không raise raw exceptions)
- [ ] Platform check nếu dùng OS-specific APIs
- [ ] README hoặc docstring mô tả rõ skill làm gì và khi nào dùng
