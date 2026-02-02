#!/usr/bin/env python3
"""Check documentation coverage - find undocumented commands."""

import json
import re
import subprocess
import sys
from pathlib import Path

DOCS_DIR = Path("osm_core/cli/docs")


def get_documented_commands():
    """Get all documented command names."""
    commands = set()
    for f in DOCS_DIR.glob("*.json"):
        if f.name.startswith("_"):
            continue
        try:
            doc = json.loads(f.read_text(encoding='utf-8'))
            commands.add(doc.get("name", f.stem))
            # Also add aliases
            for alias in doc.get("aliases", []):
                commands.add(alias)
        except Exception:
            pass
    return commands


def get_cli_commands():
    """Get all CLI subcommands by parsing main.py."""
    commands = set()
    main_py = Path("osm_core/cli/main.py")

    if main_py.exists():
        content = main_py.read_text(encoding='utf-8')
        # Find subparser.add_parser calls
        for match in re.finditer(r"add_parser\s*\(\s*['\"](\w[\w-]*)['\"]", content):
            commands.add(match.group(1))

    # Also check commands directory - parse actual command names from add_parser calls
    cmd_dir = Path("osm_core/cli/commands")
    if cmd_dir.exists():
        for f in cmd_dir.glob("*.py"):
            if f.name.startswith("_") or f.name == "__init__.py":
                continue
            content = f.read_text(encoding='utf-8')
            # Extract actual command name from add_parser call
            match = re.search(r"add_parser\s*\(\s*['\"](\w[\w-]*)['\"]", content)
            if match:
                commands.add(match.group(1))
            elif "setup_parser" in content or "def run" in content:
                # Fallback to filename-based name
                cmd_name = f.stem.replace("_", "-")
                commands.add(cmd_name)

    return commands


def main():
    print("=" * 60)
    print("DOCUMENTATION COVERAGE CHECK")
    print("=" * 60)
    print()

    documented = get_documented_commands()
    cli_commands = get_cli_commands()

    # Exclude utility commands that don't need docs
    exclude = {'help', 'version', 'help-cmd'}
    cli_commands -= exclude

    print(f"Documented commands: {len(documented)}")
    print(f"CLI commands found: {len(cli_commands)}")
    print()

    # Find undocumented commands
    undocumented = cli_commands - documented
    if undocumented:
        print("UNDOCUMENTED COMMANDS:")
        for cmd in sorted(undocumented):
            print(f"  - {cmd}")
    else:
        print("All CLI commands are documented!")

    print()

    # Find docs without matching CLI command (orphaned docs)
    orphaned = documented - cli_commands - exclude
    # Filter out known items that are intentional
    # - gui: separate script (osmfast_gui.py), not a subcommand
    # - worship, cycling: aliases defined in other docs (poi.json, bikeability.json)
    known_special = {'cycling', 'version', 'help', 'gui', 'worship'}
    orphaned -= known_special

    if orphaned:
        print("ORPHANED DOCS (no matching CLI command):")
        for cmd in sorted(orphaned):
            print(f"  - {cmd}")
    else:
        print("No orphaned documentation found!")

    print()
    print("=" * 60)

    return len(undocumented) + len(orphaned)


if __name__ == "__main__":
    sys.exit(main())
