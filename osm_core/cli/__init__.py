"""Command-line interface for OSMFast.

This module provides the CLI entry point for the osmfast command.
It is used by setuptools to create the console script.

Usage:
    # After pip install:
    osmfast --help
    osmfast extract map.osm features.json
    osmfast stats map.osm

    # Or via Python:
    python -m osm_core.cli
"""

import sys
from osm_core.cli.main import main as _main, create_parser

__all__ = ['main', 'create_parser']


def main() -> int:
    """Entry point for the osmfast CLI.

    This function is called by the console script created by setuptools.
    It wraps the actual main function to ensure proper exit code handling.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    try:
        return _main() or 0
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"osmfast: fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
