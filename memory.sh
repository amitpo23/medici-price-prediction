#!/bin/bash
# memory.sh — Aggregate project context for Claude Code session
# Usage: source memory.sh (or ./memory.sh to print context)

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

CONTEXT=""

# 1. Session primer
if [ -f primer.md ]; then
  CONTEXT+="$(cat primer.md)"$'\n\n'
fi

# 2. Recent git history
CONTEXT+="## Recent Git History"$'\n'
CONTEXT+="$(git log --oneline -10 2>/dev/null)"$'\n\n'

# 3. Auto commit log
if [ -f .claude-memory.md ]; then
  CONTEXT+="$(cat .claude-memory.md)"$'\n\n'
fi

# 4. Modified files (unstaged)
MODIFIED=$(git diff --name-only 2>/dev/null | head -10)
if [ -n "$MODIFIED" ]; then
  CONTEXT+="## Currently Modified Files"$'\n'
  CONTEXT+="$MODIFIED"$'\n\n'
fi

# 5. Lessons
if [ -f tasks/lessons.md ]; then
  CONTEXT+="$(cat tasks/lessons.md)"$'\n\n'
fi

echo "$CONTEXT"
