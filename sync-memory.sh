#!/usr/bin/env bash
# sync-memory.sh — Sync project memory between machines via Git
# Usage: ./sync-memory.sh [push|pull|full]
# - pull: fetch latest memory from remote (start of session)
# - push: commit & push memory to remote (end of session)
# - full: pull + push (default)
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1

MODE="${1:-full}"
HOSTNAME=$(hostname -s 2>/dev/null || echo "unknown")
NOW=$(date '+%Y-%m-%d %H:%M:%S')
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")

# Memory files to sync
MEMORY_FILES=(
    "primer.md"
    ".claude-memory.md"
    "docs/MEMORY_LOG.md"
    "tasks/lessons.md"
    ".session-log/"
    ".dev-logs/"
)

# ─── Colors ───
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}✅ $1${NC}"; }
log_warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# ─── Pull: fetch latest memory from remote ───
do_pull() {
    echo "📥 Pulling latest memory from remote..."

    # Stash local changes to memory files
    git stash push -m "sync-memory-temp" -- "${MEMORY_FILES[@]}" 2>/dev/null

    if git pull --rebase origin "$BRANCH" 2>/dev/null; then
        log_info "Pull successful"
    else
        log_warn "Pull failed — working offline"
    fi

    # Re-apply local changes
    git stash pop 2>/dev/null || true
}

# ─── Push: commit & push memory to remote ───
do_push() {
    echo "📤 Pushing memory to remote..."

    # Ensure session log directory exists
    mkdir -p .session-log

    # Stage only memory files that exist
    for file in "${MEMORY_FILES[@]}"; do
        if [ -e "$file" ]; then
            git add "$file" 2>/dev/null
        fi
    done

    # Check if there's anything to commit
    if git diff --cached --quiet 2>/dev/null; then
        log_info "Memory already up to date — nothing to push"
        return 0
    fi

    # Commit
    git commit -m "chore(memory): sync from $HOSTNAME at $NOW" 2>/dev/null
    if [ $? -eq 0 ]; then
        log_info "Memory committed"
    else
        log_warn "Nothing to commit"
        return 0
    fi

    # Push
    if git push origin "$BRANCH" 2>/dev/null; then
        log_info "Pushed to remote"
    else
        log_warn "Push failed — will sync later"
    fi
}

# ─── Status: show memory file state ───
show_status() {
    echo ""
    echo "📋 Memory Files Status:"
    echo "─────────────────────────"
    for file in "${MEMORY_FILES[@]}"; do
        if [ -e "$file" ]; then
            if [ -d "$file" ]; then
                count=$(find "$file" -type f 2>/dev/null | wc -l | tr -d ' ')
                mod=$(stat -c '%y' "$file" 2>/dev/null | cut -d'.' -f1 || stat -f '%Sm' "$file" 2>/dev/null || echo "?")
                echo "  📁 $file ($count files, last: $mod)"
            else
                mod=$(stat -c '%y' "$file" 2>/dev/null | cut -d'.' -f1 || stat -f '%Sm' "$file" 2>/dev/null || echo "?")
                lines=$(wc -l < "$file" 2>/dev/null | tr -d ' ')
                echo "  📄 $file (${lines} lines, last: $mod)"
            fi
        else
            echo "  ⬜ $file (missing)"
        fi
    done
    echo "─────────────────────────"
    echo "🖥  Machine: $HOSTNAME"
    echo "🌿 Branch: $BRANCH"
    echo "🕐 Time: $NOW"
    echo ""
}

# ─── Main ───
case "$MODE" in
    pull)
        do_pull
        show_status
        ;;
    push)
        do_push
        show_status
        ;;
    full)
        do_pull
        do_push
        show_status
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: ./sync-memory.sh [pull|push|full|status]"
        echo "  pull   — fetch latest memory (start of session)"
        echo "  push   — commit & push memory (end of session)"
        echo "  full   — pull then push (default)"
        echo "  status — show memory file state"
        exit 1
        ;;
esac
