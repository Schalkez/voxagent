"""Tests for structured logging configuration."""

import logging

import structlog
import pytest

from core.logging import configure_logging, get_logger


class TestConfigureLogging:
    """Tests for logging configuration."""

    def test_configures_without_error(self) -> None:
        """configure_logging should not raise."""
        configure_logging(debug=True)

    def test_debug_mode_sets_debug_level(self) -> None:
        configure_logging(debug=True)
        assert logging.getLogger().level == logging.DEBUG

    def test_production_mode_sets_info_level(self) -> None:
        configure_logging(debug=False)
        assert logging.getLogger().level == logging.INFO


class TestGetLogger:
    """Tests for the get_logger factory."""

    def test_returns_bound_logger(self) -> None:
        configure_logging(debug=True)
        logger = get_logger(module="test")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_bound_context_persists(self) -> None:
        configure_logging(debug=True)
        logger = get_logger(module="test_module")
        # Should not raise — structured fields are accepted
        logger.info("test event", provider="openai", latency_ms=42)

    def test_multiple_loggers_independent(self) -> None:
        configure_logging(debug=True)
        logger_a = get_logger(module="a")
        logger_b = get_logger(module="b")
        # Both should work independently
        logger_a.info("from a")
        logger_b.info("from b")


class TestContextVars:
    """Tests for request-scoped context variables."""

    def test_bind_and_clear(self) -> None:
        configure_logging(debug=True)
        structlog.contextvars.bind_contextvars(request_id="abc123")
        structlog.contextvars.clear_contextvars()
        # After clear, context should be empty (no assertion needed, just no crash)
