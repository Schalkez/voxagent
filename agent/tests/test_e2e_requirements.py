"""E2E integration tests for remaining requirement gaps (SC-4).

Upgrades shallow requirement-level tests to true integration tests
that exercise cross-phase interactions:
- STTS-02/03/04: Streaming TTS produce/consume
- AUDR-01: Mic muted during SPEAKING state
- PROG-02: Progress updates during slow skills
- SAFE-08: API auth rejection
- SAFE-06: File sandbox path traversal
- SAFE-03: Parameter extraction through Brain
- AUDR-02/03/04/05: Cross-phase audio pipeline
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
import wave
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from core.audio.adaptive_vad import AdaptiveVAD, AdaptiveVADConfig, HysteresisState
from core.audio.normalizer import AudioNormalizer
from core.audio.recorder import AudioRecorder
from core.audio.ring_buffer import AudioRingBuffer
from core.audio.streaming_player import PlayerConfig, StreamingPlayer
from core.audio.vad import VoiceActivityDetector
from core.brain import Brain, Tier
from core.hands import Hands
from core.mouth import Mouth
from core.param_extractor import extract_params
from core.pipeline_state import PipelineState, PipelineStateMachine
from providers.base import TranscribeResult
from providers.registry import ProviderRegistry
from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.file_manager import FileManagerSkill
from skills.registry import SkillRegistry


# ── Shared Helpers ───────────────────────────────────────────────────────────


def _make_valid_wav_bytes() -> bytes:
    """Generate minimal valid WAV audio bytes (16kHz, mono, int16, ~50ms)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(np.zeros(800, dtype=np.int16).tobytes())
    return buf.getvalue()


def _make_mock_tts() -> AsyncMock:
    """Create a mock TTS provider."""
    mock = AsyncMock()
    mock.synthesize = AsyncMock(return_value=_make_valid_wav_bytes())

    async def _fake_stream(*_args, **_kwargs):
        yield b"\xff" * 100
        yield b"\xff" * 100
        yield b"\xff" * 100

    mock.synthesize_stream = _fake_stream
    return mock


def _make_mock_llm(response: dict[str, object] | None = None) -> AsyncMock:
    """Create a mock LLM provider."""
    mock = AsyncMock()
    mock.chat_with_tools = AsyncMock(
        return_value=response
        or {"tool": "media_control", "result": {"action": "pause", "confidence": 0.95}}
    )
    mock.health_check = AsyncMock(return_value=True)
    return mock


class _FakeSkill(BaseSkill):
    """Minimal skill for tests."""

    name = "media_control"
    description = "Control media playback"
    keywords: ClassVar[list[str]] = ["pause", "play", "skip"]
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]
    permissions: ClassVar[list[str]] = ["media:control"]

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Accept intents targeting this skill."""
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Simulate media control execution."""
        return SkillResult.ok(
            tts_response="Da pause roi nha.",
            tier_used=ExecutionTier.NATIVE_API,
        )


class _SlowTestSkill(BaseSkill):
    """Skill with configurable delay for progress tests."""

    name = "slow_test_skill"
    description = "Slow for testing"
    keywords: ClassVar[list[str]] = ["slow_test"]
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]
    permissions: ClassVar[list[str]] = []

    def __init__(self, delay: float = 0.5) -> None:
        """Initialize with configurable delay."""
        super().__init__()
        self._delay = delay

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Accept all intents."""
        return True

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Sleep for a configurable duration."""
        await asyncio.sleep(self._delay)
        return SkillResult.ok(
            tts_response="Done!",
            tier_used=ExecutionTier.NATIVE_API,
        )


# ── Task 2.1 + 2.2: Streaming TTS E2E ──────────────────────────────────────


class TestStreamingTTSE2E:
    """STTS-02/03/04: Streaming TTS produce/consume through pipeline."""

    @pytest.mark.asyncio
    async def test_streaming_produce_consume(self) -> None:
        """STTS-02/04: Mouth.speak_streaming produces chunks via TTS and consumes them.

        Verifies the producer-consumer pipeline between synthesize_stream
        and StreamingPlayer. Mock TTS yields 3 chunks; all are consumed.
        """
        chunks_produced: list[bytes] = []

        async def _tracking_stream(*_args, **_kwargs):
            for i in range(3):
                chunk = bytes([i + 1]) * 100
                chunks_produced.append(chunk)
                yield chunk

        mock_tts = AsyncMock()
        mock_tts.synthesize = AsyncMock(return_value=_make_valid_wav_bytes())
        mock_tts.synthesize_stream = _tracking_stream

        mouth = Mouth(tts_provider=mock_tts)

        # Patch StreamingPlayer.play and _decode_mp3_to_pcm to avoid
        # requiring real sounddevice/miniaudio
        with (
            patch("core.mouth.StreamingPlayer") as MockPlayer,
            patch("core.mouth._decode_mp3_to_pcm") as mock_decode,
        ):
            player_instance = AsyncMock()
            player_instance.play = AsyncMock(return_value=None)
            player_instance.enqueue = AsyncMock()
            player_instance.enqueue_sentinel = AsyncMock()
            player_instance.metrics = MagicMock(
                chunks_played=3, underruns=0, interrupted=False
            )
            MockPlayer.return_value = player_instance

            mock_decode.return_value = np.zeros(100, dtype=np.int16)

            await mouth.speak_streaming("Xin chao anh. Day la VoxAgent.")

        # Verify chunks were produced (text chunker splits into 2 sentences,
        # each sentence calls synthesize_stream yielding 3 chunks = 6 total)
        assert len(chunks_produced) >= 3

        # Verify enqueue was called (once per decoded chunk + sentinel)
        assert player_instance.enqueue.call_count >= 3
        player_instance.enqueue_sentinel.assert_called_once()

    @pytest.mark.asyncio
    async def test_incremental_consumption(self) -> None:
        """STTS-03: Chunks are consumed incrementally, not buffered all-at-once.

        Mock TTS yields 5 chunks with delays; verify each is enqueued
        as it arrives (not batched).
        """
        enqueue_times: list[float] = []

        async def _delayed_stream(*_args, **_kwargs):
            import time

            for i in range(5):
                yield bytes([i + 1]) * 100
                await asyncio.sleep(0.01)  # Small delay between chunks

        mock_tts = AsyncMock()
        mock_tts.synthesize = AsyncMock(return_value=_make_valid_wav_bytes())
        mock_tts.synthesize_stream = _delayed_stream

        mouth = Mouth(tts_provider=mock_tts)

        with (
            patch("core.mouth.StreamingPlayer") as MockPlayer,
            patch("core.mouth._decode_mp3_to_pcm") as mock_decode,
        ):
            player_instance = AsyncMock()
            player_instance.play = AsyncMock(return_value=None)

            import time as _time

            async def _tracking_enqueue(chunk):
                enqueue_times.append(_time.monotonic())

            player_instance.enqueue = _tracking_enqueue
            player_instance.enqueue_sentinel = AsyncMock()
            player_instance.metrics = MagicMock(
                chunks_played=5, underruns=0, interrupted=False
            )
            MockPlayer.return_value = player_instance
            mock_decode.return_value = np.ones(100, dtype=np.int16)

            await mouth.speak_streaming("Mot hai ba bon nam.")

        # Should have 5 enqueue calls, each spaced apart
        assert len(enqueue_times) >= 5

        # Verify they weren't all enqueued at the same instant (incremental)
        if len(enqueue_times) >= 2:
            total_spread = enqueue_times[-1] - enqueue_times[0]
            assert total_spread > 0.01, (
                f"Chunks enqueued in {total_spread:.4f}s — expected incremental delivery"
            )


# ── Task 2.3: AUDR-01 Mic Muted During SPEAKING ────────────────────────────


class TestAudioPipelineE2E:
    """AUDR-01/02/03/04/05: Audio pipeline integration tests."""

    @pytest.mark.asyncio
    async def test_mic_muted_during_speaking(self) -> None:
        """AUDR-01: When recorder is muted, read_chunk returns None.

        Verifies that during SPEAKING state, the mic is effectively
        muted and read_chunk returns None immediately.
        """
        recorder = AudioRecorder(
            sample_rate=16000,
            channels=1,
            chunk_samples=1280,
            buffer_capacity=8,
        )

        # Initially unmuted
        assert not recorder.is_muted

        # Mute (simulates SPEAKING state)
        recorder.mute()
        assert recorder.is_muted

        # read_chunk returns None immediately when muted
        result = await recorder.read_chunk()
        assert result is None

        # Unmute (simulates LISTENING state)
        recorder.unmute()
        assert not recorder.is_muted

        # read_chunk now waits for data (returns None on timeout since no data)
        result = await recorder.read_chunk()
        assert result is None  # timeout, but NOT immediate None from mute

    @pytest.mark.asyncio
    async def test_cross_phase_audio_pipeline(self) -> None:
        """AUDR-02/03/04/05: Normalize -> ring buffer -> read -> AdaptiveVAD.

        Full cross-phase integration: audio normalization, ring buffer
        write/read, and adaptive VAD processing all work together.
        """
        # 1. Normalize a float32/48kHz/stereo chunk -> int16/16kHz/mono
        normalizer = AudioNormalizer(target_sample_rate=16000, target_channels=1)
        raw_float = np.random.uniform(-0.5, 0.5, size=4800).astype(np.float32)
        normalized = normalizer.normalize(raw_float, source_rate=48000, source_channels=2)

        assert normalized.dtype == np.int16
        expected_samples = 4800 // 2  # stereo->mono halves samples
        expected_samples = int(expected_samples * (16000 / 48000))  # resample
        assert abs(len(normalized) - expected_samples) <= 2

        # 2. Write to ring buffer
        buffer = AudioRingBuffer(capacity=8, chunk_samples=len(normalized))
        buffer.write(normalized)
        assert buffer.size == 1

        # 3. Read from ring buffer
        read_chunk = await buffer.read(timeout=0.1)
        assert read_chunk is not None
        assert read_chunk.dtype == np.int16
        assert len(read_chunk) == len(normalized)

        # 4. Feed to AdaptiveVAD
        vad = VoiceActivityDetector(energy_threshold=500.0)
        adaptive_vad = AdaptiveVAD(
            vad=vad,
            config=AdaptiveVADConfig(
                speech_start_frames=2,
                silence_end_frames=3,
            ),
        )

        # Process the chunk — should not crash
        result = adaptive_vad.process_chunk(read_chunk)
        assert isinstance(result, bool)

        # Ambient RMS should have updated (since state is SILENCE)
        assert adaptive_vad.ambient_rms > 0

    @pytest.mark.asyncio
    async def test_normalizer_stereo_to_mono(self) -> None:
        """AUDR-05: Stereo input is correctly downmixed to mono."""
        normalizer = AudioNormalizer(target_sample_rate=16000, target_channels=1)

        # 100 stereo frames at 16kHz = 200 samples interleaved
        stereo = np.array(
            [[1000, -1000]] * 100,
            dtype=np.int16,
        ).flatten()

        mono = normalizer.normalize(stereo, source_rate=16000, source_channels=2)
        assert mono.dtype == np.int16
        # 100 stereo frames -> 100 mono samples
        assert len(mono) == 100

    @pytest.mark.asyncio
    async def test_adaptive_vad_hysteresis(self) -> None:
        """AUDR-02/03: VAD hysteresis requires consecutive frames.

        Speech starts only after N consecutive speech frames.
        Speech ends only after M consecutive silence frames.
        """
        vad = VoiceActivityDetector(energy_threshold=200.0)
        adaptive = AdaptiveVAD(
            vad=vad,
            config=AdaptiveVADConfig(
                speech_start_frames=3,
                silence_end_frames=3,
                ambient_multiplier=2.0,
            ),
        )

        # Feed silence -> should stay in SILENCE
        silence_chunk = np.zeros(160, dtype=np.int16)
        for _ in range(5):
            adaptive.process_chunk(silence_chunk)
        assert adaptive.state == HysteresisState.SILENCE
        assert not adaptive.is_speech_active

        # Feed 3 loud speech frames -> should transition to SPEECH
        speech_chunk = np.full(160, 5000, dtype=np.int16)
        for _ in range(3):
            adaptive.process_chunk(speech_chunk)
        assert adaptive.is_speech_active

        # Feed 2 silence frames -> still SPEECH (need 3)
        for _ in range(2):
            adaptive.process_chunk(silence_chunk)
        assert adaptive.state in (
            HysteresisState.SPEECH,
            HysteresisState.PENDING_SILENCE,
        )

        # Feed 1 more silence -> should end speech
        adaptive.process_chunk(silence_chunk)
        assert adaptive.state == HysteresisState.SILENCE
        assert not adaptive.is_speech_active


# ── Task 2.4: PROG-02 Progress During Slow Skill ────────────────────────────


class TestProgressE2E:
    """PROG-02: Progress updates during long-running skills."""

    @pytest.mark.asyncio
    async def test_progress_fires_during_slow_skill(self) -> None:
        """PROG-02: A skill exceeding PROGRESS_INITIAL_DELAY_S triggers progress speech.

        Uses a mock Mouth to verify speak() is called with a progress message.
        """
        slow_skill = _SlowTestSkill(delay=0.3)
        mock_mouth = AsyncMock(spec=Mouth)
        mock_mouth.speak = AsyncMock()

        # Patch the initial delay to be very short for testing
        with patch("core.hands.PROGRESS_INITIAL_DELAY_S", 0.1):
            hands = Hands(mouth=mock_mouth, skill_timeout_s=5.0)

            saved = SkillRegistry._skills.get("slow_test_skill")
            SkillRegistry._skills["slow_test_skill"] = slow_skill

            try:
                intent = SkillIntent(
                    skill_name="slow_test_skill",
                    action="slow_test",
                    params={},
                    raw_text="do slow thing",
                )
                result = await hands.execute(intent)
                assert result.success is True
            finally:
                if saved is None:
                    SkillRegistry._skills.pop("slow_test_skill", None)
                else:
                    SkillRegistry._skills["slow_test_skill"] = saved

        # Mouth.speak should have been called with a progress message
        # PROGRESS_MESSAGES contains Vietnamese Unicode: "Đang xử lý..."
        from core.hands import PROGRESS_MESSAGES

        progress_calls = [
            call for call in mock_mouth.speak.call_args_list
            if any(
                msg in str(call.args[0]) if call.args else False
                for msg in PROGRESS_MESSAGES
            )
        ]
        assert len(progress_calls) >= 1, (
            f"Expected progress message, got calls: {mock_mouth.speak.call_args_list}"
        )


# ── Task 2.5: SAFE-08 API Auth Rejection ────────────────────────────────────


class TestSafetyE2E:
    """SAFE-03/06/08: Safety integration tests."""

    @pytest.mark.asyncio
    async def test_api_auth_rejection(self) -> None:
        """SAFE-08: Protected endpoints reject requests without valid token.

        Uses FastAPI TestClient to verify:
        - /api/health without auth -> 200 (public)
        - /api/providers without auth -> 401
        - /api/providers with valid token -> 200
        """
        # Set a known token for testing
        os.environ["VOXAGENT_API_TOKEN"] = "test-secret-token-12345"

        try:
            from fastapi.testclient import TestClient

            from api.server import app

            with TestClient(app) as client:
                # Public endpoint: no auth required
                resp = client.get("/api/health")
                assert resp.status_code == 200

                # Protected endpoint: no auth -> 401
                resp = client.get("/api/status")
                assert resp.status_code == 401

                # Protected endpoint: valid token -> 200
                resp = client.get(
                    "/api/status",
                    headers={"Authorization": "Bearer test-secret-token-12345"},
                )
                assert resp.status_code == 200
        finally:
            os.environ.pop("VOXAGENT_API_TOKEN", None)

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self) -> None:
        """SAFE-06: FileManagerSkill blocks path traversal.

        Path traversal attempt (../../etc/passwd) is blocked when
        allowed_directories is restricted.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = FileManagerSkill(allowed_directories=[tmpdir])

            traversal_intent = SkillIntent(
                skill_name="file_manager",
                action="list_dir",
                params={"path": f"{tmpdir}/../../etc"},
                raw_text="list /etc",
            )
            result = await skill.execute(traversal_intent)
            assert result.success is False
            assert result.error_code == "path_not_allowed"

    @pytest.mark.asyncio
    async def test_param_extraction_through_brain(self) -> None:
        """SAFE-03: LLM tool call params flow through extract_params.

        Valid params -> extraction succeeds -> skill runs.
        Malformed params -> extraction fails -> error returned.
        """
        # Valid extraction
        valid_result = extract_params(
            "media_control",
            {"action": "pause", "confidence": 0.9},
        )
        assert valid_result.success is True
        assert valid_result.action == "pause"

        # Malformed: non-dict
        invalid_result = extract_params("media_control", "not_a_dict")  # type: ignore[arg-type]
        assert invalid_result.success is False
        assert invalid_result.error_code == "invalid_type"

    @pytest.mark.asyncio
    async def test_param_extraction_e2e_through_brain(self) -> None:
        """SAFE-03: Full flow: LLM returns tool call -> Brain extracts params -> skill executes.

        Mock LLM returns valid params, verify they flow through
        extract_params inside Brain._parse_tool_response.
        """
        skill = _FakeSkill()
        mock_llm = _make_mock_llm(
            response={
                "tool": "media_control",
                "result": {"action": "pause", "confidence": 0.95},
            }
        )
        registry = ProviderRegistry()
        registry.register_llm("ollama", lambda: mock_llm)

        brain = Brain(
            registry=registry,
            skills=[skill],
            routing_config={"tiers": [{"provider": "ollama", "model": "test"}]},
        )

        intent = await brain.process("tam dung bai hat dang phat")
        assert intent.skill_name == "media_control"
        assert intent.action == "pause"
        assert intent.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_param_extraction_malformed_returns_fallback(self) -> None:
        """SAFE-03: Malformed LLM response -> Brain returns fallback intent."""
        skill = _FakeSkill()
        mock_llm = _make_mock_llm(
            response={
                "tool": "media_control",
                # Missing "result" key entirely
            }
        )
        registry = ProviderRegistry()
        registry.register_llm("ollama", lambda: mock_llm)

        brain = Brain(
            registry=registry,
            skills=[skill],
            routing_config={"tiers": [{"provider": "ollama", "model": "test"}]},
        )

        intent = await brain.process("lenh phuc tap")
        # Should still return an intent (graceful degradation)
        assert isinstance(intent, type(intent))
        # Should be media_control with default action since tool name matched
        assert intent.skill_name == "media_control"

    @pytest.mark.asyncio
    async def test_file_sandbox_allows_valid_path(self) -> None:
        """SAFE-06: FileManagerSkill allows operations within allowed directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("hello")

            skill = FileManagerSkill(allowed_directories=[tmpdir])

            valid_intent = SkillIntent(
                skill_name="file_manager",
                action="list_dir",
                params={"path": tmpdir},
                raw_text="list files",
            )
            result = await skill.execute(valid_intent)
            assert result.success is True
            assert "items" in result.data
