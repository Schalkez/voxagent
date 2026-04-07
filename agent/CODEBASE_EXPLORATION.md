
# VoxAgent Codebase Exploration Report

## Executive Summary
VoxAgent is a modular voice agent with:
- Skill-based execution via plugin registry
- Multi-tier provider system with fallback
- Execution tiers: NATIVE_API, SHELL, APP_API, UI, KEYBOARD
- REST API for management
- Comprehensive test coverage

## 1. ExecutionTier Enum (skills/base.py, lines 13-30)

Values:
- NATIVE_API = "native_api" (Tier A)
- SHELL = "shell" (Tier A)
- APP_API = "app_api" (Tier B)
- UI = "ui" (Tier C)
- KEYBOARD = "keyboard" (Tier D)

## 2. BaseSkill Class (skills/base.py, lines 71-120)

Class Attributes:
- name: str
- description: str
- keywords: ClassVar[list[str]]
- execution_tiers: ClassVar[list[ExecutionTier]]
- permissions: ClassVar[list[str]]

Abstract Methods:
- async def can_handle(intent: SkillIntent) -> bool
- async def execute(intent: SkillIntent) -> SkillResult

Input (SkillIntent):
- skill_name: str
- action: str
- params: dict[str, str]
- raw_text: str

Output (SkillResult):
- success: bool
- tts_response: str
- data: dict[str, object]
- error: str | None
- cancelled: bool
- tier_used: ExecutionTier | None

## 3. STT Provider Base Class (providers/base.py, lines 109-122)

Abstract Method:
async def transcribe(audio: bytes, language: str = "vi") -> TranscribeResult

Return Type (TranscribeResult):
- text: str
- confidence: float (0.0-1.0)
- language: str
- duration_ms: int

Implementations:
1. WhisperLocalProvider (providers/stt/whisper_local.py)
   - Uses faster-whisper (CTranslate2)
   - Model sizes: tiny, base, small, medium, large-v3
   - On-device, lazy-loads

2. OpenAIWhisperProvider (providers/stt/openai_whisper.py)
   - Cloud-based OpenAI API
   - Requires API key
   - Endpoint: https://api.openai.com/v1/audio/transcriptions

## 4. Project Structure

Top-Level:
- api/ (REST API)
- core/ (Agent pipeline)
- providers/ (LLM, STT, TTS, Vision)
- skills/ (Executable skills)
- system/ (OS abstraction)
- tests/ (Test suite)

Core Modules:
- brain.py (LLM decision-making)
- ears.py (Audio & STT)
- hands.py (Skill execution)
- mouth.py (TTS output)
- config.py (Configuration)

Providers:
- LLM: anthropic, openai, groq, ollama, mistral, deepseek, openrouter
- STT: whisper_local, openai_whisper
- TTS: piper, edge_tts, voice_cloning
- Vision: anthropic_vision, openai_vision, gemini_vision

Skills:
- media_control, app_launcher, system_control
- file_manager, browser_control, terminal
- screen_reader, code_reviewer, etc.

## 5. Test Patterns

Pattern 1: Mock Providers (test_providers.py)
- Inherit from LLMProvider, STTProvider, etc.
- Implement abstract methods with mock returns
- Use in ProviderRegistry

Pattern 2: Mock Skills (test_hands.py)
- Create DummySkill inheriting BaseSkill
- Use @pytest.fixture with SkillRegistry

Pattern 3: Async Mocks (test_final_coverage.py)
- Use unittest.mock.AsyncMock
- Patch with new_callable=AsyncMock

Pattern 4: Fallback Testing (test_providers.py)
- Register multiple providers
- Set fallback chain
- Test health-based selection

Pattern 5: Patching (test_llm_providers.py)
- Patch module functions with return_value
- Mock API key retrieval

## 6. Configuration (core/config.py)

Built-in Profiles:
1. full_local - Ollama + Local Whisper
2. cloud_free - Groq + Local Whisper
3. hybrid - Groq + Anthropic
4. budget_cloud - Groq + Ollama fallback

## Key Principles

- Async-First
- Plugin Architecture
- Execution Tiers
- Multi-Provider Fallback
- Configuration Profiles
- Vietnamese Language Support
- Safety-First

## Quick Reference

Files of Interest:
- skills/base.py (120 lines) - ExecutionTier, BaseSkill
- providers/base.py (156 lines) - Provider ABCs
- skills/registry.py (93 lines) - Skill registration
- core/config.py (375 lines) - Config management
- providers/stt/whisper_local.py (116 lines) - Local STT
- providers/stt/openai_whisper.py (96 lines) - Cloud STT
- tests/test_providers.py (156 lines) - Mocking patterns
- tests/test_hands.py (62 lines) - Skill execution
- tests/test_skills.py (169 lines) - Skill tests
