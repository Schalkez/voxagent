# Getting Started

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
