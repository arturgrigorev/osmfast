"""Detailed help command for OSMFast CLI."""

import sys
from typing import Optional

from ..docs_loader import (
    get_command_doc,
    list_documented_commands as get_documented_list,
    list_all_commands,
)


def format_help(doc: dict) -> str:
    """Format command documentation for display."""
    lines = []

    # Header
    lines.append("=" * 70)
    lines.append(f"OSMFAST {doc['name'].upper()}")
    lines.append("=" * 70)
    lines.append("")

    # Summary
    lines.append(doc["summary"])
    lines.append("")

    # Note for aliases
    if "note" in doc:
        lines.append(f"Note: {doc['note']}")
        lines.append("")

    # Description
    lines.append("DESCRIPTION")
    lines.append("-" * 40)
    lines.append(doc["description"].strip())
    lines.append("")

    # Usage
    lines.append("USAGE")
    lines.append("-" * 40)
    for usage in doc["usage"]:
        lines.append(f"  {usage}")
    lines.append("")

    # Options
    if "options" in doc:
        lines.append("OPTIONS")
        lines.append("-" * 40)
        for opt, desc in doc["options"].items():
            lines.append(f"  {opt}")
            lines.append(f"      {desc}")
        lines.append("")

    # Examples
    if "examples" in doc:
        lines.append("EXAMPLES")
        lines.append("-" * 40)
        for item in doc["examples"]:
            # Handle both list and tuple formats
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                title, cmd = item[0], item[1]
            else:
                continue
            lines.append(f"  # {title}")
            lines.append(f"  {cmd}")
            lines.append("")

    # Output
    if "output" in doc:
        lines.append("OUTPUT")
        lines.append("-" * 40)
        lines.append(doc["output"].strip())
        lines.append("")

    # Related commands
    if "related" in doc:
        lines.append("SEE ALSO")
        lines.append("-" * 40)
        related = ", ".join(f"osmfast {cmd}" for cmd in doc["related"])
        lines.append(f"  {related}")
        lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


def list_documented_commands() -> str:
    """List all commands with documentation available."""
    from ..docs_loader import _docs_cache, _aliases_cache, _load_all_docs
    _load_all_docs()

    lines = []
    lines.append("=" * 70)
    lines.append("OSMFAST HELP - Available Command Documentation")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Usage: osmfast help <command>")
    lines.append("")
    lines.append("Commands with detailed documentation:")
    lines.append("-" * 40)

    for cmd in sorted(_docs_cache.keys()):
        doc = _docs_cache[cmd]
        lines.append(f"  {cmd:20} {doc['summary']}")

    lines.append("")
    lines.append("Additional commands (see related command for docs):")
    lines.append("-" * 40)

    for cmd, base in sorted(_aliases_cache.items()):
        lines.append(f"  {cmd:20} (see: {base})")

    lines.append("")
    lines.append("For basic usage of any command: osmfast <command> --help")
    lines.append("For detailed documentation: osmfast help <command>")
    lines.append("=" * 70)

    return "\n".join(lines)


def run(args) -> int:
    """Execute the help command."""
    command = getattr(args, 'command_name', None)

    if not command:
        # List all documented commands
        print(list_documented_commands())
        return 0

    # Get documentation for specific command
    doc = get_command_doc(command)

    if doc:
        print(format_help(doc))
        return 0
    else:
        print(f"No detailed documentation for '{command}'.")
        print(f"Try 'osmfast {command} --help' for basic usage.")
        print(f"Use 'osmfast help' to list documented commands.")
        return 1


def setup_parser(subparsers):
    """Setup the help subcommand parser."""
    parser = subparsers.add_parser(
        'help',
        help='Show detailed help for a command',
        description='Display comprehensive documentation for OSMFast commands'
    )
    parser.add_argument(
        'command_name',
        nargs='?',
        help='Command to get help for'
    )
    parser.set_defaults(func=run)
    return parser
