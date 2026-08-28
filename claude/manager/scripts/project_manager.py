#!/usr/bin/env python3
"""
Project Manager - Query and manage INAV projects

This script helps manage the project index by:
- Listing projects by status
- Showing project details
- Generating compact summaries
- Querying by various criteria
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class Project:
    """Represents a project from INDEX.md"""
    name: str
    status: str  # TODO, IN_PROGRESS, COMPLETE, BACKBURNER, CANCELLED
    emoji: str
    priority: Optional[str] = None
    assignee: Optional[str] = None
    created: Optional[str] = None
    completed: Optional[str] = None
    location: Optional[str] = None
    line_start: int = 0
    line_end: int = 0

    @property
    def is_active(self):
        return self.status in ('TODO', 'IN_PROGRESS', 'BACKBURNER')

    @property
    def is_completed(self):
        return self.status in ('COMPLETE', 'CANCELLED')

def parse_index(index_path: Path) -> List[Project]:
    """Parse INDEX.md and extract all projects"""
    projects = []
    current_project = None

    with open(index_path) as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        # Match project headers
        match = re.match(r'^### ([📋🚧✅⏸️❌]) (.+)$', line)
        if match:
            # Save previous project
            if current_project:
                current_project.line_end = i - 1
                projects.append(current_project)

            # Start new project
            emoji = match.group(1)
            name = match.group(2)

            status_map = {
                '📋': 'TODO',
                '🚧': 'IN_PROGRESS',
                '✅': 'COMPLETE',
                '⏸️': 'BACKBURNER',
                '❌': 'CANCELLED'
            }

            current_project = Project(
                name=name,
                status=status_map.get(emoji, 'UNKNOWN'),
                emoji=emoji,
                line_start=i
            )

        # Extract metadata
        elif current_project:
            if match := re.match(r'\*\*Priority:\*\* (.+)', line):
                current_project.priority = match.group(1).strip()
            elif match := re.match(r'\*\*Assignee:\*\* (.+)', line):
                current_project.assignee = match.group(1).strip()
            elif match := re.match(r'\*\*Created:\*\* (.+)', line):
                current_project.created = match.group(1).strip()
            elif match := re.match(r'\*\*Completed:\*\* (.+)', line):
                current_project.completed = match.group(1).strip()
            elif match := re.match(r'\*\*Location:\*\* `(.+)`', line):
                current_project.location = match.group(1).strip()

    # Add last project
    if current_project:
        current_project.line_end = len(lines)
        projects.append(current_project)

    return projects

def list_projects(projects: List[Project], status: Optional[str] = None):
    """List projects, optionally filtered by status"""
    filtered = projects
    if status:
        filtered = [p for p in projects if p.status == status]

    print(f"\n{'Status':<15} {'Priority':<10} {'Project':<50} {'Created':<12}")
    print("=" * 100)

    for p in filtered:
        priority = p.priority or 'N/A'
        created = p.created or 'N/A'
        print(f"{p.emoji} {p.status:<12} {priority:<10} {p.name:<50} {created:<12}")

    print(f"\nTotal: {len(filtered)} projects")

def show_details(projects: List[Project], name: str):
    """Show full details for a specific project"""
    matches = [p for p in projects if name.lower() in p.name.lower()]

    if not matches:
        print(f"No project found matching '{name}'")
        return

    if len(matches) > 1:
        print(f"Multiple matches found for '{name}':")
        for p in matches:
            print(f"  - {p.name}")
        return

    p = matches[0]
    print(f"\n{p.emoji} {p.name}")
    print("=" * 80)
    print(f"Status:    {p.status}")
    print(f"Priority:  {p.priority or 'N/A'}")
    print(f"Assignee:  {p.assignee or 'N/A'}")
    print(f"Created:   {p.created or 'N/A'}")
    print(f"Completed: {p.completed or 'N/A'}")
    print(f"Location:  {p.location or 'N/A'}")
    print(f"Lines:     {p.line_start}-{p.line_end} ({p.line_end - p.line_start + 1} lines)")

def stats(projects: List[Project]):
    """Show project statistics"""
    by_status = {}
    for p in projects:
        by_status[p.status] = by_status.get(p.status, 0) + 1

    by_priority = {}
    for p in projects:
        if p.priority:
            by_priority[p.priority] = by_priority.get(p.priority, 0) + 1

    print("\n=== Project Statistics ===\n")

    print("By Status:")
    for status, count in sorted(by_status.items()):
        print(f"  {status:<15} {count:>3} projects")

    print(f"\nTotal Projects: {len(projects)}")
    print(f"Active Projects: {sum(1 for p in projects if p.is_active)}")
    print(f"Completed: {sum(1 for p in projects if p.is_completed)}")

    if by_priority:
        print("\nBy Priority:")
        for priority, count in sorted(by_priority.items()):
            print(f"  {priority:<15} {count:>3} projects")

def main():
    # Local project data lives in claude/projects/ (gitignored); this script is
    # framework tooling under claude/manager/scripts/.
    index_path = Path(__file__).resolve().parents[3] / "claude" / "projects" / "INDEX.md"

    if not index_path.exists():
        print(f"Error: INDEX.md not found at {index_path}")
        sys.exit(1)

    projects = parse_index(index_path)

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python project_manager.py list [status]")
        print("  python project_manager.py show <name>")
        print("  python project_manager.py stats")
        print("\nStatus options: TODO, IN_PROGRESS, COMPLETE, BACKBURNER, CANCELLED")
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        status = sys.argv[2].upper() if len(sys.argv) > 2 else None
        list_projects(projects, status)

    elif command == "show":
        if len(sys.argv) < 3:
            print("Usage: python project_manager.py show <name>")
            sys.exit(1)
        show_details(projects, sys.argv[2])

    elif command == "stats":
        stats(projects)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
