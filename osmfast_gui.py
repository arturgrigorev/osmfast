#!/usr/bin/env python3
"""
OSMFast GUI - Graphical interface for OSMFast command-line tool.

A tkinter-based GUI application providing:
- Command reference browser with categories
- Interactive command builder with autocomplete
- Command runner with output display
- Example snippets and documentation

Usage:
    python osmfast_gui.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import threading
import os
import sys
import json
import shlex
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Import centralized documentation loader
try:
    from osm_core.cli.docs_loader import (
        get_command_doc, get_summary, get_description,
        get_related_commands, get_option_help
    )
    DOCS_AVAILABLE = True
except ImportError:
    DOCS_AVAILABLE = False
    def get_command_doc(cmd): return None
    def get_summary(cmd): return ""
    def get_description(cmd): return ""
    def get_related_commands(cmd): return []
    def get_option_help(cmd, opt): return ""


# =============================================================================
# Common Filter Values (for autocomplete dropdowns)
# =============================================================================

COMMON_NODE_FILTERS = [
    "amenity=restaurant",
    "amenity=cafe",
    "amenity=bar",
    "amenity=pub",
    "amenity=fast_food",
    "amenity=hospital",
    "amenity=clinic",
    "amenity=pharmacy",
    "amenity=school",
    "amenity=university",
    "amenity=bank",
    "amenity=atm",
    "amenity=fuel",
    "amenity=parking",
    "amenity=police",
    "amenity=fire_station",
    "amenity=post_office",
    "amenity=library",
    "amenity=theatre",
    "amenity=cinema",
    "amenity=*",
    "shop=supermarket",
    "shop=convenience",
    "shop=clothes",
    "shop=bakery",
    "shop=butcher",
    "shop=*",
    "tourism=hotel",
    "tourism=guest_house",
    "tourism=museum",
    "tourism=attraction",
    "tourism=*",
    "leisure=park",
    "leisure=playground",
    "leisure=sports_centre",
    "leisure=*",
    "natural=tree",
    "natural=water",
    "natural=*",
    "historic=monument",
    "historic=castle",
    "historic=*",
]

COMMON_WAY_FILTERS = [
    "highway=motorway",
    "highway=trunk",
    "highway=primary",
    "highway=secondary",
    "highway=tertiary",
    "highway=residential",
    "highway=service",
    "highway=footway",
    "highway=cycleway",
    "highway=path",
    "highway=*",
    "building=yes",
    "building=residential",
    "building=commercial",
    "building=industrial",
    "building=*",
    "landuse=residential",
    "landuse=commercial",
    "landuse=industrial",
    "landuse=forest",
    "landuse=*",
    "waterway=river",
    "waterway=stream",
    "waterway=canal",
    "waterway=*",
    "railway=rail",
    "railway=subway",
    "railway=tram",
    "railway=*",
    "natural=water",
    "natural=wood",
    "natural=*",
    "boundary=administrative",
    "boundary=*",
]

COMMON_AMENITY_TYPES = [
    "restaurant",
    "cafe",
    "bar",
    "pub",
    "fast_food",
    "hospital",
    "clinic",
    "doctors",
    "pharmacy",
    "school",
    "university",
    "college",
    "kindergarten",
    "bank",
    "atm",
    "fuel",
    "parking",
    "police",
    "fire_station",
    "post_office",
    "library",
    "theatre",
    "cinema",
    "place_of_worship",
    "community_centre",
    "marketplace",
    "toilets",
]

COMMON_SHOP_TYPES = [
    "supermarket",
    "convenience",
    "clothes",
    "bakery",
    "butcher",
    "greengrocer",
    "hardware",
    "electronics",
    "furniture",
    "books",
    "sports",
    "jewelry",
    "hairdresser",
    "beauty",
    "optician",
    "pharmacy",
    "florist",
    "car",
    "car_repair",
    "bicycle",
    "mobile_phone",
    "department_store",
    "mall",
]

COMMON_TOURISM_TYPES = [
    "hotel",
    "guest_house",
    "hostel",
    "motel",
    "apartment",
    "camp_site",
    "caravan_site",
    "museum",
    "attraction",
    "viewpoint",
    "artwork",
    "gallery",
    "zoo",
    "theme_park",
    "information",
    "picnic_site",
]

# =============================================================================
# Command Definitions
# =============================================================================

COMMAND_CATEGORIES = {
    "Rendering": [
        ("render", "Render maps as PNG, PDF, HTML, or 3D WebGL", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", True),
            ("-f/--format", "Output format", "choice:png,pdf,html,leaflet,webgl,3d", False),
            ("--style", "Color style", "choice:default,dark,light,blueprint", False),
            ("--width", "Image width in pixels (PNG)", "int", False),
            ("--height", "Image height in pixels (PNG)", "int", False),
            ("--page-size", "Page size (PDF)", "choice:letter,a4,a3,a2,legal", False),
            ("--orientation", "Page orientation (PDF)", "choice:portrait,landscape", False),
            ("--dpi", "DPI for PDF (default: 300)", "int", False),
            ("--title", "Map title", "text", False),
            ("--filter", "Filter by tag (e.g., highway=*)", "filter_ways", False),
            ("--layer", "Render specific layer", "choice:all,roads,buildings,water,pois,landuse", False),
            ("--tiles", "Tile provider (HTML)", "choice:osm,carto-light,carto-dark,esri-satellite", False),
            ("--no-legend", "Hide legend (PNG)", "bool", False),
            ("--no-scale", "Hide scale bar (PNG)", "bool", False),
        ]),
    ],
    "Data Extraction": [
        ("extract", "Extract features with Osmosis-compatible filtering", [
            ("input", "Input OSM file", "file", True),
            ("output", "Output file (optional, stdout if omitted)", "save", False),
            ("--format", "Output format", "choice:json,geojson,csv,osm", False),
            ("--accept-nodes", "Accept nodes filter (e.g., amenity=restaurant)", "filter_nodes", False),
            ("--accept-ways", "Accept ways filter (e.g., highway=*)", "filter_ways", False),
            ("--reject-nodes", "Reject nodes filter", "filter_nodes", False),
            ("--reject-ways", "Reject ways filter", "filter_ways", False),
            ("--used-node", "Only nodes referenced by filtered ways", "bool", False),
            ("--bbox", "Bounding box (min_lat min_lon max_lat max_lon)", "text", False),
        ]),
        ("filter", "Filter OSM data, output filtered OSM", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", True),
            ("--accept-nodes", "Accept nodes filter", "filter_nodes", False),
            ("--accept-ways", "Accept ways filter", "filter_ways", False),
            ("--reject-nodes", "Reject nodes filter", "filter_nodes", False),
            ("--reject-ways", "Reject ways filter", "filter_ways", False),
            ("--used-node", "Only nodes referenced by filtered ways", "bool", False),
            ("--bbox", "Bounding box (min_lat min_lon max_lat max_lon)", "text", False),
        ]),
        ("convert", "Convert between formats (OSM, GeoJSON, JSON, CSV)", [
            ("input", "Input file", "file", True),
            ("-o/--output", "Output file", "save", True),
            ("--format", "Output format", "choice:json,geojson,csv,osm", False),
        ]),
        ("merge", "Merge multiple OSM files", [
            ("files", "Input files (space-separated)", "files", True),
            ("-o/--output", "Output file", "save", True),
        ]),
        ("clip", "Clip data by polygon boundary", [
            ("input", "Input OSM file", "file", True),
            ("--polygon", "Polygon file (GeoJSON)", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("split", "Split large files into tiles", [
            ("input", "Input OSM file", "file", True),
            ("--grid", "Grid size (e.g., 2x2)", "text", False),
            ("-o/--output-dir", "Output directory", "dir", False),
        ]),
        ("sample", "Random sample of features", [
            ("input", "Input OSM file", "file", True),
            ("-n/--count", "Number of samples", "int", False),
            ("--percent", "Percentage to sample", "float", False),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("head", "First N elements from file", [
            ("input", "Input OSM file", "file", True),
            ("-n/--count", "Number of elements", "int", False),
            ("-o/--output", "Output file", "save", False),
        ]),
    ],
    "Feature Extraction": [
        ("poi", "Extract points of interest by category", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
            ("-f/--format", "Output format", "choice:geojson,json,csv", False),
            ("-c/--category", "POI category", "choice:food,shop,health,education,transport,tourism,finance,service,worship,all", False),
            ("--include-ways", "Include POIs from ways (use centroid)", "bool", False),
            ("--named-only", "Only named POIs", "bool", False),
            ("--stats", "Show statistics only", "bool", False),
            ("--list-categories", "List available categories", "bool", False),
        ]),
        ("buildings", "Extract buildings with height estimation", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
            ("-f/--format", "Output format", "choice:geojson,json,csv", False),
            ("--min-height", "Only buildings >= N meters", "float", False),
            ("--max-height", "Only buildings <= N meters", "float", False),
            ("--floor-height", "Meters per floor (default: 3.0)", "float", False),
            ("--type", "Building type (e.g., residential)", "text", False),
            ("--no-estimate", "Do not estimate height from levels", "bool", False),
            ("--stats", "Show statistics only", "bool", False),
        ]),
        ("roads", "Extract road network with attributes", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
            ("-f/--format", "Output format", "choice:geojson,json,csv", False),
            ("--class", "Road class", "choice:major,minor,path,all", False),
            ("--type", "Highway type (e.g., primary)", "text", False),
            ("--min-length", "Minimum segment length in meters", "float", False),
            ("--named-only", "Only named roads", "bool", False),
            ("--stats", "Show statistics only", "bool", False),
        ]),
        ("amenity", "Extract amenities (restaurants, banks, etc.)", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
            ("--type", "Amenity type (e.g., restaurant, cafe)", "type_amenity", False),
        ]),
        ("shop", "Extract shops and retail", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
            ("--type", "Shop type", "type_shop", False),
        ]),
        ("food", "Extract food-related POIs", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("healthcare", "Extract hospitals, clinics, pharmacies", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("education", "Extract schools, universities", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("tourism", "Extract tourist attractions", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
            ("--type", "Tourism type", "type_tourism", False),
        ]),
        ("leisure", "Extract parks, sports facilities", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("natural", "Extract natural features", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("water", "Extract water bodies", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("landuse", "Extract land use areas", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("trees", "Extract trees and forests", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("parking", "Extract parking facilities", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("transit", "Extract public transit stops", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("railway", "Extract railway infrastructure", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("power", "Extract power infrastructure", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("historic", "Extract historic sites", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("emergency", "Extract emergency services", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("barrier", "Extract barriers and fences", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("boundary", "Extract administrative boundaries", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
            ("--admin-level", "Admin level (1-10)", "int", False),
        ]),
    ],
    "Routing & Navigation": [
        ("route", "Calculate shortest/fastest route", [
            ("input", "Input OSM file", "file", True),
            ("--from", "Origin coordinates (lat,lon)", "text", True),
            ("--to", "Destination coordinates (lat,lon)", "text", True),
            ("--mode/-m", "Travel mode", "choice:walk,bike,drive", False),
            ("--optimize", "Optimize for time or distance", "choice:time,distance", False),
            ("-o/--output", "Output file", "save", False),
            ("-f/--format", "Output format", "choice:geojson,json,text", False),
        ]),
        ("route-multi", "Multi-stop route planning", [
            ("input", "Input OSM file", "file", True),
            ("--waypoints/-w", "Waypoints (lat,lon;lat,lon;...)", "text", True),
            ("--mode/-m", "Travel mode", "choice:walk,bike,drive", False),
            ("--optimize", "Optimize for time or distance", "choice:time,distance", False),
            ("-o/--output", "Output file", "save", False),
            ("-f/--format", "Output format", "choice:geojson,json,text", False),
        ]),
        ("directions", "Turn-by-turn navigation directions", [
            ("input", "Input OSM file", "file", True),
            ("--from", "Origin coordinates (lat,lon)", "text", True),
            ("--to", "Destination coordinates (lat,lon)", "text", True),
            ("--mode/-m", "Travel mode", "choice:walk,bike,drive", False),
            ("-o/--output", "Output file", "save", False),
            ("-f/--format", "Output format", "choice:text,json", False),
        ]),
        ("isochrone", "Generate travel time polygons", [
            ("input", "Input OSM file", "file", True),
            ("--lat", "Center latitude", "float", True),
            ("--lon", "Center longitude", "float", True),
            ("--time/-t", "Time intervals in minutes (e.g., 5,10,15)", "text", False),
            ("--mode/-m", "Travel mode", "choice:walk,bike,drive", False),
            ("--resolution", "Points for polygon boundary (default: 36)", "int", False),
            ("-o/--output", "Output file", "save", True),
        ]),
        ("alternatives", "Find alternative routes", [
            ("input", "Input OSM file", "file", True),
            ("--from", "Origin coordinates (lat,lon)", "text", True),
            ("--to", "Destination coordinates (lat,lon)", "text", True),
            ("--mode/-m", "Travel mode", "choice:walk,bike,drive", False),
            ("--count/-n", "Number of alternatives (default: 3)", "int", False),
            ("-o/--output", "Output file", "save", False),
            ("-f/--format", "Output format", "choice:geojson,json,text", False),
        ]),
        ("distance-matrix", "Calculate distances between multiple points", [
            ("input", "Input OSM file", "file", True),
            ("--points/-p", "Points as lat,lon;lat,lon or CSV file path", "text", True),
            ("--mode/-m", "Travel mode", "choice:walk,bike,drive", False),
            ("--metric", "What to calculate", "choice:time,distance,both", False),
            ("-o/--output", "Output file", "save", False),
            ("-f/--format", "Output format", "choice:json,csv,text", False),
        ]),
        ("nearest-road", "Find nearest road to a point", [
            ("input", "Input OSM file", "file", True),
            ("--lat", "Latitude", "float", True),
            ("--lon", "Longitude", "float", True),
        ]),
    ],
    "Network Analysis": [
        ("network", "Export road network as graph (GraphML, JSON)", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
            ("-f/--format", "Output format", "choice:graphml,json,geojson,csv", False),
            ("--mode", "Travel mode", "choice:drive,walk,bike,all", False),
            ("--directed", "Create directed graph (respects oneway)", "bool", False),
            ("--include-speeds", "Include speed estimates and travel times", "bool", False),
            ("--stats", "Show network statistics only", "bool", False),
        ]),
        ("connectivity", "Find disconnected components and dead ends", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
            ("--mode/-m", "Travel mode", "choice:walk,bike,drive", False),
            ("-f/--format", "Output format", "choice:geojson,json,text", False),
            ("--show-components", "Output all components as GeoJSON", "bool", False),
        ]),
        ("centrality", "Calculate betweenness centrality for intersections", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
            ("-n/--top", "Show top N nodes (default: 20)", "int", False),
            ("--sample", "Sample size for approximation (default: 100)", "int", False),
            ("-f/--format", "Output format", "choice:geojson,json,text", False),
        ]),
        ("bottleneck", "Find critical edges whose removal disconnects network", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
            ("-n/--top", "Show top N bottlenecks", "int", False),
            ("-f/--format", "Output format", "choice:geojson,json,text", False),
        ]),
        ("detour-factor", "Calculate network vs straight-line distance ratio", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
            ("--mode/-m", "Travel mode", "choice:walk,bike,drive", False),
            ("--sample", "Number of random pairs to sample", "int", False),
            ("-f/--format", "Output format", "choice:json,text", False),
        ]),
    ],
    "Spatial Operations": [
        ("nearest", "Find K nearest features of a type", [
            ("input", "Input OSM file", "file", True),
            ("--lat", "Latitude of search point", "float", True),
            ("--lon", "Longitude of search point", "float", True),
            ("--filter/-f", "Filter (e.g., amenity=restaurant)", "filter_nodes", True),
            ("-k/--count", "Number of nearest features (default: 5)", "int", False),
            ("--max-distance", "Maximum distance in meters", "float", False),
            ("-o/--output", "Output file", "save", False),
            ("--format", "Output format", "choice:geojson,json,text", False),
        ]),
        ("within", "Find features within polygon", [
            ("input", "Input OSM file", "file", True),
            ("--polygon", "Polygon file (GeoJSON)", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("buffer", "Create buffer zones around features", [
            ("input", "Input OSM file", "file", True),
            ("--filter", "Tag filter", "filter_nodes", True),
            ("--radius", "Buffer radius (e.g., 500m)", "text", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("centroid", "Calculate centroids of ways", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("bbox", "Extract/calculate bounding box", [
            ("input", "Input OSM file", "file", True),
            ("--format", "Output format", "choice:text,json,geojson", False),
        ]),
        ("densify", "Add points to geometries", [
            ("input", "Input OSM file", "file", True),
            ("--distance", "Maximum distance between points", "float", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("simplify", "Simplify geometries", [
            ("input", "Input OSM file", "file", True),
            ("--tolerance", "Simplification tolerance", "float", True),
            ("-o/--output", "Output file", "save", False),
        ]),
    ],
    "Data Analysis": [
        ("stats", "Comprehensive file statistics", [
            ("input", "Input OSM file", "file", True),
            ("--summary", "Brief summary only", "bool", False),
            ("--json", "Output as JSON", "bool", False),
        ]),
        ("count", "Quick element counting", [
            ("input", "Input OSM file", "file", True),
            ("--filter", "Tag filter", "filter_nodes", False),
            ("--by", "Group by tag key", "text", False),
            ("--top", "Top N results", "int", False),
        ]),
        ("tags", "Analyze tag usage", [
            ("input", "Input OSM file", "file", True),
            ("--top", "Top N tags", "int", False),
        ]),
        ("unique", "Find unique tag values", [
            ("input", "Input OSM file", "file", True),
            ("--key", "Tag key to analyze", "text", True),
        ]),
        ("names", "Extract all named features", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("address", "Extract addresses", [
            ("input", "Input OSM file", "file", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("surface", "Analyze road surfaces", [
            ("input", "Input OSM file", "file", True),
        ]),
        ("info", "Quick file information", [
            ("input", "Input OSM file", "file", True),
        ]),
    ],
    "Data Manipulation": [
        ("sort", "Sort elements by attribute", [
            ("input", "Input OSM file", "file", True),
            ("--by", "Sort by attribute", "text", True),
            ("--reverse", "Reverse order", "bool", False),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("join", "Join OSM data with external data", [
            ("input", "Input OSM file", "file", True),
            ("--data", "External data file", "file", True),
            ("--on", "Join key", "text", True),
            ("-o/--output", "Output file", "save", False),
        ]),
        ("lookup", "Look up elements by ID", [
            ("input", "Input OSM file", "file", True),
            ("--id", "Element ID", "text", True),
            ("--type", "Element type", "choice:node,way,relation", False),
        ]),
        ("search", "Search by name or tag", [
            ("input", "Input OSM file", "file", True),
            ("--query", "Search query", "text", True),
            ("--field", "Field to search", "choice:name,tag,all", False),
            ("-o/--output", "Output file", "save", False),
        ]),
    ],
}

# Example commands for quick reference
EXAMPLE_COMMANDS = [
    # Rendering
    ("Render PNG map", "render city.osm -o map.png --style dark"),
    ("Render 3D WebGL", "render city.osm -o city3d.html --format webgl"),
    ("Render Leaflet map", "render city.osm -o map.html --format leaflet"),
    ("Render PDF A4", "render city.osm -o map.pdf --format pdf --page-size a4"),
    ("Render roads only", "render city.osm -o roads.png --layer roads"),
    # Data extraction
    ("Extract restaurants", "extract --accept-nodes amenity=restaurant city.osm restaurants.geojson"),
    ("Extract roads", "extract --accept-ways highway=* --used-node city.osm roads.json"),
    ("Filter by bbox", "extract --bbox 51.4 -0.2 51.5 -0.1 london.osm area.json"),
    ("Extract to CSV", "extract --accept-nodes shop=* city.osm shops.csv --format csv"),
    ("Extract cycleways", "extract --accept-ways highway=cycleway city.osm bike.geojson"),
    ("Reject motorways", "extract --reject-ways highway=motorway city.osm no_motorway.osm"),
    # Feature extraction
    ("Extract buildings", "buildings city.osm -o buildings.geojson"),
    ("Tall buildings only", "buildings city.osm -o tall.geojson --min-height 20"),
    ("Building stats", "buildings city.osm --stats"),
    ("Extract POIs", "poi city.osm -o pois.geojson --category food"),
    ("Named POIs only", "poi city.osm -o named.geojson --named-only"),
    ("Extract hospitals", "healthcare city.osm -o hospitals.geojson"),
    ("Extract schools", "education city.osm -o schools.geojson"),
    ("Extract parks", "leisure city.osm -o parks.geojson"),
    ("Extract hotels", "tourism city.osm -o hotels.geojson --type hotel"),
    ("Extract parking", "parking city.osm -o parking.geojson"),
    ("Extract trees", "trees city.osm -o trees.geojson"),
    ("Extract water", "water city.osm -o water.geojson"),
    ("Major roads only", "roads city.osm -o major.geojson --class major"),
    ("Road stats", "roads city.osm --stats"),
    # Routing
    ("Calculate route", "route city.osm --from 51.5,-0.1 --to 51.6,-0.2 --mode drive"),
    ("Bike route", "route city.osm --from 51.5,-0.1 --to 51.6,-0.2 --mode bike"),
    ("Walking directions", "directions city.osm --from 51.5,-0.1 --to 51.52,-0.08 --mode walk"),
    ("Generate isochrone", "isochrone city.osm -o iso.geojson --lat 51.5 --lon -0.1 --time 5,10,15"),
    ("15-min walk zone", "isochrone city.osm -o walk15.geojson --lat 51.5 --lon -0.1 --time 15 --mode walk"),
    ("Alternative routes", "alternatives city.osm --from 51.5,-0.1 --to 51.6,-0.2 --count 3"),
    ("Distance matrix", "distance-matrix city.osm --points 51.5,-0.1;51.6,-0.2;51.55,-0.15 --mode drive"),
    # Spatial
    ("Find nearest cafes", "nearest city.osm --lat 51.5 --lon -0.1 --filter amenity=cafe -k 5"),
    ("Find nearest ATMs", "nearest city.osm --lat 51.5 --lon -0.1 --filter amenity=atm -k 3"),
    ("Nearest pharmacy", "nearest city.osm --lat 51.5 --lon -0.1 --filter amenity=pharmacy -k 1"),
    ("Nearest fuel", "nearest city.osm --lat 51.5 --lon -0.1 --filter amenity=fuel -k 3"),
    ("Get bounding box", "bbox city.osm --format json"),
    ("Calculate centroids", "centroid city.osm -o centroids.geojson"),
    # Network
    ("Export network", "network city.osm -o graph.json --mode drive"),
    ("Bike network", "network city.osm -o bike_graph.json --mode bike"),
    ("Network stats", "network city.osm --stats"),
    ("Check connectivity", "connectivity city.osm --mode drive"),
    ("Find bottlenecks", "bottleneck city.osm -o bottlenecks.geojson"),
    ("Centrality analysis", "centrality city.osm -o central.geojson --top 10"),
    # Analysis
    ("Get file stats", "stats city.osm"),
    ("Quick info", "info city.osm"),
    ("Stats as JSON", "stats city.osm --json"),
    ("Count amenities", "count city.osm --filter amenity=* --by amenity --top 20"),
    ("Count shops", "count city.osm --filter shop=* --by shop --top 15"),
    ("List unique values", "unique city.osm --key cuisine"),
    ("Analyze tags", "tags city.osm --top 30"),
    ("Extract addresses", "address city.osm -o addresses.geojson"),
    ("Extract names", "names city.osm -o named.geojson"),
    ("Road surfaces", "surface city.osm"),
    # File operations
    ("Merge files", "merge area1.osm area2.osm -o combined.osm"),
    ("Sample 100 features", "sample city.osm -n 100 -o sample.osm"),
    ("Sample 10 percent", "sample city.osm --percent 10 -o sample.osm"),
    ("First 50 elements", "head city.osm -n 50 -o head.osm"),
    ("Convert to GeoJSON", "convert city.osm -o city.geojson --format geojson"),
    ("Search by name", "search city.osm --query \"Main Street\" -o results.geojson"),
    ("Lookup by ID", "lookup city.osm --id 123456 --type node"),
]


# =============================================================================
# Main GUI Application
# =============================================================================

class OSMFastGUI:
    """Main GUI application for OSMFast."""

    # Config file for storing preferences
    CONFIG_FILE = Path.home() / ".osmfast_gui_config.json"
    MAX_RECENT_FILES = 10

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("OSMFast GUI")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)

        # State
        self.current_command = None
        self.arg_widgets: Dict[str, Tuple[Any, str]] = {}  # name -> (var, type_str)
        self.process: Optional[subprocess.Popen] = None
        self._stop_requested = False  # Flag for graceful thread termination
        self.recent_files: List[str] = []
        self.command_history: List[str] = []

        # Load config
        self.load_config()

        # Configure styles
        self.setup_styles()

        # Build UI
        self.create_menu()
        self.create_main_layout()
        self.create_status_bar()

        # Populate commands
        self.populate_command_tree()

        # Bind events
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_keyboard_shortcuts()

    def load_config(self):
        """Load configuration from file."""
        try:
            if self.CONFIG_FILE.exists():
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.recent_files = config.get('recent_files', [])[:self.MAX_RECENT_FILES]
                    self.command_history = config.get('command_history', [])[-50:]
        except (OSError, json.JSONDecodeError, KeyError):
            self.recent_files = []
            self.command_history = []

    def save_config(self):
        """Save configuration to file."""
        try:
            config = {
                'recent_files': self.recent_files[:self.MAX_RECENT_FILES],
                'command_history': self.command_history[-50:]
            }
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except (OSError, TypeError):
            pass

    def add_recent_file(self, filepath: str):
        """Add file to recent files list."""
        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
        self.recent_files.insert(0, filepath)
        self.recent_files = self.recent_files[:self.MAX_RECENT_FILES]
        self.update_recent_files_menu()
        self.save_config()

    def add_to_history(self, cmd: str):
        """Add command to history."""
        if cmd and (not self.command_history or self.command_history[-1] != cmd):
            self.command_history.append(cmd)
            self.save_config()

    def bind_keyboard_shortcuts(self):
        """Bind keyboard shortcuts."""
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-r>", lambda e: self.run_command())
        self.root.bind("<Control-l>", lambda e: self.clear_output())
        self.root.bind("<Control-k>", lambda e: self.clear_args())
        self.root.bind("<F5>", lambda e: self.run_command())
        self.root.bind("<Escape>", lambda e: self.stop_command())
        self.root.bind("<Control-c>", lambda e: self.copy_command())

    def setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()

        # Try to use a modern theme
        available_themes = style.theme_names()
        if 'clam' in available_themes:
            style.theme_use('clam')
        elif 'vista' in available_themes:
            style.theme_use('vista')

        # Custom styles
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Code.TLabel", font=("Consolas", 10))
        style.configure("Category.Treeview", font=("Segoe UI", 10))
        style.configure("Run.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Link.TButton", font=("Segoe UI", 9), padding=2)

    def create_menu(self):
        """Create menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        self.file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Open OSM File...", command=self.open_file, accelerator="Ctrl+O")

        # Recent files submenu
        self.recent_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label="Recent Files", menu=self.recent_menu)
        self.update_recent_files_menu()

        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.on_close, accelerator="Alt+F4")

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Copy Command", command=self.copy_command, accelerator="Ctrl+C")
        edit_menu.add_command(label="Clear Arguments", command=self.clear_args, accelerator="Ctrl+K")
        edit_menu.add_command(label="Clear Output", command=self.clear_output, accelerator="Ctrl+L")

        # Run menu
        run_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Run", menu=run_menu)
        run_menu.add_command(label="Run Command", command=self.run_command, accelerator="F5 / Ctrl+R")
        run_menu.add_command(label="Stop Command", command=self.stop_command, accelerator="Escape")

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Expand All Categories", command=self.expand_all_categories)
        view_menu.add_command(label="Collapse All Categories", command=self.collapse_all_categories)
        view_menu.add_separator()
        view_menu.add_command(label="Command History", command=self.show_history)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        help_menu.add_command(label="View README", command=self.show_readme)
        help_menu.add_separator()
        help_menu.add_command(label="About OSMFast", command=self.show_about)

    def update_recent_files_menu(self):
        """Update recent files menu."""
        self.recent_menu.delete(0, tk.END)
        if self.recent_files:
            for filepath in self.recent_files:
                # Truncate long paths
                display = filepath if len(filepath) < 60 else "..." + filepath[-57:]
                self.recent_menu.add_command(
                    label=display,
                    command=lambda f=filepath: self.load_recent_file(f)
                )
            self.recent_menu.add_separator()
            self.recent_menu.add_command(label="Clear Recent", command=self.clear_recent_files)
        else:
            self.recent_menu.add_command(label="(No recent files)", state=tk.DISABLED)

    def load_recent_file(self, filepath: str):
        """Load a recent file into the input field."""
        if os.path.exists(filepath):
            if "input" in self.arg_widgets:
                var, _ = self.arg_widgets["input"]
                var.set(filepath)
                self.add_recent_file(filepath)
        else:
            messagebox.showerror("File Not Found", f"File no longer exists:\n{filepath}")
            if filepath in self.recent_files:
                self.recent_files.remove(filepath)
                self.update_recent_files_menu()
                self.save_config()

    def clear_recent_files(self):
        """Clear recent files list."""
        self.recent_files = []
        self.update_recent_files_menu()
        self.save_config()

    def expand_all_categories(self):
        """Expand all category nodes in the tree."""
        for item in self.command_tree.get_children():
            self.command_tree.item(item, open=True)

    def collapse_all_categories(self):
        """Collapse all category nodes in the tree."""
        for item in self.command_tree.get_children():
            self.command_tree.item(item, open=False)

    def show_history(self):
        """Show command history in a dialog."""
        if not self.command_history:
            messagebox.showinfo("Command History", "No commands in history yet.")
            return

        history_win = tk.Toplevel(self.root)
        history_win.title("Command History")
        history_win.geometry("700x400")
        history_win.transient(self.root)

        ttk.Label(history_win, text="Double-click a command to use it:", padding=10).pack(anchor=tk.W)

        # Listbox with scrollbar
        frame = ttk.Frame(history_win)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        listbox = tk.Listbox(frame, font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Populate with history (most recent first)
        for cmd in reversed(self.command_history):
            listbox.insert(tk.END, cmd)

        def on_select(event):
            selection = listbox.curselection()
            if selection:
                cmd = listbox.get(selection[0])
                self.cmd_preview.delete(0, tk.END)
                self.cmd_preview.insert(0, cmd)
                history_win.destroy()

        listbox.bind("<Double-1>", on_select)

    def show_shortcuts(self):
        """Show keyboard shortcuts dialog."""
        shortcuts = """Keyboard Shortcuts
==================

File Operations:
  Ctrl+O          Open OSM file

Editing:
  Ctrl+K          Clear all arguments
  Ctrl+L          Clear output

Execution:
  F5 / Ctrl+R     Run command
  Escape          Stop running command
  Ctrl+C          Copy command to clipboard

Tips:
- Double-click a command in the tree to select it
- Click an example to populate the command preview
- Use Tab to navigate between input fields
- Use View > Command History for previous commands
"""
        messagebox.showinfo("Keyboard Shortcuts", shortcuts)

    def create_main_layout(self):
        """Create main application layout."""
        # Main paned window (horizontal split)
        self.main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel: Command browser
        self.create_command_browser()

        # Right panel: Command builder and output
        self.create_right_panel()

    def create_command_browser(self):
        """Create command browser panel."""
        left_frame = ttk.Frame(self.main_paned, width=300)
        self.main_paned.add(left_frame, weight=1)

        # Search box
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Command tree
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.command_tree = ttk.Treeview(tree_frame, style="Category.Treeview", show="tree")
        self.command_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.command_tree.yview)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.command_tree.configure(yscrollcommand=tree_scroll.set)

        # Bind selection
        self.command_tree.bind("<<TreeviewSelect>>", self.on_command_select)
        self.command_tree.bind("<Double-1>", self.on_command_double_click)

        # Quick examples section
        examples_frame = ttk.LabelFrame(left_frame, text="Quick Examples", padding=5)
        examples_frame.pack(fill=tk.X, pady=(10, 0))

        examples_list_frame = ttk.Frame(examples_frame)
        examples_list_frame.pack(fill=tk.X)

        self.examples_listbox = tk.Listbox(examples_list_frame, height=12, font=("Segoe UI", 9))
        examples_scroll = ttk.Scrollbar(examples_list_frame, orient=tk.VERTICAL, command=self.examples_listbox.yview)
        self.examples_listbox.configure(yscrollcommand=examples_scroll.set)

        self.examples_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        examples_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for name, _ in EXAMPLE_COMMANDS:
            self.examples_listbox.insert(tk.END, name)

        self.examples_listbox.bind("<<ListboxSelect>>", self.on_example_select)

    def create_right_panel(self):
        """Create right panel with command builder and output."""
        right_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(right_frame, weight=3)

        # Vertical paned window
        right_paned = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
        right_paned.pack(fill=tk.BOTH, expand=True)

        # Top: Command builder
        builder_frame = ttk.LabelFrame(right_paned, text="Command Builder", padding=10)
        right_paned.add(builder_frame, weight=4)

        self.create_command_builder(builder_frame)

        # Bottom: Output (smaller by default)
        output_frame = ttk.LabelFrame(right_paned, text="Output", padding=5)
        right_paned.add(output_frame, weight=1)

        self.create_output_panel(output_frame)

    def create_command_builder(self, parent):
        """Create command builder interface."""
        # Command info
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        self.cmd_name_label = ttk.Label(info_frame, text="Select a command", style="Title.TLabel")
        self.cmd_name_label.pack(anchor=tk.W)

        self.cmd_desc_label = ttk.Label(info_frame, text="", style="Subtitle.TLabel", wraplength=600)
        self.cmd_desc_label.pack(anchor=tk.W, pady=(5, 0))

        # Examples section (collapsible)
        self.examples_detail_frame = ttk.LabelFrame(info_frame, text="Usage Examples", padding=5)
        # Initially hidden until a command with examples is selected

        self.examples_text = tk.Text(
            self.examples_detail_frame,
            font=("Consolas", 9),
            height=3,
            wrap=tk.WORD,
            state=tk.DISABLED,
            background="#f5f5f5"
        )
        self.examples_text.pack(fill=tk.X, expand=True)

        # Related commands section
        self.related_frame = ttk.Frame(info_frame)
        self.related_label = ttk.Label(self.related_frame, text="Related: ", foreground="gray")
        self.related_links_frame = ttk.Frame(self.related_frame)

        # Arguments frame (scrollable)
        args_container = ttk.Frame(parent)
        args_container.pack(fill=tk.BOTH, expand=True)

        # Canvas for scrolling
        self.args_canvas = tk.Canvas(args_container, highlightthickness=0)
        args_scrollbar = ttk.Scrollbar(args_container, orient=tk.VERTICAL, command=self.args_canvas.yview)

        self.args_frame = ttk.Frame(self.args_canvas)
        self.args_frame.bind("<Configure>", lambda e: self.args_canvas.configure(scrollregion=self.args_canvas.bbox("all")))

        self.args_canvas.create_window((0, 0), window=self.args_frame, anchor=tk.NW)
        self.args_canvas.configure(yscrollcommand=args_scrollbar.set)

        self.args_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        args_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mouse wheel to canvas only (not globally)
        self.args_canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.args_frame.bind("<MouseWheel>", self.on_mousewheel)
        # Linux uses Button-4/5 for scroll
        self.args_canvas.bind("<Button-4>", lambda e: self.args_canvas.yview_scroll(-1, "units"))
        self.args_canvas.bind("<Button-5>", lambda e: self.args_canvas.yview_scroll(1, "units"))

        # Command preview and run buttons
        preview_frame = ttk.Frame(parent)
        preview_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(preview_frame, text="Command:").pack(anchor=tk.W)

        self.cmd_preview = ttk.Entry(preview_frame, font=("Consolas", 10))
        self.cmd_preview.pack(fill=tk.X, pady=(5, 0))

        # Buttons
        btn_frame = ttk.Frame(preview_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.run_btn = ttk.Button(btn_frame, text="Run Command", command=self.run_command, style="Run.TButton")
        self.run_btn.pack(side=tk.LEFT)

        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_command, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(10, 0))

        ttk.Button(btn_frame, text="Copy Command", command=self.copy_command).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(btn_frame, text="Clear", command=self.clear_args).pack(side=tk.LEFT, padx=(10, 0))

    def create_output_panel(self, parent):
        """Create output display panel."""
        # Output text area
        self.output_text = scrolledtext.ScrolledText(
            parent,
            font=("Consolas", 10),
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)

        # Configure tags for coloring
        self.output_text.tag_configure("error", foreground="red")
        self.output_text.tag_configure("success", foreground="green")
        self.output_text.tag_configure("info", foreground="blue")

        # Clear button
        clear_frame = ttk.Frame(parent)
        clear_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(clear_frame, text="Clear Output", command=self.clear_output).pack(side=tk.RIGHT)

    def create_status_bar(self):
        """Create status bar at the bottom of the window."""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(2, 0))

        # Left side: Status message
        self.status_label = ttk.Label(self.status_frame, text="Ready", anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, padx=5)

        # Right side: Command count and info
        self.info_label = ttk.Label(
            self.status_frame,
            text=f"{sum(len(cmds) for cmds in COMMAND_CATEGORIES.values())} commands available",
            anchor=tk.E
        )
        self.info_label.pack(side=tk.RIGHT, padx=5)

    def set_status(self, message: str, is_error: bool = False):
        """Update status bar message."""
        self.status_label.config(text=message, foreground="red" if is_error else "")
        if not is_error:
            # Clear non-error messages after 5 seconds
            self.root.after(5000, lambda: self.status_label.config(text="Ready"))

    def populate_command_tree(self):
        """Populate command tree with categories and commands."""
        for category, commands in COMMAND_CATEGORIES.items():
            cat_id = self.command_tree.insert("", tk.END, text=category, open=False)
            for cmd_name, cmd_desc, _ in commands:
                # Try to get summary from JSON docs, fallback to inline
                summary = get_summary(cmd_name) or cmd_desc
                self.command_tree.insert(cat_id, tk.END, text=cmd_name, values=(summary,))

    def on_search(self, *args):
        """Filter commands based on search text."""
        search_text = self.search_var.get().lower()

        # Clear and repopulate tree
        for item in self.command_tree.get_children():
            self.command_tree.delete(item)

        for category, commands in COMMAND_CATEGORIES.items():
            matching_commands = []
            for cmd_name, cmd_desc, cmd_args in commands:
                # Get summary from JSON docs for searching
                summary = get_summary(cmd_name) or cmd_desc
                if search_text in cmd_name.lower() or search_text in summary.lower():
                    matching_commands.append((cmd_name, summary, cmd_args))

            if matching_commands or not search_text:
                cat_id = self.command_tree.insert("", tk.END, text=category, open=bool(search_text))
                for cmd_name, summary, _ in (matching_commands if search_text else [(n, get_summary(n) or d, a) for n, d, a in commands]):
                    self.command_tree.insert(cat_id, tk.END, text=cmd_name, values=(summary,))

    def on_command_select(self, event):
        """Handle command selection."""
        selection = self.command_tree.selection()
        if not selection:
            return

        item = selection[0]
        parent = self.command_tree.parent(item)

        # Only handle leaf nodes (commands, not categories)
        if not parent:
            return

        cmd_name = self.command_tree.item(item, "text")
        category = self.command_tree.item(parent, "text")

        # Find command definition
        for cat, commands in COMMAND_CATEGORIES.items():
            if cat == category:
                for name, desc, args in commands:
                    if name == cmd_name:
                        self.current_command = (name, desc, args)
                        self.display_command(name, desc, args)
                        return

    def on_command_double_click(self, event):
        """Handle double-click on command."""
        self.on_command_select(event)
        if self.current_command:
            self.search_entry.focus_set()

    def select_command_by_name(self, cmd_name: str):
        """Select and display a command by its name (used for related commands navigation)."""
        # Search through all categories
        for cat, commands in COMMAND_CATEGORIES.items():
            for name, desc, args in commands:
                if name == cmd_name:
                    self.current_command = (name, desc, args)
                    self.display_command(name, desc, args)
                    # Try to select it in the tree
                    for cat_item in self.command_tree.get_children():
                        for cmd_item in self.command_tree.get_children(cat_item):
                            if self.command_tree.item(cmd_item, "text") == cmd_name:
                                self.command_tree.selection_set(cmd_item)
                                self.command_tree.see(cmd_item)
                                # Expand the category
                                self.command_tree.item(cat_item, open=True)
                                return
                    return
        # If not found in categories, show a message
        self.set_status(f"Command '{cmd_name}' not found in GUI", is_error=True)

    def on_example_select(self, event):
        """Handle example selection."""
        selection = self.examples_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        _, cmd = EXAMPLE_COMMANDS[idx]

        # Set command preview
        self.cmd_preview.delete(0, tk.END)
        self.cmd_preview.insert(0, f"osmfast {cmd}")

    def display_command(self, name: str, desc: str, args: List[Tuple]):
        """Display command details and create argument inputs."""
        self.cmd_name_label.config(text=f"osmfast {name}")

        # Try to get richer description from JSON docs
        json_desc = get_description(name)
        display_desc = json_desc if json_desc else desc
        self.cmd_desc_label.config(text=display_desc)

        # Get full command documentation for examples and related
        doc = get_command_doc(name)

        # Display usage examples from JSON docs
        if doc and doc.get("examples"):
            self.examples_detail_frame.pack(fill=tk.X, pady=(5, 0))
            self.examples_text.config(state=tk.NORMAL)
            self.examples_text.delete(1.0, tk.END)
            examples = doc["examples"][:3]  # Show first 3 examples
            for title, example_cmd in examples:
                self.examples_text.insert(tk.END, f"{title}: {example_cmd}\n")
            self.examples_text.config(state=tk.DISABLED)
        else:
            self.examples_detail_frame.pack_forget()

        # Display related commands as clickable links
        related = get_related_commands(name)
        for widget in self.related_links_frame.winfo_children():
            widget.destroy()

        if related:
            self.related_frame.pack(fill=tk.X, pady=(5, 0))
            self.related_label.pack(side=tk.LEFT)
            self.related_links_frame.pack(side=tk.LEFT)
            for i, rel_cmd in enumerate(related[:5]):  # Show first 5 related
                btn = ttk.Button(
                    self.related_links_frame,
                    text=rel_cmd,
                    command=lambda c=rel_cmd: self.select_command_by_name(c),
                    style="Link.TButton"
                )
                btn.pack(side=tk.LEFT, padx=(0 if i == 0 else 5, 0))
        else:
            self.related_frame.pack_forget()

        # Clear existing argument widgets
        for widget in self.args_frame.winfo_children():
            widget.destroy()
        self.arg_widgets.clear()

        # Create argument inputs
        for i, (arg_name, arg_desc, arg_type, required) in enumerate(args):
            # Try to get better help text from JSON docs
            json_help = get_option_help(name, arg_name) if DOCS_AVAILABLE else ""
            display_desc = json_help if json_help else arg_desc
            self.create_arg_input(i, arg_name, display_desc, arg_type, required)

        # Update command preview
        self.update_preview()

    def create_arg_input(self, row: int, name: str, desc: str, arg_type: str, required: bool):
        """Create input widget for an argument."""
        frame = ttk.Frame(self.args_frame)
        frame.pack(fill=tk.X, pady=2)

        # Label
        label_text = f"{name}{'*' if required else ''}:"
        label = ttk.Label(frame, text=label_text, width=20, anchor=tk.W)
        label.pack(side=tk.LEFT)

        # Input widget based on type
        if arg_type == "bool":
            var = tk.BooleanVar(value=False)
            widget = ttk.Checkbutton(frame, variable=var, text=desc)
            widget.pack(side=tk.LEFT)
            self.arg_widgets[name] = (var, "bool")

        elif arg_type == "file":
            var = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=var, width=40)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            btn = ttk.Button(frame, text="Browse...",
                           command=lambda v=var: self.browse_file(v))
            btn.pack(side=tk.LEFT, padx=(5, 0))
            self.arg_widgets[name] = (var, "file")
            var.trace_add("write", lambda *a: self.update_preview())

        elif arg_type == "files":
            var = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=var, width=40)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            btn = ttk.Button(frame, text="Browse...",
                           command=lambda v=var: self.browse_files(v))
            btn.pack(side=tk.LEFT, padx=(5, 0))
            self.arg_widgets[name] = (var, "files")
            var.trace_add("write", lambda *a: self.update_preview())

        elif arg_type == "save":
            var = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=var, width=40)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            btn = ttk.Button(frame, text="Save As...",
                           command=lambda v=var: self.browse_save(v))
            btn.pack(side=tk.LEFT, padx=(5, 0))
            self.arg_widgets[name] = (var, "save")
            var.trace_add("write", lambda *a: self.update_preview())

        elif arg_type == "dir":
            var = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=var, width=40)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            btn = ttk.Button(frame, text="Browse...",
                           command=lambda v=var: self.browse_dir(v))
            btn.pack(side=tk.LEFT, padx=(5, 0))
            self.arg_widgets[name] = (var, "dir")
            var.trace_add("write", lambda *a: self.update_preview())

        elif arg_type.startswith("choice:"):
            choices = arg_type.split(":")[1].split(",")
            var = tk.StringVar()
            combo = ttk.Combobox(frame, textvariable=var, values=choices, width=20, state="readonly")
            combo.pack(side=tk.LEFT)
            self.arg_widgets[name] = (var, "choice")
            var.trace_add("write", lambda *a: self.update_preview())

        elif arg_type in ("int", "float"):
            var = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=var, width=15)
            entry.pack(side=tk.LEFT)
            self.arg_widgets[name] = (var, arg_type)
            var.trace_add("write", lambda *a: self.update_preview())

        elif arg_type == "filter_nodes":
            # Editable combobox with common node filters
            var = tk.StringVar()
            combo = ttk.Combobox(frame, textvariable=var, values=COMMON_NODE_FILTERS, width=40)
            combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.arg_widgets[name] = (var, "text")
            var.trace_add("write", lambda *a: self.update_preview())
            # Bind to filter values as user types
            combo.bind('<KeyRelease>', lambda e, c=combo: self._filter_combobox(e, c, COMMON_NODE_FILTERS))

        elif arg_type == "filter_ways":
            # Editable combobox with common way filters
            var = tk.StringVar()
            combo = ttk.Combobox(frame, textvariable=var, values=COMMON_WAY_FILTERS, width=40)
            combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.arg_widgets[name] = (var, "text")
            var.trace_add("write", lambda *a: self.update_preview())
            combo.bind('<KeyRelease>', lambda e, c=combo: self._filter_combobox(e, c, COMMON_WAY_FILTERS))

        elif arg_type == "type_amenity":
            # Editable combobox with common amenity types
            var = tk.StringVar()
            combo = ttk.Combobox(frame, textvariable=var, values=COMMON_AMENITY_TYPES, width=30)
            combo.pack(side=tk.LEFT)
            self.arg_widgets[name] = (var, "text")
            var.trace_add("write", lambda *a: self.update_preview())
            combo.bind('<KeyRelease>', lambda e, c=combo: self._filter_combobox(e, c, COMMON_AMENITY_TYPES))

        elif arg_type == "type_shop":
            # Editable combobox with common shop types
            var = tk.StringVar()
            combo = ttk.Combobox(frame, textvariable=var, values=COMMON_SHOP_TYPES, width=30)
            combo.pack(side=tk.LEFT)
            self.arg_widgets[name] = (var, "text")
            var.trace_add("write", lambda *a: self.update_preview())
            combo.bind('<KeyRelease>', lambda e, c=combo: self._filter_combobox(e, c, COMMON_SHOP_TYPES))

        elif arg_type == "type_tourism":
            # Editable combobox with common tourism types
            var = tk.StringVar()
            combo = ttk.Combobox(frame, textvariable=var, values=COMMON_TOURISM_TYPES, width=30)
            combo.pack(side=tk.LEFT)
            self.arg_widgets[name] = (var, "text")
            var.trace_add("write", lambda *a: self.update_preview())
            combo.bind('<KeyRelease>', lambda e, c=combo: self._filter_combobox(e, c, COMMON_TOURISM_TYPES))

        else:  # text
            var = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=var, width=40)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.arg_widgets[name] = (var, "text")
            var.trace_add("write", lambda *a: self.update_preview())

        # Description tooltip
        if desc and arg_type != "bool":
            desc_label = ttk.Label(frame, text=f"({desc})", foreground="gray")
            desc_label.pack(side=tk.LEFT, padx=(10, 0))

    def update_preview(self):
        """Update command preview based on current inputs."""
        if not self.current_command:
            return

        name, _, args = self.current_command
        cmd_parts = ["osmfast", name]

        positional_args = []

        for arg_name, _, arg_type, _ in args:
            if arg_name not in self.arg_widgets:
                continue

            var, var_type = self.arg_widgets[arg_name]
            value = var.get() if hasattr(var, 'get') else var

            if not value:
                continue

            if var_type == "bool":
                if value:
                    # Extract just the flag name
                    flag = arg_name.split("/")[0] if "/" in arg_name else arg_name
                    cmd_parts.append(flag)
            elif arg_name.startswith("-"):
                flag = arg_name.split("/")[0] if "/" in arg_name else arg_name
                cmd_parts.extend([flag, f'"{value}"' if " " in str(value) else str(value)])
            else:
                # Positional argument
                positional_args.append(f'"{value}"' if " " in str(value) else str(value))

        cmd_parts.extend(positional_args)

        self.cmd_preview.delete(0, tk.END)
        self.cmd_preview.insert(0, " ".join(cmd_parts))

    def _filter_combobox(self, event, combo: ttk.Combobox, all_values: List[str]):
        """Filter combobox values based on current text (autocomplete)."""
        # Skip special keys
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Tab', 'Escape'):
            return

        current = combo.get().lower()
        if not current:
            combo['values'] = all_values
            return

        # Filter values that contain the current text
        filtered = [v for v in all_values if current in v.lower()]

        if filtered:
            combo['values'] = filtered
            # Open the dropdown if we have matches
            if len(filtered) < len(all_values):
                combo.event_generate('<Down>')
        else:
            combo['values'] = all_values

    def browse_file(self, var: tk.StringVar):
        """Browse for input file."""
        filename = filedialog.askopenfilename(
            title="Select OSM File",
            filetypes=[
                ("OSM Files", "*.osm"),
                ("All Files", "*.*")
            ]
        )
        if filename:
            var.set(filename)
            self.add_recent_file(filename)
            self.set_status(f"Loaded: {os.path.basename(filename)}")

    def browse_files(self, var: tk.StringVar):
        """Browse for multiple input files."""
        filenames = filedialog.askopenfilenames(
            title="Select OSM Files",
            filetypes=[
                ("OSM Files", "*.osm"),
                ("All Files", "*.*")
            ]
        )
        if filenames:
            var.set(" ".join(f'"{f}"' for f in filenames))

    def browse_save(self, var: tk.StringVar):
        """Browse for output file."""
        filename = filedialog.asksaveasfilename(
            title="Save Output As",
            filetypes=[
                ("GeoJSON Files", "*.geojson"),
                ("JSON Files", "*.json"),
                ("CSV Files", "*.csv"),
                ("OSM Files", "*.osm"),
                ("GraphML Files", "*.graphml"),
                ("All Files", "*.*")
            ]
        )
        if filename:
            var.set(filename)

    def browse_dir(self, var: tk.StringVar):
        """Browse for directory."""
        dirname = filedialog.askdirectory(title="Select Directory")
        if dirname:
            var.set(dirname)

    def run_command(self):
        """Execute the current command."""
        cmd = self.cmd_preview.get().strip()
        if not cmd:
            messagebox.showwarning("No Command", "Please build a command first.")
            return

        # Basic validation: must start with osmfast
        if not cmd.startswith("osmfast"):
            messagebox.showwarning("Invalid Command", "Command must start with 'osmfast'.")
            return

        # Add to history
        self.add_to_history(cmd)

        # Disable run button, enable stop
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.set_status("Running command...")

        # Clear output and reset stop flag
        self._stop_requested = False
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, f"Running: {cmd}\n\n", "info")
        self.output_text.config(state=tk.DISABLED)

        # Run in background thread
        def run_thread():
            try:
                # On Windows, use shell=True for proper path handling
                # On Unix, use shlex.split for safer argument parsing
                if sys.platform == 'win32':
                    self.process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        cwd=os.path.dirname(os.path.abspath(__file__))
                    )
                else:
                    self.process = subprocess.Popen(
                        shlex.split(cmd),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        cwd=os.path.dirname(os.path.abspath(__file__))
                    )

                # Read output line by line
                for line in iter(self.process.stdout.readline, ''):
                    if self._stop_requested:
                        break
                    self.root.after(0, self.append_output, line)

                if not self._stop_requested:
                    self.process.wait()
                    returncode = self.process.returncode if self.process else -1

                    if returncode == 0:
                        self.root.after(0, self.append_output, "\n[Command completed successfully]\n", "success")
                    elif returncode > 0:
                        self.root.after(0, self.append_output, f"\n[Command failed with exit code {returncode}]\n", "error")

            except Exception as e:
                self.root.after(0, self.append_output, f"\n[Error: {str(e)}]\n", "error")
            finally:
                self.process = None
                self._stop_requested = False
                self.root.after(0, self.command_finished)

        thread = threading.Thread(target=run_thread, daemon=True)
        thread.start()

    def stop_command(self):
        """Stop the running command."""
        if self.process:
            self._stop_requested = True
            self.process.terminate()
            self.append_output("\n[Command terminated by user]\n", "error")
            self.command_finished()

    def command_finished(self):
        """Called when command finishes."""
        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.set_status("Command completed")

    def append_output(self, text: str, tag: str = None):
        """Append text to output area."""
        self.output_text.config(state=tk.NORMAL)
        if tag:
            self.output_text.insert(tk.END, text, tag)
        else:
            self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)

    def clear_output(self):
        """Clear output area."""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)

    def clear_args(self):
        """Clear all argument inputs."""
        for var, var_type in self.arg_widgets.values():
            if var_type == "bool":
                var.set(False)
            else:
                var.set("")
        self.update_preview()

    def copy_command(self):
        """Copy command to clipboard."""
        cmd = self.cmd_preview.get().strip()
        if cmd:
            self.root.clipboard_clear()
            self.root.clipboard_append(cmd)
            self.set_status("Command copied to clipboard")

    def open_file(self):
        """Open file and populate input field."""
        filename = filedialog.askopenfilename(
            title="Select OSM File",
            filetypes=[
                ("OSM Files", "*.osm"),
                ("All Files", "*.*")
            ]
        )
        if filename:
            self.add_recent_file(filename)
            if "input" in self.arg_widgets:
                var, _ = self.arg_widgets["input"]
                var.set(filename)
            self.set_status(f"Opened: {os.path.basename(filename)}")

    def on_mousewheel(self, event):
        """Handle mouse wheel scrolling (cross-platform)."""
        # Windows returns delta in multiples of 120, macOS returns actual scroll amount
        if sys.platform == 'darwin':
            # macOS: delta is actual scroll amount
            scroll_amount = -1 if event.delta > 0 else 1
        else:
            # Windows/Linux: delta is in multiples of 120
            scroll_amount = int(-1 * (event.delta / 120))
        self.args_canvas.yview_scroll(scroll_amount, "units")

    def show_about(self):
        """Show about dialog."""
        about_text = """OSMFast GUI

A graphical interface for OSMFast - Ultra-High Performance OpenStreetMap Data Extraction & Analysis Tool.

Features:
- 60+ CLI commands for OSM operations
- Memory-mapped I/O parsing
- 7,000+ features/second
- Zero external dependencies

Version: 1.0.0
Python: Pure Python 3 standard library
"""
        messagebox.showinfo("About OSMFast", about_text)

    def show_readme(self):
        """Show README in a new window."""
        readme_path = os.path.join(os.path.dirname(__file__), "README.md")

        if not os.path.exists(readme_path):
            messagebox.showerror("Error", "README.md not found!")
            return

        try:
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError as e:
            messagebox.showerror("Error", f"Failed to read README.md: {e}")
            return

        # Create new window
        readme_win = tk.Toplevel(self.root)
        readme_win.title("OSMFast README")
        readme_win.geometry("800x600")

        # Read and display README
        text = scrolledtext.ScrolledText(readme_win, wrap=tk.WORD, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text.insert(tk.END, content)
        text.config(state=tk.DISABLED)

    def on_close(self):
        """Handle window close."""
        if self.process:
            if messagebox.askyesno("Running Command", "A command is still running. Stop it and exit?"):
                self.stop_command()
            else:
                return
        self.root.destroy()


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Main entry point."""
    root = tk.Tk()

    # Set icon if available
    try:
        # Could set a custom icon here
        pass
    except tk.TclError:
        pass

    app = OSMFastGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
