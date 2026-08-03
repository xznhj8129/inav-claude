# ⚠️ CRITICAL CHECKLIST - Read Before Modifying Any Code

**STOP! Complete this checklist before making ANY code changes:**

**Use a task list tool to track each step as you complete it.**

## 0. Read Coding Standards

**Read `claude/developer/guides/coding-standards.md` before writing any code.**
General instinct ("explain why, not what") isn't enough on its own — this repo
has specific rules beyond that default, including: never write
discovery-narrative comments or docs ("used to be X", "this used to fail
because Y") — describe only the current state and current rationale; history
belongs in the commit message, not the code or guide text.

## 1. Check Lock Files

```bash
# Check if directory is locked by another session
cat claude/locks/inav.lock 2>/dev/null || echo "No lock"
cat claude/locks/inav-configurator.lock 2>/dev/null || echo "No lock"
```

**If locked:** STOP. Report to manager that repo is locked. Do NOT proceed.

## 2. Acquire Lock (if unlocked)

Use the `/start-task` skill - it handles lock acquisition and branch creation automatically.

Or manually:
```bash
# For firmware
cat > claude/locks/inav.lock << EOF
LOCKED_BY: Developer
TASK: [task-name-from-assignment]
LOCKED_AT: $(date '+%Y-%m-%d %H:%M')
BRANCH: [branch-name]
SESSION_ID: $CLAUDE_CODE_SESSION_ID
EOF

# For configurator
cat > claude/locks/inav-configurator.lock << EOF
LOCKED_BY: Developer
TASK: [task-name-from-assignment]
LOCKED_AT: $(date '+%Y-%m-%d %H:%M')
BRANCH: [branch-name]
SESSION_ID: $CLAUDE_CODE_SESSION_ID
EOF
```

use inav.lock for the inav/ directory, inav2.lock for the inav2/ directory, or inav3.lock for the inav3 directory

## 3. Create Git Branch
The branch MUST be created off of the correct version branch — never off master.

```bash
claude/developer/scripts/git/new-branch.sh <repo> <bugfix|feature|breaking> <branch-name>
```

See `.claude/skills/git-workflow/SKILL.md` ("Creating Branches") for the current
base-branch decision table (including any active temporary override) and the manual
fallback if the script can't be used.

## 4. Plan End-User Documentation (If Needed)

**Evaluate if your planned change needs end-user documentation:**

- ✅ **New features** → Draft documentation NOW (before coding)
- ✅ **Behavior changes** → Draft documentation NOW
- ℹ️ **Bug fixes** → Generally no docs needed
- ℹ️ **New targets** → Generally no docs needed
- ℹ️ **Refactoring** → Only if user-facing behavior changes

**If documentation is needed:**

1. **Draft the user documentation NOW** (before implementing)
   - Write it in `claude/projects/active/[project-name]/notes/draft-user-docs.md`
   - Describe the feature from the user's perspective
   - Include examples, configuration steps, and any CLI/settings changes

2. **Use this as a design review:**
   - **If the draft docs are complex** → Feature design may be too complex
   - **If hard to explain clearly** → User experience needs simplification
   - **If requires many steps** → Consider streamlining the workflow

3. **This draft will be updated later:**
   - After implementation, update the draft to match actual behavior
   - Then add to `inav/docs/` and/or `inavwiki/` before PR

## 5. Check for Specialized Agents

**Before starting implementation, check if specialized agents apply:**

| Task involves... | Use this agent FIRST |
|------------------|----------------------|
| MSP protocol work | **msp-expert** - Message formats, mspapi2 usage |
| Settings/CLI parameters | **settings-lookup** - Setting names, defaults, valid values |
| Finding firmware code | **inav-architecture** - Locates subsystems before Grep |
| Target configuration issues | **target-developer** - Flash overflow, DMA conflicts, gyro detection, pin mapping |
| SITL operations | **sitl-operator** - Start/stop/configure SITL |
| Building firmware/configurator | **inav-builder** - ALL builds (never cmake/make/npm directly) |
| Testing/validation | **test-engineer** - Reproduce bugs, run tests |

**Pattern matching:**
- Task mentions "MSP" → use **msp-expert**
- Task mentions "setting" or CLI → use **settings-lookup**
- Need to find code location → use **inav-architecture**
- Task mentions "target", "flash overflow", "DMA conflict", "gyro detection" → use **target-developer**
- Need to build anything → use **inav-builder**

## 5. Use Agents - NEVER Direct Commands

**❌ NEVER:**
- `cmake ..`
- `make TARGETNAME`
- `npm start` (for builds)
- Direct Grep on `inav/src/` without agent guidance

**✅ ALWAYS:**
- Use `inav-builder` agent for ALL builds
- Use `test-engineer` agent for ALL testing
- Use `inav-architecture` agent BEFORE searching firmware code

## 6. Before Searching Firmware Code

**❌ NEVER:** Start with `Grep` or `Explore` on `inav/src/`

**✅ ALWAYS:** Ask `inav-architecture` agent first:
```
"Where is [functionality I need to find]?"
```

The agent will tell you exactly which files/directories to look at. THEN use Grep/Read on those specific locations.

## 6. Debugging Tools Available

When investigating bugs or understanding code behavior:

1. **Serial printf debugging** - Use DEBUG macros in firmware code (via `/mwptools` for CLI)
2. **Chrome DevTools MCP** - For configurator debugging (via `/test-configurator`)
3. **GDB** - For SITL debugging (`gdb inav/build_sitl/bin/SITL.elf`)

See `guides/debugging-guide.md` for detailed usage instructions.

---

**Once this checklist is complete, proceed with your task.**

---

## 7. When committing code
1. *Do NOT mention Claude in commit messages* - Do NOT put "Co-Authored-By: Claude Sonnet 4.6" or similar in a commit message
2. *Read claude/developer/guides/CRITICAL-BEFORE-COMMIT.md*

## Self-Improvement: Lessons Learned

When you discover something important about PRE-CODING SETUP that will likely help in future sessions, add it to this section. Only add insights that are:
- **Reusable** - will apply to future pre-coding setup, not one-off situations
- **About setup/preparation** - lock files, branches, agent usage, search strategy
- **Concise** - one line per lesson

Use the Edit tool to append new entries. Format: `- **Brief title**: One-sentence insight`

### Lessons

- **Fix blockers, don't route around them**: If goal X is blocked by small problem Y, fix Y first — don't pivot to complex workarounds (e.g. if a build fails due to an unrelated compile error in another file, fix that error rather than trying to analyze LTO bitcode object files to simulate what the linker would have produced). We build correct solutions, not workarounds.
- **Always use fc-flasher agent for hardware flashing**: Never invoke `dfu-util` directly. STM32H7 boards silently fail DFU exit with raw dfu-util ("can't detach"), leaving the FC stuck. The fc-flasher agent uses the known-good script that handles all STM32 variants correctly.
- **Harness-only tasks (`.claude/`, `claude/`) skip branch creation**: A guardrail hook blocks `git checkout -b` in the root `inavflight/` repo — branches belong in the project repos (`inav/`, `inav-configurator/`, etc.). For tasks that only touch harness config/docs, commit straight to `master`, matching existing harness commit history.
-- **Floats must end in `f` to avoid promotion to double**: We don't want to load the double-precision math library by accidentally using 2.0 instead of 2.0f

<!-- Add new lessons above this line -->
