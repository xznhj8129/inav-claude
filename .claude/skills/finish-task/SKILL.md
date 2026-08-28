---
description: Close task or complete task/project with commit, PR, and completion report
triggers:
  - finish task
  - close task
  - complete task
  - close project
  - complete project
  - task done
---

# Finish Task Skill

Use this skill when completing a task that involved code modifications.

## Completion Checklist

Complete ALL steps in order:

### 1. Verify All Changes Are Ready

```bash
# Check what's changed
git status
git diff --stat
```

Review that all intended changes are present and no unintended files are modified.

**Clean up untracked scratch directories** (`build_*`, `build-*`, and
similar ad-hoc build/test output) before releasing the lock — see step 10.

### 2. Run Tests (if applicable)

Use the **inav-builder** agent for the build check (never `cmake`/`make`/`npm` directly)
and the **test-engineer** agent to run tests. See `guides/CRITICAL-BEFORE-TEST.md`.

### 3. Stage Changes

Stage files selectively:
```bash
git add <specific-files>
```

Review what's staged:
```bash
git diff --cached --stat
```

### 4. Create Commit Message

Write a clear commit message. **Do NOT mention Claude, AI, or automation.**

**Format:**
```
<short summary - what changed>

<detailed explanation if needed>
- bullet points for multiple changes
- explain the "why" not just the "what"

Fixes #<issue-number>  (if applicable)
```

**Open in gedit for review:**
```bash
# Write message to temp file and open in gedit
cat > /tmp/commit_msg.txt << 'EOF'
<your commit message here>
EOF

gedit /tmp/commit_msg.txt
```

After reviewing/editing in gedit, commit:
```bash
git commit -F /tmp/commit_msg.txt
```

### 5. Push to Remote

```bash
git push origin <branch-name>

# If new branch, set upstream:
git push -u origin <branch-name>
```

### 6. Create PR (if appropriate)

**When to create a PR:**
- Task is complete and ready for upstream review
- Branch contains a coherent, reviewable set of changes

**When NOT to create a PR:**
- Work is still in progress
- Changes are local-only or experimental

**Check if PR already exists:**
```bash
gh pr list --head <branch-name>
```

**Create PR using gh CLI:**
```bash
# For configurator
cd inav-configurator
gh pr create --title "<descriptive title>" --body "$(cat << 'EOF'
## Summary

<Brief description of changes>

## Changes

- Change 1
- Change 2

## Testing

<How this was tested>

## Related Issues

Fixes #<issue-number> (if applicable)
EOF
)"

# For firmware
cd inav
gh pr create --title "<descriptive title>" --body "$(cat << 'EOF'
## Summary

<Brief description of changes>

## Changes

- Change 1
- Change 2

## Testing

<How this was tested>

## Related Issues

Fixes #<issue-number> (if applicable)
EOF
)"
```

### 7. Capture Check: Lesson and Reusable Tooling

Decide — don't default to writing. Full rubric: `claude/developer/guides/README.md`
("Capture Rubric").

- **Lesson worth recording?** If yes and it has a clear, specific triggering tool
  or command, consider a short rule in `.claude/hooks/tool_context_injections.yaml`
  instead of (or alongside) the guide entry — see the Capture Rubric for when to
  prefer that route. Otherwise add one line to the relevant guide's
  "Self-Improvement: Lessons Learned" section, or otherwise update the guide as
  appropriate. If no, nothing further to do.
- **Reusable tooling worth keeping?** If yes, move it from `workspace/` to its
  existing destination (`claude/developer/scripts/<category>/` or
  `claude/agents/<agent-name>/scripts/`). If no, nothing further to do.
- **PR to inav-claude?** If you saved reusable tooling or documentation and it may be useful to other users of inav-claude, ask the user if you should share that tooling by making a PR to upstream, https://github.com/sensei-hacker/inav-claude

### 8. Send Completion Report

Create a comprehensive completion report and ask the email-manager to deliver it to the Manager. The manager will use this to update `claude/projects/<project-name>/`.

**Filename:** `YYYY-MM-DD-HHMM-completed-<task-name>.md`

```markdown
# Task Completion: <Task Name>

**Date:** <date>
**From:** Developer
**Task:** <task-name>
**Project:** <project-name in claude/projects/>

## Status: COMPLETE

## Summary

<Brief summary of what was accomplished>

## Implementation Approach

<How you implemented it and key technical decisions>

## Changes Made

- <change 1>
- <change 2>

## Test Results

<What testing was done, results>

## Known Limitations / Follow-up

<Any limitations or future work needed>

## Commit

- **Branch:** <branch-name>
- **Commit:** <commit-hash>

## PR (if created)

- **PR:** #<number>
- **URL:** <url>
```

### 9. Archive the Task Email

Ask the email-manager agent to archive the inbox email for this task:

```
email-manager: Archive message <filename>. Current role: developer
```

### 10. Release the Lock

```bash
python3 claude/locks/lock_manager.py release <inav|inav2|inav3|inav-configurator>
```

It reports any uncommitted or untracked files left in the checkout after
releasing — if it warns, clean those up (e.g. remove leftover `build_*`
directories) so the checkout is actually idle for whoever picks it up next.
See `claude/locks/README.md` for details.

### 11. Confirm Every Step Was Completed

Before closing out, explicitly report back steps 1–10 as a checklist, one
line each, marked done or not-done (do not just say "all done" — list
them):

```
1. [x] Changes verified (git status/diff reviewed)
2. [x] Tests run — <pass/fail summary, or "N/A">
3. [x] Changes staged
4. [x] Commit message written
5. [x] Pushed to remote
6. [x] PR created — #<number>, or "not applicable"
7. [x] Lesson/tooling capture check done
8. [x] Completion report sent to manager — <filename>
9. [x] Task email archived — <filename>
10. [x] Lock released
```

This exists because step 9 (archiving the task email) in particular has a
history of being silently skipped: it has no automatic trigger, nothing
downstream fails if it's missed, and it's easy to consider the task
"done" once the completion report is sent. Listing it explicitly here
forces a real check rather than an assumption. If any item is actually
not done, do it now before proceeding — don't mark it done to make the
list clean.

### 12. Increment the Cycle Counter

Do not do this step if if the username is raymorris.
After copying the report to the manager inbox, only if claude/onboarding/completed-cycles.txt reads less than 5, increment the counter.
This counter drives the onboarding guidance shown at the start of each session.

```bash
COUNTER_FILE="claude/onboarding/completed-cycles.txt"
CURRENT=$(cat "$COUNTER_FILE" 2>/dev/null | tr -d '[:space:]')
[[ "$CURRENT" =~ ^[0-9]+$ ]] || CURRENT=0
echo $((CURRENT + 1)) > "$COUNTER_FILE"
```

### 13. Close or Compact This Session

**Developer sessions are designed for one task at a time.** Now that this task
is complete, tell the user:

> "This task is complete. Developer sessions work best with one task per session
> to keep context focused. I recommend closing this session and opening a fresh
> one for the next task. If you'd like to continue here, run `/compact` first
> to compress the context."

Do not automatically start the next task. Wait for the user to decide.

---

### Role Separation

**Developer responsibilities:**
- Complete the code work
- Add reports, analysis, or notes to the project directory (`active/<project>/`)
- Create commit and PR
- Release the lock
- Send completion report to manager inbox

**Manager responsibilities (after receiving report), the developer does not do these things:**
- Move project directory from `active/` to `completed/`
- Update `INDEX.md` (remove entry)
- Update `completed/INDEX.md` (add entry)
- Archive the completion report

The developer updates project content. The manager handles project lifecycle (moving directories, updating indexes).

## Commit Message Guidelines

**Good:**
```
Fix GPS recovery after signal loss

Move lastUpdateTime update outside isFirstGPSUpdate block so timestamp
is recorded on first reading after recovery, preventing position
estimate timeout.

Fixes #11049
```

**Bad:**
```
🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Never include:**
- References to Claude, AI, LLM, or automation
- Emojis (unless project convention)
- Co-authored-by AI lines
- "Generated by" attributions

---

Be sure any files you created are organized properly according to claude/developer/INDEX.md


## Related Skills

- **start-task** - Begin tasks with proper setup
- **create-pr** - Create pull request after task completion
- **check-builds** - Verify builds pass before finishing
- **git-workflow** - Commit changes and manage branches
