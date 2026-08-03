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

### 2. Check for Existing Lock

```bash
# For firmware work
cat claude/locks/inav.lock 2>/dev/null && echo "LOCKED - STOP" || echo "Available"

# For configurator work
cat claude/locks/inav-configurator.lock 2>/dev/null && echo "LOCKED - STOP" || echo "Available"
```

**If locked:** STOP. Report to manager that the repo is locked. Do not proceed.

You may be able to use inav2/ as your working directory after checking and potentially creating the lock file claude/locks/inav2.lock


### 3. Acquire the Lock

```bash
# For firmware
cat > claude/locks/inav.lock << EOF
LOCKED_BY: Developer
TASK: [task-name-from-assignment]
LOCKED_AT: $(date '+%Y-%m-%d %H:%M')
BRANCH: [branch-name]
SESSION_ID: $CLAUDE_CODE_SESSION_ID
EOF

use inav.lock for the inav/ directory, inav2.lock for the inav2/ directory, or inav3.lock for the inav3/ directory

# For configurator
cat > claude/locks/inav-configurator.lock << EOF
LOCKED_BY: Developer
TASK: [task-name-from-assignment]
LOCKED_AT: $(date '+%Y-%m-%d %H:%M')
BRANCH: [branch-name]
SESSION_ID: $CLAUDE_CODE_SESSION_ID
EOF
```



### 4. Verify Clean Working Directory

```bash
# For firmware
cd inav && git status --porcelain

# For configurator
cd inav-configurator && git status --porcelain
```

**If output is not empty:** STOP. There are uncommitted changes. Either:
- Commit them if they belong to a previous task
- Stash them: `git stash`
- Or report to manager for guidance

### 5. Check Out the Correct Branch

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

### 6. Work in the Project Directory

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

### 7. Confirm Ready

Verify:
```bash
# Show lock contents
cat claude/locks/*.lock 2>/dev/null

# Show current branch
git branch --show-current

# Confirm clean
git status --porcelain
```

### 8. Write a Failing Test First (test-engineer agent)

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
# 1. Check lock
cat claude/locks/inav-configurator.lock 2>/dev/null || echo "Available"

# 2. Check clean
cd inav-configurator
git status --porcelain

# 3. Checkout branch (existing)
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

# 6. Ready to work!
```

## When Task is Complete

Remember to release the lock:
```bash
rm claude/locks/inav.lock
# or
rm claude/locks/inav-configurator.lock
```

Include in your completion report: "Released <repo>.lock"

---

## For Managers: Creating a New Project

When creating a new project to assign to a developer:

### 1. Create Project Directory

```bash
mkdir -p claude/projects/active/<project-name>
```

### 2. Create Project Files

- `summary.md` - Project overview, objectives, approach (use template from `claude/projects/README.md`)
- `todo.md` - Task breakdown (use template from `claude/projects/README.md`)
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
