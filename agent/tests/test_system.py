"""Tests for system automation factory and platform stubs."""

from unittest.mock import patch

import pytest

from system.base import Notification, ProcessInfo, UIElement, WindowInfo


class TestSystemDataclasses:
    """Test system base dataclasses."""

    def test_window_info_frozen(self) -> None:
        wi = WindowInfo(title="T", process_name="p", pid=1, bounds=(0, 0, 0, 0))
        with pytest.raises(AttributeError):
            wi.title = "X"

    def test_process_info(self) -> None:
        pi = ProcessInfo(name="test", pid=42, memory_mb=1.5)
        assert pi.name == "test"
        assert pi.pid == 42

    def test_ui_element_defaults(self) -> None:
        el = UIElement(role="button", name="OK")
        assert el.value is None
        assert el.bounds is None

    def test_notification(self) -> None:
        n = Notification(app="Test", title="Hi", body="Hello", timestamp="2024-01-01")
        assert n.app == "Test"


class TestSystemFactory:
    """Test factory module."""

    def test_factory_returns_automation(self) -> None:
        import system.factory as f

        # Reset singleton for test
        f._automation = None
        auto = f.get_system_automation()
        assert auto is not None

    def test_factory_caches_singleton(self) -> None:
        import system.factory as f

        f._automation = None
        a = f.get_system_automation()
        b = f.get_system_automation()
        assert a is b

    def test_factory_unsupported_os(self) -> None:
        import system.factory as f

        f._automation = None
        with patch("system.factory.platform.system", return_value="FakeOS"), pytest.raises(OSError, match="Unsupported"):
            f.get_system_automation()
        f._automation = None
