# Claude Workspace

This directory contains organizational structures, communication channels, and documentation for Claude Code when working on the INAV codebase.

## Your Role

**Which role are you taking on?**

### 🎯 Development Manager

**You coordinate, track, and assign work.**

📖 **Read your guide:** [`claude/manager/README.md`](manager/README.md)

**Quick actions:**
- Check inbox: `ls claude/manager/email/inbox/`
- View active projects: `cat claude/projects/INDEX.md`
- Assign tasks: Create in `manager/email/sent/`, copy to `developer/email/inbox/`

---

### 💻 Developer

**You implement code based on manager assignments.**

📖 **Read your guide:** [`claude/developer/README.md`](developer/README.md)

**Quick actions:**
- Check inbox: `ls claude/developer/email/inbox/`
- Build firmware: `cd inav && ./build.sh TARGETNAME`
- Build configurator: `cd inav-configurator && npm start`
- Report completion: Create in `developer/email/sent/`, copy to `manager/email/inbox/`

---

### 📦 Release Manager

**You handle tagging, building, and publishing releases.**

📖 **Read your guide:** [`claude/release-manager/README.md`](release-manager/README.md)

**Quick actions:**
- Check latest tags: `git tag --sort=-v:refname | head -5`
- List PRs since tag: `gh pr list --state merged --limit 50`
- Create draft release: `gh release create X.Y.Z --draft`
- Build firmware: `cd inav && mkdir build && cd build && cmake .. && make`
- Build configurator: `cd inav-configurator && npm run dist`

---

## 📊 Context Engineering Presentation

**Want to learn how this system works?** See [`claude/presentation/presentation-slides.md`](presentation/presentation-slides.md)

A 12-15 minute technical presentation explaining the context engineering techniques that make Claude Code consistently follow best practices:

- **5 Core Techniques:** Role separation, JIT documentation, specialized agents, reusable skills, enforcement hooks
- **Real Results:** 78 projects completed in 2 months with consistent workflow adherence
- **Context Efficiency:** ~1,500 lines loaded per task vs ~10-15k without system
- **Universal Workflow:** 12-step development process adaptable to any software project

**Files:**
- **Slides:** `claude/presentation/presentation-slides.md` (Marp format, dark theme)
- **Export:** See `claude/presentation/EXPORT-INSTRUCTIONS.md` for HTML/PDF/PPTX
- **Cheat Sheet:** `claude/presentation/PRESENTATION-CHEAT-SHEET.md`
- **All materials:** `claude/presentation/` directory

**Key Insight:** Context engineering turns Claude from a smart assistant into a reliable, professional development team member with consistent process adherence.

---

## Directory Structure

```
claude/
├── manager/              - Development manager files
│   ├── README.md        - Manager role guide ⭐ START HERE if you're the manager
│   └── email/           - Email communication
│       ├── inbox/       - Reports from developer
│       ├── inbox-archive/ - Archived reports
│       └── sent/        - Tasks sent to developer
│
├── developer/            - Developer files
│   ├── README.md        - Developer role guide ⭐ START HERE if you're the developer
│   ├── workspace/       - Active task working directories (gitignored)
│   └── email/           - Email communication
│       ├── inbox/       - Tasks from manager
│       ├── inbox-archive/ - Archived assignments
│       └── sent/        - Reports to manager
│
├── release-manager/      - Release manager files
│   ├── README.md        - Release manager guide ⭐ START HERE if you're releasing
│   ├── releases/        - Release notes and changelogs
│   └── email/           - Email communication
│       ├── inbox/       - Incoming messages
│       ├── inbox-archive/ - Archived messages
│       └── sent/        - Outgoing messages
│
├── projects/             - Active project tracking (manager-owned)
│   ├── INDEX.md         - Master project tracking
│   └── <project-name>/  - Individual project directories
│       ├── summary.md
│       └── todo.md
│
├── archived_projects/    - Completed/cancelled projects
│
└── README.md            - This file
```

## Communication Flow

```
Manager creates task
    ↓
manager/email/sent/ → copy → developer/email/inbox/
                            ↓
                    Developer reads & implements
                            ↓
developer/email/sent/ → copy → manager/email/inbox/
    ↓
Manager reviews & archives
```

## Project Tracking

All projects are tracked in **`claude/projects/INDEX.md`**

- View active projects: `grep "^### 🚧" claude/projects/INDEX.md`
- View completed: `grep "^### ✅" claude/projects/INDEX.md`
- View backburner: `grep "^### ⏸️" claude/projects/INDEX.md`

## Key Principles

### Role Separation

**Manager:**
- ✅ Creates projects and tracks progress
- ✅ Assigns tasks via email
- ✅ Updates INDEX.md
- ✅ Archives completed work
- ❌ Never edits source code

**Developer:**
- ✅ Implements assigned tasks
- ✅ Writes and tests code
- ✅ Reports completion
- ✅ Asks questions when unclear
- ❌ Never directly updates INDEX.md or project tracking

**Release Manager:**
- ✅ Creates version tags in both repos
- ✅ Generates changelogs from merged PRs
- ✅ Builds firmware and configurator
- ✅ Creates and publishes GitHub releases
- ❌ Never modifies source code (only builds it)

### Communication Protocol

1. **Assignments flow:** manager → developer
2. **Reports flow:** developer → manager
3. **All communication** uses the email system (sent/inbox folders)
4. **Archive processed messages** to keep inboxes clean

### Project Lifecycle

```
TODO → IN PROGRESS → COMPLETED → Archived
             ↓
          BACKBURNER (paused)
             ↓
        CANCELLED (abandoned)
```

## Quick Reference

### Manager Commands

```bash
# Check for completion reports
ls -lt claude/manager/email/inbox/

# View active projects
grep "Status: IN PROGRESS" claude/projects/*/summary.md

# Archive completed project
mv claude/projects/<name> claude/archived_projects/

# Archive completion report
mv claude/manager/email/inbox/<report>.md claude/manager/email/inbox-archive/
```

### Developer Commands

```bash
# Check for new assignments
ls -lt claude/developer/email/inbox/

# Send completion report
cp claude/developer/email/sent/<report>.md claude/manager/email/inbox/

# Archive processed assignment
mv claude/developer/email/inbox/<task>.md claude/developer/email/inbox-archive/

# Build & test
cd inav && ./build.sh TARGETNAME
cd inav-configurator && npm test
```

## Initial Setup

After cloning this repository, run the installer before doing anything
else — see **[`claude/INSTALL.md`](../claude/INSTALL.md)** for full
details. Short version:

```bash
./claude/install.sh
```

It auto-detects whether this is a fresh clone or an already-working
installation and handles settings paths, projects/emails, and the
`/home/user/` → your home directory substitution accordingly. Safe to
re-run — it won't touch existing data on a working installation.

---

## Getting Started

1. **First time in this repo?** Run `claude/install.sh` — see
   [`claude/INSTALL.md`](../claude/INSTALL.md). (Root `CLAUDE.md`'s
   MANDATORY FIRST ACTION checks for this automatically.)
2. **Determine your role** (Manager, Developer, Release Manager, or
   Security Analyst)
3. **Read your role-specific README:**
   - Manager: [`claude/manager/README.md`](manager/README.md)
   - Developer: [`claude/developer/README.md`](developer/README.md)
   - Release Manager: [`claude/release-manager/README.md`](release-manager/README.md)
   - Security Analyst: [`claude/security-analyst/README.md`](security-analyst/README.md)
4. Tell your human which role you have detected and ask them if you should read your inbox now
5. **Start working** according to your role

---

## Need Help?

- **Manager guide:** `claude/manager/README.md` - Project management, task assignment, tracking
- **Developer guide:** `claude/developer/README.md` - Building, testing, coding standards, architecture
- **Release Manager guide:** `claude/release-manager/README.md` - Tagging, building, publishing releases
- **Project index:** `claude/projects/INDEX.md` - All project status and tracking

**Remember:** Read your role-specific README for detailed instructions!
