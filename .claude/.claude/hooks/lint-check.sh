#!/usr/bin/env bash
set -euo pipefail

# PostToolUse hook: Advisory lint check after Write/Edit
# Non-blocking — outputs warnings so Claude can self-correct

INPUT=$(cat)

# Extract file path from tool input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE_PATH" ] && exit 0

# Verify file exists
[ -f "$FILE_PATH" ] || exit 0

WARNINGS=""

case "$FILE_PATH" in
  *.py)
    # Python: ruff check (no --fix, just report)
    if command -v ruff &>/dev/null; then
      LINT_OUTPUT=$(ruff check "$FILE_PATH" 2>/dev/null || true)
      if [ -n "$LINT_OUTPUT" ]; then
        WARNINGS="Ruff warnings in $(basename "$FILE_PATH"):
$LINT_OUTPUT"
      fi
    fi
    ;;
  *.ts|*.tsx)
    # TypeScript: eslint on single file
    DASHBOARD_DIR="$CLAUDE_PROJECT_DIR/voxagent/dashboard"
    if [ -x "$DASHBOARD_DIR/node_modules/.bin/eslint" ]; then
      LINT_OUTPUT=$(cd "$DASHBOARD_DIR" && npx eslint "$FILE_PATH" 2>/dev/null || true)
      if [ -n "$LINT_OUTPUT" ]; then
        WARNINGS="ESLint warnings in $(basename "$FILE_PATH"):
$LINT_OUTPUT"
      fi
    fi
    ;;
  *)
    exit 0
    ;;
esac

# Output warnings as context for Claude
if [ -n "$WARNINGS" ]; then
  if command -v jq &>/dev/null; then
    jq -n --arg warnings "$WARNINGS" '{
      hookSpecificOutput: {
        hookEventName: "PostToolUse",
        additionalContext: $warnings
      }
    }'
  else
    echo "$WARNINGS"
  fi
fi

exit 0
