# OSMFast

**Ultra-High Performance OpenStreetMap Data Extraction & Analysis Tool**

OSMFast is a blazing-fast, pure Python tool for extracting, analyzing, and transforming OpenStreetMap (OSM) data. It combines memory-mapped I/O, regex pattern caching, and streaming architecture to achieve **7,000+ features/second** with constant memory usage.

## Features

- **High Performance**: Memory-mapped parsing with LRU pattern cache
- **Zero Dependencies**: Pure Python 3 standard library only (pyshp optional for Shapefile)
- **60+ Commands**: Comprehensive CLI for all OSM operations
- **Multiple Formats**: GeoJSON, JSON, CSV, OSM XML, GraphML, Shapefile export
- **Shapefile Export**: Full geometry calculations (length, sinuosity, bearing, lane-km)
- **Road Hierarchy**: Flexible filtering by road levels and infrastructure (bridges, tunnels)
- **Specialized Extraction**: Traffic safety, cycling infrastructure, road network scripts
- **Routing & Analysis**: A* routing, isochrones, network analysis
- **Osmosis Compatible**: Familiar filtering syntax
- **Python API**: Use as a library in your projects

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/osmfast.git
cd osmfast

# Run directly (no installation needed)
python osmfast.py --help

# Or install in development mode
pip install -e .

# Launch the GUI (optional)
python osmfast_gui.py
```

### Requirements

- Python 3.8+
- No external dependencies for core functionality

**Optional:**
- `pyshp` - For Shapefile export (`pip install pyshp`)

## Quick Start

```bash
# Extract all features to GeoJSON
osmfast extract city.osm -o features.geojson

# Get file statistics
osmfast stats city.osm

# Find nearest restaurants
osmfast nearest city.osm --lat 51.5 --lon -0.1 --filter "amenity=restaurant"

# Calculate a driving route
osmfast route city.osm --origin "51.5,-0.1" --destination "51.6,-0.2"

# Export road network as graph
osmfast network city.osm -o graph.json --mode drive
```

## CLI Commands

OSMFast provides 60+ git-style subcommands organized by category:

### Data Extraction

| Command | Description |
|---------|-------------|
| `extract` | Extract features with Osmosis-compatible filtering |
| `filter` | Filter OSM data, output filtered OSM |
| `convert` | Convert between formats (OSM, GeoJSON, JSON, CSV) |
| `merge` | Merge multiple OSM files |
| `clip` | Clip data by polygon boundary |
| `split` | Split large files into tiles |
| `sample` | Random sample of features |
| `head` | First N elements from file |

### Feature Extraction

| Command | Description |
|---------|-------------|
| `poi` | Extract points of interest by category |
| `buildings` | Extract buildings with height estimation |
| `roads` | Extract road network with attributes |
| `amenity` | Extract amenities (restaurants, banks, etc.) |
| `shop` | Extract shops and retail |
| `food` | Extract food-related POIs |
| `healthcare` | Extract hospitals, clinics, pharmacies |
| `education` | Extract schools, universities |
| `tourism` | Extract tourist attractions |
| `leisure` | Extract parks, sports facilities |
| `natural` | Extract natural features |
| `water` | Extract water bodies |
| `landuse` | Extract land use areas |
| `trees` | Extract trees and forests |
| `parking` | Extract parking facilities |
| `transit` | Extract public transit stops |
| `railway` | Extract railway infrastructure |
| `power` | Extract power infrastructure |
| `historic` | Extract historic sites |
| `emergency` | Extract emergency services |
| `barrier` | Extract barriers and fences |
| `boundary` | Extract administrative boundaries |

### Routing & Navigation

| Command | Description |
|---------|-------------|
| `route` | Calculate shortest/fastest route |
| `route-multi` | Multi-stop route planning |
| `directions` | Turn-by-turn navigation directions |
| `isochrone` | Generate travel time polygons |
| `alternatives` | Find alternative routes |
| `distance-matrix` | Calculate distances between multiple points |
| `nearest-road` | Find nearest road to a point |

### Network Analysis

| Command | Description |
|---------|-------------|
| `network` | Export road network as graph (GraphML, JSON) |
| `connectivity` | Analyze network connectivity |
| `centrality` | Find central nodes in network |
| `bottleneck` | Identify network bottlenecks |
| `detour-factor` | Calculate route directness |

### Spatial Operations

| Command | Description |
|---------|-------------|
| `nearest` | Find K nearest features |
| `within` | Find features within polygon |
| `buffer` | Create buffer zones around features |
| `centroid` | Calculate centroids of ways |
| `bbox` | Extract/calculate bounding box |
| `densify` | Add points to geometries |
| `simplify` | Simplify geometries |
| `nearby-features` | Find features near a point |

### Data Analysis

| Command | Description |
|---------|-------------|
| `stats` | Comprehensive file statistics |
| `count` | Quick element counting |
| `tags` | Analyze tag usage |
| `unique` | Find unique tag values |
| `names` | Extract all named features |
| `address` | Extract addresses |
| `surface` | Analyze road surfaces |
| `info` | Quick file information |

### Data Manipulation

| Command | Description |
|---------|-------------|
| `sort` | Sort elements by attribute |
| `join` | Join OSM data with external data |
| `lookup` | Look up elements by ID |
| `search` | Search by name or tag |

## Command Examples

### Extract Features

```bash
# Extract all features
osmfast extract map.osm -o features.json

# Extract with format
osmfast extract map.osm -f geojson -o features.geojson
osmfast extract map.osm -f csv -o features.csv

# Filter by tag (Osmosis-compatible syntax)
osmfast extract --accept-nodes amenity=restaurant map.osm -o restaurants.json
osmfast extract --accept-ways highway=* --used-node map.osm -o roads.json

# Filter by bounding box
osmfast extract --bbox 51.5 -0.2 51.4 -0.1 london.osm -o area.json

# Combine filters
osmfast extract \
  --accept-nodes amenity=cafe,restaurant \
  --reject-nodes cuisine=fast_food \
  --bbox 51.5 -0.2 51.4 -0.1 \
  london.osm -o food.json
```

### Routing

```bash
# Basic route
osmfast route map.osm \
  --origin "51.5,-0.1" \
  --destination "51.6,-0.2" \
  --mode drive

# Route with GeoJSON output
osmfast route map.osm \
  --origin "51.5,-0.1" \
  --destination "51.6,-0.2" \
  -f geojson -o route.geojson

# Walking directions
osmfast directions map.osm \
  --origin "51.5,-0.1" \
  --destination "51.51,-0.11" \
  --mode walk

# Multi-stop route
osmfast route-multi map.osm \
  --waypoints "51.5,-0.1;51.52,-0.12;51.55,-0.15" \
  --mode drive

# Isochrone (5, 10, 15 minute walking)
osmfast isochrone map.osm \
  --lat 51.5 --lon -0.1 \
  --time "5,10,15" \
  --mode walk \
  -o isochrone.geojson
```

### Network Analysis

```bash
# Export as JSON graph
osmfast network map.osm -o graph.json --mode drive

# Export as GraphML for NetworkX/Gephi
osmfast network map.osm -o graph.graphml -f graphml

# Directed graph with speeds
osmfast network map.osm -o graph.json \
  --directed --include-speeds

# Network statistics only
osmfast network map.osm --stats --mode drive

# Connectivity analysis
osmfast connectivity map.osm --mode drive

# Find bottlenecks
osmfast bottleneck map.osm --top 10
```

### POI Extraction

```bash
# All POIs
osmfast poi map.osm -o pois.geojson

# Specific category
osmfast poi map.osm --category food -o restaurants.geojson

# List categories
osmfast poi map.osm --list-categories

# Named POIs only
osmfast poi map.osm --named-only -o named_pois.json

# Buildings with height estimation
osmfast buildings map.osm -o buildings.geojson

# Roads with attributes
osmfast roads map.osm -o roads.geojson --class major
```

### Spatial Queries

```bash
# Find 5 nearest cafes
osmfast nearest map.osm \
  --lat 51.5 --lon -0.1 \
  --filter "amenity=cafe" \
  -k 5

# Find features within polygon
osmfast within map.osm \
  --polygon boundary.geojson \
  -o features_in_area.geojson

# Create 500m buffer around hospitals
osmfast buffer map.osm \
  --filter "amenity=hospital" \
  --radius 500m \
  -o hospital_buffers.geojson
```

### File Statistics

```bash
# Full statistics
osmfast stats map.osm

# Summary only
osmfast stats --summary map.osm

# JSON output for processing
osmfast stats --json map.osm > stats.json

# Count specific elements
osmfast count map.osm --filter "highway=*"
osmfast count map.osm --by highway --top 20
```

## Graphical Interface (GUI)

OSMFast includes an optional GUI for users who prefer a visual interface:

```bash
python osmfast_gui.py
```

### GUI Features

- **Command Browser**: Browse all 60+ commands organized by category
- **Interactive Builder**: Build commands with file pickers and dropdowns
- **Autocomplete Search**: Quickly find commands by typing in the search box
- **Command Runner**: Execute commands and view output in real-time
- **Recent Files**: Quick access to recently used OSM files
- **Command History**: Browse and reuse previous commands
- **Quick Examples**: One-click access to common command patterns

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open OSM file |
| `F5` / `Ctrl+R` | Run command |
| `Escape` | Stop running command |
| `Ctrl+C` | Copy command to clipboard |
| `Ctrl+K` | Clear arguments |
| `Ctrl+L` | Clear output |

## Python API

### Basic Usage

```python
from osm_core import OSMFast, OSMFilter

# Simple extraction
extractor = OSMFast()
result = extractor.extract_features('map.osm')

# Access extracted data
amenities = result['features']['amenities']
highways = result['features']['highways']
buildings = result['features']['buildings']

for amenity in amenities:
    print(f"{amenity.name}: {amenity.category}")
```

### With Filtering

```python
from osm_core import OSMFast, OSMFilter

# Create filter
osm_filter = OSMFilter()
osm_filter.add_accept_filter('nodes', 'amenity', 'restaurant')
osm_filter.add_accept_filter('nodes', 'amenity', 'cafe')
osm_filter.set_bounding_box(51.5, -0.2, 51.4, -0.1)  # top, left, bottom, right

# Extract with filter
extractor = OSMFast(osm_filter)
result = extractor.extract_features('london.osm')
```

### Direct Parser Access

```python
from osm_core import UltraFastOSMParser

parser = UltraFastOSMParser()
nodes, ways = parser.parse_file_ultra_fast('map.osm')

# Process nodes
for node in nodes:
    if 'amenity' in node.tags:
        print(f"Found {node.tags['amenity']} at {node.lat}, {node.lon}")

# Process ways
for way in ways:
    if 'highway' in way.tags:
        print(f"Road: {way.tags.get('name', 'unnamed')}")
```

### Models

```python
from osm_core import OSMNode, OSMWay, SemanticFeature

# Create node
node = OSMNode(
    id="12345",
    lat=51.5,
    lon=-0.1,
    tags={"amenity": "restaurant", "name": "Pizza Place"}
)

# Convert to GeoJSON
geojson = node.to_geojson_feature()

# Create way
way = OSMWay(
    id="67890",
    node_refs=["1", "2", "3", "1"],  # Closed polygon
    tags={"building": "residential"}
)

print(f"Is closed: {way.is_closed}")
print(f"Is area: {way.is_area}")
```

## Export Formats

| Format | Extension | Description | Use Case |
|--------|-----------|-------------|----------|
| GeoJSON | `.geojson` | GeoJSON FeatureCollection | GIS software, web maps |
| JSON | `.json` | Structured JSON | APIs, processing |
| CSV | `.csv` | Comma-separated values | Spreadsheets, databases |
| OSM | `.osm` | OSM XML format | OSM tools, JOSM |
| GraphML | `.graphml` | Graph XML format | NetworkX, Gephi, igraph |
| Shapefile | `.shp` | ESRI Shapefile (requires pyshp) | ArcGIS, QGIS, desktop GIS |
| Text | stdout | Human-readable | Terminal output |

### Format Examples

```bash
# GeoJSON for web maps
osmfast extract map.osm -f geojson -o data.geojson

# CSV for spreadsheets
osmfast poi map.osm -f csv -o pois.csv

# GraphML for network analysis
osmfast network map.osm -f graphml -o graph.graphml

# OSM XML for other tools
osmfast filter --accept-ways highway=* map.osm -o roads.osm

# Shapefile with road geometry
osmfast extract map.osm -f shapefile --road-geometry -o roads
```

## Shapefile Export with Road Geometry

Extract roads to Shapefile format with calculated geometry attributes:

```bash
# Basic shapefile export with road geometry
osmfast extract --format shapefile --road-geometry city.osm roads

# Filter by road hierarchy level
osmfast extract --format shapefile --road-levels main city.osm main_roads
osmfast extract --format shapefile --road-levels 1,2,3 city.osm arterials

# Extract infrastructure (bridges, tunnels)
osmfast extract --format shapefile --road-levels main --infrastructure bridges city.osm bridges
osmfast extract --format shapefile --infrastructure tunnels --only-infrastructure city.osm tunnels_only
```

### Road Hierarchy Levels

| Level | Name | Highway Types |
|-------|------|---------------|
| 1 | Freeways | motorway, motorway_link |
| 2 | Arterials | trunk, trunk_link, primary, primary_link |
| 3 | Collectors | secondary, secondary_link, tertiary, tertiary_link |
| 4 | Local | residential, unclassified, living_street |
| 5 | Service | service, track, road |
| 6 | Non-motorized | pedestrian, footway, cycleway, path, steps |

**Presets:** `motorway`, `arterial`, `main`, `driveable`, `all`

### Infrastructure Filters

| Filter | Description |
|--------|-------------|
| `bridges` | Bridge segments (bridge=yes, viaduct, etc.) |
| `tunnels` | Tunnel segments (tunnel=yes, culvert, etc.) |
| `fords` | Ford crossings |
| `embankments` | Roads on embankments |
| `covered` | Covered ways |
| `all` | All infrastructure types |

### Geometry Attributes

Shapefile exports include calculated fields:

| Field | Description |
|-------|-------------|
| `length_m` | Segment length in meters |
| `length_km` | Segment length in kilometers |
| `sinuosity` | Curvature ratio (1.0 = straight) |
| `bearing` | Direction in degrees (0-360) |
| `speed_kph` | Speed from maxspeed tag or default |
| `travel_min` | Estimated travel time in minutes |
| `lanes` | Number of lanes |
| `lane_km` | lanes × length_km |
| `has_sidwlk` | Has sidewalk (1/0) |
| `is_lit` | Has street lighting (1/0) |
| `is_oneway` | One-way street (1/0) |
| `bridge` | Bridge type if applicable |
| `tunnel` | Tunnel type if applicable |

## Specialized Extraction Scripts

Standalone scripts for domain-specific extraction:

### Road Network Extraction

```bash
# Extract all roads with geometry calculations
python extract_roads_geometry.py city.osm output_dir

# Creates:
# - roads_all_geometry.shp (all roads)
# - roads_motorway_geometry.shp (by category)
# - roads_primary_geometry.shp
# - ...etc
```

### Traffic Safety Extraction

```bash
# Extract traffic safety features
python extract_traffic_safety.py city.osm output_dir

# Extracts:
# - Traffic signals
# - Pedestrian crossings
# - Stop/give way signs
# - Speed cameras
# - Street lamps
# - Traffic calming (humps, chicanes)
# - Safety barriers (bollards, guard rails)
```

### Cycling Infrastructure Extraction

```bash
# Extract cycling infrastructure
python extract_cycling.py city.osm output_dir

# Extracts:
# - Dedicated cycleways
# - Shared paths with bicycle access
# - Roads with cycle lanes
# - Roads with bicycle designation
# - Bicycle parking
# - Bicycle rental stations
# - Bicycle repair stations
# - Bicycle shops
```

### Flexible Network Extraction

```bash
# Flexible extraction with road levels and infrastructure filters
python extract_network.py city.osm output_dir --levels main --infrastructure bridges,tunnels

# Options:
# --levels LEVELS       Road levels (1-6) or presets (motorway/arterial/main/driveable/all)
# --infrastructure TYPE  Filter: bridges,tunnels,fords,embankments,covered,all
# --only-infrastructure  Only extract roads with specified infrastructure
# --split-by-type       Create separate shapefiles by highway type
# --split-by-infra      Create separate shapefiles by infrastructure type
```

## Performance

OSMFast is optimized for speed and memory efficiency:

| Metric | Value |
|--------|-------|
| Parsing Speed | 7,000+ features/second |
| Memory Usage | Constant (streaming) |
| File Size Support | Tested up to 10GB |

### Performance Techniques

- **Memory-mapped I/O**: Direct file access without loading entire file
- **Regex Pattern Cache**: LRU cache with pre-compiled critical patterns
- **Generator Streaming**: Constant memory regardless of file size
- **Optimized Data Structures**: Frozensets for O(1) lookups

### Benchmarks

```bash
# Run performance tests
pytest tests/performance/ -v

# Quick benchmark
time osmfast stats large_file.osm
```

## Project Structure

```
osmfast/
├── osmfast.py                    # CLI entry point
├── extract_roads_geometry.py     # Road network extraction with geometry
├── extract_traffic_safety.py     # Traffic safety feature extraction
├── extract_cycling.py            # Cycling infrastructure extraction
├── extract_network.py            # Flexible network extraction with filters
├── osm_core/                     # Main package
│   ├── models/                   # Data models
│   │   ├── elements.py           # OSMNode, OSMWay, OSMRelation
│   │   ├── features.py           # SemanticFeature
│   │   └── statistics.py         # OSMStats
│   ├── filters/                  # Filtering system
│   │   ├── osm_filter.py         # Main OSMFilter class
│   │   ├── tag_filter.py         # Tag-based filtering
│   │   ├── bbox_filter.py        # Bounding box filtering
│   │   └── semantic_categories.py # Road levels, infrastructure types
│   ├── parsing/                  # Parsers
│   │   ├── mmap_parser.py        # UltraFastOSMParser
│   │   └── pattern_cache.py      # OptimizedPatternCache
│   ├── extraction/               # Feature extraction
│   ├── export/                   # Format exporters (JSON, GeoJSON, CSV, Shapefile)
│   ├── utils/                    # Utilities (geo_utils for geometry calculations)
│   └── cli/                      # CLI infrastructure
│       ├── main.py               # Command dispatcher
│       └── commands/             # 60+ subcommands
└── tests/                        # Test suite
    ├── unit/                     # Unit tests
    ├── integration/              # Integration tests
    ├── regression/               # Regression tests
    └── performance/              # Performance tests
```

## Testing

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_models.py -v

# Run specific test class
pytest tests/cli/test_network_command.py::TestNetworkBasicExport -v

# Run with coverage
pytest tests/ --cov=osm_core --cov-report=html
```

### Test Categories

- **Unit Tests**: Models, filters, parsers, utilities
- **Integration Tests**: End-to-end workflows, format output
- **Regression Tests**: Bug fixes (e.g., oneway=-1 handling)
- **Performance Tests**: Speed and memory benchmarks

## Configuration

OSMFast uses sensible defaults but can be configured:

### Speed Defaults (km/h)

| Highway Type | Speed |
|--------------|-------|
| motorway | 110 |
| trunk | 90 |
| primary | 60 |
| secondary | 50 |
| tertiary | 40 |
| residential | 30 |
| footway | 5 |
| cycleway | 15 |

### Travel Modes

| Mode | Allowed Roads |
|------|---------------|
| `drive` | motorway, trunk, primary, secondary, tertiary, residential, service |
| `walk` | footway, path, pedestrian, steps, residential |
| `bike` | cycleway, path, track, residential |
| `all` | All highway types |

## Common Use Cases

### GIS Analyst: Extract POIs for Web Map

```bash
osmfast poi city.osm \
  --category food \
  --named-only \
  -f geojson \
  -o restaurants.geojson
```

### Urban Planner: Road Network Analysis

```bash
# Extract major roads
osmfast roads city.osm \
  --class major \
  -o major_roads.geojson

# Analyze connectivity
osmfast connectivity city.osm --mode drive

# Find bottlenecks
osmfast bottleneck city.osm --top 20
```

### Data Scientist: Building Analysis

```bash
# Extract buildings with areas
osmfast buildings city.osm \
  -f csv \
  -o buildings.csv

# Process in Python/pandas
python -c "import pandas as pd; df = pd.read_csv('buildings.csv'); print(df.groupby('building')['area_sqm'].describe())"
```

### Developer: API Integration

```python
from osm_core import OSMFast

extractor = OSMFast()
result = extractor.extract_features('city.osm')

# Convert to API response
import json
response = {
    'restaurants': [
        {'name': a.name, 'lat': a.lat, 'lon': a.lon}
        for a in result['features']['amenities']
        if a.category == 'restaurant'
    ]
}
print(json.dumps(response))
```

## Troubleshooting

### Common Issues

**File not found error**
```bash
osmfast: error: File not found: 'map.osm'
```
Solution: Check file path and ensure file exists.

**No features extracted**
```bash
osmfast: warning: No features extracted
```
Solution: Check filter syntax, try `osmfast stats file.osm` to verify content.

**Memory issues with large files**
Solution: OSMFast uses streaming, but for very large files (>10GB), ensure sufficient system memory for the output.

### Getting Help

```bash
# General help
osmfast --help

# Command-specific help
osmfast extract --help
osmfast route --help
osmfast network --help
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `pytest tests/`
5. Submit a pull request

### Development Setup

```bash
git clone https://github.com/yourusername/osmfast.git
cd osmfast
pip install -e .
pytest tests/
```

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- OpenStreetMap contributors for the data
- Osmosis project for filter syntax inspiration
- Python community for the excellent standard library

---

**OSMFast** - Fast, simple, powerful OSM data extraction.
