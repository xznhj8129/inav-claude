#!/bin/bash

# Claude Workspace Installation Script
# Usage: ./install.sh [fresh|continue]

set -e

CLAUDE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLED_MARKER="$CLAUDE_DIR/.installed"
cd "$CLAUDE_DIR"

echo "=================================="
echo "Claude Workspace Installation"
echo "=================================="
echo ""

# Detect whether this is a fresh clone or a working installation.
# Uses three independent signals to avoid false positives either way.
detect_install_state() {
    local signals=0

    # Signal 1: .installed marker exists
    [ -f "$INSTALLED_MARKER" ] && signals=$((signals + 1))

    # Signal 2: INDEX.md has local modifications (someone has been working)
    local repo_root
    repo_root="$(cd "$CLAUDE_DIR/.." && pwd)"
    git -C "$repo_root" diff --quiet -- claude/projects/INDEX.md 2>/dev/null
    [ $? -eq 1 ] && signals=$((signals + 1))

    # Signal 3: user has created their own emails (any file in any role's sent/)
    local user_emails=0
    for role in manager developer release-manager security-analyst; do
        local count
        count=$(find "$role/email/sent" -type f 2>/dev/null | wc -l)
        user_emails=$((user_emails + count))
    done
    [ "$user_emails" -gt 0 ] && signals=$((signals + 1))

    # 0 signals = definitely first time (fresh clone, untouched)
    # 1 signal  = ambiguous, ask the user
    # 2-3       = working installation, protect it
    echo "$signals"
}

# Function to stamp workspace as installed
mark_installed() {
    echo "installed=$(date -Iseconds)" > "$INSTALLED_MARKER"
}

# Function to create directory structure
create_directories() {
    echo "Creating directory structure..."

    # Project directories
    mkdir -p projects/active
    mkdir -p projects/backburner
    mkdir -p projects/completed

    # Role directories with email
    for role in manager developer release-manager security-analyst; do
        mkdir -p "$role/email/inbox"
        mkdir -p "$role/email/sent"
        mkdir -p "$role/email/inbox-archive"
    done

    # Developer workspace
    mkdir -p developer/workspace

    # Locks directory
    mkdir -p locks

    echo "✓ Directories created"
}

# Function to clear active content
clear_active_content() {
    echo "Clearing active content..."

    # Clear active/backburner projects (keep completed for reference)
    rm -rf projects/active/* 2>/dev/null || true
    rm -rf projects/backburner/* 2>/dev/null || true

    # Clear all email directories
    for role in manager developer release-manager security-analyst; do
        rm -rf "$role/email/inbox/"* 2>/dev/null || true
        rm -rf "$role/email/sent/"* 2>/dev/null || true
        rm -rf "$role/email/inbox-archive/"* 2>/dev/null || true
    done

    # Clear developer workspace
    rm -rf developer/workspace/* 2>/dev/null || true

    # Clear locks
    rm -f locks/*.lock 2>/dev/null || true

    # Reset projects INDEX.md to empty template
    cat > projects/INDEX.md << 'INDEXEOF'
# Active Projects Index

This file tracks **active** projects only (TODO, IN PROGRESS, BACKBURNER, BLOCKED).

**Last Updated:** $(date +%Y-%m-%d)
**Active:** 0 | **Backburner:** 0 | **Blocked:** 0

> **Completed projects:** See [completed/INDEX.md](completed/INDEX.md)
> **Blocked projects:** See `blocked/` directory
>
> **When completing a project:**
> 1. Move directory from `active/` to `completed/`
> 2. Remove entry from this file
> 3. Add entry to `completed/INDEX.md`
>
> **When blocking a project:**
> 1. Move directory from `active/` to `blocked/`
> 2. Update entry in this file with 🚫 BLOCKED status
> 3. Note what is blocking progress

---

## Status Definitions

| Status | Description |
|--------|-------------|
| 📋 **TODO** | Project defined but work not started |
| 🚧 **IN PROGRESS** | Actively being worked on |
| 🚫 **BLOCKED** | Waiting on external dependency (user reproduction, hardware, etc.) |
| ⏸️ **BACKBURNER** | Paused, will resume later (internal decision) |
| ❌ **CANCELLED** | Abandoned, not pursuing |

| Indicator | Meaning |
|-----------|---------|
| ✉️ **Assigned** | Developer has been notified via email |
| 📝 **Planned** | Project created but developer not yet notified |

---

## Active Projects

_No active projects. Use `/start-task` to create one._
INDEXEOF

    # Fix the date placeholder (heredoc can't expand inline with single quotes)
    sed -i "s/\$(date +%Y-%m-%d)/$(date +%Y-%m-%d)/" projects/INDEX.md

    echo "✓ Active content cleared"
    echo "✓ Projects INDEX.md reset"
}

# Function to list available roles, skills, and agents
show_capabilities() {
    REPO_ROOT="$(cd "$CLAUDE_DIR/.." && pwd)"

    echo ""
    echo "=================================="
    echo "Available Roles, Skills, and Agents"
    echo "=================================="

    echo ""
    echo "ROLES (tell Claude which role to take):"
    for dir in "$CLAUDE_DIR"/*/README.md; do
        role="$(basename "$(dirname "$dir")")"
        case "$role" in
            manager)          echo "  - Manager — Project planning, task assignment, progress tracking" ;;
            developer)        echo "  - Developer — Code implementation, bug fixes, testing" ;;
            release-manager)  echo "  - Release Manager — Release artifacts, builds, uploads" ;;
            security-analyst) echo "  - Security Analyst — Security review, crypto analysis, threat modeling" ;;
        esac
    done

    echo ""
    echo "SKILLS (invoke with /skill-name):"
    for skill_dir in "$REPO_ROOT"/.claude/skills/*/; do
        skill="$(basename "$skill_dir")"
        [ -f "$skill_dir/SKILL.md" ] && echo "  - /$skill"
    done

    echo ""
    echo "AGENTS (launched automatically by Claude as needed):"
    for agent_file in "$REPO_ROOT"/.claude/agents/*.md; do
        agent="$(basename "$agent_file" .md)"
        [ "$agent" = "CLAUDE" ] && continue
        echo "  - $agent"
    done

    echo ""
    echo "WORKFLOW:"
    echo "  1. User tells Claude which role to take (manager or developer)"
    echo "  2. Manager creates tasks and sends them to developer via internal email"
    echo "  3. Developer picks up assignments, implements changes, reports back"
    echo "  4. Manager reviews, updates tracking, assigns next task"
    echo "  The permissions-manager agent controls which commands run"
    echo "  automatically vs. which require user approval."
    echo ""
    echo "  Ask Claude any questions about this workflow or how roles interact."
}

# Function to show status
show_status() {
    echo ""
    echo "Current Status:"
    echo "---------------"

    active_count=$(find projects/active -maxdepth 1 -type d 2>/dev/null | wc -l)
    active_count=$((active_count - 1))  # Subtract 1 for the directory itself

    completed_count=$(find projects/completed -maxdepth 1 -type d 2>/dev/null | wc -l)
    completed_count=$((completed_count - 1))

    echo "Active projects: $active_count"
    echo "Completed projects: $completed_count"
    echo ""
}

# Main logic
MODE="${1:-}"
INSTALL_STATE=$(detect_install_state)

if [ "$INSTALL_STATE" -eq 0 ]; then
    # ── Definitely first time: fresh clone, untouched ──
    echo "First-time setup detected (fresh clone from GitHub)."
    echo "Clearing previous owner's projects and emails..."
    MODE="${MODE:-fresh}"

elif [ "$INSTALL_STATE" -eq 1 ]; then
    # ── Ambiguous: partially set up, ask the user ──
    if [ -z "$MODE" ]; then
        echo "This workspace may have been partially set up."
        echo ""
        echo "Options:"
        echo "  fresh    - Clear all projects/emails and start clean"
        echo "  continue - Keep everything as-is"
        echo ""
        read -p "Choose mode [fresh/continue]: " MODE
    fi

else
    # ── 2-3 signals: working installation, protect it ──
    if [ -z "$MODE" ]; then
        MODE="continue"
    fi

    if [ "$MODE" = "fresh" ]; then
        active_count=$(find projects/active -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)
        echo ""
        echo "WARNING: This is an active workspace with your own data."
        if [ "$active_count" -gt 0 ]; then
            echo "You have $active_count active project(s) that will be deleted:"
            for d in projects/active/*/; do
                [ -d "$d" ] && echo "  - $(basename "$d")"
            done
        fi
        echo ""
        read -p "Type 'yes' to confirm wiping all projects and emails: " CONFIRM
        if [ "$CONFIRM" != "yes" ]; then
            echo "Aborted. No changes made."
            exit 0
        fi
    fi
fi

case "$MODE" in
    fresh)
        echo ""
        echo "Setting up fresh workspace..."
        create_directories
        clear_active_content
        mark_installed
        echo ""
        echo "✓ Fresh workspace ready!"
        show_capabilities
        ;;
    continue)
        echo ""
        echo "Continuing with existing data..."
        create_directories
        mark_installed
        echo ""
        echo "✓ Workspace verified!"
        show_status
        show_capabilities
        ;;
    *)
        echo "Unknown mode: $MODE"
        echo "Usage: ./install.sh [fresh|continue]"
        exit 1
        ;;
esac

echo ""
echo "Optional: vector memory system (passive context injection between sessions)"
echo "  pip install chromadb"
echo "  (Without it, the stop hook runs but memory injection is silently skipped)"
echo ""
echo "For help, see INSTALL.md"
