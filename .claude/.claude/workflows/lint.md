---
description: how to lint and format VoxAgent code
---

// turbo-all

1. Format code with ruff:
```bash
ruff format .
```
2. Lint with ruff:
```bash
ruff check . --fix
```
3. Type check with mypy:
```bash
mypy core/ providers/ skills/ --ignore-missing-imports
```
