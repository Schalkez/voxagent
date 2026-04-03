"""VoxAgent application entry point and lifecycle manager."""

import asyncio
import signal
import sys
from dataclasses import dataclass, field


@dataclass
class VoxAgentApp:
    """Main application orchestrator.

    Manages the lifecycle of all pipeline modules:
    EARS → BRAIN → HANDS → MOUTH, plus EYES and AUTOPILOT.
    """

    debug: bool = False
    _running: bool = field(default=False, init=False)

    async def start(self) -> None:
        """Initialize all modules and start the main listening loop.

        Sets up signal handlers for graceful shutdown on SIGINT/SIGTERM.
        """
        self._running = True

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        if self.debug:
            print("[VoxAgent] Starting in debug mode...")

        try:
            await self._run_loop()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Graceful shutdown of all modules.

        Releases audio resources, closes database connections,
        and cancels any running autopilot tasks.
        """
        if not self._running:
            return
        self._running = False

        if self.debug:
            print("[VoxAgent] Shutting down...")

    async def _run_loop(self) -> None:
        """Main event loop: EARS → BRAIN → HANDS → MOUTH.

        Continuously listens for voice commands and processes them
        through the pipeline until stopped.
        """
        while self._running:
            await asyncio.sleep(0.1)  # Placeholder for EARS.wait_for_command()


def main() -> None:
    """CLI entry point for the voxagent command."""
    app = VoxAgentApp(debug="--debug" in sys.argv)
    asyncio.run(app.start())


if __name__ == "__main__":
    main()
