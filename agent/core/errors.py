"""VoxError exception hierarchy for VoxAgent.

Provides typed, domain-specific exceptions with severity levels,
user-facing Vietnamese messages, and retry flags. All pipeline
boundaries catch VoxError instead of bare Exception.
"""

from __future__ import annotations

from enum import Enum


class ErrorSeverity(Enum):
    """Severity level for VoxAgent errors."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class VoxError(Exception):
    """Base exception for all VoxAgent domain errors.

    Attributes:
        message: Technical error description for logs.
        severity: How bad is this? (info/warning/critical).
        user_message: Human-readable message safe to speak via TTS (Vietnamese).
        retryable: Whether the operation can be retried.
        context: Optional dict of structured context (provider, skill, etc.).
    """

    def __init__(
        self,
        message: str,
        *,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        user_message: str = "",
        retryable: bool = False,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.severity = severity
        self.user_message = user_message or "Da co loi xay ra."
        self.retryable = retryable
        self.context = context or {}


class ProviderError(VoxError):
    """Error from an LLM/STT/TTS/Vision provider."""

    def __init__(
        self,
        message: str,
        *,
        provider_name: str = "",
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        user_message: str = "Khong ket noi duoc nha cung cap.",
        retryable: bool = True,
        context: dict[str, object] | None = None,
    ) -> None:
        ctx = {**(context or {}), "provider": provider_name}
        super().__init__(
            message,
            severity=severity,
            user_message=user_message,
            retryable=retryable,
            context=ctx,
        )
        self.provider_name = provider_name


class ProviderNotAvailableError(ProviderError):
    """Raised when a requested provider is not registered or unreachable."""

    def __init__(self, provider_name: str, available: list[str] | None = None) -> None:
        detail = f"Provider '{provider_name}' not available"
        if available:
            detail += f". Available: {available}"
        super().__init__(
            detail,
            provider_name=provider_name,
            severity=ErrorSeverity.WARNING,
            user_message=f"Khong tim thay nha cung cap {provider_name}.",
            retryable=False,
        )


class AudioError(VoxError):
    """Error in the audio capture/playback pipeline."""

    def __init__(
        self,
        message: str,
        *,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        user_message: str = "Co loi voi am thanh.",
        retryable: bool = False,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            severity=severity,
            user_message=user_message,
            retryable=retryable,
            context=context,
        )


class PipelineError(VoxError):
    """Error in the EARS->BRAIN->HANDS->MOUTH pipeline."""

    def __init__(
        self,
        message: str,
        *,
        stage: str = "",
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        user_message: str = "Co loi trong qua trinh xu ly.",
        retryable: bool = False,
        context: dict[str, object] | None = None,
    ) -> None:
        ctx = {**(context or {}), "stage": stage}
        super().__init__(
            message,
            severity=severity,
            user_message=user_message,
            retryable=retryable,
            context=ctx,
        )
        self.stage = stage


class ConfigError(VoxError):
    """Error in configuration loading or validation."""

    def __init__(
        self,
        message: str,
        *,
        severity: ErrorSeverity = ErrorSeverity.CRITICAL,
        user_message: str = "Cau hinh bi loi.",
        retryable: bool = False,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            severity=severity,
            user_message=user_message,
            retryable=retryable,
            context=context,
        )


class SkillError(VoxError):
    """Error during skill execution."""

    def __init__(
        self,
        message: str,
        *,
        skill_name: str = "",
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        user_message: str = "Khong the thuc hien ky nang nay.",
        retryable: bool = False,
        context: dict[str, object] | None = None,
    ) -> None:
        ctx = {**(context or {}), "skill": skill_name}
        super().__init__(
            message,
            severity=severity,
            user_message=user_message,
            retryable=retryable,
            context=ctx,
        )
        self.skill_name = skill_name
