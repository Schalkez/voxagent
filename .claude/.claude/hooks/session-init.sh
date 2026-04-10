#!/usr/bin/env bash
set -euo pipefail

# SessionStart hook: Load git context for Claude
# Provides branch info, recent commits, and working tree status

cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0

# Verify we're in a git repo
git rev-parse --is-inside-work-tree &>/dev/null || exit 0

BRANCH=$(git branch --show-current 2>/dev/null || echo "detached")
COMMITS=$(git log --oneline -5 2>/dev/null || echo "no commits")
MODIFIED=$(git diff --name-only 2>/dev/null | wc -l | tr -d ' ')
STAGED=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')
STASH_COUNT=$(git stash list 2>/dev/null | wc -l | tr -d ' ')

# Check Python venv
VENV_STATUS="not activated"
if [ -d "voxagent/agent/.venv" ]; then
  VENV_STATUS="exists at voxagent/agent/.venv"
fi

# Check node_modules
NODE_STATUS="not installed"
if [ -d "voxagent/dashboard/node_modules" ]; then
  NODE_STATUS="installed"
fi

CONTEXT="Git: branch=$BRANCH | modified=$MODIFIED staged=$STAGED untracked=$UNTRACKED"
[ "$STASH_COUNT" -gt 0 ] && CONTEXT="$CONTEXT stash=$STASH_COUNT"
CONTEXT="$CONTEXT
Recent commits:
$COMMITS
Environment: python-venv=$VENV_STATUS | node_modules=$NODE_STATUS"

# Output as JSON for Claude Code
if command -v jq &>/dev/null; then
  jq -n --arg ctx "$CONTEXT" '{
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: $ctx
    }
  }'
else
  # Fallback: plain text context
  echo "$CONTEXT"
fi

exit 0
