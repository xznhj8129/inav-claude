# Projects Directory

Central project registry for tracking all INAV-related projects.

## Quick Links

| Link | Description |
|------|-------------|
| **[INDEX.md](INDEX.md)** | Active projects (TODO, IN PROGRESS, BACKBURNER, BLOCKED) |
| **[completed/INDEX.md](completed/INDEX.md)** | Completed and cancelled projects |

## Directory Structure

```
claude/projects/             # Local per-user data (gitignored — never committed)
├── INDEX.md                 # Active projects index (keep concise!)
│
├── active/                  # Projects being worked on
│   └── <project-name>/
│       ├── MANIFEST.md      # Index of EVERYTHING (mandatory)
│       ├── summary.md       # Full details
│       ├── todo.md          # Task tracking
│       ├── notes/           # devlogs, design decisions, research
│       ├── pr/              # PR bodies, specs
│       ├── tests/           # project test scripts
│       ├── scripts/         # project-specific tooling
│       └── artifacts/       # diffs, binaries, captured data
│
├── blocked/                 # Blocked on external dependency
│   └── <project-name>/
│
├── backburner/              # Paused projects (will resume)
│   └── <project-name>/
│
└── completed/               # Finished projects
    ├── INDEX.md             # Completed projects index
    └── <project-name>/      # Archived project directories
```

> **Lifecycle tooling is framework, not data:** `project_ops.py`,
> `project_manager.py`, and `compact_index.py` live in
> `claude/manager/scripts/` (tracked). Only the projects *data* above is
> local and gitignored.

## Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│  CREATE                                                     │
│  ├─ Create active/<project-name>/ with summary.md, todo.md  │
│  └─ Add entry to INDEX.md                                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  WORK                                                       │
│  ├─ Update todo.md as tasks complete                        │
│  └─ Status in INDEX.md: 📋 TODO → 🚧 IN PROGRESS            │
└─────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────────┐
│  PAUSE           │ │  BLOCK       │ │  COMPLETE            │
│  ├─ mv to        │ │  ├─ mv to    │ │  ├─ mv to completed/ │
│  │  backburner/  │ │  │  blocked/ │ │  ├─ Remove from      │
│  └─ Status:      │ │  └─ Status:  │ │  │  INDEX.md         │
│     ⏸️ BACKBURNER │ │     🚫 BLOCKED│ │  └─ Add to          │
└──────────────────┘ └──────────────┘ │     completed/       │
       │                    │          │     INDEX.md         │
       │                    │          └──────────────────────┘
       ▼                    ▼
┌──────────────────┐ ┌──────────────┐
│  RESUME          │ │  UNBLOCK     │
│  ├─ mv to active/│ │  ├─ mv to    │
│  └─ Status:      │ │  │  active/  │
│     🚧 IN PROGRESS│ │  └─ Status:  │
└──────────────────┘ │     🚧 IN     │
                     │     PROGRESS  │
                     └──────────────┘
```

## Project Lifecycle Tool — project_ops.py

**⚠️ ALWAYS use `project_ops.py` for project lifecycle transitions.** Do NOT manually move directories and edit INDEX files — use the tool to keep everything in sync atomically.

```bash
# Complete a project (moves dir, removes from INDEX.md, adds to completed/INDEX.md)
python3 claude/manager/scripts/project_ops.py complete <project-name>

# Cancel a project
python3 claude/manager/scripts/project_ops.py cancel <project-name>

# Block a project (moves active/ → blocked/)
python3 claude/manager/scripts/project_ops.py block <project-name>

# Backburner a project (moves active/ → backburner/)
python3 claude/manager/scripts/project_ops.py backburner <project-name>

# Resume a blocked or backburner project (moves back to active/)
python3 claude/manager/scripts/project_ops.py resume <project-name>

# Audit for inconsistencies
python3 claude/manager/scripts/project_ops.py audit

# Audit and auto-fix simple issues
python3 claude/manager/scripts/project_ops.py audit --fix
```

## Skills

Use these skills for common operations:

| Skill | Description |
|-------|-------------|
| `/start-task` | Create new project with directory and assignment email |
| `/finish-task` | Mark project complete, move to completed/, update indexes |

## Key Rules

### INDEX.md is Navigation Only

Each entry should be 10-15 lines max:
- Status, type, priority, dates
- One-sentence summary
- Directory location
- Links (issue, PR, email)

**Details go in the project's summary.md, not INDEX.md.**

### Before Condensing INDEX Entries

1. READ the project's summary.md
2. VERIFY all details exist there
3. If missing, ADD to summary.md first
4. THEN condense the INDEX entry

### Single Source of Truth

- Project details → `<project-name>/summary.md`
- Task tracking → `<project-name>/todo.md`
- **Everything the project owns → `<project-name>/MANIFEST.md`**
- INDEX.md → Navigation and status only

### MANIFEST.md is mandatory

Every project directory contains a `MANIFEST.md` indexing **everything** belonging to that project:

- every file in the directory, with its purpose
- git branches, by repo, with tip commits and merged/outstanding state
- upstream PR numbers and status
- mail paths in the role mailboxes (`claude/*/email/` is gitignored — those files are local-only)
- memory slugs under `~/.claude/projects/<slug>/memory/`, which the harness loads and which cannot live in the repo
- external references — anything outside the repo the project depends on

`project_ops.py audit` enforces it: a file not listed in its manifest is an error, and a directory under `claude/developer/workspace/` with no owning project is reported as an orphan. That pair is what keeps material from going missing.

**Project material does not belong in `claude/developer/workspace/`** — that is scratch only.

---

## Detailed Reference

### Creating a New Project

1. **Create project directory:**
   ```bash
   mkdir -p claude/projects/active/<project-name>
   ```

2. **Create summary.md** using template below

3. **Create todo.md** using template below

4. **Add to INDEX.md** (concise entry only)

5. **Send assignment email** (if assigning to developer)

### INDEX.md Entry Format

```markdown
### 📋 project-name

**Status:** TODO | **Type:** Bug Fix | **Priority:** MEDIUM
**Created:** 2025-12-29 | **Assignee:** Developer

One-sentence summary of what this project accomplishes.

**Directory:** `active/project-name/`
**Issue:** [#12345](url) | **Assignment:** `manager/email/sent/...`

---
```

**⚠️ Never put anything else on the `### <emoji> project-name` heading
line** — no trailing notes like "— READY TO COMPLETE" or "(needs review)".
`project_ops.py` parses that exact line to find/remove/update entries; a
trailing annotation caused real INDEX.md corruption (March and July 2026 —
see the `fix-project-ops-script` project) by breaking the match while the
tool reported success. Put notes in the entry body instead (e.g. a
`**Note:**` line).

### summary.md Template

```markdown
# Project: <Name>

**Status:** 📋 TODO
**Priority:** MEDIUM
**Type:** Bug Fix | Feature | Refactor | Investigation
**Created:** YYYY-MM-DD
**Estimated Effort:** X-Y hours

## Overview

<What this project accomplishes in 2-3 sentences>

## Problem

<What issue this solves>

## Solution

<High-level approach>

## Implementation

<Technical details, phases, files to modify>

## Success Criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Related

- **Issue:** #XXXXX
- **PR:** #XXXXX (when created)
- **Assignment:** `path/to/email`
```

### todo.md Template

```markdown
# Todo: <Project Name>

## Phase 1: <Name>

- [ ] Task 1
- [ ] Task 2

## Phase 2: <Name>

- [ ] Task 3
- [ ] Task 4

## Completion

- [ ] Code compiles
- [ ] Tests pass
- [ ] PR created
- [ ] Completion report sent
```

### Completing a Project

**Use `project_ops.py` — it handles all steps atomically:**
```bash
python3 claude/manager/scripts/project_ops.py complete <project-name>
```

This automatically: moves the directory to completed/, removes the entry from INDEX.md, adds an entry to completed/INDEX.md, and updates all counts.

### Cancelling a Project

```bash
python3 claude/manager/scripts/project_ops.py cancel <project-name>
```

**When to cancel vs backburner:**
- **Cancel:** Requirements changed, no longer needed, blocked permanently, superseded
- **Backburner:** Still valuable, lower priority, waiting on external dependency

### Status Icons

| Icon | Status | Meaning |
|------|--------|---------|
| 📋 | TODO | Defined, not started |
| 🚧 | IN PROGRESS | Actively being worked on |
| ⏸️ | BACKBURNER | Paused, will resume |
| ✅ | COMPLETED | Finished and merged |
| ❌ | CANCELLED | Abandoned |

### Priority Levels

| Priority | When to Use |
|----------|-------------|
| CRITICAL | Blocking issue, fix immediately |
| HIGH | Important, work on soon |
| MEDIUM-HIGH | Should do, good to complete |
| MEDIUM | Normal priority |
| LOW | Nice to have |

### Naming Conventions

Use kebab-case with descriptive prefixes:

- `feature-<description>` - New functionality
- `fix-<description>` - Bug fixes
- `refactor-<description>` - Code restructuring
- `investigate-<description>` - Research/analysis
- `reproduce-<description>` - Bug reproduction

---

## Not To Be Confused With

| Directory | Purpose |
|-----------|---------|
| `claude/projects/` | Persistent project tracking (this directory) |
| `claude/developer/workspace/` | Temporary working files (gitignored) |
| `claude/developer/investigations/` | Research and analysis reports |
| `claude/developer/reports/` | Completed analysis documents |
