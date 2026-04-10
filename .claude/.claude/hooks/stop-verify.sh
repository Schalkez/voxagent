#!/usr/bin/env bash
set -euo pipefail

# Stop hook: Smart test verification
# Only runs when significant Python code changed in core/providers/skills
# Non-blocking — test failures are warnings, not blocks

cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0

# Check if git is available
git rev-parse --is-inside-work-tree &>/dev/null || exit 0

# Find changed Python files in critical directories
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null || true)
[ -z "$CHANGED_FILES" ] && CHANGED_FILES=$(git diff --name-only 2>/dev/null || true)
[ -z "$CHANGED_FILES" ] && exit 0

# Filter to meaningful Python code changes
CRITICAL_FILES=""
while IFS= read -r file; do
  case "$file" in
    */core/*.py|*/providers/*.py|*/skills/*.py)
      CRITICAL_FILES="$CRITICAL_FILES $file"
      ;;
  esac
done <<< "$CHANGED_FILES"

# No critical files changed, skip tests
[ -z "$CRITICAL_FILES" ] && exit 0

# Check if pytest is available
command -v python &>/dev/null || exit 0

# Determine which test files to run using glob-based discovery
TEST_ARGS=""
AGENT_DIR="$CLAUDE_PROJECT_DIR/voxagent/agent"
TESTS_DIR="$AGENT_DIR/tests"

[ -d "$TESTS_DIR" ] || exit 0

for file in $CRITICAL_FILES; do
  BASENAME=$(basename "$file" .py)
  case "$file" in
    */core/*)
      # Direct match: core/memory.py -> test_memory.py
      DIRECT="$TESTS_DIR/test_${BASENAME}.py"
      [ -f "$DIRECT" ] && TEST_ARGS="$TEST_ARGS $DIRECT"
      # Glob match: core/memory.py -> any test file containing "memory" in name
      for match in "$TESTS_DIR"/test_*"${BASENAME}"*.py; do
        [ -f "$match" ] && TEST_ARGS="$TEST_ARGS $match"
      done
      ;;
    */providers/*)
      # Direct match first
      DIRECT="$TESTS_DIR/test_providers.py"
      [ -f "$DIRECT" ] && TEST_ARGS="$TEST_ARGS $DIRECT"
      # Also match provider-specific test files (e.g., test_llm_providers.py)
      for match in "$TESTS_DIR"/test_*provider*.py; do
        [ -f "$match" ] && TEST_ARGS="$TEST_ARGS $match"
      done
      # Match by specific provider name
      for match in "$TESTS_DIR"/test_*"${BASENAME}"*.py; do
        [ -f "$match" ] && TEST_ARGS="$TEST_ARGS $match"
      done
      ;;
    */skills/*)
      # Direct match first
      DIRECT="$TESTS_DIR/test_skills.py"
      [ -f "$DIRECT" ] && TEST_ARGS="$TEST_ARGS $DIRECT"
      # Also match skill-specific test files (e.g., test_spotify_skill.py)
      for match in "$TESTS_DIR"/test_*skill*.py; do
        [ -f "$match" ] && TEST_ARGS="$TEST_ARGS $match"
      done
      # Match by specific skill name
      for match in "$TESTS_DIR"/test_*"${BASENAME}"*.py; do
        [ -f "$match" ] && TEST_ARGS="$TEST_ARGS $match"
      done
      ;;
  esac
done

# Deduplicate test files
TEST_ARGS=$(echo "$TEST_ARGS" | tr ' ' '\n' | sort -u | tr '\n' ' ')
[ -z "$TEST_ARGS" ] && exit 0

# Run targeted tests
cd "$AGENT_DIR"
TEST_OUTPUT=$(python -m pytest $TEST_ARGS -x --tb=short -q 2>&1 || true)

# Report results
if echo "$TEST_OUTPUT" | grep -q "FAILED\|ERROR"; then
  CONTEXT="Test failures detected after code changes:
$TEST_OUTPUT

Changed files: $CRITICAL_FILES"

  if command -v jq &>/dev/null; then
    jq -n --arg ctx "$CONTEXT" '{
      hookSpecificOutput: {
        hookEventName: "Stop",
        additionalContext: $ctx
      }
    }'
  else
    echo "$CONTEXT"
  fi
fi

exit 0
