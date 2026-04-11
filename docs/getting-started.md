# Getting Started

## Key Features

VoxAgent includes production-grade features out of the box:

- **Streaming TTS** -- Sentence-level chunking with gapless playback. First audio plays within 1.5s.
- **Barge-In** -- Say "Hey Vox" to interrupt VoxAgent mid-speech. Audio fades out in 20ms with no clicks.
- **Provider Fallback Chains** -- If your primary LLM/TTS/STT fails, VoxAgent auto-switches to the next provider. Circuit breakers prevent wasted API calls.
- **Adaptive VAD** -- Voice Activity Detection adapts to ambient noise (fan, AC). Hysteresis prevents premature cutoffs during natural pauses.
- **Safety Hardening** -- Terminal AST validation, prompt injection detection, file path sandboxing, per-skill execution timeouts, API bearer token auth.
- **Structured Error Handling** -- Typed VoxError hierarchy with Vietnamese user-facing messages. Zero silent failures.

## Installation

```bash
pip install voxagent-agent
```

Or from source:

```bash
git clone https://github.com/voxagent/voxagent
cd voxagent
pip install -e ".[dev]"
```

## First Run

```bash
voxagent setup   # Interactive wizard
voxagent start   # Start listening — say "VoxAgent" to activate
```

## Profiles

VoxAgent ships with 4 built-in profiles:

| Profile | Best for | GPU needed |
|---------|----------|------------|
| `full_local` | Privacy, offline | Yes (8GB+ VRAM) |
| `cloud_free` | Quick start | No |
| `hybrid` | Best quality | Optional |
| `budget_cloud` | Low cost | No |

```bash
voxagent start --profile cloud_free
```

## Dashboard

The management dashboard runs at `http://localhost:8642`:

```bash
voxagent-api   # Start API server
```
