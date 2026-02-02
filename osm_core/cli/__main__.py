"""Allow running osm_core.cli as a module.

Usage:
    python -m osm_core.cli --help
    python -m osm_core.cli extract map.osm features.json
"""

import sys
from osm_core.cli import main

if __name__ == "__main__":
    sys.exit(main())
