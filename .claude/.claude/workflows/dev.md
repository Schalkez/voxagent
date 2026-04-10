---
description: how to run the development environment for VoxAgent
---

// turbo-all

1. Navigate to the project root
2. Create and activate virtual environment (if not exists):
```bash
python -m venv .venv && .venv/Scripts/activate
```
3. Install dependencies:
```bash
pip install -e ".[dev]"
```
4. Run VoxAgent in development mode:
```bash
python -m core.app --debug
```
