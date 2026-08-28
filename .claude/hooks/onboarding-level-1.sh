#!/bin/bash
# Second-cycle onboarding message — shown when completed-cycles.txt == 1
# Called by session-start.sh. Outputs a JSON systemMessage.

python3 - <<'PYEOF'
import json

msg = """\
Welcome back — second cycle in this framework.

WORKFLOW REMINDER:
  Manager session   →  plan project, assign task to developer inbox
  Developer session →  implement, test, PR, report back
  Manager session   →  review completion, archive

ESSENTIAL AGENTS (use these, never the raw commands):
  inav-builder       → ALL firmware / configurator builds
  test-engineer      → write failing test BEFORE fixing the bug
  inav-architecture  → locate code BEFORE using grep
  email-manager      → all inbox / send / archive / audit operations

REMINDER: If starting as Developer, check inbox first with the
email-manager agent. If you want to work on something NOT in
the inbox, ask the manager to create it as a project first.

Which role today?  manager / developer / release-manager / security-analyst"""

print(json.dumps({"systemMessage": msg}))
PYEOF
