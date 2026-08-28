# Claude Workspace Installation

Welcome! This guide will help you set up the Claude workspace for INAV development.

## Setup

Just run:

```bash
./claude/install.sh
```

The script automatically detects whether this is a first-time setup or a working installation:

- **First-time clone from GitHub** — Automatically clears the previous owner's projects, emails, and INDEX.md so you start clean. No arguments needed.
- **Already set up** — Defaults to `continue` (verify directories, show capabilities). Your projects and emails are protected.
- **Ambiguous state** — Asks you to choose `fresh` or `continue`.

If you explicitly pass `fresh` on a working installation, the script lists your active projects and requires you to type `yes` to confirm.

### What "fresh" clears

- `projects/active/`, `projects/backburner/` directories
- `projects/INDEX.md` (reset to empty template)
- All email directories (`inbox/`, `sent/`, etc.)
- Developer workspace and lock files

### What is always kept

- `projects/completed/` (historical reference)
- `examples/` (templates)

### Manual setup

If you prefer to do it by hand:

```bash
# Clear previous owner's projects and index
rm -rf claude/projects/active/* claude/projects/backburner/*
# Edit claude/projects/INDEX.md — remove entries under "## Active Projects"

# Clear emails
rm -rf claude/*/email/inbox/* claude/*/email/sent/*

# Create directory structure
mkdir -p claude/projects/{active,backburner,completed}
mkdir -p claude/{manager,developer,release-manager,security-analyst}/email/{inbox,sent,inbox-archive}
mkdir -p claude/developer/workspace
mkdir -p claude/locks
```

## Directory Structure

After installation, you'll have:

```
claude/
├── INSTALL.md              # This file
├── examples/               # High-quality templates (always kept)
│   ├── projects/
│   └── emails/
├── projects/
│   ├── active/             # Current work
│   ├── backburner/         # Paused projects
│   └── completed/          # Historical reference
├── manager/
│   └── email/
├── developer/
│   ├── email/
│   └── workspace/          # Temporary working files
├── release-manager/
│   └── email/
├── security-analyst/
│   └── email/
└── locks/                  # Repo lock files
```

## Next Steps

The install script prints all available roles, skills, and agents when it finishes. You can also discover them at any time:

```bash
# List roles (each has a README.md)
ls -d claude/*/README.md

# List skills (invoke with /skill-name)
ls .claude/skills/

# List agents (launched automatically by Claude as needed)
ls .claude/agents/*.md
```

### Workflow overview

1. **User** tells Claude which role to take (manager or developer)
2. **Manager** creates tasks and sends them to the developer via internal email
3. **Developer** picks up assignments, implements changes, and reports back
4. **Manager** reviews reports, updates tracking, and assigns the next task

The **permissions-manager** agent controls which commands Claude runs automatically vs. which require user approval.

Ask Claude any questions about how these roles interact or how to customize the setup.

### Getting started

1. **Choose your role** and read its guide (`claude/<role>/README.md`)
2. **Review examples** in `claude/examples/` for project and email templates
3. **Use `/start-task`** to begin your first task

## Troubleshooting

### "Directory already exists" errors

The install script is safe to run multiple times. It won't delete existing content unless you explicitly choose "fresh" mode.

### Missing directories

Run the install script with any option to create missing directories:
```bash
./claude/install.sh continue
```

### Permission issues

Make the script executable:
```bash
chmod +x claude/install.sh
```

## About This Repository

This workspace supports multi-role INAV development:
- **Manager** - Project planning and task assignment
- **Developer** - Code implementation
- **Release Manager** - Release coordination
- **Security Analyst** - Security review (PrivacyLRS)

The email system enables asynchronous communication between roles across Claude sessions.
