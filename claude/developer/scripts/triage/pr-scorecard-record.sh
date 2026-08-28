#!/bin/bash
# pr-scorecard-record.sh - Record or list PR scorecard results
#
# Writes a scored PR to pr-scorecard-history.json in the same directory.
# Once recorded, pr-scorecard.sh will return the cached result for 14 days.
#
# Usage:
#   Record a score:
#     pr-scorecard-record.sh <owner/repo> <PR_NUMBER> <SCORE> <LABEL> [TITLE] [URL]
#
#   List recent scored PRs:
#     pr-scorecard-record.sh --list [owner/repo]
#
# Examples:
#   pr-scorecard-record.sh iNavFlight/inav 11220 74 "Looking Good" "Fix nav bug" "https://github.com/..."
#   pr-scorecard-record.sh --list
#   pr-scorecard-record.sh --list iNavFlight/inav

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CACHE_FILE="$(cd "$SCRIPT_DIR/../../../local-data/triage" 2>/dev/null && pwd)/pr-scorecard-history.json"
mkdir -p "$(dirname "$CACHE_FILE")"

# ---------------------------------------------------------------------------
# --list mode
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--list" ]]; then
    FILTER_REPO="${2:-}"

    if [[ ! -f "$CACHE_FILE" ]]; then
        echo "No scorecard history yet. (${CACHE_FILE} does not exist)"
        exit 0
    fi

    TODAY_TS=$(date +%s)

    echo "============================================================"
    echo "PR SCORECARD HISTORY"
    if [[ -n "$FILTER_REPO" ]]; then
        echo "Repo filter: $FILTER_REPO"
    fi
    echo "============================================================"
    printf "%-45s  %-6s  %-18s  %-12s  %-12s  %s\n" \
        "PR" "SCORE" "LABEL" "SCORED" "EXPIRES" "STATUS"
    echo "------------------------------------------------------------------------------------------------------------------------------"

    jq -r --arg filter "$FILTER_REPO" --argjson now "$TODAY_TS" '
        to_entries |
        map(select($filter == "" or (.key | startswith($filter)))) |
        sort_by(.value.scored_at) | reverse |
        .[] |
        (.value.expires_at | strptime("%Y-%m-%d") | mktime) as $exp |
        (if $exp > $now then "fresh" else "expired" end) as $status |
        [.key, (.value.score | tostring), .value.label, .value.scored_at, .value.expires_at, $status] |
        @tsv
    ' "$CACHE_FILE" 2>/dev/null | \
    while IFS=$'\t' read -r key score label scored expires status; do
        printf "%-45s  %-6s  %-18s  %-12s  %-12s  %s\n" \
            "$key" "$score" "$label" "$scored" "$expires" "$status"
    done

    echo ""
    TOTAL=$(jq 'keys | length' "$CACHE_FILE" 2>/dev/null || echo 0)
    echo "Total entries: $TOTAL"
    exit 0
fi

# ---------------------------------------------------------------------------
# Record mode
# ---------------------------------------------------------------------------
REPO="${1:?Usage: pr-scorecard-record.sh <owner/repo> <PR_NUMBER> <SCORE> <LABEL> [TITLE] [URL]}"
PR_NUMBER="${2:?Usage: pr-scorecard-record.sh <owner/repo> <PR_NUMBER> <SCORE> <LABEL> [TITLE] [URL]}"
SCORE="${3:?Usage: pr-scorecard-record.sh <owner/repo> <PR_NUMBER> <SCORE> <LABEL> [TITLE] [URL]}"
LABEL="${4:?Usage: pr-scorecard-record.sh <owner/repo> <PR_NUMBER> <SCORE> <LABEL> [TITLE] [URL]}"
TITLE="${5:-}"
URL="${6:-}"

# Validate score is a number 0-100
if ! [[ "$SCORE" =~ ^[0-9]+$ ]] || [[ "$SCORE" -gt 100 ]]; then
    echo "Error: SCORE must be an integer 0-100 (got: $SCORE)" >&2
    exit 1
fi

TODAY=$(date +%Y-%m-%d)
EXPIRES=$(date -d "+14 days" +%Y-%m-%d)
CACHE_KEY="${REPO}/${PR_NUMBER}"

# Create cache file if it doesn't exist
if [[ ! -f "$CACHE_FILE" ]]; then
    echo "{}" > "$CACHE_FILE"
fi

# Build the entry and merge into the cache file
ENTRY=$(jq -n \
    --arg scored_at  "$TODAY" \
    --arg expires_at "$EXPIRES" \
    --argjson score  "$SCORE" \
    --arg lbl        "$LABEL" \
    --arg title      "$TITLE" \
    --arg url        "$URL" \
    '{
        "scored_at":  $scored_at,
        "expires_at": $expires_at,
        "score":      $score,
        "label":      $lbl,
        "title":      $title,
        "url":        $url
    }')

UPDATED=$(jq --arg key "$CACHE_KEY" --argjson entry "$ENTRY" \
    '.[$key] = $entry' "$CACHE_FILE")
echo "$UPDATED" > "$CACHE_FILE"

echo "Recorded: $CACHE_KEY"
echo "  Score:   $SCORE / 100"
echo "  Label:   $LABEL"
echo "  Scored:  $TODAY"
echo "  Expires: $EXPIRES"
echo "  Cached in: $CACHE_FILE"
