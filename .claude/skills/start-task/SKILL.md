---
description: Start task or begin project with lock acquisition and branch setup
triggers:
  - start task
  - begin task
  - start project
  - begin project
  - new task
---

# Start Task Skill

Use this skill when beginning any assigned task that involves modifying code.

## 🚨 Read Critical Guidelines First

**Before starting, read:** `claude/developer/guides/CRITICAL-BEFORE-CODE.md`

This checklist covers:
- Lock file verification and acquisition
- Branch creation best practices
- Agent usage requirements (never use direct commands)
- Using inav-architecture before searching

**Read it now using the Read tool, then proceed with the steps below.**

---

## Pre-Work Checklist

Before writing any code, complete ALL of these steps in order:

### 1. Identify the Repository

Determine which repo(s) your task requires:
- `inav/` - Firmware (C code)
- `inav-configurator/` - Configurator (JavaScript/Electron)

### 2. Acquire the Lock

**Use `claude/locks/lock_manager.py` — never check or write lock files by
hand.** It checks for an existing lock, verifies the checkout is actually
clean (so you never inherit uncommitted changes from a previous task), and
acquires the lock in one step:

```bash
# For firmware — tries inav/, inav2/, inav3/ in order
REPO=$(python3 claude/locks/lock_manager.py acquire --task <task-name> --branch <branch-name> --type firmware)

# For configurator
REPO=$(python3 claude/locks/lock_manager.py acquire --task <task-name> --branch <branch-name> --type configurator)
```

`$REPO` is the checkout name to `cd` into (e.g. `inav2`) — use it for every
step below.

**If it exits non-zero:** every candidate is either locked by another
session or has an unexpectedly dirty working tree. STOP. Report to the
manager. Do not force an acquisition, hand-write a lock file, or `git
stash`/discard whatever is sitting in a dirty candidate — see
`claude/locks/README.md` for why (a dirty-but-unlocked checkout may be
someone else's unfinished, uncommitted work).

### 3. Check Out the Correct Branch

Check if a branch is specified in the task assignment.

**If branch exists:**
```bash
git checkout <branch-name>
git pull origin <branch-name> 2>/dev/null || true  # Pull if remote exists
```

**If branch doesn't exist - CREATE FROM CORRECT BASE:**

⚠️ **CRITICAL:** You MUST specify the base branch when creating a new branch.

**Use the script — it's the single authority for base-branch selection:**

```bash
claude/developer/scripts/git/new-branch.sh <repo> <bugfix|feature|breaking> <new-branch-name>
```

See `.claude/skills/git-workflow/SKILL.md` ("Creating Branches") for the full decision
table (including the current temporary `inav/` override) and the manual fallback.

**❌ NEVER use `git checkout -b <branch-name>` without specifying base branch** - this creates the branch from your current HEAD, which may include unrelated changes.

**Branch naming conventions:**
- **PrivacyLRS:** No slashes (e.g., `fix-counter-sync`, `encryption-tests`)
- **INAV:** Kebab-case (e.g., `fix-telemetry-bug`, `feature-battery-limit`)

### 4. Work in the Project Directory

Task files go in the project's own directory, not a separate workspace:

```bash
P=claude/projects/active/<project-name>
mkdir -p $P/{notes,tests}     # add pr/ scripts/ artifacts/ as needed
```

| Subdir | Holds |
|--------|-------|
| `notes/` | devlogs, design decisions, research |
| `pr/` | PR bodies, specs |
| `tests/` | test scripts |
| `scripts/` | project-specific tooling |
| `artifacts/` | diffs, binaries, captured data |

**Every file you add must be listed in the project's `MANIFEST.md`** — `project_ops.py audit` fails otherwise. The manifest also records branches, PR numbers, mail paths and memory slugs, so the project stays findable in one place.

`claude/developer/workspace/` is scratch only. Anything left there with no owning project is reported as an orphan by the audit.

### 5. Confirm Ready

Verify:
```bash
# Show lock status for all checkouts
python3 claude/locks/lock_manager.py status

# Show current branch
git branch --show-current
```

### 6. Write a Failing Test First (test-engineer agent)

**Before writing any implementation code**, have the test-engineer agent write
a test that reproduces the issue and currently fails:

```
Agent: test-engineer
Prompt: "Write a test that reproduces this issue: [paste issue description from
         the task assignment]. The test should FAIL now and PASS after the fix."
```

**Why first:** A failing test proves you've reproduced the actual bug — not just
a related symptom. A passing test after the fix proves you solved it.

**If the user explicitly asks to skip this step**, you may proceed — they are
the boss. But note it in your workspace notes and completion report.

For pure new features with no failing behavior to reproduce, ask the
test-engineer to write acceptance tests instead (tests that define what
"done" looks like before you build it).

## Now Begin Work

Only after completing ALL steps above (including the failing test) should you
begin implementing the task.

## Example: Starting a Configurator Task

```bash
# 1. Acquire lock
REPO=$(python3 claude/locks/lock_manager.py acquire --task fix-decompiler-condition-numbers --branch transpiler_clean_copy --type configurator)

# 2. Checkout branch (existing)
cd "$REPO"
git checkout transpiler_clean_copy

# 4. Acquire lock
cat > claude/locks/inav-configurator.lock << EOF
LOCKED_BY: Developer
TASK: fix-decompiler-condition-numbers
LOCKED_AT: $(date '+%Y-%m-%d %H:%M')
BRANCH: transpiler_clean_copy
EOF

# 5. Create project subdirs
mkdir -p claude/projects/active/fix-decompiler-condition-numbers/{notes,tests}

# 4. Ready to work!
```

## When Task is Complete

Remember to release the lock:
```bash
python3 claude/locks/lock_manager.py release <inav|inav2|inav3|inav-configurator>
```

It reports any uncommitted/untracked files left in the checkout — clean
those up (e.g. leftover `build_*` directories) so the next task can pick it
up automatically.

Include in your completion report: "Released <repo>.lock"

---

## For Managers: Creating a New Project

When creating a new project to assign to a developer:

### 1. Create Project Directory

```bash
mkdir -p claude/projects/active/<project-name>
```

### 2. Create Project Files

- `summary.md` - Project overview, objectives, approach (use template from `claude/manager/projects/README.md`)
- `todo.md` - Task breakdown (use template from `claude/manager/projects/README.md`)
- `MANIFEST.md` - **Mandatory.** Index of everything the project owns: files, git branches, upstream PRs, mail paths, memory slugs, external references

### 3. Add to INDEX.md

Add concise entry (10-15 lines max):
- Status, type, priority, dates
- One-sentence summary
- Directory: `active/<project-name>/`
- Assignment email path

### 4. Send Assignment Email

Create in `claude/manager/email/sent/` and copy to `claude/developer/email/inbox/`

---

## Related Skills

- **finish-task** - Complete tasks and release locks
- **git-workflow** - Create branches and manage git state
- **create-pr** - Create pull request after completing task
