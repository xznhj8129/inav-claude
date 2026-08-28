#!/usr/bin/env python3
"""
Fetch and categorize GitHub issues from iNavFlight repositories.

Usage:
    ./fetch_issues.py                              # Fetch recent open issues (inav)
    ./fetch_issues.py --pages 3                    # Fetch 3 pages (300 issues)
    ./fetch_issues.py --issue 11156                # View specific issue details
    ./fetch_issues.py --refresh                    # Refresh issues.json cache
    ./fetch_issues.py --repo inav-configurator      # Use inav-configurator instead
    ./fetch_issues.py --repo inav,inav-configurator --days 90 --refresh
                                                     # Multi-repo, date-filtered (uses Search API)

Repo shorthand "inav" / "inav-configurator" expands to iNavFlight/<name>; a
full "owner/name" is used as-is.

--days N uses GitHub's Search API (issues created in the last N days) instead
of paging through all open issues — much cheaper when you only care about a
recent window, since it filters server-side rather than fetching everything
and discarding old issues.
"""

import subprocess
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_REPO = "iNavFlight/inav"
SCRIPT_DIR = Path(__file__).parent
# Local data lives outside the repo tree (gitignored); cache files go there.
LOCAL_DATA_DIR = SCRIPT_DIR.parents[2] / "claude" / "local-data" / "issue-triage"
ISSUES_CACHE = LOCAL_DATA_DIR / "issues.json"
TRIAGE_FILE = LOCAL_DATA_DIR / "triage.md"

def expand_repo(name):
    """Expand shorthand repo names to owner/name form."""
    name = name.strip()
    if "/" in name:
        return name
    return f"iNavFlight/{name}"

def run_gh_api(endpoint, paginate=False, jq=None):
    """Run gh api command and return parsed JSON (or jq-filtered lines)."""
    cmd = ["gh", "api", endpoint]
    if paginate:
        cmd.append("--paginate")
    if jq:
        cmd.extend(["-q", jq])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        return None
    if jq:
        return result.stdout
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON from: {endpoint}", file=sys.stderr)
        return None

def fetch_issues(repos, pages=2):
    """Fetch open issues (not PRs) from the given repositories by paging."""
    all_issues = []

    for repo in repos:
        for page in range(1, pages + 1):
            print(f"Fetching {repo} page {page}...", file=sys.stderr)
            endpoint = f"repos/{repo}/issues?state=open&per_page=100&page={page}&sort=created&direction=desc"
            data = run_gh_api(endpoint)

            if not data:
                break

            # Filter out PRs, tag with source repo
            issues = [i for i in data if 'pull_request' not in i]
            for i in issues:
                i['_repo'] = repo
            all_issues.extend(issues)

            if len(data) < 100:
                break  # No more pages

    return all_issues

def fetch_issues_since(repos, days):
    """Fetch open issues created in the last `days` days via the Search API.

    Much cheaper than fetch_issues() when only a recent window matters: the
    date filter and repo scoping happen server-side, so there's no need to
    page through the full open-issue backlog and discard old results.
    """
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    all_issues = []

    for repo in repos:
        print(f"Searching {repo} for issues created since {since}...", file=sys.stderr)
        query = f"repo:{repo}+is:issue+is:open+created:>={since}"
        endpoint = f"search/issues?q={query}&per_page=100&sort=created&order=desc"
        data = run_gh_api(endpoint, paginate=True)

        if not data:
            continue

        # --paginate with a plain (non -q) call returns one JSON doc per
        # page on separate lines; handle both that and a single-page dict.
        items = []
        if isinstance(data, dict):
            items = data.get('items', [])
        all_issues.extend(items)
        for i in items:
            i['_repo'] = repo

    return all_issues

def format_issue_summary(issue):
    """Format a single issue for display."""
    labels = ", ".join([l['name'] for l in issue.get('labels', [])])
    created = issue['created_at'][:10]
    comments = issue.get('comments', 0)
    repo = issue.get('_repo', '').split('/')[-1]

    title = issue['title']
    if len(title) > 70:
        title = title[:67] + "..."

    return f"{repo:>18} #{issue['number']:5d} | {created} | {comments:2d}c | {title} [{labels}]"

def view_issue(issue_number, repo=DEFAULT_REPO):
    """View detailed information about a specific issue."""
    endpoint = f"repos/{repo}/issues/{issue_number}"
    issue = run_gh_api(endpoint)

    if not issue:
        return

    print(f"\n{'='*80}")
    print(f"Issue #{issue['number']}: {issue['title']}")
    print(f"{'='*80}")
    print(f"URL: {issue['html_url']}")
    print(f"Created: {issue['created_at'][:10]} by {issue['user']['login']}")
    print(f"Comments: {issue.get('comments', 0)}")
    labels = ", ".join([l['name'] for l in issue.get('labels', [])])
    print(f"Labels: {labels or '(none)'}")
    print(f"\n--- Body ---\n")
    body = issue.get('body', '(no description)')
    if body and len(body) > 2000:
        print(body[:2000] + "\n\n... [truncated]")
    else:
        print(body)
    print(f"\n{'='*80}\n")

def save_issues(issues):
    """Save issues to cache file."""
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_data = {
        'fetched_at': datetime.now().isoformat(),
        'count': len(issues),
        'issues': issues
    }
    with open(ISSUES_CACHE, 'w') as f:
        json.dump(cache_data, f, indent=2)
    print(f"Saved {len(issues)} issues to {ISSUES_CACHE}", file=sys.stderr)

def load_cached_issues():
    """Load issues from cache if available."""
    if ISSUES_CACHE.exists():
        with open(ISSUES_CACHE) as f:
            data = json.load(f)
        print(f"Loaded {data['count']} issues from cache (fetched {data['fetched_at'][:10]})", file=sys.stderr)
        return data['issues']
    return None

def print_issues_list(issues):
    """Print formatted list of issues."""
    print(f"\n{'#':>6} | {'Created':10} | {'C':>3} | {'Title':<70}")
    print("-" * 100)
    for issue in issues:
        print(format_issue_summary(issue))

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Fetch and analyze GitHub issues')
    parser.add_argument('--pages', type=int, default=2, help='Number of pages to fetch (100 issues/page)')
    parser.add_argument('--issue', type=int, help='View specific issue number')
    parser.add_argument('--refresh', action='store_true', help='Force refresh from GitHub')
    parser.add_argument('--search', type=str, help='Search issues by keyword')
    parser.add_argument('--repo', type=str, default='inav',
                         help='Comma-separated repo(s): shorthand ("inav", "inav-configurator") or "owner/name"')
    parser.add_argument('--days', type=int,
                         help='Only fetch issues created in the last N days (uses Search API, much cheaper than --pages)')
    args = parser.parse_args()

    repos = [expand_repo(r) for r in args.repo.split(',')]

    if args.issue:
        view_issue(args.issue, repo=repos[0])
        return

    # Load or fetch issues
    if args.refresh or not ISSUES_CACHE.exists():
        if args.days:
            issues = fetch_issues_since(repos, args.days)
        else:
            issues = fetch_issues(repos, args.pages)
        if issues:
            save_issues(issues)
    else:
        issues = load_cached_issues()

    if not issues:
        print("No issues found", file=sys.stderr)
        return

    # Filter by search if specified
    if args.search:
        keyword = args.search.lower()
        issues = [i for i in issues if keyword in i['title'].lower() or
                  (i.get('body') and keyword in i['body'].lower())]
        print(f"Found {len(issues)} issues matching '{args.search}'")

    print_issues_list(issues)
    print(f"\nTotal: {len(issues)} open issues")
    print(f"\nUse --issue NUMBER to view details")

if __name__ == '__main__':
    main()
