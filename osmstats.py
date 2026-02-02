#!/usr/bin/env python3
"""
OSMStats - OSM File Statistics and Analysis Tool

DEPRECATED: This script is deprecated. Use 'osmfast stats' instead.

Usage:
    osmfast stats map.osm
    osmfast stats --summary map.osm
    osmfast stats --json map.osm
"""
import sys
import warnings


def main():
    """Entry point that redirects to osmfast stats."""
    warnings.warn(
        "osmstats.py is deprecated. Use 'osmfast stats' instead.",
        DeprecationWarning,
        stacklevel=2
    )

    # Convert arguments to osmfast stats format
    args = ['stats'] + sys.argv[1:]

    from osm_core.cli.main import main as osmfast_main
    sys.exit(osmfast_main(args))


if __name__ == "__main__":
    main()
