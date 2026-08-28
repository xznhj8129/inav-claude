#!/usr/bin/env python3
"""Compile a deduplicated list of recent PR authors across iNavFlight repos.

Part of the "notify-contributors-inav10-schedule" project
(claude/projects/active/notify-contributors-inav10-schedule/). Phase 1 only:
this script queries, filters, and dedupes -- it never posts anything. The
approved comment text and posting step live in
notify-contributors-schedule-post.py, run only after explicit user approval
of the list this script produces.

Usage:
    python3 notify-contributors-schedule.py [--days 90] [--out review-list.json]

Requires: gh CLI authenticated (gh auth status).

Output: a JSON list of {author, repo, pr_number, pr_title, pr_url, pr_state,
created_at} -- one entry per unique human author, chosen as their single
most recent qualifying PR across both repos -- plus a human-readable table
printed to stdout for review.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

REPOS = ["iNavFlight/inav", "iNavFlight/inav-configurator"]

BOT_SUFFIXES = ("[bot]",)
KNOWN_BOTS = {
    "dependabot", "github-actions", "qodo-code-review", "coderabbitai",
    "copilot", "sonarqubecloud", "codecov", "vercel",
}


def is_bot(login: str) -> bool:
    lower = login.lower()
    if lower.endswith(BOT_SUFFIXES):
        return True
    return lower in KNOWN_BOTS


def fetch_prs(repo: str, since: str) -> list:
    """Fetch PRs (any state) created on/after `since` (YYYY-MM-DD)."""
    cmd = [
        "gh", "pr", "list", "--repo", repo, "--state", "all",
        "--search", f"created:>={since}",
        "--json", "number,author,title,createdAt,url,state",
        "--limit", "1000",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR querying {repo}: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--out", default=None, help="Write JSON review list to this path")
    args = ap.parse_args()

    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%d")
    print(f"Cutoff date ({args.days} days back from now): {cutoff_date}", file=sys.stderr)

    all_prs = []
    for repo in REPOS:
        prs = fetch_prs(repo, cutoff_date)
        print(f"{repo}: {len(prs)} PRs since {cutoff_date}", file=sys.stderr)
        for pr in prs:
            pr["_repo"] = repo
        all_prs.extend(prs)

    flagged_ambiguous = []
    by_author = {}
    for pr in all_prs:
        author = pr.get("author") or {}
        login = author.get("login", "")
        if not login:
            flagged_ambiguous.append(pr)
            continue
        if is_bot(login):
            continue
        # heuristic flag for anything bot-shaped but not in our known list
        if "bot" in login.lower() and login.lower() not in KNOWN_BOTS and not login.lower().endswith("[bot]"):
            flagged_ambiguous.append(pr)

        created_at = pr["createdAt"]
        existing = by_author.get(login)
        if existing is None or created_at > existing["createdAt"]:
            by_author[login] = pr

    review_list = []
    for login, pr in sorted(by_author.items(), key=lambda kv: kv[1]["createdAt"], reverse=True):
        review_list.append({
            "author": login,
            "repo": pr["_repo"],
            "pr_number": pr["number"],
            "pr_title": pr["title"],
            "pr_url": pr["url"],
            "pr_state": pr["state"],
            "created_at": pr["createdAt"],
        })

    print(f"\n{'AUTHOR':<20} {'REPO':<28} {'PR#':<7} {'STATE':<8} {'CREATED':<12} TITLE")
    print("-" * 120)
    for entry in review_list:
        print(f"{entry['author']:<20} {entry['repo']:<28} #{entry['pr_number']:<6} "
              f"{entry['pr_state']:<8} {entry['created_at'][:10]:<12} {entry['pr_title'][:50]}")

    print(f"\nTotal unique authors: {len(review_list)}", file=sys.stderr)

    if flagged_ambiguous:
        print(f"\n⚠️  {len(flagged_ambiguous)} PR(s) with ambiguous/bot-like authors flagged "
              f"for manual review (excluded from list above):", file=sys.stderr)
        for pr in flagged_ambiguous:
            login = (pr.get("author") or {}).get("login", "<no login>")
            print(f"    {pr['_repo']} #{pr['number']}: author={login!r} title={pr['title']!r}",
                  file=sys.stderr)

    if args.out:
        with open(args.out, "w") as f:
            json.dump(review_list, f, indent=2)
        print(f"\nWrote review list to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
