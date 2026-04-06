"""Tests for the Eyes module."""

import pytest

from core.eyes import Eyes, UIElement, WindowInfo


class TestWindowInfo:
    """Test WindowInfo dataclass."""

    def test_frozen(self) -> None:
        wi = WindowInfo(title="Test", process_name="test.exe", pid=123, bounds=(0, 0, 100, 100))
        with pytest.raises(AttributeError):
            wi.title = "Other"

    def test_fields(self) -> None:
        wi = WindowInfo(title="Test", process_name="proc", pid=1, bounds=(10, 20, 30, 40))
        assert wi.title == "Test"
        assert wi.pid == 1
        assert wi.bounds == (10, 20, 30, 40)


class TestUIElement:
    """Test UIElement dataclass."""

    def test_defaults(self) -> None:
        el = UIElement(role="button", name="OK")
        assert el.value is None
        assert el.bounds is None

    def test_frozen(self) -> None:
        el = UIElement(role="button", name="OK")
        with pytest.raises(AttributeError):
            el.role = "text"


class TestEyes:
    """Test Eyes stub methods."""

    @pytest.mark.asyncio
    async def test_get_active_window_returns_default(self) -> None:
        eyes = Eyes()
        wi = await eyes.get_active_window()
        assert isinstance(wi, WindowInfo)

    @pytest.mark.asyncio
    async def test_find_element_returns_none(self) -> None:
        eyes = Eyes()
        result = await eyes.find_element("button", "OK")
        assert result is None

    @pytest.mark.asyncio
    async def test_read_screen_text_returns_empty(self) -> None:
        eyes = Eyes()
        text = await eyes.read_screen_text()
        assert isinstance(text, str)
