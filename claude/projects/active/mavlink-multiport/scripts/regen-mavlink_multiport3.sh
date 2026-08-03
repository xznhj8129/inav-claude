#!/usr/bin/env bash
#
# Regenerate the `mavlink_multiport3` integration branch.
#
# mavlink_multiport3 is DEFINED as — and must never drift from — the
# combination of the current tips of:
#
#     mav/07-tunnel                        full 7-PR MAVLink stack   (PR #11718)
#   + mav/reconnect-refine                 reconnect follow-up       (PR #11731)
#   + fix/sitl-scheduler-dup-preprocessor  SITL build hotfix         (PR #11738)
#
# It is a regenerable integration + test branch, NOT a PR. Because it is a
# static git pointer it cannot auto-follow those inputs — so run this whenever
# any of them changes and it is rebuilt to exactly their current combination.
#
# Lifecycle-safe: as each input merges upstream and mav/07-tunnel is rebased to
# include it, that input's commits are already in the base, so they are detected
# and skipped (or dropped as empty). The branch therefore keeps meaning "07 plus
# whatever of those follow-ups isn't upstream yet" through the entire merge cycle,
# and once everything has merged it collapses to just mav/07-tunnel.
#
# Usage:  ./regen-mavlink_multiport3.sh
#
set -euo pipefail

REPO="/media/anon/WD2TB/DataVault/TechProjects/Software/GitRepos/inav-claude/inav"
BASE="mav/07-tunnel"
EXTRAS=("mav/reconnect-refine" "fix/sitl-scheduler-dup-preprocessor")

cd "$REPO"

echo "Regenerating mavlink_multiport3 = $BASE + ${EXTRAS[*]}"
git checkout -B mavlink_multiport3 "$BASE" >/dev/null

for ext in "${EXTRAS[@]}"; do
    if ! git rev-parse --verify --quiet "$ext" >/dev/null; then
        echo "  ! input branch '$ext' not found — skipping (already merged/deleted?)"
        continue
    fi
    if git merge-base --is-ancestor "$ext" HEAD; then
        echo "  = $ext already contained in $BASE — nothing to add"
        continue
    fi
    mb="$(git merge-base "$ext" "$BASE")"
    n="$(git rev-list --count "$mb..$ext")"
    echo "  + applying $ext ($n commit(s))"
    # If a cherry-pick lands empty (that change already reached the base another
    # way), git stops — run `git cherry-pick --skip` and re-run this script.
    git cherry-pick "$mb..$ext"
done

echo
echo "Done. mavlink_multiport3 = $(git rev-parse --short HEAD)"
echo "Commits on top of $BASE:"
git --no-pager log --oneline "$BASE..HEAD" | sed 's/^/    /'
echo
echo "Next: build-verify (SITL + mavlink_unittest) before relying on it."
