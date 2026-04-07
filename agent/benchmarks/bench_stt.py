"""Benchmark STT provider latency and accuracy.

Reads WAV files and a JSON manifest of expected transcriptions, then
measures transcription time and Word Error Rate (WER) per provider.

Manifest format (``manifest.json`` alongside the WAV directory)::

    {
      "files": [
        {"wav": "sample_01.wav", "expected": "xin chào thế giới"},
        {"wav": "sample_02.wav", "expected": "hôm nay trời đẹp"}
      ]
    }

Usage:
    python -m benchmarks.bench_stt --wav-dir tests/fixtures/wav
    python -m benchmarks.bench_stt --wav-dir data/wav --providers whisper_local openai
"""

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

from providers.base import STTProvider, TranscribeResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MS_PER_SECOND = 1_000
MANIFEST_FILENAME = "manifest.json"
TABLE_SEPARATOR_WIDTH = 80
DEFAULT_LANGUAGE = "vi"


# ---------------------------------------------------------------------------
# WER calculation
# ---------------------------------------------------------------------------


def _levenshtein(source: list[str], target: list[str]) -> int:
    """Compute Levenshtein edit distance between two word lists.

    Args:
        source: Hypothesis word list.
        target: Reference word list.

    Returns:
        Minimum number of insertions, deletions, and substitutions.
    """
    n, m = len(source), len(target)
    dp: list[list[int]] = [[0] * (m + 1) for _ in range(n + 1)]

    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if source[i - 1] == target[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )

    return dp[n][m]


def word_error_rate(hypothesis: str, reference: str) -> float:
    """Calculate Word Error Rate between hypothesis and reference.

    WER = levenshtein(hyp_words, ref_words) / len(ref_words).

    Args:
        hypothesis: Transcribed text from the provider.
        reference: Ground-truth expected text.

    Returns:
        WER as a float (0.0 = perfect, >1.0 possible with many insertions).
    """
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()

    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    distance = _levenshtein(hyp_words, ref_words)
    return distance / len(ref_words)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class SampleResult:
    """Result for a single WAV file transcription.

    Attributes:
        wav_name: Filename of the WAV sample.
        expected: Ground-truth text.
        transcribed: Text returned by the provider.
        latency_ms: Transcription wall-clock time in milliseconds.
        wer: Word Error Rate for this sample.
    """

    wav_name: str
    expected: str
    transcribed: str
    latency_ms: float
    wer: float


@dataclass
class ProviderBenchmark:
    """Aggregated results for one STT provider.

    Attributes:
        provider_name: Identifier of the provider.
        samples: Per-file results.
    """

    provider_name: str
    samples: list[SampleResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ManifestEntry:
    """One entry from the WAV manifest.

    Attributes:
        wav_path: Absolute path to the WAV file.
        expected: Expected transcription text.
    """

    wav_path: Path
    expected: str


def _load_manifest(wav_dir: Path) -> list[ManifestEntry]:
    """Load and validate the manifest from *wav_dir*.

    Args:
        wav_dir: Directory containing WAV files and ``manifest.json``.

    Returns:
        List of ManifestEntry objects.

    Raises:
        FileNotFoundError: If manifest or a WAV file is missing.
        ValueError: If manifest format is invalid.
    """
    manifest_path = wav_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = data.get("files")
    if not isinstance(files, list):
        raise ValueError("Manifest must contain a 'files' array")

    entries: list[ManifestEntry] = []
    for item in files:
        wav_name = item.get("wav", "")
        expected = item.get("expected", "")
        wav_path = wav_dir / wav_name

        if not wav_path.exists():
            raise FileNotFoundError(f"WAV file not found: {wav_path}")

        entries.append(ManifestEntry(wav_path=wav_path, expected=expected))

    return entries


# ---------------------------------------------------------------------------
# Provider discovery
# ---------------------------------------------------------------------------


def _discover_providers(names: list[str] | None) -> dict[str, STTProvider]:
    """Discover and instantiate STT providers by name.

    Uses a lazy import approach to avoid import-time side-effects.

    Args:
        names: Explicit provider names, or None to auto-discover all.

    Returns:
        Mapping of provider name to instance.

    Raises:
        ImportError: If a requested provider module cannot be found.
    """
    registry: dict[str, type[STTProvider]] = {}

    try:
        from providers.stt.whisper_local import WhisperLocalProvider

        registry["whisper_local"] = WhisperLocalProvider
    except ImportError:
        pass

    try:
        from providers.stt.openai_whisper import OpenAIWhisperProvider

        registry["openai"] = OpenAIWhisperProvider
    except ImportError:
        pass

    if names is None:
        names = list(registry.keys())

    providers: dict[str, STTProvider] = {}
    for name in names:
        cls = registry.get(name)
        if cls is None:
            raise ImportError(f"Unknown STT provider: {name}")
        providers[name] = cls()

    return providers


# ---------------------------------------------------------------------------
# Benchmarking
# ---------------------------------------------------------------------------


async def _bench_sample(
    provider: STTProvider,
    entry: ManifestEntry,
) -> SampleResult:
    """Benchmark a single WAV sample against one provider.

    Args:
        provider: The STT provider instance.
        entry: Manifest entry with WAV path and expected text.

    Returns:
        SampleResult with latency and WER.
    """
    audio_bytes = entry.wav_path.read_bytes()

    start = time.perf_counter()
    result: TranscribeResult = await provider.transcribe(audio_bytes, language=DEFAULT_LANGUAGE)
    latency_ms = (time.perf_counter() - start) * MS_PER_SECOND

    wer = word_error_rate(result.text, entry.expected)

    return SampleResult(
        wav_name=entry.wav_path.name,
        expected=entry.expected,
        transcribed=result.text,
        latency_ms=latency_ms,
        wer=wer,
    )


async def _bench_provider(
    name: str,
    provider: STTProvider,
    entries: list[ManifestEntry],
) -> ProviderBenchmark:
    """Benchmark all samples against one provider.

    Args:
        name: Provider identifier.
        provider: The STT provider instance.
        entries: All manifest entries to transcribe.

    Returns:
        ProviderBenchmark with per-sample results.
    """
    bench = ProviderBenchmark(provider_name=name)
    for entry in entries:
        sample = await _bench_sample(provider, entry)
        bench.samples.append(sample)
    return bench


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _print_provider_results(bench: ProviderBenchmark) -> None:
    """Print per-sample and summary results for one provider.

    Args:
        bench: The provider benchmark results.
    """
    separator = "=" * TABLE_SEPARATOR_WIDTH
    print(f"\n{separator}")
    print(f"  Provider: {bench.provider_name}")
    print(separator)

    header = f"  {'File':<25} | {'Latency (ms)':>13} | {'WER':>8} | Transcribed"
    print(header)
    print(f"  {'-' * (TABLE_SEPARATOR_WIDTH - 4)}")

    for s in bench.samples:
        preview = s.transcribed[:30] + ("…" if len(s.transcribed) > 30 else "")
        print(f"  {s.wav_name:<25} | {s.latency_ms:>13.2f} | {s.wer:>8.3f} | {preview}")

    if bench.samples:
        latencies = [s.latency_ms for s in bench.samples]
        wers = [s.wer for s in bench.samples]
        print(f"\n  Avg latency : {statistics.mean(latencies):.2f} ms")
        print(f"  Avg WER     : {statistics.mean(wers):.3f}")
        print(f"  Min/Max WER : {min(wers):.3f} / {max(wers):.3f}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _main(wav_dir: Path, provider_names: list[str] | None) -> None:
    """Run STT benchmarks across all providers.

    Args:
        wav_dir: Directory with WAV files and manifest.
        provider_names: Explicit list or None for auto-discover.
    """
    entries = _load_manifest(wav_dir)
    print(f"Loaded {len(entries)} samples from {wav_dir / MANIFEST_FILENAME}")

    providers = _discover_providers(provider_names)
    print(f"Benchmarking providers: {', '.join(providers)}")

    for name, provider in providers.items():
        bench = await _bench_provider(name, provider, entries)
        _print_provider_results(bench)


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments.

    Returns:
        Parsed namespace with ``wav_dir`` and ``providers``.
    """
    parser = argparse.ArgumentParser(
        description="Benchmark STT provider latency and Word Error Rate",
    )
    parser.add_argument(
        "--wav-dir",
        type=Path,
        required=True,
        help="Directory containing WAV files and manifest.json",
    )
    parser.add_argument(
        "--providers",
        nargs="*",
        default=None,
        help="Provider names to benchmark (default: all discovered)",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point — parse args and run async benchmarks."""
    args = _parse_args()
    asyncio.run(_main(args.wav_dir, args.providers))


if __name__ == "__main__":
    main()
