---
description: Review pull requests including bot suggestions and CI checks
triggers:
  - review pr
  - check pr
  - review pull request
  - checkout pr
  - check pull request
  - review github pr
---

# Pull Request Review Workflow

Complete workflow for reviewing pull requests, including checking out the code, reviewing bot suggestions, and verifying builds.

## Quick PR Checkout

```bash
# Checkout a PR by number
gh pr checkout <PR_NUMBER>

# View PR details
gh pr view <PR_NUMBER>

# Check CI/build status
gh pr checks <PR_NUMBER>
```

## Full Review Process

### 1. Fetch PR Information

**Read comments before the diff.** Comments often carry context a diff-only read misses — author clarifications, prior reviewer findings, CI failures, or scope changes since the PR opened. Reading them first avoids re-discovering (or contradicting) ground already covered.

```bash
# View PR description and metadata
gh pr view <PR_NUMBER>

# List all PR comments — read this before the diff
gh pr view <PR_NUMBER> --comments

# View PR diff
gh pr diff <PR_NUMBER>
```

### 2. Checkout PR Code

```bash
# Checkout the PR branch
gh pr checkout <PR_NUMBER>

# Verify you're on the correct branch
git branch --show-current
```

### 3. Review Bot Comments **CAREFULLY**

**CRITICAL:** Bot suggestions require careful human evaluation.

When reviewing bot comments (from GitHub bots, linters, or AI assistants):

#### DO:
- ✅ Read each suggestion carefully and understand what it's proposing
- ✅ Evaluate whether the suggestion improves code quality
- ✅ Check if the suggestion aligns with project coding standards
- ✅ Verify the suggestion doesn't break functionality
- ✅ Test changes if accepting bot suggestions
- ✅ Consider context the bot might not understand

#### DON'T:
- ❌ Accept all bot suggestions blindly
- ❌ Assume the bot understands project-specific conventions
- ❌ Let the bot override your engineering judgment
- ❌ Accept suggestions that reduce code clarity
- ❌ Apply suggestions without understanding them

#### Common Bot Suggestion Categories:

1. **Code Style/Formatting**
   - Usually safe to accept if consistent with project style
   - Verify it doesn't conflict with existing patterns

2. **Performance Optimizations**
   - Evaluate whether the optimization is meaningful
   - Check for potential side effects or edge cases

3. **Security/Bug Fixes**
   - These are high-priority but verify the fix is correct
   - Ensure the fix doesn't introduce new issues

4. **Refactoring Suggestions**
   - Consider whether the refactoring improves readability
   - Check if it aligns with project architecture

5. **Dependency Updates**
   - Verify compatibility with existing code
   - Check for breaking changes in changelogs

### 4. Check Build Status

```bash
# Check all CI checks
gh pr checks <PR_NUMBER>

# List recent workflow runs
gh run list --limit 5

# View specific workflow run
gh run view <RUN_ID>
```

### 5. Test Locally

**For firmware changes:**
```bash
cd inav
./build.sh SITL  # or specific target
```

**For configurator changes:**
```bash
cd inav-configurator
ENABLE_REMOTE_DEBUGGING=1 NODE_ENV=development npm start --remote-debugging-port=9222
```

### 6. Review Checklist

Use this checklist when reviewing PRs:

- [ ] Code follows project conventions and style
- [ ] Changes are well-documented (comments, commit messages)
- [ ] No unnecessary or debug code left in
- [ ] All CI checks passing
- [ ] Bot suggestions reviewed and valid ones addressed
- [ ] Invalid bot suggestions documented/dismissed
- [ ] Changes tested locally if significant
- [ ] No breaking changes (or properly documented if unavoidable)
- [ ] Related issues/PRs referenced

## Viewing PR Comments

```bash
# View all comments including bot suggestions
gh api repos/iNavFlight/inav/pulls/<PR_NUMBER>/comments

# For configurator repo
gh api repos/iNavFlight/inav-configurator/pulls/<PR_NUMBER>/comments
```

## Adding Review Comments

**Note:** `gh pr review` (formal review with an approve/request-changes verdict) is blocked by a repo policy hook for this project — PR reviews must be submitted through the GitHub web interface, not the CLI. Use `gh pr comment` instead to post findings as a regular comment:

```bash
gh pr comment <PR_NUMBER> --body-file <path-to-drafted-comment.md>
```

### Never post without explicit confirmation of the final text

Do not run `gh pr comment` / `gh pr review` until the user has seen and approved the *exact* text being posted — even if they asked at the start of the task for the review to be "posted when done." That earlier instruction authorizes drafting, not auto-publishing; investigation often turns up findings (e.g. a claimed compile failure) that are much more consequential than what was originally scoped, so the wording needs a final human check before it goes out publicly under the user's name. Workflow:

1. Draft the review.
2. Write it to an easily-edited file in `/tmp` (e.g. `/tmp/pr<NUMBER>-review-draft.md`) — not a deep scratchpad path, and not the user's home directory (that leaves old drafts cluttering it) — so they can revise it directly.
3. Wait for explicit go-ahead ("post it", "looks good, post") before calling `gh pr comment`.
4. If the user has since edited the file themselves, post the file's current contents — don't regenerate from memory.

This was learned the hard way on PR #11756 (2026-08-04): a review was posted automatically once finished, based on an earlier "post it when done," and the user had to delete the public comment because they wanted to see the wording first.

### Tone and attribution for AI-drafted reviews

When the findings were produced primarily by AI analysis (not verified independently by the human), lead the comment with a brief attribution line making that clear, and phrase findings as questions for the author to check rather than flat assertions — even for findings you've verified yourself (e.g. by actually reproducing a build failure locally). This applies regardless of confidence level; frame it as "here's what I found, please confirm" not "here's the verdict."

Bad: `## Blocking: X does not compile` / `## Bug: Y is misconfigured`

Good: `## SYNERDUINOH7 — did it actually build for you?` / `## Possible USE_IMU_BMI088 mix-up?`

Example attribution line: *"I took a look at this with an AI-based tool I have. It may well be wrong on any of the points below — please treat it as a set of questions to check rather than a verdict, and correct me if I've misread something."*

## Common Review Scenarios

### Bot Suggested Too Many Changes

If a bot has suggested many changes:
1. Group suggestions by category (style, performance, bugs)
2. Evaluate each category separately
3. Accept valid categories as a group
4. Document why certain suggestions were rejected
5. Provide clear feedback to PR author

### Build Failures

If CI checks are failing:
1. Check `gh pr checks <PR_NUMBER>` for specific failures
2. View workflow logs: `gh run view <RUN_ID> --log`
3. Reproduce locally if needed
4. Provide specific guidance on fixes

### Merge Conflicts

If PR has conflicts:
1. PR author should resolve conflicts
2. Verify conflict resolution doesn't break functionality
3. Re-test after conflicts are resolved

## After Review

```bash
# Return to your working branch
git checkout <YOUR_BRANCH>

# Or return to master
git checkout master
```

## Example Review Workflow

```bash
# 1. Check out PR #2433
gh pr checkout 2433

# 2. View PR and comments
gh pr view 2433 --comments

# 3. Review bot suggestions carefully
# (Read through comments, evaluate each suggestion)

# 4. Check builds
gh pr checks 2433

# 5. Test locally
cd inav-configurator
ENABLE_REMOTE_DEBUGGING=1 NODE_ENV=development npm start --remote-debugging-port=9222

# 6. Leave review
gh pr review 2433 --approve -b "Reviewed bot suggestions. Accepted valid ones, documented rejected ones. Code looks good!"

# 7. Return to your branch
git checkout master
```

## Resources

- **GitHub CLI docs:** `gh pr --help`
- **Example past reviews:** `claude/pr-review-firmware-2026-02-28.md` and `claude/pr-review-configurator-2026-02-28.md` — full-batch review reports showing the severity-bucket format used historically

---

## Related Skills

- **git-workflow** - Checkout PR branches and manage git operations
- **create-pr** - Create your own pull requests
- **check-builds** - Check CI build status for PRs under review
- **check-pr-docs** - Check whether a PR updated documentation where required
- **pr-scorecard** - Score a single PR's merge-readiness (CI, reviews, testing evidence, maturity, risk)
- **pr-scorecard-triage** - Walk a batch of open PRs by scorecard, suggesting merge/comment/label/approve
- **pr-triage** - Triage open PRs for merge readiness and assign milestones
- **find-symbol** - Jump to a function/struct/variable definition via ctags while reading a diff
- **communication** - Cross-role message templates, if a review needs to be routed to Manager/Release Manager
- **run-configurator** - Test configurator PRs locally
- **build-sitl** - Build and test firmware PRs

## Related Agents

Dispatch these with the Agent tool when a review needs more than the CLI steps above:

- **check-pr-bots** - Fast fetch/format of all bot comments (Qodo, github-actions, etc.) on a PR — good first step before reading the raw diff
- **inav-code-review** - Deep, severity-categorized code-quality/safety review of C99/JS changes
- **inav-architecture** - Locates relevant files/subsystems fast when the PR touches an unfamiliar area
- **target-developer** - target.h/DMA/timer/pin-mapping/flash-overflow expert — use for any PR touching `src/main/target/*` (this caught a real DMA collision and confirmed a false-positive bot flag during the PR #11756 review)
- **inav-builder** - The only sanctioned way to actually build firmware/configurator to verify a suspected compile issue — never run cmake/make/npm directly
- **test-engineer** - Reproduce bugs or write/run tests against the PR's changes (does not fix code)

**Both `check-pr-bots` and `inav-code-review` link back to this skill for the posting-tone/confirmation rules below — if you're using them standalone outside a full `/pr-review` pass, still follow "Never post without explicit confirmation" and "Tone and attribution for AI-drafted reviews" before publishing anything they find.**

## Related Documentation

- `claude/developer/guides/CRITICAL-BEFORE-PR.md` - Pre-PR checklist; useful context for judging whether someone else's PR is actually ready
- `claude/developer/guides/CRITICAL-BEFORE-MERGE.md` - Merge-direction rules and the GitHub web conflict-resolver trap — read before recommending or performing a merge
- `claude/developer/guides/coding-standards.md` - Primary coding standards referenced by `inav-code-review`
- `claude/developer/guides/root-cause-analysis.md` - Useful when a review finding needs deeper investigation
