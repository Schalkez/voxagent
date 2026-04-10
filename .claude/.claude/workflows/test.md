---
description: how to run tests for VoxAgent
---

// turbo-all

1. Run all tests:
```bash
python -m pytest tests/ -v
```
2. Run with coverage:
```bash
python -m pytest tests/ --cov=core --cov=providers --cov=skills --cov-report=term-missing
```
3. Run specific module tests:
```bash
python -m pytest tests/test_brain.py -v
```
4. Run benchmarks:
```bash
python -m pytest tests/benchmarks/ -v --benchmark-only
```
