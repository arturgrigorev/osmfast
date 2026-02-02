"""Allow running osm_core as a module.

Usage:
    python -m osm_core --help
    python -m osm_core extract map.osm features.json
    python -m osm_core stats map.osm
"""

import sys
from osm_core.cli import main

if __name__ == "__main__":
    sys.exit(main())
