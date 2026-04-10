"""Type-safe parameter extraction from LLM tool calls.

Validates and converts raw LLM function-calling results into typed
Pydantic models. Malformed parameters return structured errors
instead of crashing the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from core.logging import get_logger

logger = get_logger(module="param_extractor")


# ── Constants ──

MAX_PARAM_VALUE_LENGTH = 2048
MAX_PARAMS_COUNT = 20


# ── Pydantic models for known skill actions ──


class TerminalParams(BaseModel):
    """Parameters for the terminal skill."""

    action: str
    command: str = ""
    confidence: float = 0.9


class MediaControlParams(BaseModel):
    """Parameters for the media_control skill."""

    action: str
    confidence: float = 0.9


class FileManagerParams(BaseModel):
    """Parameters for the file_manager skill."""

    action: str
    path: str = ""
    source: str = ""
    destination: str = ""
    query: str = ""
    confidence: float = 0.9


class AppLauncherParams(BaseModel):
    """Parameters for the app_launcher skill."""

    action: str
    app_name: str = ""
    confidence: float = 0.9


class SystemControlParams(BaseModel):
    """Parameters for the system_control skill."""

    action: str
    confidence: float = 0.9


class GenericParams(BaseModel):
    """Fallback parameters for unrecognized skills."""

    action: str = "default"
    confidence: float = 0.9


# ── Skill-to-model mapping ──

_SKILL_PARAM_MODELS: dict[str, type[BaseModel]] = {
    "terminal": TerminalParams,
    "media_control": MediaControlParams,
    "file_manager": FileManagerParams,
    "app_launcher": AppLauncherParams,
    "system_control": SystemControlParams,
}


@dataclass(frozen=True)
class ExtractionResult:
    """Result of parameter extraction and validation.

    Attributes:
        success: Whether extraction succeeded.
        action: The validated action string.
        params: Validated key-value parameters (strings).
        confidence: Confidence score from LLM.
        error: Error message if validation failed.
        error_code: Machine-readable error code.
    """

    success: bool
    action: str = "default"
    params: dict[str, str] = None  # type: ignore[assignment]
    confidence: float = 0.9
    error: str = ""
    error_code: str = ""

    def __post_init__(self) -> None:
        """Initialize mutable defaults."""
        if self.params is None:
            object.__setattr__(self, "params", {})

    @staticmethod
    def ok(
        action: str,
        params: dict[str, str],
        confidence: float = 0.9,
    ) -> ExtractionResult:
        """Create a successful extraction result.

        Args:
            action: Validated action name.
            params: Validated parameters dict.
            confidence: Confidence score.

        Returns:
            ExtractionResult with success=True.
        """
        return ExtractionResult(
            success=True,
            action=action,
            params=params,
            confidence=confidence,
        )

    @staticmethod
    def fail(error: str, *, error_code: str = "invalid_params") -> ExtractionResult:
        """Create a failed extraction result.

        Args:
            error: Human-readable error description.
            error_code: Machine-readable error code.

        Returns:
            ExtractionResult with success=False.
        """
        return ExtractionResult(
            success=False,
            error=error,
            error_code=error_code,
        )


def _sanitize_raw_args(raw: dict[str, Any]) -> dict[str, Any]:
    """Sanitize raw arguments from LLM output.

    Enforces maximum parameter count and value lengths to prevent
    resource exhaustion from oversized LLM outputs.

    Args:
        raw: Raw arguments dict from LLM tool call.

    Returns:
        Sanitized dict with truncated values.

    Raises:
        ValueError: If parameter count exceeds the limit.
    """
    if len(raw) > MAX_PARAMS_COUNT:
        msg = f"Too many parameters ({len(raw)} > {MAX_PARAMS_COUNT})"
        raise ValueError(msg)

    sanitized: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, str) and len(value) > MAX_PARAM_VALUE_LENGTH:
            sanitized[key] = value[:MAX_PARAM_VALUE_LENGTH]
        else:
            sanitized[key] = value
    return sanitized


def extract_params(skill_name: str, raw_args: dict[str, Any]) -> ExtractionResult:
    """Extract and validate parameters from LLM tool call output.

    Looks up the Pydantic model for the given skill, validates the raw
    args against it, and returns a typed ExtractionResult. Falls back
    to GenericParams for unknown skills.

    Args:
        skill_name: Name of the target skill.
        raw_args: Raw arguments dict from the LLM tool call response.

    Returns:
        ExtractionResult with validated action, params, and confidence.
    """
    if not isinstance(raw_args, dict):
        return ExtractionResult.fail(
            f"Expected dict, got {type(raw_args).__name__}",
            error_code="invalid_type",
        )

    # Sanitize before validation
    try:
        sanitized = _sanitize_raw_args(raw_args)
    except ValueError as e:
        return ExtractionResult.fail(str(e), error_code="param_overflow")

    # Select the right model
    model_class = _SKILL_PARAM_MODELS.get(skill_name, GenericParams)

    try:
        validated = model_class.model_validate(sanitized)
    except ValidationError as e:
        errors = "; ".join(
            f"{err['loc']}: {err['msg']}" for err in e.errors()
        )
        logger.warning(
            "param validation failed",
            skill=skill_name,
            errors=errors,
        )
        return ExtractionResult.fail(
            f"Parameter validation failed: {errors}",
            error_code="validation_error",
        )

    # Convert validated model to param dict
    model_dict = validated.model_dump()
    action = str(model_dict.pop("action", "default"))
    confidence = float(model_dict.pop("confidence", 0.9))

    # Convert remaining values to strings for SkillIntent compatibility
    params = {str(k): str(v) for k, v in model_dict.items() if v}

    logger.debug(
        "params extracted",
        skill=skill_name,
        action=action,
        param_count=len(params),
    )

    return ExtractionResult.ok(action=action, params=params, confidence=confidence)
