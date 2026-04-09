"""Structured logging configuration for VoxAgent.

Configures structlog to wrap the stdlib logging module.
All modules should use ``get_logger()`` from this module instead
of ``logging.getLogger()``.

Usage::

    from core.logging import get_logger
    logger = get_logger()
    logger.info("transcription complete", provider="whisper", latency_ms=245)
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(*, debug: bool = False) -> None:
    """Configure structlog + stdlib logging for the entire application.

    Must be called once at application startup (in app.py or server.py)
    before any logger is used.

    Args:
        debug: If True, set log level to DEBUG and use ConsoleRenderer
               for human-readable dev output. If False, use JSON renderer
               for production.
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Configure stdlib root logger
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stderr,
        force=True,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if debug:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=True,
        )
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Also configure a formatter for stdlib handlers to use structlog processing
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Apply formatter to all existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)


def get_logger(**initial_context: object) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        **initial_context: Key-value pairs to bind to every log entry
                          from this logger (e.g., module="brain").

    Returns:
        A structlog BoundLogger that supports .info(), .warning(), etc.
        with keyword arguments for structured fields.

    Example::

        logger = get_logger(module="brain")
        logger.info("intent resolved", skill="media_control", latency_ms=42)
    """
    return structlog.get_logger(**initial_context)
