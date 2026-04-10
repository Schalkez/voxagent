#!/usr/bin/env bash
set -euo pipefail

# PostToolUse hook: Auto-format Python files with ruff after Write/Edit
# Runs on single file only for speed (~50ms)

INPUT=$(cat)

# Extract file path from tool input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE_PATH" ] && exit 0

# Only process Python files
[[ "$FILE_PATH" != *.py ]] && exit 0

# Verify file exists
[ -f "$FILE_PATH" ] || exit 0

# Check ruff is available
command -v ruff &>/dev/null || exit 0

# Format the file
ruff format "$FILE_PATH" 2>/dev/null || true

# Auto-fix safe lint issues
ruff check --fix "$FILE_PATH" 2>/dev/null || true

exit 0
