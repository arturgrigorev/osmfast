"""Load command documentation from JSON files.

This module provides a centralized way to access command documentation,
eliminating duplication across help_cmd.py, setup_parser functions, and HTML docs.
"""

import json
import re
from pathlib import Path
from typing import Dict, Optional, List

# Cache for loaded docs
_docs_cache: Dict[str, dict] = {}
_aliases_cache: Dict[str, str] = {}
_loaded = False

DOCS_DIR = Path(__file__).parent / "docs"


def _load_all_docs() -> None:
    """Load all command documentation from JSON files."""
    global _loaded
    if _loaded:
        return

    for json_file in DOCS_DIR.glob("*.json"):
        if json_file.name.startswith("_"):
            continue  # Skip schema and internal files

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                doc = json.load(f)

            name = doc.get("name", json_file.stem)
            _docs_cache[name] = doc

            # Register aliases
            for alias in doc.get("aliases", []):
                _aliases_cache[alias] = name
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load {json_file}: {e}")

    _loaded = True


def get_command_doc(command: str) -> Optional[dict]:
    """Get documentation for a command.

    Args:
        command: Command name (e.g., "stats", "extract")

    Returns:
        Documentation dict or None if not found
    """
    _load_all_docs()

    # Check direct documentation
    if command in _docs_cache:
        return _docs_cache[command].copy()

    # Check aliases
    if command in _aliases_cache:
        base_cmd = _aliases_cache[command]
        if base_cmd in _docs_cache:
            doc = _docs_cache[base_cmd].copy()
            doc["note"] = f"This command is similar to '{base_cmd}'. See 'osmfast help {base_cmd}' for detailed documentation."
            return doc

    return None


def get_summary(command: str) -> str:
    """Get one-line summary for argparse help.

    Args:
        command: Command name

    Returns:
        Summary string or empty string if not found
    """
    doc = get_command_doc(command)
    return doc.get("summary", "") if doc else ""


def get_description(command: str) -> str:
    """Get full description for argparse description.

    Args:
        command: Command name

    Returns:
        Description string or empty string if not found
    """
    doc = get_command_doc(command)
    return doc.get("description", "") if doc else ""


def get_option_help(command: str, option: str) -> str:
    """Get help text for a specific option.

    Args:
        command: Command name
        option: Option key (e.g., "-o, --output" or "--output" or "--mode/-m")

    Returns:
        Help string or empty string if not found
    """
    doc = get_command_doc(command)
    if not doc:
        return ""

    options = doc.get("options", {})

    # Try exact match first
    if option in options:
        return options[option]

    # Normalize the option for flexible matching
    # Extract all option variants (e.g., "-o", "--output" from "-o, --output" or "-o/--output")
    option_parts = set(re.split(r'[,/\s]+', option.strip()))

    # Try finding by any matching part
    for key, value in options.items():
        key_parts = set(re.split(r'[,/\s]+', key.strip()))
        # If any option part matches
        if option_parts & key_parts:
            return value

    return ""


def list_documented_commands() -> List[str]:
    """Get list of all documented commands.

    Returns:
        Sorted list of command names
    """
    _load_all_docs()
    return sorted(_docs_cache.keys())


def list_all_commands() -> List[str]:
    """Get list of all commands including aliases.

    Returns:
        Sorted list of all command names and aliases
    """
    _load_all_docs()
    all_cmds = set(_docs_cache.keys()) | set(_aliases_cache.keys())
    return sorted(all_cmds)


def get_related_commands(command: str) -> List[str]:
    """Get related commands for a given command.

    Args:
        command: Command name

    Returns:
        List of related command names
    """
    doc = get_command_doc(command)
    return doc.get("related", []) if doc else []


def reload_docs() -> None:
    """Force reload of all documentation from disk."""
    global _loaded
    _docs_cache.clear()
    _aliases_cache.clear()
    _loaded = False
    _load_all_docs()
