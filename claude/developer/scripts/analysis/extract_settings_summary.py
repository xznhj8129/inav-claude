#!/usr/bin/env python3
"""Condense inav/src/main/fc/settings.yaml into one line per setting.

Drops C-level plumbing (field, headers, type, condition) that isn't needed
to judge whether a setting should exist per
inav/docs/development/settings/when-to-add-a-setting.md. Keeps only
what's needed to judge each setting: name, owning group, default, valid
range/table, and description.

Usage: extract_settings_summary.py [settings.yaml path] > settings_condensed.txt
Then split the output into batches for parallel review, e.g.:
    split -l 120 -d --additional-suffix=.txt settings_condensed.txt batch_
"""
import sys
import yaml

path = sys.argv[1] if len(sys.argv) > 1 else "inav/src/main/fc/settings.yaml"

with open(path) as f:
    data = yaml.safe_load(f)

for group in data.get("groups", []):
    group_name = group.get("name", "?")
    for member in group.get("members", []):
        name = member.get("name", "?")
        default = member.get("default_value", "")
        lo = member.get("min", "")
        hi = member.get("max", "")
        table = member.get("table", "")
        rng = f"table={table}" if table else (f"{lo}..{hi}" if (lo != "" or hi != "") else "")
        desc = (member.get("description") or "").replace("\n", " ").strip()
        print(f"{group_name}: {name} = {default} [{rng}] -- {desc}")
