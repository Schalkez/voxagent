"""Benchmark execution-tier latency for VoxAgent skills.

Measures latency per ExecutionTier using mocked skill.execute() calls.
Prints a table: Tier | Avg Latency (ms) | P95 Latency (ms) | Success Rate.

Usage:
    python -m benchmarks.bench_tiers
    python -m benchmarks.bench_tiers --iterations 200
"""

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import ClassVar
from unittest.mock import patch

from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_ITERATIONS = 100
PERCENTILE_95 = 0.95
MS_PER_SECOND = 1_000
TABLE_SEPARATOR_WIDTH = 72

# Simulated latency per tier (seconds) — reflects real-world ordering
SIMULATED_LATENCY: dict[ExecutionTier, float] = {
    ExecutionTier.NATIVE_API: 0.001,
    ExecutionTier.SHELL: 0.002,
    ExecutionTier.APP_API: 0.005,
    ExecutionTier.UI: 0.015,
    ExecutionTier.KEYBOARD: 0.030,
}


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class TierMetrics:
    """Collected latency samples and outcomes for one tier.

    Attributes:
        latencies_ms: Recorded latency per call in milliseconds.
        successes: Number of successful calls.
        failures: Number of failed calls.
    """

    latencies_ms: list[float] = field(default_factory=list)
    successes: int = 0
    failures: int = 0


# ---------------------------------------------------------------------------
# Stub skill
# ---------------------------------------------------------------------------


class _BenchmarkSkill(BaseSkill):
    """Minimal concrete skill used only for benchmarking."""

    name = "benchmark_stub"
    description = "Stub skill for tier benchmarks"
    keywords: ClassVar[list[str]] = []
    execution_tiers: ClassVar[list[ExecutionTier]] = list(ExecutionTier)
    permissions: ClassVar[list[str]] = []

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Always returns True — this stub handles every intent."""
        return True

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Execute with simulated tier latency.

        Args:
            intent: The parsed user intent (tier selected via ``intent.action``).

        Returns:
            SkillResult with the tier recorded in ``tier_used``.
        """
        tier = ExecutionTier(intent.action)
        delay = SIMULATED_LATENCY.get(tier, 0.0)
        await asyncio.sleep(delay)
        return SkillResult(success=True, tier_used=tier)


# ---------------------------------------------------------------------------
# Core benchmark logic
# ---------------------------------------------------------------------------


def _build_intent(tier: ExecutionTier) -> SkillIntent:
    """Build a SkillIntent that targets *tier*.

    Args:
        tier: The execution tier to benchmark.

    Returns:
        A SkillIntent whose ``action`` encodes the tier value.
    """
    return SkillIntent(
        skill_name="benchmark_stub",
        action=tier.value,
        params={},
        raw_text="benchmark run",
    )


async def _run_single(skill: BaseSkill, intent: SkillIntent) -> tuple[float, bool]:
    """Time a single ``skill.execute()`` call.

    Args:
        skill: The skill instance to benchmark.
        intent: Intent passed to ``execute()``.

    Returns:
        Tuple of (latency_ms, success).
    """
    start = time.perf_counter()
    result = await skill.execute(intent)
    elapsed_ms = (time.perf_counter() - start) * MS_PER_SECOND
    return elapsed_ms, result.success


async def _bench_tier(
    skill: BaseSkill,
    tier: ExecutionTier,
    iterations: int,
) -> TierMetrics:
    """Benchmark one tier over *iterations* calls.

    Args:
        skill: The skill instance to benchmark.
        tier: The execution tier being measured.
        iterations: Number of repetitions.

    Returns:
        Aggregated TierMetrics for the tier.
    """
    intent = _build_intent(tier)
    metrics = TierMetrics()

    for _ in range(iterations):
        latency_ms, ok = await _run_single(skill, intent)
        metrics.latencies_ms.append(latency_ms)
        if ok:
            metrics.successes += 1
        else:
            metrics.failures += 1

    return metrics


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _p95(values: list[float]) -> float:
    """Return the 95th-percentile value from *values*.

    Args:
        values: List of numeric observations.

    Returns:
        The P95 value, or 0.0 for empty input.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * PERCENTILE_95)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def _print_table(results: dict[ExecutionTier, TierMetrics]) -> None:
    """Print the benchmark summary table.

    Args:
        results: Mapping of tier to collected metrics.
    """
    header = f"{'Tier':<15} | {'Avg Latency (ms)':>17} | {'P95 Latency (ms)':>17} | {'Success Rate':>12}"
    separator = "-" * TABLE_SEPARATOR_WIDTH
    print(f"\n{header}")
    print(separator)

    for tier in ExecutionTier:
        metrics = results[tier]
        total = metrics.successes + metrics.failures
        avg = statistics.mean(metrics.latencies_ms) if metrics.latencies_ms else 0.0
        p95 = _p95(metrics.latencies_ms)
        rate = (metrics.successes / total * 100) if total else 0.0
        print(f"{tier.name:<15} | {avg:>17.3f} | {p95:>17.3f} | {rate:>11.1f}%")

    print(separator)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _main(iterations: int) -> None:
    """Run benchmarks for all tiers.

    Args:
        iterations: Number of iterations per tier.
    """
    skill = _BenchmarkSkill()
    results: dict[ExecutionTier, TierMetrics] = {}

    print(f"Benchmarking {len(ExecutionTier)} tiers x {iterations} iterations ...")

    with patch.object(skill, "execute", wraps=skill.execute):
        for tier in ExecutionTier:
            results[tier] = await _bench_tier(skill, tier, iterations)

    _print_table(results)


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed namespace with ``iterations``.
    """
    parser = argparse.ArgumentParser(
        description="Benchmark VoxAgent execution-tier latency",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Number of iterations per tier (default: {DEFAULT_ITERATIONS})",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point — parse args and run async benchmarks."""
    args = _parse_args()
    asyncio.run(_main(args.iterations))


if __name__ == "__main__":
    main()
