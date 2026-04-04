"""VoxAgent application entry point and lifecycle manager.

Orchestrates the EARS → BRAIN → HANDS → MOUTH pipeline
and manages module initialization and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from core.brain import Brain
from core.config import VoxAgentConfig, load_config
from core.hands import Hands
from core.memory import Memory
from core.mouth import Mouth
from providers.registry import ProviderNotFoundError, ProviderRegistry
from skills.base import SkillIntent

if TYPE_CHECKING:
    from core.ears import Ears
    from providers.base import STTProvider, TTSProvider

logger = logging.getLogger("voxagent.app")

_DB_PATH = str(Path.home() / ".voxagent" / "memory.db")


@dataclass
class VoxAgentApp:
    """Main application orchestrator.

    Manages the lifecycle of all pipeline modules:
    EARS → BRAIN → HANDS → MOUTH, plus Memory.
    """

    debug: bool = False
    _running: bool = field(default=False, init=False)
    _config: VoxAgentConfig = field(default_factory=load_config, init=False)
    _registry: ProviderRegistry = field(default_factory=ProviderRegistry, init=False)
    _ears: Ears | None = field(default=None, init=False)
    _brain: Brain | None = field(default=None, init=False)
    _hands: Hands = field(default_factory=Hands, init=False)
    _mouth: Mouth = field(default_factory=Mouth, init=False)
    _memory: Memory = field(default_factory=Memory, init=False)

    async def start(self) -> None:
        """Initialize all modules and start the main listening loop.

        Sets up signal handlers for graceful shutdown on SIGINT/SIGTERM.
        """
        self._running = True

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        logger.info("Starting VoxAgent (debug=%s)...", self.debug)

        await self._init_modules()

        if self.debug:
            logger.info("[VoxAgent] Pipeline ready: EARS → BRAIN → HANDS → MOUTH")

        try:
            await self._run_loop()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def _init_modules(self) -> None:
        """Initialize all pipeline modules from configuration."""
        # 1. Register providers
        self._register_providers()

        # 2. Memory
        await self._memory.connect(_DB_PATH)

        # 3. TTS → Mouth
        tts = self._get_tts_provider()
        self._mouth = Mouth(tts_provider=tts)

        # 4. STT → Ears
        stt = self._get_stt_provider()
        if stt is not None:
            from core.ears import Ears

            self._ears = Ears(stt_provider=stt, config=self._config)

        # 5. Brain (needs registry + skills)
        from skills.registry import registry as skill_registry

        all_skills = list(skill_registry.get_all_skills().values())
        self._brain = Brain(
            registry=self._registry,
            skills=all_skills,
            config=self._config,
        )

        logger.info("All modules initialized")

    def _register_providers(self) -> None:
        """Register all available providers in the registry."""
        try:
            from providers.openai_provider import OpenAIProvider

            self._registry.register_llm("openai", OpenAIProvider)
        except ImportError:
            pass
        try:
            from providers.groq_provider import GroqProvider

            self._registry.register_llm("groq", GroqProvider)
        except ImportError:
            pass
        try:
            from providers.anthropic_provider import AnthropicProvider

            self._registry.register_llm("anthropic", AnthropicProvider)
        except ImportError:
            pass
        try:
            from providers.ollama_provider import OllamaProvider

            self._registry.register_llm("ollama", OllamaProvider)
        except ImportError:
            pass
        try:
            from providers.stt.whisper_local import WhisperLocalProvider

            self._registry.register_stt("whisper_local", WhisperLocalProvider)
        except ImportError:
            pass
        try:
            from providers.stt.openai_whisper import OpenAIWhisperProvider

            self._registry.register_stt("openai_whisper", OpenAIWhisperProvider)
        except ImportError:
            pass
        try:
            from providers.tts.edge_tts_provider import EdgeTTSProvider

            self._registry.register_tts("edge_tts", EdgeTTSProvider)
        except ImportError:
            pass

        fallback = self._config.routing.fallback_chain
        if fallback:
            self._registry.set_fallback_chain(fallback)

    def _get_stt_provider(self) -> STTProvider | None:
        """Get the configured STT provider."""
        stt_name = self._config.stt.provider
        stt_map = {"local": "whisper_local", "openai": "openai_whisper"}
        provider_name = stt_map.get(stt_name, stt_name)
        try:
            return self._registry.get_stt(provider_name)
        except ProviderNotFoundError:
            logger.warning("STT provider '%s' not available", provider_name)
            return None

    def _get_tts_provider(self) -> TTSProvider | None:
        """Get the configured TTS provider."""
        tts_name = self._config.tts.provider
        tts_map = {"piper": "edge_tts", "edge": "edge_tts"}
        provider_name = tts_map.get(tts_name, tts_name)
        try:
            return self._registry.get_tts(provider_name)
        except ProviderNotFoundError:
            logger.warning("TTS provider '%s' not available", provider_name)
            return None

    async def stop(self) -> None:
        """Graceful shutdown of all modules.

        Releases audio resources, closes database connections,
        and cancels any running autopilot tasks.
        """
        if not self._running:
            return
        self._running = False

        logger.info("Shutting down VoxAgent...")

        if self._ears is not None:
            await self._ears.stop()

        await self._memory.close()
        logger.info("VoxAgent stopped")

    async def _run_loop(self) -> None:
        """Main event loop: EARS → BRAIN → HANDS → MOUTH.

        Continuously listens for voice commands and processes them
        through the pipeline until stopped.
        """
        if self._ears is None or self._brain is None:
            logger.warning("Ears or Brain not initialized — running in API-only mode")
            while self._running:
                await asyncio.sleep(1)
            return

        logger.info("Listening for commands...")

        while self._running:
            try:
                transcription = await self._ears.wait_for_command()

                if not transcription.text:
                    continue

                logger.info("Heard: '%s'", transcription.text)

                intent = await self._brain.process(transcription.text)
                logger.info("Intent: skill=%s action=%s", intent.skill_name, intent.action)

                if intent.skill_name == "unknown":
                    await self._mouth.speak("Xin lỗi, tôi không hiểu lệnh đó.")
                    continue

                skill_intent = SkillIntent(
                    skill_name=intent.skill_name,
                    action=intent.action,
                    params=intent.params,
                    raw_text=transcription.text,
                )
                result = await self._hands.execute(skill_intent)

                if result.tts_response:
                    await self._mouth.speak(result.tts_response)
                elif result.error:
                    await self._mouth.speak(f"Có lỗi: {result.error}")

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in main loop")
                await asyncio.sleep(0.5)


def main() -> None:
    """CLI entry point for the voxagent command."""
    logging.basicConfig(
        level=logging.DEBUG if "--debug" in sys.argv else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    app = VoxAgentApp(debug="--debug" in sys.argv)
    asyncio.run(app.start())


if __name__ == "__main__":
    main()
