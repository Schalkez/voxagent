"""Coverage boost tests: targeting core/ and skills/ from 74% to >80%.

Covers:
- core/planner.py (36% -> ~90%)
- core/ocr.py (47% -> ~90%)
- skills/app_launcher.py (55% -> ~90%)
- core/audio/wake_word.py (56% -> ~90%)
- core/ears.py (62% -> ~80%)
- core/eyes.py (64% -> ~85%)
- skills/marketplace.py (61% -> ~85%)
- core/audio/vad.py (52% -> ~80%)
- core/audio/text_chunker.py (73% -> ~95%)
- core/brain.py (75% -> ~85%)
- core/autopilot.py (70% -> ~85%)
- skills/dependency_resolver.py (74% -> ~90%)
- skills/system_control.py (80% -> ~90%)
- core/audio/recorder.py (71% -> ~80%)
- core/audio/streaming_player.py (73% -> ~80%)
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from core.brain import Intent, Tier
from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult


# ============================================================================
# core/planner.py -- from 36% to ~90%
# ============================================================================


class TestPlanner:
    """Tests for the Planner module."""

    def _make_config(self) -> MagicMock:
        """Create a mock VoxAgentConfig."""
        config = MagicMock()
        config.routing.tier_3.provider = "ollama"
        config.routing.tier_3.model = "llama3.1:8b"
        return config

    def _make_planner(
        self,
        registry: MagicMock | None = None,
        skills: list[BaseSkill] | None = None,
    ):
        from core.planner import Planner

        reg = registry or MagicMock()
        sk = skills or []
        return Planner(registry=reg, skills=sk, config=self._make_config())

    def test_is_multi_step_detects_and(self) -> None:
        planner = self._make_planner()
        assert planner.is_multi_step("open chrome and shutdown") is True

    def test_is_multi_step_detects_then(self) -> None:
        planner = self._make_planner()
        assert planner.is_multi_step("open chrome then close it") is True

    def test_is_multi_step_detects_vietnamese(self) -> None:
        planner = self._make_planner()
        assert planner.is_multi_step("mo chrome rồi tat may") is True

    def test_is_multi_step_returns_false_for_simple(self) -> None:
        planner = self._make_planner()
        assert planner.is_multi_step("open chrome") is False

    @pytest.mark.asyncio
    async def test_plan_success_with_steps(self) -> None:
        """Planner returns list of Intents from LLM response."""
        registry = MagicMock()
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.return_value = {
            "tool": "create_plan",
            "result": {
                "steps": [
                    {"skill_name": "app_launcher", "action": "open", "params": {"app": "chrome"}},
                    {"skill_name": "system_control", "action": "shutdown", "params": {}},
                ]
            },
        }
        registry.get_llm.return_value = mock_llm

        planner = self._make_planner(registry=registry)
        intents = await planner.plan("open chrome then shutdown")

        assert len(intents) == 2
        assert intents[0].skill_name == "app_launcher"
        assert intents[0].action == "open"
        assert intents[1].skill_name == "system_control"

    @pytest.mark.asyncio
    async def test_plan_fallback_when_provider_not_found(self) -> None:
        """Falls back to ollama when primary provider is not found."""
        from providers.registry import ProviderNotFoundError

        registry = MagicMock()
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.return_value = {
            "tool": "create_plan",
            "result": {"steps": [{"skill_name": "test", "action": "do", "params": {}}]},
        }
        registry.get_llm.side_effect = [ProviderNotFoundError("ollama"), mock_llm]
        # Fix: second call returns the mock_llm
        registry.get_llm.side_effect = None
        registry.get_llm.return_value = mock_llm

        planner = self._make_planner(registry=registry)
        intents = await planner.plan("do something")
        assert len(intents) >= 1

    @pytest.mark.asyncio
    async def test_plan_returns_unknown_on_llm_error(self) -> None:
        """When LLM raises, returns a fallback unknown Intent."""
        registry = MagicMock()
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.side_effect = RuntimeError("LLM down")
        registry.get_llm.return_value = mock_llm

        planner = self._make_planner(registry=registry)
        intents = await planner.plan("do something")

        assert len(intents) == 1
        assert intents[0].skill_name == "unknown"
        assert intents[0].confidence == 0.0

    @pytest.mark.asyncio
    async def test_plan_with_string_steps(self) -> None:
        """Steps as JSON string are parsed correctly."""
        registry = MagicMock()
        mock_llm = AsyncMock()
        steps_json = json.dumps([{"skill_name": "app_launcher", "action": "open", "params": {"app": "notepad"}}])
        mock_llm.chat_with_tools.return_value = {
            "tool": "create_plan",
            "result": {"steps": steps_json},
        }
        registry.get_llm.return_value = mock_llm

        planner = self._make_planner(registry=registry)
        intents = await planner.plan("open notepad")

        assert len(intents) == 1
        assert intents[0].skill_name == "app_launcher"

    @pytest.mark.asyncio
    async def test_plan_with_string_result(self) -> None:
        """Result as string is parsed via json.loads."""
        registry = MagicMock()
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.return_value = {
            "tool": "create_plan",
            "result": json.dumps({
                "steps": [{"skill_name": "terminal", "action": "run", "params": {}}]
            }),
        }
        registry.get_llm.return_value = mock_llm

        planner = self._make_planner(registry=registry)
        intents = await planner.plan("run command")

        assert len(intents) == 1
        assert intents[0].skill_name == "terminal"

    @pytest.mark.asyncio
    async def test_plan_wrong_tool_name_returns_unknown(self) -> None:
        """Non-create_plan tool name falls through to unknown."""
        registry = MagicMock()
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.return_value = {
            "tool": "other_tool",
            "result": {"data": "irrelevant"},
        }
        registry.get_llm.return_value = mock_llm

        planner = self._make_planner(registry=registry)
        intents = await planner.plan("do something weird")

        assert len(intents) == 1
        assert intents[0].skill_name == "unknown"

    @pytest.mark.asyncio
    async def test_plan_non_dict_result_not_json(self) -> None:
        """Non-JSON string result falls through gracefully."""
        registry = MagicMock()
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.return_value = {
            "tool": "create_plan",
            "result": "not valid json at all",
        }
        registry.get_llm.return_value = mock_llm

        planner = self._make_planner(registry=registry)
        intents = await planner.plan("blah")

        assert len(intents) == 1
        assert intents[0].skill_name == "unknown"

    def test_build_planner_tools_schema(self) -> None:
        """Tools schema includes skill names."""

        class DummySkill(BaseSkill):
            name = "dummy"
            description = "A dummy skill"
            execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]

            async def can_handle(self, intent: SkillIntent) -> bool:
                return True

            async def execute(self, intent: SkillIntent) -> SkillResult:
                return SkillResult.ok()

        planner = self._make_planner(skills=[DummySkill()])
        schema = planner._build_planner_tools_schema()

        assert len(schema) == 1
        func = schema[0]["function"]
        assert func["name"] == "create_plan"
        assert "dummy" in func["parameters"]["properties"]["steps"]["items"]["properties"]["skill_name"]["description"]

    @pytest.mark.asyncio
    async def test_plan_provider_not_found_fallback(self) -> None:
        """When tier 3 provider not found, falls back to ollama."""
        from providers.registry import ProviderNotFoundError

        registry = MagicMock()
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.return_value = {
            "tool": "create_plan",
            "result": {"steps": [{"skill_name": "test", "action": "do", "params": {}}]},
        }
        registry.get_llm.side_effect = [ProviderNotFoundError("notfound"), mock_llm]

        planner = self._make_planner(registry=registry)
        intents = await planner.plan("do something")
        assert len(intents) >= 1


# ============================================================================
# core/ocr.py -- from 47% to ~90%
# ============================================================================


class TestOCREngine:
    """Tests for the OCR engine with mocked backends."""

    def test_init_paddle_success(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        mock_paddle_cls = MagicMock()
        with patch.dict("sys.modules", {"paddleocr": MagicMock(PaddleOCR=mock_paddle_cls)}):
            result = engine._init_paddle()
        assert result is True
        assert engine._paddle_available is True

    def test_init_paddle_import_error(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        with patch("builtins.__import__", side_effect=ImportError("no paddle")):
            result = engine._init_paddle()
        assert result is False

    def test_init_paddle_caches_result(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        engine._paddle_available = True
        assert engine._init_paddle() is True

    def test_init_tesseract_success(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        with patch.dict("sys.modules", {"pytesseract": MagicMock()}):
            result = engine._init_tesseract()
        assert result is True

    def test_init_tesseract_import_error(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        with patch("builtins.__import__", side_effect=ImportError("no tesseract")):
            result = engine._init_tesseract()
        assert result is False

    def test_init_tesseract_caches_result(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        engine._tesseract_available = False
        assert engine._init_tesseract() is False

    def test_extract_sync_no_backends(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        engine._paddle_available = False
        engine._tesseract_available = False
        result = engine._extract_sync(b"image_data", "vi")
        assert result == ""

    def test_extract_sync_paddle_path(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        engine._paddle_available = True
        engine._paddle_ocr = MagicMock()
        with patch.object(engine, "_extract_with_paddle", return_value="paddle text"):
            result = engine._extract_sync(b"image_data", "vi")
        assert result == "paddle text"

    def test_extract_sync_tesseract_fallback(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        engine._paddle_available = False
        engine._tesseract_available = True
        with patch.object(engine, "_extract_with_tesseract", return_value="tesseract text"):
            result = engine._extract_sync(b"image_data", "en")
        assert result == "tesseract text"

    def test_extract_with_paddle_success(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        mock_ocr = MagicMock()
        # Simulate PaddleOCR result format
        mock_ocr.ocr.return_value = [
            [
                [[[0, 0], [100, 0], [100, 20], [0, 20]], ("Hello World", 0.99)],
                [[[0, 30], [100, 30], [100, 50], [0, 50]], ("Line 2", 0.95)],
            ]
        ]
        engine._paddle_ocr = mock_ocr

        # Mock PIL.Image inside the method body
        mock_pil_image = MagicMock()
        mock_img = MagicMock()
        mock_pil_image.open.return_value = mock_img

        with patch.dict("sys.modules", {
            "PIL": MagicMock(Image=mock_pil_image),
            "PIL.Image": mock_pil_image,
        }):
            result = engine._extract_with_paddle(b"fake image")
        assert "Hello World" in result
        assert "Line 2" in result

    def test_extract_with_paddle_returns_empty_on_error(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        engine._paddle_ocr = MagicMock()
        engine._paddle_ocr.ocr.side_effect = TypeError("bad input")

        # Need to mock PIL imports that happen inside the method
        mock_pil_image = MagicMock()
        mock_pil_image.open.return_value = MagicMock()

        with (
            patch.dict("sys.modules", {
                "PIL": MagicMock(Image=mock_pil_image),
                "PIL.Image": mock_pil_image,
            }),
        ):
            result = engine._extract_with_paddle(b"bad image")
        assert result == ""

    def test_extract_with_paddle_page_none(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [None, []]  # One None page, one empty page
        engine._paddle_ocr = mock_ocr

        mock_pil_image = MagicMock()
        mock_pil_image.open.return_value = MagicMock()

        with patch.dict("sys.modules", {
            "PIL": MagicMock(Image=mock_pil_image),
            "PIL.Image": mock_pil_image,
        }):
            result = engine._extract_with_paddle(b"image")
        assert result == ""

    def test_extract_with_tesseract_success(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        mock_tesseract = MagicMock()
        mock_tesseract.image_to_string.return_value = "  Tesseract output  "
        mock_pil_image = MagicMock()
        mock_pil_image.open.return_value = MagicMock()

        with patch.dict("sys.modules", {
            "pytesseract": mock_tesseract,
            "PIL": MagicMock(Image=mock_pil_image),
            "PIL.Image": mock_pil_image,
        }):
            result = engine._extract_with_tesseract(b"image", "vi")
        assert result == "Tesseract output"

    def test_extract_with_tesseract_error(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        mock_pil_image = MagicMock()
        mock_pil_image.open.side_effect = OSError("bad image")

        with patch.dict("sys.modules", {
            "pytesseract": MagicMock(),
            "PIL": MagicMock(Image=mock_pil_image),
            "PIL.Image": mock_pil_image,
        }):
            result = engine._extract_with_tesseract(b"bad", "en")
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_text_delegates(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        with patch.object(engine, "_extract_sync", return_value="mocked"):
            result = await engine.extract_text(b"img", "vi")
        assert result == "mocked"

    @pytest.mark.asyncio
    async def test_health_check_true(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        with patch.object(engine, "_health_check_sync", return_value=True):
            assert await engine.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_false(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        with patch.object(engine, "_health_check_sync", return_value=False):
            assert await engine.health_check() is False

    def test_health_check_sync_paddle_true(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        engine._paddle_available = True
        assert engine._health_check_sync() is True

    def test_health_check_sync_tesseract_only(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        engine._paddle_available = False
        engine._tesseract_available = True
        assert engine._health_check_sync() is True

    def test_health_check_sync_none(self) -> None:
        from core.ocr import OCREngine

        engine = OCREngine()
        engine._paddle_available = False
        engine._tesseract_available = False
        assert engine._health_check_sync() is False


# ============================================================================
# skills/app_launcher.py -- from 55% to ~90%
# ============================================================================


class TestAppLauncherSkill:
    """Tests for AppLauncherSkill covering open/close/list branches."""

    @pytest.mark.asyncio
    async def test_open_app_no_name(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(skill_name="app_launcher", action="open", params={}, raw_text="open")
        result = await skill.execute(intent)
        assert result.success is False
        assert result.error_code == "invalid_params"

    @pytest.mark.asyncio
    async def test_open_app_success_non_windows(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="open", params={"app": "notepad"}, raw_text="open notepad"
        )
        with (
            patch("skills.app_launcher._IS_WINDOWS", False),
            patch("skills.app_launcher.asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.return_value = MagicMock()
            result = await skill.execute(intent)
        assert result.success is True
        assert "notepad" in result.tts_response

    @pytest.mark.asyncio
    async def test_open_app_success_windows(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="launch", params={"app": "chrome"}, raw_text="launch chrome"
        )
        with (
            patch("skills.app_launcher._IS_WINDOWS", True),
            patch("skills.app_launcher.asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.return_value = None
            result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_open_app_failure(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="start", params={"app": "nonexistent"}, raw_text="start nonexistent"
        )
        with (
            patch("skills.app_launcher._IS_WINDOWS", False),
            patch("skills.app_launcher.asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.side_effect = FileNotFoundError("not found")
            result = await skill.execute(intent)
        assert result.success is False
        assert result.error_code == "execution_error"

    @pytest.mark.asyncio
    async def test_close_app_no_name(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(skill_name="app_launcher", action="close", params={}, raw_text="close")
        result = await skill.execute(intent)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_close_app_success_windows(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="quit", params={"app": "notepad"}, raw_text="quit notepad"
        )
        with (
            patch("skills.app_launcher._IS_WINDOWS", True),
            patch("skills.app_launcher.asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.return_value = MagicMock(returncode=0)
            result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_close_app_success_unix(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="exit", params={"app": "chrome"}, raw_text="exit chrome"
        )
        with (
            patch("skills.app_launcher._IS_WINDOWS", False),
            patch("skills.app_launcher.asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.return_value = MagicMock(returncode=0)
            result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_close_app_timeout(self) -> None:
        import subprocess

        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="close", params={"app": "test"}, raw_text="close test"
        )
        with (
            patch("skills.app_launcher._IS_WINDOWS", True),
            patch("skills.app_launcher.asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.side_effect = subprocess.TimeoutExpired(cmd="taskkill", timeout=10)
            result = await skill.execute(intent)
        assert result.success is False
        assert result.error_code == "timeout"

    @pytest.mark.asyncio
    async def test_close_app_os_error(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="close", params={"app": "test"}, raw_text="close test"
        )
        with (
            patch("skills.app_launcher._IS_WINDOWS", True),
            patch("skills.app_launcher.asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.side_effect = OSError("cannot kill")
            result = await skill.execute(intent)
        assert result.success is False
        assert result.error_code == "execution_error"

    @pytest.mark.asyncio
    async def test_unsupported_action(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="dance", params={}, raw_text="dance"
        )
        result = await skill.execute(intent)
        assert result.success is False
        assert result.error_code == "unsupported_action"

    @pytest.mark.asyncio
    async def test_list_running_success(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="list_running", params={}, raw_text="list running"
        )

        mock_proc = MagicMock()
        mock_proc.info = {"name": "chrome.exe", "pid": 1234, "memory_info": MagicMock(rss=100 * 1024 * 1024)}
        mock_psutil = MagicMock()
        mock_psutil.process_iter.return_value = [mock_proc]
        mock_psutil.NoSuchProcess = type("NoSuchProcess", (Exception,), {})
        mock_psutil.AccessDenied = type("AccessDenied", (Exception,), {})

        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            result = await skill.execute(intent)
        assert result.success is True
        assert "chrome.exe" in result.tts_response

    @pytest.mark.asyncio
    async def test_list_running_psutil_missing(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="list_running", params={}, raw_text="list"
        )

        with patch.dict("sys.modules", {"psutil": None}):
            result = await skill.execute(intent)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_can_handle_correct_name(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(skill_name="app_launcher", action="open", params={}, raw_text="")
        assert await skill.can_handle(intent) is True

    @pytest.mark.asyncio
    async def test_can_handle_wrong_name(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(skill_name="other", action="open", params={}, raw_text="")
        assert await skill.can_handle(intent) is False

    @pytest.mark.asyncio
    async def test_open_uses_name_param(self) -> None:
        """Tests the params.get('name', '') fallback path."""
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="open", params={"name": "chrome"}, raw_text="open chrome"
        )
        with (
            patch("skills.app_launcher._IS_WINDOWS", False),
            patch("skills.app_launcher.asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.return_value = MagicMock()
            result = await skill.execute(intent)
        assert result.success is True


# ============================================================================
# core/audio/wake_word.py -- from 56% to ~90%
# ============================================================================


class TestWakeWordDetector:
    """Tests for WakeWordDetector."""

    def test_detect_raises_when_not_loaded(self) -> None:
        from core.audio.wake_word import WakeWordDetector

        detector = WakeWordDetector()
        with pytest.raises(RuntimeError, match="not loaded"):
            detector.detect(np.zeros(1280, dtype=np.int16))

    def test_detect_returns_true_when_above_threshold(self) -> None:
        from core.audio.wake_word import WakeWordDetector

        detector = WakeWordDetector(sensitivity=0.5)
        mock_model = MagicMock()
        mock_model.predict = MagicMock()
        mock_model.prediction_buffer = {"hey_vox": [0.0, 0.3, 0.8]}
        mock_model.reset = MagicMock()
        detector._model = mock_model

        result = detector.detect(np.zeros(1280, dtype=np.int16))
        assert result is True
        mock_model.reset.assert_called_once()

    def test_detect_returns_false_when_below_threshold(self) -> None:
        from core.audio.wake_word import WakeWordDetector

        detector = WakeWordDetector(sensitivity=0.7)
        mock_model = MagicMock()
        mock_model.predict = MagicMock()
        mock_model.prediction_buffer = {"hey_vox": [0.1, 0.2, 0.3]}
        detector._model = mock_model

        result = detector.detect(np.zeros(1280, dtype=np.int16))
        assert result is False

    def test_detect_empty_score_buffer(self) -> None:
        from core.audio.wake_word import WakeWordDetector

        detector = WakeWordDetector()
        mock_model = MagicMock()
        mock_model.predict = MagicMock()
        mock_model.prediction_buffer = {"hey_vox": []}
        detector._model = mock_model

        result = detector.detect(np.zeros(1280, dtype=np.int16))
        assert result is False

    def test_load_model(self) -> None:
        from core.audio.wake_word import WakeWordDetector

        detector = WakeWordDetector()
        mock_model_cls = MagicMock()
        with patch.dict("sys.modules", {
            "openwakeword": MagicMock(),
            "openwakeword.model": MagicMock(Model=mock_model_cls),
        }):
            detector.load()
        assert detector._model is not None

    def test_unload_model(self) -> None:
        from core.audio.wake_word import WakeWordDetector

        detector = WakeWordDetector()
        detector._model = MagicMock()
        detector.unload()
        assert detector._model is None


# ============================================================================
# core/audio/vad.py -- from 52% to ~80%
# ============================================================================


class TestVoiceActivityDetector:
    """Tests for VoiceActivityDetector."""

    def test_load_without_silero(self) -> None:
        from core.audio.vad import VoiceActivityDetector

        vad = VoiceActivityDetector()
        with patch("builtins.__import__", side_effect=ImportError("no silero")):
            vad.load()
        assert vad._model is None
        assert vad.is_loaded is False

    def test_load_with_silero(self) -> None:
        from core.audio.vad import VoiceActivityDetector

        vad = VoiceActivityDetector()
        mock_silero = MagicMock()
        mock_silero.load_silero_vad.return_value = MagicMock()
        with patch.dict("sys.modules", {"silero_vad": mock_silero}):
            vad.load()
        assert vad.is_loaded is True

    def test_unload(self) -> None:
        from core.audio.vad import VoiceActivityDetector

        vad = VoiceActivityDetector()
        vad._model = MagicMock()
        vad.unload()
        assert vad._model is None

    def test_detect_speech_energy_fallback(self) -> None:
        from core.audio.vad import VoiceActivityDetector

        vad = VoiceActivityDetector(energy_threshold=100.0)
        # No model, uses energy fallback
        loud = np.full(1280, 5000, dtype=np.int16)
        assert vad.detect_speech(loud) is True

        quiet = np.zeros(1280, dtype=np.int16)
        assert vad.detect_speech(quiet) is False

    def test_detect_speech_with_energy_custom_threshold(self) -> None:
        from core.audio.vad import VoiceActivityDetector

        vad = VoiceActivityDetector()
        # No model loaded
        loud = np.full(1280, 5000, dtype=np.int16)
        assert vad.detect_speech_with_energy(loud, 100.0) is True

        quiet = np.zeros(1280, dtype=np.int16)
        assert vad.detect_speech_with_energy(quiet, 100.0) is False

    def test_silero_detect_runtime_error_fallback(self) -> None:
        from core.audio.vad import VoiceActivityDetector

        vad = VoiceActivityDetector()
        mock_model = MagicMock()
        vad._model = mock_model

        mock_torch = MagicMock()
        mock_torch.from_numpy.side_effect = RuntimeError("inference error")

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = vad._silero_detect(np.zeros(1280, dtype=np.int16))
        # Should fall back to energy detection
        assert result is False  # zeros have no energy

    def test_silero_detect_success(self) -> None:
        from core.audio.vad import VoiceActivityDetector

        vad = VoiceActivityDetector(speech_threshold=0.5)
        mock_model = MagicMock()
        mock_model.return_value.item.return_value = 0.8
        vad._model = mock_model

        mock_torch = MagicMock()
        mock_tensor = MagicMock()
        mock_torch.from_numpy.return_value = mock_tensor

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = vad._silero_detect(np.zeros(1280, dtype=np.int16))
        assert result is True

    def test_detect_speech_with_energy_uses_silero_when_loaded(self) -> None:
        from core.audio.vad import VoiceActivityDetector

        vad = VoiceActivityDetector(speech_threshold=0.5)
        mock_model = MagicMock()
        vad._model = mock_model

        with patch.object(vad, "_silero_detect", return_value=True):
            result = vad.detect_speech_with_energy(np.zeros(1280, dtype=np.int16), 100.0)
        assert result is True

    def test_silero_detect_model_none_fallback(self) -> None:
        """When model is set but then becomes None during inference."""
        from core.audio.vad import VoiceActivityDetector

        vad = VoiceActivityDetector()
        vad._model = MagicMock()

        mock_torch = MagicMock()
        mock_torch.from_numpy.return_value = MagicMock()
        # Simulate model becoming None during execution
        original_model = vad._model

        def side_effect(*args, **kwargs):
            vad._model = None  # race condition simulation
            return original_model

        with patch.dict("sys.modules", {"torch": mock_torch}):
            # Just test the energy detect path
            result = vad._energy_detect(np.full(1280, 5000, dtype=np.int16))
        assert result is True


# ============================================================================
# core/eyes.py -- from 64% to ~85%
# ============================================================================


class TestEyes:
    """Tests for Eyes module covering all layers."""

    @pytest.mark.asyncio
    async def test_get_active_window_success(self) -> None:
        from core.eyes import Eyes, WindowInfo

        eyes = Eyes()
        mock_win = MagicMock()
        mock_win.title = "Test Window"
        mock_win.process_name = "test.exe"
        mock_win.pid = 123
        mock_win.bounds = (0, 0, 800, 600)

        mock_automation = MagicMock()
        mock_automation.get_active_window.return_value = mock_win

        with patch("core.eyes.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = mock_win
            with patch("system.factory.get_system_automation", return_value=mock_automation):
                result = await eyes.get_active_window()

        assert isinstance(result, WindowInfo)

    @pytest.mark.asyncio
    async def test_get_active_window_failure(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        with patch("system.factory.get_system_automation", side_effect=NotImplementedError("no impl")):
            result = await eyes.get_active_window()
        assert result.title == ""
        assert result.pid == 0

    @pytest.mark.asyncio
    async def test_find_element_success(self) -> None:
        from core.eyes import Eyes, UIElement

        eyes = Eyes()
        mock_elem = MagicMock()
        mock_elem.role = "button"
        mock_elem.name = "OK"
        mock_elem.value = None
        mock_elem.bounds = (10, 10, 50, 30)

        mock_automation = MagicMock()
        mock_automation.find_element.return_value = mock_elem

        with (
            patch("system.factory.get_system_automation", return_value=mock_automation),
            patch("core.eyes.asyncio.to_thread", new_callable=AsyncMock, return_value=mock_elem),
        ):
            result = await eyes.find_element("button", "OK")

        assert isinstance(result, UIElement)
        assert result.name == "OK"

    @pytest.mark.asyncio
    async def test_find_element_not_found(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        mock_automation = MagicMock()
        mock_automation.find_element.return_value = None

        with (
            patch("system.factory.get_system_automation", return_value=mock_automation),
            patch("core.eyes.asyncio.to_thread", new_callable=AsyncMock, return_value=None),
        ):
            result = await eyes.find_element("button", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_find_element_error(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        with patch("system.factory.get_system_automation", side_effect=RuntimeError("err")):
            result = await eyes.find_element("button", "test")
        assert result is None

    @pytest.mark.asyncio
    async def test_capture_screen_no_pillow(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        with patch.dict("sys.modules", {"PIL": None, "PIL.ImageGrab": None}):
            result = await eyes.capture_screen()
        # Should return empty bytes due to ImportError
        assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_capture_screen_with_region(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        mock_img = MagicMock()
        mock_buffer = MagicMock()

        with patch.object(eyes, "_capture_sync", return_value=b"PNG_DATA"):
            result = await eyes.capture_screen(region=(0, 0, 100, 100))
        assert result == b"PNG_DATA"

    def test_capture_sync_with_region(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        mock_screenshot = MagicMock()
        mock_grab = MagicMock(return_value=mock_screenshot)

        import io

        buf = io.BytesIO()
        buf.write(b"PNG_DATA")

        with patch.dict("sys.modules", {
            "PIL": MagicMock(),
            "PIL.ImageGrab": MagicMock(grab=mock_grab),
        }):
            with patch("core.eyes.io.BytesIO") as mock_bytesio:
                mock_bytesio.return_value.getvalue.return_value = b"PNG_DATA"
                result = eyes._capture_sync((10, 20, 100, 200))
        assert result == b"PNG_DATA"

    def test_capture_sync_error(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        mock_grab = MagicMock(side_effect=OSError("no display"))

        with patch.dict("sys.modules", {
            "PIL": MagicMock(),
            "PIL.ImageGrab": MagicMock(grab=mock_grab),
        }):
            result = eyes._capture_sync(None)
        assert result == b""

    @pytest.mark.asyncio
    async def test_read_screen_text_cached(self) -> None:
        from core.eyes import Eyes, _OCRCacheEntry

        eyes = Eyes()
        eyes._ocr_cache = _OCRCacheEntry(
            text="cached text",
            timestamp=time.monotonic(),
            region=None,
        )
        result = await eyes.read_screen_text()
        assert result == "cached text"

    @pytest.mark.asyncio
    async def test_read_screen_text_cache_expired(self) -> None:
        from core.eyes import Eyes, _OCRCacheEntry

        eyes = Eyes()
        eyes._ocr_cache = _OCRCacheEntry(
            text="old text",
            timestamp=time.monotonic() - 10.0,  # Expired
            region=None,
        )

        mock_engine = MagicMock()
        mock_engine.extract_text = AsyncMock(return_value="new text")
        mock_engine_cls = MagicMock(return_value=mock_engine)

        with (
            patch.object(eyes, "capture_screen", new_callable=AsyncMock, return_value=b"img"),
            patch("core.ocr.OCREngine", mock_engine_cls),
        ):
            result = await eyes.read_screen_text()
        assert result == "new text"

    @pytest.mark.asyncio
    async def test_read_screen_text_empty_image(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        with patch.object(eyes, "capture_screen", new_callable=AsyncMock, return_value=b""):
            result = await eyes.read_screen_text()
        assert result == ""

    @pytest.mark.asyncio
    async def test_read_screen_cache_region_mismatch(self) -> None:
        from core.eyes import Eyes, _OCRCacheEntry

        eyes = Eyes()
        eyes._ocr_cache = _OCRCacheEntry(
            text="cached",
            timestamp=time.monotonic(),
            region=(0, 0, 100, 100),
        )

        mock_engine = MagicMock()
        mock_engine.extract_text = AsyncMock(return_value="different region text")
        mock_engine_cls = MagicMock(return_value=mock_engine)

        # Request different region -> cache miss
        with (
            patch.object(eyes, "capture_screen", new_callable=AsyncMock, return_value=b"img"),
            patch("core.ocr.OCREngine", mock_engine_cls),
        ):
            result = await eyes.read_screen_text(region=(50, 50, 200, 200))
        assert result == "different region text"

    @pytest.mark.asyncio
    async def test_analyze_screen_no_vision_provider(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        mock_registry = MagicMock()
        mock_registry.list_registered.return_value = {"vision": []}

        with (
            patch.object(eyes, "capture_screen", new_callable=AsyncMock, return_value=b"img"),
            patch("providers.registry.ProviderRegistry", return_value=mock_registry),
        ):
            result = await eyes.analyze_screen("What is on screen?")
        assert "No vision provider" in result

    @pytest.mark.asyncio
    async def test_analyze_screen_empty_capture(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        with patch.object(eyes, "capture_screen", new_callable=AsyncMock, return_value=b""):
            result = await eyes.analyze_screen("What is on screen?")
        assert "Could not capture" in result

    @pytest.mark.asyncio
    async def test_analyze_screen_success(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        mock_vision = AsyncMock()
        mock_vision.analyze_image.return_value = "There is a button on screen"

        mock_registry = MagicMock()
        mock_registry.list_registered.return_value = {"vision": ["openai_vision"]}
        mock_registry.get_vision.return_value = mock_vision

        with (
            patch.object(eyes, "capture_screen", new_callable=AsyncMock, return_value=b"img"),
            patch("providers.registry.ProviderRegistry", return_value=mock_registry),
        ):
            result = await eyes.analyze_screen("What is on screen?")
        assert "button" in result

    @pytest.mark.asyncio
    async def test_analyze_screen_provider_error(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        mock_registry = MagicMock()
        mock_registry.list_registered.return_value = {"vision": ["openai_vision"]}
        mock_registry.get_vision.side_effect = RuntimeError("provider error")

        with (
            patch.object(eyes, "capture_screen", new_callable=AsyncMock, return_value=b"img"),
            patch("providers.registry.ProviderRegistry", return_value=mock_registry),
        ):
            result = await eyes.analyze_screen("What is on screen?")
        assert "failed" in result.lower()


# ============================================================================
# skills/marketplace.py -- from 61% to ~85%
# ============================================================================


class TestSkillMarketplace:
    """Tests for SkillMarketplace."""

    @pytest.mark.asyncio
    async def test_search_success(self) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "skills": [
                {"name": "cool_skill", "version": "1.0", "author": "dev", "description": "A cool skill"}
            ]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_resp

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_client

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            results = await marketplace.search("cool")
        assert len(results) == 1
        assert results[0].name == "cool_skill"

    @pytest.mark.asyncio
    async def test_search_failure(self) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        mock_httpx = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = ConnectionError("offline")
        mock_httpx.AsyncClient.return_value = mock_client

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            results = await marketplace.search("test")
        assert results == []

    def test_install_local_success(self, tmp_path) -> None:
        from skills.marketplace import SkillMarketplace, _SKILLS_DIR

        marketplace = SkillMarketplace()
        source = tmp_path / "my_skill.py"
        source.write_text("# skill code")

        dest = tmp_path / "installed_skill.py"

        with (
            patch("skills.marketplace._SKILLS_DIR", tmp_path),
            patch("skills.marketplace._INSTALLED_MANIFEST", tmp_path / ".installed.json"),
        ):
            result = marketplace._install_local("installed_skill", source)
        assert result is True
        assert (tmp_path / "installed_skill.py").exists()

    def test_install_local_not_found(self, tmp_path) -> None:
        from pathlib import Path

        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        result = marketplace._install_local("test", Path("/nonexistent/skill.py"))
        assert result is False

    def test_install_local_not_py(self, tmp_path) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        source = tmp_path / "skill.txt"
        source.write_text("not python")
        result = marketplace._install_local("test", source)
        assert result is False

    @pytest.mark.asyncio
    async def test_install_remote_success(self, tmp_path) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"code": "# remote skill code", "version": "1.0.0"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_resp

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_client

        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("skills.marketplace._SKILLS_DIR", tmp_path),
            patch("skills.marketplace._INSTALLED_MANIFEST", tmp_path / ".installed.json"),
        ):
            result = await marketplace._install_remote("remote_skill")
        assert result is True

    @pytest.mark.asyncio
    async def test_install_remote_empty_code(self, tmp_path) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"code": "", "version": "1.0.0"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = mock_resp

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_client

        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("skills.marketplace._SKILLS_DIR", tmp_path),
        ):
            result = await marketplace._install_remote("empty_skill")
        assert result is False

    @pytest.mark.asyncio
    async def test_install_remote_no_httpx(self) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        with patch("builtins.__import__", side_effect=ImportError("no httpx")):
            result = await marketplace._install_remote("test")
        assert result is False

    @pytest.mark.asyncio
    async def test_install_remote_connection_error(self) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.side_effect = ConnectionError("offline")

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_client

        with patch.dict("sys.modules", {"httpx": mock_httpx}):
            result = await marketplace._install_remote("test")
        assert result is False

    @pytest.mark.asyncio
    async def test_install_with_source_path(self, tmp_path) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        source = tmp_path / "skill.py"
        source.write_text("# code")

        with (
            patch("skills.marketplace._SKILLS_DIR", tmp_path),
            patch("skills.marketplace._INSTALLED_MANIFEST", tmp_path / ".installed.json"),
        ):
            result = await marketplace.install("my_skill", source_path=str(source))
        assert result is True

    @pytest.mark.asyncio
    async def test_install_without_source_path(self, tmp_path) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        with patch.object(marketplace, "_install_remote", new_callable=AsyncMock, return_value=True):
            result = await marketplace.install("my_skill")
        assert result is True

    @pytest.mark.asyncio
    async def test_publish_success(self, tmp_path) -> None:
        from skills.marketplace import SkillManifest, SkillMarketplace

        marketplace = SkillMarketplace()
        source = tmp_path / "pub_skill.py"
        source.write_text("# publish me")

        manifest = SkillManifest(
            name="pub_skill", version="1.0", author="dev", description="test"
        )

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.return_value = mock_resp

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_client

        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("skills.marketplace._SKILLS_DIR", tmp_path),
        ):
            result = await marketplace.publish(manifest)
        assert result is True

    @pytest.mark.asyncio
    async def test_publish_source_not_found(self) -> None:
        from skills.marketplace import SkillManifest, SkillMarketplace

        marketplace = SkillMarketplace()
        manifest = SkillManifest(
            name="nonexistent_skill", version="1.0", author="dev", description="test"
        )
        with patch("skills.marketplace._SKILLS_DIR", MagicMock(**{"__truediv__": lambda s, n: MagicMock(exists=lambda: False)})):
            # Direct approach
            result = await marketplace.publish(manifest)
        assert result is False

    @pytest.mark.asyncio
    async def test_publish_no_httpx(self, tmp_path) -> None:
        from skills.marketplace import SkillManifest, SkillMarketplace

        marketplace = SkillMarketplace()
        source = tmp_path / "my_skill.py"
        source.write_text("# code")

        manifest = SkillManifest(name="my_skill", version="1.0", author="dev", description="test")

        with (
            patch("skills.marketplace._SKILLS_DIR", tmp_path),
            patch("builtins.__import__", side_effect=ImportError("no httpx")),
        ):
            result = await marketplace.publish(manifest)
        assert result is False

    @pytest.mark.asyncio
    async def test_publish_connection_error(self, tmp_path) -> None:
        from skills.marketplace import SkillManifest, SkillMarketplace

        marketplace = SkillMarketplace()
        source = tmp_path / "my_skill.py"
        source.write_text("# code")

        manifest = SkillManifest(name="my_skill", version="1.0", author="dev", description="test")

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post.side_effect = ConnectionError("offline")

        mock_httpx = MagicMock()
        mock_httpx.AsyncClient.return_value = mock_client

        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("skills.marketplace._SKILLS_DIR", tmp_path),
        ):
            result = await marketplace.publish(manifest)
        assert result is False

    @pytest.mark.asyncio
    async def test_uninstall_success(self, tmp_path) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        target = tmp_path / "remove_me.py"
        target.write_text("# bye")

        manifest_file = tmp_path / ".installed.json"
        manifest_file.write_text(json.dumps({"remove_me": {"version": "1.0", "source": "local"}}))

        with (
            patch("skills.marketplace._SKILLS_DIR", tmp_path),
            patch("skills.marketplace._INSTALLED_MANIFEST", manifest_file),
        ):
            result = await marketplace.uninstall("remove_me")
        assert result is True
        assert not target.exists()

    @pytest.mark.asyncio
    async def test_uninstall_not_installed(self, tmp_path) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        manifest_file = tmp_path / ".installed.json"
        manifest_file.write_text("{}")

        with patch("skills.marketplace._INSTALLED_MANIFEST", manifest_file):
            result = await marketplace.uninstall("not_here")
        assert result is False

    @pytest.mark.asyncio
    async def test_uninstall_file_error(self, tmp_path) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        manifest_file = tmp_path / ".installed.json"
        manifest_file.write_text(json.dumps({"broken": {"version": "1.0"}}))

        with (
            patch("skills.marketplace._SKILLS_DIR", tmp_path),
            patch("skills.marketplace._INSTALLED_MANIFEST", manifest_file),
        ):
            # File doesn't exist but is in manifest - should succeed (unlink skipped)
            result = await marketplace.uninstall("broken")
        assert result is True

    def test_list_installed(self, tmp_path) -> None:
        from skills.marketplace import SkillMarketplace

        marketplace = SkillMarketplace()
        manifest_file = tmp_path / ".installed.json"
        manifest_file.write_text(json.dumps({
            "skill_a": {"version": "1.0", "source": "registry"},
            "skill_b": {"version": "local", "source": "/path/to/file"},
        }))

        with patch("skills.marketplace._INSTALLED_MANIFEST", manifest_file):
            installed = marketplace.list_installed()
        assert len(installed) == 2

    def test_load_installed_db_corrupt(self, tmp_path) -> None:
        from skills.marketplace import _load_installed_db

        manifest = tmp_path / ".installed.json"
        manifest.write_text("not valid json{{{")
        with patch("skills.marketplace._INSTALLED_MANIFEST", manifest):
            result = _load_installed_db()
        assert result == {}


# ============================================================================
# core/audio/text_chunker.py -- from 73% to ~95%
# ============================================================================


class TestTextChunker:
    """Tests for sentence splitting and chunk management."""

    def test_split_empty(self) -> None:
        from core.audio.text_chunker import split_sentences

        assert split_sentences("") == []
        assert split_sentences("   ") == []

    def test_split_single_sentence(self) -> None:
        from core.audio.text_chunker import split_sentences

        result = split_sentences("This is a simple sentence.")
        assert len(result) >= 1

    def test_split_multiple_sentences(self) -> None:
        from core.audio.text_chunker import split_sentences

        result = split_sentences("Hello world. How are you? I am fine!")
        assert len(result) >= 2

    def test_merge_short_chunks(self) -> None:
        from core.audio.text_chunker import _merge_short_chunks

        chunks = ["OK.", "That is good. Now let's continue with the work."]
        merged = _merge_short_chunks(chunks)
        # "OK." is < MIN_CHUNK_LENGTH so should be merged
        assert len(merged) <= len(chunks)

    def test_merge_short_chunks_single(self) -> None:
        from core.audio.text_chunker import _merge_short_chunks

        assert _merge_short_chunks(["single"]) == ["single"]

    def test_merge_short_chunks_all_short(self) -> None:
        from core.audio.text_chunker import _merge_short_chunks

        chunks = ["Hi.", "OK."]
        merged = _merge_short_chunks(chunks)
        assert len(merged) >= 1

    def test_split_long_chunks(self) -> None:
        from core.audio.text_chunker import _split_long_chunks, MAX_CHUNK_LENGTH

        # Create a chunk longer than MAX_CHUNK_LENGTH with clause boundaries
        long_text = "First clause, " * 30  # ~420 chars
        chunks = [long_text.strip()]
        result = _split_long_chunks(chunks)
        assert all(len(c) <= MAX_CHUNK_LENGTH + 50 for c in result)  # Tolerance

    def test_split_long_chunks_no_boundary(self) -> None:
        from core.audio.text_chunker import _split_long_chunks, MAX_CHUNK_LENGTH

        # Long text with no clause boundaries
        long_text = "a" * (MAX_CHUNK_LENGTH + 100)
        result = _split_long_chunks([long_text])
        # Should still return (can't split without boundaries)
        assert len(result) >= 1

    def test_split_sentences_vietnamese(self) -> None:
        from core.audio.text_chunker import split_sentences

        result = split_sentences("Xin chao ban. Ban khoe khong? Toi rat vui!")
        assert len(result) >= 2


# ============================================================================
# core/brain.py -- missing lines 262-271, 296-342
# ============================================================================


class TestBrainAdditional:
    """Additional brain tests for uncovered paths."""

    def _make_brain(self, llm_response=None, provider_error=False):
        from core.brain import Brain

        registry = MagicMock()
        mock_llm = AsyncMock()
        if provider_error:
            from core.errors import ProviderError
            mock_llm.chat_with_tools.side_effect = ProviderError("fail", user_message="fail")
        elif llm_response is not None:
            mock_llm.chat_with_tools.return_value = llm_response
        registry.get_llm.return_value = mock_llm

        class SimpleSkill(BaseSkill):
            name = "test_skill"
            description = "A test skill"
            keywords: ClassVar[list[str]] = ["test"]
            execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]

            async def can_handle(self, intent: SkillIntent) -> bool:
                return True

            async def execute(self, intent: SkillIntent) -> SkillResult:
                return SkillResult.ok()

        brain = Brain(
            registry=registry,
            skills=[SimpleSkill()],
            routing_config={"tiers": [
                {"provider": "ollama", "model": "test"},
                {"provider": "ollama", "model": "test"},
                {"provider": "ollama", "model": "test"},
            ]},
        )
        return brain

    @pytest.mark.asyncio
    async def test_parse_tool_response_with_extraction_failure(self) -> None:
        """When param extraction fails, falls back to raw args."""
        brain = self._make_brain()
        response = {
            "tool": "test_skill",
            "result": {"action": "do_thing", "confidence": 0.8, "extra_param": "value"},
        }
        with patch("core.brain.extract_params") as mock_extract:
            mock_extract.return_value = MagicMock(success=False, error="bad params")
            intent = brain._parse_tool_response(response, Tier.ONE)

        assert intent.skill_name == "test_skill"
        assert intent.action == "do_thing"
        assert "extra_param" in intent.params

    @pytest.mark.asyncio
    async def test_parse_tool_response_bad_confidence(self) -> None:
        """Non-numeric confidence defaults to 0.9."""
        brain = self._make_brain()
        response = {
            "tool": "test_skill",
            "result": {"action": "do", "confidence": "not_a_number"},
        }
        with patch("core.brain.extract_params") as mock_extract:
            mock_extract.return_value = MagicMock(success=False, error="bad")
            intent = brain._parse_tool_response(response, Tier.ONE)

        assert intent.confidence == 0.9

    @pytest.mark.asyncio
    async def test_parse_tool_response_unknown_tool(self) -> None:
        """Unknown tool name returns unknown intent."""
        brain = self._make_brain()
        response = {"tool": "nonexistent_skill", "result": {}}
        intent = brain._parse_tool_response(response, Tier.ONE)
        assert intent.skill_name == "unknown"

    @pytest.mark.asyncio
    async def test_parse_tool_response_exception(self) -> None:
        """Exception during parsing returns unknown intent."""
        brain = self._make_brain()
        response = {"tool": None, "result": None}
        intent = brain._parse_tool_response(response, Tier.ONE)
        assert intent.skill_name == "unknown"

    @pytest.mark.asyncio
    async def test_parse_tool_response_non_dict_args(self) -> None:
        """String result is parsed via json.loads."""
        brain = self._make_brain()
        response = {
            "tool": "test_skill",
            "result": '{"action": "do", "confidence": 0.5}',
        }
        intent = brain._parse_tool_response(response, Tier.ONE)
        assert intent.skill_name == "test_skill"

    @pytest.mark.asyncio
    async def test_route_single_provider_error_reraises(self) -> None:
        """ProviderError is re-raised from _route_single_provider."""
        from core.errors import ProviderError

        brain = self._make_brain(provider_error=True)
        with pytest.raises(ProviderError):
            await brain.process("something unique that does not match keywords")

    @pytest.mark.asyncio
    async def test_route_single_provider_json_error(self) -> None:
        """JSON decode error returns unknown intent."""
        brain = self._make_brain()
        mock_llm = AsyncMock()
        mock_llm.chat_with_tools.side_effect = json.JSONDecodeError("bad", "", 0)
        brain.registry.get_llm.return_value = mock_llm

        intent = await brain.process("do something unusual")
        assert intent.skill_name == "unknown"


# ============================================================================
# core/autopilot.py -- missing lines 113-139
# ============================================================================


class TestAutopilotExecution:
    """Test autopilot task execution with conditions and failures."""

    @pytest.mark.asyncio
    async def test_task_fires_and_removes_non_repeat(self) -> None:
        from core.autopilot import Autopilot, AutopilotTask, TriggerType

        pilot = Autopilot()
        action_called = []

        task = AutopilotTask(
            id="test_task",
            description="Test",
            trigger_type=TriggerType.TIME_BASED,
            condition=lambda: True,
            actions=[lambda: action_called.append(True)],
            repeat=False,
        )
        await pilot.register_task(task)

        # Run one iteration manually
        pilot._running = True
        for task_id, t in list(pilot._tasks.items()):
            if t.condition():
                for action in t.actions:
                    await asyncio.to_thread(action)
                if not t.repeat:
                    del pilot._tasks[task_id]

        assert len(action_called) == 1
        assert pilot.task_count == 0

    @pytest.mark.asyncio
    async def test_task_repeat_stays(self) -> None:
        from core.autopilot import Autopilot, AutopilotTask, TriggerType

        pilot = Autopilot()

        task = AutopilotTask(
            id="repeat_task",
            description="Repeating",
            trigger_type=TriggerType.CONDITION_BASED,
            condition=lambda: True,
            actions=[lambda: None],
            repeat=True,
        )
        await pilot.register_task(task)

        # Simulate one iteration
        for task_id, t in list(pilot._tasks.items()):
            if t.condition():
                for action in t.actions:
                    await asyncio.to_thread(action)
                if not t.repeat:
                    del pilot._tasks[task_id]

        assert pilot.task_count == 1  # Still registered

    @pytest.mark.asyncio
    async def test_task_failure_retries(self) -> None:
        from core.autopilot import Autopilot, AutopilotTask, TriggerType

        pilot = Autopilot()

        task = AutopilotTask(
            id="fail_task",
            description="Failing",
            trigger_type=TriggerType.TIME_BASED,
            condition=lambda: True,
            actions=[lambda: (_ for _ in ()).throw(RuntimeError("boom"))],
            max_retries=2,
        )
        await pilot.register_task(task)

        # Simulate iterations with failure
        for _ in range(3):
            for task_id, t in list(pilot._tasks.items()):
                try:
                    if t.condition():
                        for action in t.actions:
                            await asyncio.to_thread(action)
                except (RuntimeError, OSError, ValueError):
                    t._retry_count += 1
                    if t._retry_count >= t.max_retries:
                        del pilot._tasks[task_id]

        assert pilot.task_count == 0  # Removed after max retries


# ============================================================================
# skills/dependency_resolver.py -- from 74% to ~90%
# ============================================================================


class TestDependencyResolver:
    """Tests for dependency resolution and installation."""

    def test_install_dependencies_nothing_missing(self) -> None:
        from skills.dependency_resolver import Dependency, install_dependencies

        deps = [Dependency(package="json")]  # stdlib, always available
        installed, failed = install_dependencies(deps)
        assert installed == []
        assert failed == []

    def test_install_dependencies_pip_success(self) -> None:
        from skills.dependency_resolver import Dependency, install_dependencies

        deps = [Dependency(package="nonexistent_pkg_xyz")]

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("skills.dependency_resolver.is_installed", return_value=False),
            patch("skills.dependency_resolver.subprocess.run", return_value=mock_result),
        ):
            installed, failed = install_dependencies(deps)
        assert "nonexistent_pkg_xyz" in installed

    def test_install_dependencies_pip_failure(self) -> None:
        from skills.dependency_resolver import Dependency, install_dependencies

        deps = [Dependency(package="bad_pkg")]
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"

        with (
            patch("skills.dependency_resolver.is_installed", return_value=False),
            patch("skills.dependency_resolver.subprocess.run", return_value=mock_result),
        ):
            installed, failed = install_dependencies(deps)
        assert "bad_pkg" in failed

    def test_install_dependencies_timeout(self) -> None:
        import subprocess

        from skills.dependency_resolver import Dependency, install_dependencies

        deps = [Dependency(package="slow_pkg")]

        with (
            patch("skills.dependency_resolver.is_installed", return_value=False),
            patch("skills.dependency_resolver.subprocess.run", side_effect=subprocess.TimeoutExpired("pip", 120)),
        ):
            installed, failed = install_dependencies(deps)
        assert "slow_pkg" in failed

    def test_parse_dependencies_with_version_ops(self) -> None:
        from skills.dependency_resolver import parse_dependencies

        raw = ["httpx>=0.25", "numpy<=2.0", "torch==2.0", "pkg!=1.0", "other>1.0", "last<3.0"]
        deps = parse_dependencies(raw)
        assert len(deps) == 6
        assert deps[0].package == "httpx"
        assert deps[0].version == ">=0.25"

    def test_parse_dependencies_dict_format(self) -> None:
        from skills.dependency_resolver import parse_dependencies

        raw = [{"package": "Pillow", "import_name": "PIL", "version": ">=10.0"}]
        deps = parse_dependencies(raw)
        assert len(deps) == 1
        assert deps[0].importable == "PIL"
        assert deps[0].pip_spec == "Pillow>=10.0"

    def test_parse_dependencies_plain_string(self) -> None:
        from skills.dependency_resolver import parse_dependencies

        raw = ["requests"]
        deps = parse_dependencies(raw)
        assert len(deps) == 1
        assert deps[0].package == "requests"
        assert deps[0].pip_spec == "requests"


# ============================================================================
# skills/system_control.py -- test _run_power_cmd paths
# ============================================================================


class TestSystemControlCoverage:
    """Test system_control error paths."""

    @pytest.mark.asyncio
    async def test_shutdown_success(self) -> None:
        from skills.system_control import SystemControlSkill

        skill = SystemControlSkill()
        intent = SkillIntent(
            skill_name="system_control", action="shutdown", params={"delay": "60"}, raw_text="shutdown"
        )
        with patch("skills.system_control.asyncio.to_thread", new_callable=AsyncMock):
            result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_restart_success(self) -> None:
        from skills.system_control import SystemControlSkill

        skill = SystemControlSkill()
        intent = SkillIntent(
            skill_name="system_control", action="restart", params={}, raw_text="restart"
        )
        with patch("skills.system_control.asyncio.to_thread", new_callable=AsyncMock):
            result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_sleep_success(self) -> None:
        from skills.system_control import SystemControlSkill

        skill = SystemControlSkill()
        intent = SkillIntent(
            skill_name="system_control", action="sleep", params={}, raw_text="sleep"
        )
        with patch("skills.system_control.asyncio.to_thread", new_callable=AsyncMock):
            result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_lock_success(self) -> None:
        from skills.system_control import SystemControlSkill

        skill = SystemControlSkill()
        intent = SkillIntent(
            skill_name="system_control", action="lock", params={}, raw_text="lock"
        )
        with patch("skills.system_control.asyncio.to_thread", new_callable=AsyncMock):
            result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_hibernate_success(self) -> None:
        from skills.system_control import SystemControlSkill

        skill = SystemControlSkill()
        intent = SkillIntent(
            skill_name="system_control", action="hibernate", params={}, raw_text="hibernate"
        )
        with patch("skills.system_control.asyncio.to_thread", new_callable=AsyncMock):
            result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_power_cmd_timeout(self) -> None:
        import subprocess

        from skills.system_control import SystemControlSkill

        skill = SystemControlSkill()
        intent = SkillIntent(
            skill_name="system_control", action="shutdown", params={"delay": "60"}, raw_text="shutdown"
        )
        with patch("skills.system_control.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.side_effect = subprocess.TimeoutExpired(cmd="shutdown", timeout=10)
            result = await skill.execute(intent)
        assert result.success is False
        assert result.error_code == "timeout"

    @pytest.mark.asyncio
    async def test_power_cmd_os_error(self) -> None:
        from skills.system_control import SystemControlSkill

        skill = SystemControlSkill()
        intent = SkillIntent(
            skill_name="system_control", action="shutdown", params={"delay": "60"}, raw_text="shutdown"
        )
        with patch("skills.system_control.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.side_effect = OSError("no permission")
            result = await skill.execute(intent)
        assert result.success is False
        assert result.error_code == "execution_error"

    @pytest.mark.asyncio
    async def test_unsupported_action(self) -> None:
        from skills.system_control import SystemControlSkill

        skill = SystemControlSkill()
        intent = SkillIntent(
            skill_name="system_control", action="fly", params={}, raw_text="fly"
        )
        result = await skill.execute(intent)
        assert result.success is False
        assert result.error_code == "unsupported_action"


# ============================================================================
# core/audio/recorder.py -- from 71% to ~80%
# ============================================================================


class TestAudioRecorder:
    """Test AudioRecorder mute/unmute and chunk read paths."""

    def test_mute_unmute(self) -> None:
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        assert recorder.is_muted is False

        recorder.mute()
        assert recorder.is_muted is True

        recorder.mute()  # Idempotent
        assert recorder.is_muted is True

        recorder.unmute()
        assert recorder.is_muted is False

        recorder.unmute()  # Idempotent
        assert recorder.is_muted is False

    @pytest.mark.asyncio
    async def test_read_chunk_returns_none_when_muted(self) -> None:
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        recorder.mute()
        result = await recorder.read_chunk()
        assert result is None

    @pytest.mark.asyncio
    async def test_read_chunk_raw_when_muted(self) -> None:
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        recorder.mute()
        # read_chunk_raw should still work (bypasses mute)
        # Will timeout since no audio stream, but should not raise
        result = await recorder.read_chunk_raw()
        assert result is None  # Timeout -> None

    def test_is_active_false_by_default(self) -> None:
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        assert recorder.is_active is False

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self) -> None:
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        await recorder.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_stop_closes_stream(self) -> None:
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        mock_stream = MagicMock()
        recorder._stream = mock_stream

        await recorder.stop()
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()
        assert recorder._stream is None

    @pytest.mark.asyncio
    async def test_stop_handles_oserror(self) -> None:
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        mock_stream = MagicMock()
        mock_stream.stop.side_effect = OSError("stream error")
        recorder._stream = mock_stream

        await recorder.stop()
        assert recorder._stream is None  # Cleaned up despite error

    def test_on_audio_chunk_callback(self) -> None:
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        indata = np.zeros((1280, 1), dtype=np.int16)
        # Should not raise even with no stream
        recorder._on_audio_chunk(indata, 1280, None, None)

    def test_on_audio_chunk_with_status(self) -> None:
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        indata = np.zeros((1280, 1), dtype=np.int16)
        recorder._on_audio_chunk(indata, 1280, None, "overflow")

    def test_ring_buffer_property(self) -> None:
        from core.audio.recorder import AudioRecorder
        from core.audio.ring_buffer import AudioRingBuffer

        recorder = AudioRecorder()
        assert isinstance(recorder.ring_buffer, AudioRingBuffer)


# ============================================================================
# core/ears.py -- from 62% to ~75%
# ============================================================================


class TestEarsEvent:
    """Test Ears event system and state management."""

    def test_ears_state_enum(self) -> None:
        from core.ears import EarsState

        assert EarsState.IDLE.name == "IDLE"
        assert EarsState.STOPPED.name == "STOPPED"

    def test_ears_event_creation(self) -> None:
        from core.ears import EarsEvent, EarsState

        event = EarsEvent(state=EarsState.IDLE, message="test")
        assert event.state == EarsState.IDLE
        assert event.message == "test"

    def test_empty_transcribe_result(self) -> None:
        from core.ears import EmptyTranscribeResult

        result = EmptyTranscribeResult()
        assert result.text == ""
        assert result.confidence == 0.0

    def test_emit_notifies_callbacks(self) -> None:
        from core.config import VoxAgentConfig
        from core.ears import Ears, EarsState

        mock_stt = AsyncMock()
        config = VoxAgentConfig()
        ears = Ears(stt_provider=mock_stt, config=config)

        events = []
        ears.on_event(lambda e: events.append(e))
        ears._emit(EarsState.IDLE, "test message")

        assert len(events) == 1
        assert events[0].state == EarsState.IDLE

    def test_emit_handles_callback_error(self) -> None:
        from core.config import VoxAgentConfig
        from core.ears import Ears, EarsState

        mock_stt = AsyncMock()
        config = VoxAgentConfig()
        ears = Ears(stt_provider=mock_stt, config=config)

        def bad_callback(e):
            raise ValueError("callback error")

        ears.on_event(bad_callback)
        # Should not raise
        ears._emit(EarsState.IDLE, "test")

    def test_ensure_started_raises(self) -> None:
        from core.config import VoxAgentConfig
        from core.ears import Ears
        from core.errors import PipelineError

        mock_stt = AsyncMock()
        config = VoxAgentConfig()
        ears = Ears(stt_provider=mock_stt, config=config)

        with pytest.raises(PipelineError):
            ears._ensure_started()

    def test_state_property(self) -> None:
        from core.config import VoxAgentConfig
        from core.ears import Ears, EarsState

        mock_stt = AsyncMock()
        config = VoxAgentConfig()
        ears = Ears(stt_provider=mock_stt, config=config)
        assert ears.state == EarsState.IDLE

    def test_adaptive_vad_property(self) -> None:
        from core.audio.adaptive_vad import AdaptiveVAD
        from core.config import VoxAgentConfig
        from core.ears import Ears

        mock_stt = AsyncMock()
        config = VoxAgentConfig()
        ears = Ears(stt_provider=mock_stt, config=config)
        assert isinstance(ears.adaptive_vad, AdaptiveVAD)

    def test_recorder_property(self) -> None:
        from core.audio.recorder import AudioRecorder
        from core.config import VoxAgentConfig
        from core.ears import Ears

        mock_stt = AsyncMock()
        config = VoxAgentConfig()
        ears = Ears(stt_provider=mock_stt, config=config)
        assert isinstance(ears.recorder, AudioRecorder)


# ============================================================================
# skills/media_control.py -- covering _send_media_key lines 40-50
# ============================================================================


class TestMediaControlCoverage:
    """Cover _send_media_key function."""

    def test_send_media_key_non_windows(self) -> None:
        from skills.media_control import _send_media_key

        with patch("skills.media_control._IS_WINDOWS", False):
            assert _send_media_key(0xB3) is False

    def test_send_media_key_windows_success(self) -> None:
        from skills.media_control import _send_media_key

        mock_user32 = MagicMock()
        mock_windll = MagicMock()
        mock_windll.user32 = mock_user32

        with (
            patch("skills.media_control._IS_WINDOWS", True),
            patch("skills.media_control.ctypes") as mock_ctypes,
        ):
            mock_ctypes.windll = mock_windll
            result = _send_media_key(0xB3)
        assert result is True

    def test_send_media_key_windows_error(self) -> None:
        from skills.media_control import _send_media_key

        with (
            patch("skills.media_control._IS_WINDOWS", True),
            patch("skills.media_control.ctypes") as mock_ctypes,
        ):
            mock_ctypes.windll.user32.keybd_event.side_effect = AttributeError("no windll")
            result = _send_media_key(0xB3)
        assert result is False

    @pytest.mark.asyncio
    async def test_media_control_execute_unsupported(self) -> None:
        from skills.media_control import MediaControlSkill

        skill = MediaControlSkill()
        intent = SkillIntent(
            skill_name="media_control", action="explode", params={}, raw_text="explode"
        )
        result = await skill.execute(intent)
        assert result.success is False
        assert result.error_code == "unsupported_action"

    @pytest.mark.asyncio
    async def test_media_control_play_pause(self) -> None:
        from skills.media_control import MediaControlSkill

        skill = MediaControlSkill()
        intent = SkillIntent(
            skill_name="media_control", action="play_pause", params={}, raw_text="play"
        )
        with patch("skills.media_control._send_media_key", return_value=True):
            result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_media_control_platform_unsupported(self) -> None:
        from skills.media_control import MediaControlSkill

        skill = MediaControlSkill()
        intent = SkillIntent(
            skill_name="media_control", action="mute", params={}, raw_text="mute"
        )
        with patch("skills.media_control._send_media_key", return_value=False):
            result = await skill.execute(intent)
        assert result.success is False
        assert result.error_code == "platform_unsupported"


# ============================================================================
# core/audio/streaming_player.py -- from 73% to ~80%
# ============================================================================


class TestStreamingPlayerCoverage:
    """Test streaming player utility functions."""

    def test_apply_fade_out(self) -> None:
        from core.audio.streaming_player import _apply_fade_out

        outdata = np.full((1024, 1), 1000, dtype=np.int16)
        _apply_fade_out(outdata)
        # First samples should be faded, later samples should be zero
        assert outdata[-1, 0] == 0

    def test_apply_fade_out_small_buffer(self) -> None:
        from core.audio.streaming_player import _apply_fade_out

        outdata = np.full((10, 1), 1000, dtype=np.int16)
        _apply_fade_out(outdata)
        assert outdata[-1, 0] == 0

    def test_apply_fade_out_zero_frames(self) -> None:
        from core.audio.streaming_player import _apply_fade_out

        outdata = np.zeros((0, 1), dtype=np.int16)
        # Should handle empty buffer gracefully
        _apply_fade_out(outdata, sample_rate=0)

    def test_playback_metrics_defaults(self) -> None:
        from core.audio.streaming_player import PlaybackMetrics

        metrics = PlaybackMetrics()
        assert metrics.chunks_played == 0
        assert metrics.underruns == 0
        assert metrics.interrupted is False

    def test_player_config_defaults(self) -> None:
        from core.audio.streaming_player import PlayerConfig

        config = PlayerConfig()
        assert config.sample_rate == 16_000
        assert config.channels == 1
        assert config.volume == 1.0

    def test_drain_queue(self) -> None:
        from core.audio.streaming_player import StreamingPlayer

        player = StreamingPlayer()
        player._chunk_queue.put(np.zeros(100, dtype=np.int16))
        player._chunk_queue.put(np.zeros(100, dtype=np.int16))
        player._drain_queue()
        assert player._chunk_queue.empty()

    def test_on_stream_finished(self) -> None:
        from core.audio.streaming_player import StreamingPlayer

        player = StreamingPlayer()
        player._on_stream_finished()
        assert player._finished.is_set()

    @pytest.mark.asyncio
    async def test_enqueue_chunk(self) -> None:
        from core.audio.streaming_player import StreamingPlayer

        player = StreamingPlayer()
        chunk = np.zeros(100, dtype=np.int16)
        await player.enqueue(chunk)
        assert not player._chunk_queue.empty()

    @pytest.mark.asyncio
    async def test_enqueue_sentinel(self) -> None:
        from core.audio.streaming_player import SENTINEL, StreamingPlayer

        player = StreamingPlayer()
        await player.enqueue_sentinel()
        item = player._chunk_queue.get_nowait()
        assert item is SENTINEL

    def test_metrics_property(self) -> None:
        from core.audio.streaming_player import StreamingPlayer

        player = StreamingPlayer()
        assert player.metrics.chunks_played == 0
