---
description: Query and manage project status using the project manager tool
triggers:
  - check projects
  - project status
  - list projects
  - active projects
  - show projects
  - what projects
  - completed projects
  - find project
---

# Project Management Skill

Query and manage INAV project tracking using the project_manager.py tool.

## Project Manager Tool

Located at: `claude/manager/scripts/project_manager.py`

This Python script provides powerful project querying capabilities across INDEX.md and COMPLETED_PROJECTS.md.

## Quick Commands

### List Active Projects (TODO)

```bash
python3 claude/manager/scripts/project_manager.py list TODO
```

Shows all active TODO projects with priority, assignee, and creation date.

### List All Projects

```bash
python3 claude/manager/scripts/project_manager.py list
```

Shows all projects regardless of status.

### List by Status

```bash
# Completed projects
python3 claude/manager/scripts/project_manager.py list COMPLETE

# Backburner projects
python3 claude/manager/scripts/project_manager.py list BACKBURNER

# In progress
python3 claude/manager/scripts/project_manager.py list IN_PROGRESS

# Cancelled
python3 claude/manager/scripts/project_manager.py list CANCELLED
```

### Show Project Details

```bash
python3 claude/manager/scripts/project_manager.py show <name>
```

Example:
```bash
python3 claude/manager/scripts/project_manager.py show finding5
python3 claude/manager/scripts/project_manager.py show transpiler
```

Shows full details for a specific project including:
- Status, priority, assignee
- Creation and completion dates
- Location in filesystem
- Line numbers in INDEX.md

### View Statistics

```bash
python3 claude/manager/scripts/project_manager.py stats
```

Shows:
- Count by status (TODO, COMPLETE, etc.)
- Count by priority (HIGH, MEDIUM, etc.)
- Total projects
- Active vs completed breakdown

## Project File Locations

- **Active projects index:** `claude/projects/INDEX.md` (active/blocked/backburner only)
- **Completed projects archive:** `claude/projects/completed/INDEX.md`
- **Project directories:** `claude/projects/{active,blocked,backburner,completed}/{name}/`
- **Project manager tool:** `claude/manager/scripts/project_manager.py` (queries INDEX.md)
- **Lifecycle tool:** `claude/manager/scripts/project_ops.py` (moves dirs + updates indexes atomically)

## Project Directory Layout

Everything belonging to a project lives in its directory. Subdirectories are created only when the project has that kind of content.

```
claude/projects/<status>/<project-name>/
├── MANIFEST.md      # index of EVERYTHING, in-repo and external
├── summary.md       # status, scope, current state
├── todo.md
├── notes/           # devlogs, design decisions, research
├── pr/              # PR bodies, split specs
├── tests/           # project test scripts
├── scripts/         # project-specific tooling
└── artifacts/       # diffs, binaries, captured data
```

**`MANIFEST.md` is mandatory** and is the project's index of record. It lists every file in the directory plus the things a directory cannot hold: git branches, upstream PRs, mail paths, memory slugs, and external references. `project_ops.py audit` fails if a file is missing from its manifest, or if a working directory exists with no owning project.

Do **not** scatter project material into `claude/developer/workspace/` — that is scratch only, and anything left there is reported as an orphan.

## Status Definitions

| Status | Emoji | Meaning |
|--------|-------|---------|
| TODO | 📋 | Defined but not started |
| IN_PROGRESS | 🚧 | Actively being worked on |
| COMPLETE | ✅ | Finished and merged |
| BACKBURNER | ⏸️ | Paused, will resume later |
| CANCELLED | ❌ | Abandoned |

## Assignment Status

| Indicator | Meaning |
|-----------|---------|
| ✉️ Assigned | Developer notified via email |
| 📝 Planned | Created but not yet assigned |

## Usage Examples

### Finding a Specific Project

When you need to find a project but don't know the exact name:

```bash
# Search by partial name
python3 claude/manager/scripts/project_manager.py show chacha

# Will show: privacylrs-fix-finding5-chacha-benchmark
```

### Checking What's Active

```bash
# Quick view of what needs to be done
python3 claude/manager/scripts/project_manager.py list TODO
```

Output:
```
Status          Priority   Project                                            Created
====================================================================================================
📋 TODO         HIGH       fix-cli-align-mag-roll-invalid-name                2025-12-02
📋 TODO         CRITICAL   privacylrs-fix-finding1-stream-cipher-desync       2025-11-30
...
```

### Checking Recent Completions

```bash
# View all completed projects
python3 claude/manager/scripts/project_manager.py list COMPLETE
```

### Project Statistics

```bash
python3 claude/manager/scripts/project_manager.py stats
```

Output:
```
=== Project Statistics ===

By Status:
  CANCELLED           1 projects
  COMPLETE           37 projects
  TODO                8 projects

Total Projects: 46
Active Projects: 8
Completed: 38
```

## For Managers Only

### Completing a project

Use `project_ops.py` — it moves the directory, removes the INDEX.md entry, adds the completed/INDEX.md entry and updates counts, atomically:

```bash
python3 claude/manager/scripts/project_ops.py complete <project-name>
```

Then verify:

```bash
python3 claude/manager/scripts/project_ops.py audit
python3 claude/manager/scripts/project_manager.py stats
```

Update the **Last Updated** date in the INDEX.md header.

### Manual Index Queries (Fallback)

If project_manager.py is unavailable:

```bash
# View active projects section
grep -A 20 "^## Active Projects" claude/projects/INDEX.md

# Count by status
grep -c "^### 📋" claude/projects/INDEX.md  # TODO
grep -c "^### ✅" claude/projects/INDEX.md  # COMPLETE
grep -c "^### ⏸️" claude/projects/INDEX.md  # BACKBURNER
```

## Tool Benefits

✅ **Fast queries** - No need to search through 2000+ lines manually
✅ **Smart search** - Partial name matching
✅ **Statistics** - Instant project counts and breakdowns
✅ **Status filtering** - View only what you need
✅ **Detail view** - See everything about a specific project

## Troubleshooting

### Tool Not Found

```bash
# Verify tool exists
ls -lh claude/manager/scripts/project_manager.py

# Make executable if needed
chmod +x claude/manager/scripts/project_manager.py
```

### Syntax Errors

The tool requires Python 3.7+ for dataclasses:
```bash
python3 --version  # Should be 3.7 or higher
```

### No Matches Found

If searching for a project returns no results:
```bash
# List all projects to see exact names
python3 claude/manager/scripts/project_manager.py list
```

---

## Related Skills

- **email** - Read task assignments (tasks often reference projects)
- **communication** - Communicate about project status
