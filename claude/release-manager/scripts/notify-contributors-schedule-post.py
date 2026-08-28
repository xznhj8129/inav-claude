#!/usr/bin/env python3
"""Post the INAV 10 schedule FYI comment to the approved (author, PR) list.

Part of the "notify-contributors-inav10-schedule" project
(claude/projects/active/notify-contributors-inav10-schedule/). Phase 3 --
run ONLY after the user has explicitly approved the review list produced by
notify-contributors-schedule.py and the exact comment text below.

Usage:
    python3 notify-contributors-schedule-post.py review-list.json [--dry-run]

Posts via `gh pr comment <number> --repo <repo> --body "..."` to each entry
in the JSON list. Continues past individual failures (e.g. a PR closed or
locked since the list was compiled) and reports a per-PR success/failure
summary at the end.
"""
import argparse
import json
import subprocess
import sys

COMMENT_TEXT = (
    "Just an FYI for contributors: The tentative schedule for INAV 10 is to "
    "have a full release in mid December. That means RC2 needs to be in "
    "early to mid November, which places INAV 10.0RC1 at September 1. "
    "Please plan to have any new features for INAV 10.0 ready for RC1 no "
    "later than September 1. After that, 10.1 will follow about six to "
    "seven months later."
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("review_list", help="Path to approved review-list.json")
    ap.add_argument("--dry-run", action="store_true", help="Print actions without posting")
    args = ap.parse_args()

    with open(args.review_list) as f:
        entries = json.load(f)

    results = []
    for entry in entries:
        repo = entry["repo"]
        pr_number = entry["pr_number"]
        author = entry["author"]

        if args.dry_run:
            print(f"[DRY RUN] Would comment on {repo} #{pr_number} (author: {author})")
            results.append((author, repo, pr_number, "DRY-RUN"))
            continue

        cmd = [
            "gh", "pr", "comment", str(pr_number),
            "--repo", repo,
            "--body", COMMENT_TEXT,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"OK    {repo} #{pr_number} (author: {author})")
            results.append((author, repo, pr_number, "OK"))
        else:
            err = result.stderr.strip().replace("\n", " ")
            print(f"FAIL  {repo} #{pr_number} (author: {author}): {err}", file=sys.stderr)
            results.append((author, repo, pr_number, f"FAIL: {err}"))

    ok_count = sum(1 for r in results if r[3] == "OK")
    fail_count = sum(1 for r in results if r[3].startswith("FAIL"))
    print(f"\nSummary: {ok_count} posted, {fail_count} failed, {len(results)} total", file=sys.stderr)

    if fail_count:
        print("\nFailures:", file=sys.stderr)
        for author, repo, pr_number, status in results:
            if status.startswith("FAIL"):
                print(f"  {repo} #{pr_number} (author: {author}): {status}", file=sys.stderr)


if __name__ == "__main__":
    main()
