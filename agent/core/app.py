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
            except (RuntimeError, OSError, KeyError):
                logger.exception("Error in main loop")
                await asyncio.sleep(0.5)


def main() -> None:
    """CLI entry point for the voxagent command.

    Supports:
        voxagent start [--debug] [--profile <name>]
        voxagent setup  (first-time config wizard)
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="voxagent",
        description="VoxAgent — Voice-controlled desktop AI agent",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # voxagent start
    start_parser = subparsers.add_parser("start", help="Start the voice agent")
    start_parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    start_parser.add_argument(
        "--profile",
        choices=["full_local", "cloud_free", "hybrid", "budget_cloud"],
        help="Load a built-in configuration profile",
    )

    # voxagent setup
    subparsers.add_parser("setup", help="Run first-time configuration wizard")

    args = parser.parse_args()

    # Default to "start" if no command given
    if args.command is None:
        args.command = "start"
        args.debug = "--debug" in sys.argv
        args.profile = None

    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "debug", False) else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if args.command == "setup":
        _run_setup()
        return

    # Load profile if specified, otherwise use default config
    if getattr(args, "profile", None):
        from core.config import load_profile, save_config

        config = load_profile(args.profile)
        save_config(config)
        logger.info("Loaded profile: %s", args.profile)

    # Auto-generate config on first run
    _ensure_config_exists()

    app = VoxAgentApp(debug=getattr(args, "debug", False))
    asyncio.run(app.start())


def _ensure_config_exists() -> None:
    """Create default config file if it doesn't exist yet."""
    config_dir = Path.home() / ".voxagent"
    config_file = config_dir / "config.yaml"

    if config_file.exists():
        return

    from core.config import save_config

    config_dir.mkdir(parents=True, exist_ok=True)
    default_config = load_config()
    save_config(default_config)
    logger.info("Created default config at %s", config_file)


def _run_setup() -> None:
    """Interactive first-time setup wizard."""
    from core.config import list_profiles, load_profile, save_config

    print("\n🤖 VoxAgent Setup Wizard\n")
    print("Available configuration profiles:\n")

    profiles = list_profiles()
    for i, (name, desc) in enumerate(profiles.items(), 1):
        print(f"  {i}. {name:15s} — {desc}")

    print()
    choice = input("Choose a profile (1-4) or press Enter for 'cloud_free': ").strip()

    profile_names = list(profiles.keys())
    selected = profile_names[int(choice) - 1] if choice in ("1", "2", "3", "4") else "cloud_free"

    config = load_profile(selected)
    save_config(config)
    print(f"\n✅ Config saved with profile '{selected}' at ~/.voxagent/config.yaml")
    print("Run 'voxagent start' to begin.\n")


if __name__ == "__main__":
    main()
