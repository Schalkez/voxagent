#!/usr/bin/env bash
set -euo pipefail

# PostToolUse hook: Auto-format TypeScript/CSS files with Prettier after Write/Edit
# Uses --cache for speed (~50ms cached)

INPUT=$(cat)

# Extract file path from tool input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE_PATH" ] && exit 0

# Only process frontend files
case "$FILE_PATH" in
  *.ts|*.tsx|*.js|*.jsx|*.css) ;;
  *) exit 0 ;;
esac

# Verify file exists
[ -f "$FILE_PATH" ] || exit 0

# Find the dashboard directory (where package.json lives)
DASHBOARD_DIR="$CLAUDE_PROJECT_DIR/voxagent/dashboard"
[ -f "$DASHBOARD_DIR/package.json" ] || exit 0

# Use prettier directly if available, otherwise npx
if [ -x "$DASHBOARD_DIR/node_modules/.bin/prettier" ]; then
  "$DASHBOARD_DIR/node_modules/.bin/prettier" --write --cache "$FILE_PATH" 2>/dev/null || true
elif command -v npx &>/dev/null; then
  npx --prefix "$DASHBOARD_DIR" prettier --write --cache "$FILE_PATH" 2>/dev/null || true
fi

exit 0
