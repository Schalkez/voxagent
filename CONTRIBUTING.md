# Contributing to VoxAgent

Welcome! We appreciate your interest in contributing to VoxAgent. This document outlines the process for contributing to the project.

## Development Environment Setup

1. **Python Setup (v3.12+)**:
   We use `uv` and standard `pyproject.toml` for Python dependency management.
   ```bash
   cd agent
   pip install -e ".[dev,audio,stt]"
   ```

2. **Frontend Setup (Node v20+, Next.js 16)**:
   We use `pnpm` for frontend dependency management.
   ```bash
   cd dashboard
   pnpm install
   ```

## Code Quality Standards

VoxAgent mandates strict quality gates for backend code:

1. **Linter**: We use `ruff check` configured in `pyproject.toml`. All PRs must pass `ruff` with zero warnings.
2. **Types**: We enforce Strict Mode in `mypy`.
3. **Security**: All PRs must pass the `bandit` security audit (`bandit -c pyproject.toml -r agent/core`).
4. **Docs Coverage**: We strictly require 80%+ docstring coverage via `interrogate` (`interrogate -c pyproject.toml`).
5. **Dead Code**: We reject unused code via `vulture`.

## Commit Conventional Format

We loosely follow Conventional Commits:
- `feat:` for new features
- `fix:` for bug resolution
- `refactor:` for code restructuring without behavioral change
- `docs:` for documentation updates
- `test:` for test-suite updates

## Submitting Pull Requests

1. **Tests First**: Write unit tests for new features (`test_*.py`). Execute `pytest tests/ --cov` and ensure it doesn't depress our >55% strict coverage gating.
2. **Open PR against `main`**: Outline what bug or CR/WR item you are fixing.
3. **CI Pipeline**: Ensure GitHub Actions turns green!
