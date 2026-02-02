"""Render bikeability analysis visualization with map features."""
import argparse
import json
import math
import os
import subprocess
import sys


COMMAND_HELP = 'Generate interactive bikeability visualization map'
COMMAND_DESCRIPTION = '''Generate an interactive HTML map showing bikeability analysis results.

Runs bikeability analysis and creates a Leaflet-based visualization showing:
- Cycling infrastructure (cycleways, bike lanes, bike roads)
- Dangerous intersections where bike routes cross car roads
- Bike facilities (parking, rental, shops)
- Traffic separation indicators

Examples:
  osmfast render-bikeability map.osm --lat -33.9 --lon 151.207
  osmfast render-bikeability map.osm --lat 51.5 --lon -0.1 --radius 1000
  osmfast render-bikeability map.osm --lat 40.7 --lon -74.0 -o bikemap.html
'''

# Cycling infrastructure colors
BIKE_COLORS = {
    'cycleway': '#00C853',      # Green - dedicated cycleway
    'bike_lane': '#7C4DFF',     # Purple - bike lane on road
    'bike_road': '#00BCD4',     # Cyan - bike road/Fahrradstraße
    'shared': '#FF9800',        # Orange - shared path
    'main_road': '#F44336',     # Red - main road (dangerous)
    'residential': '#2196F3',   # Blue - residential
}

# POI symbols for cycling
BIKE_POI_SYMBOLS = {
    'bicycle_parking': ('🅿️', '#4CAF50', 'parking'),
    'bicycle_rental': ('🚲', '#2196F3', 'rental'),
    'bicycle_repair_station': ('🔧', '#FF9800', 'repair'),
    'bicycle_shop': ('🏪', '#9C27B0', 'shop'),
    'bike_shop': ('🏪', '#9C27B0', 'shop'),
    'compressed_air': ('💨', '#607D8B', 'air'),
}


def setup_parser(subparsers) -> None:
    """Add render-bikeability subcommand parser."""
    parser = subparsers.add_parser(
        'render-bikeability',
        help=COMMAND_HELP,
        description=COMMAND_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_arguments(parser)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add arguments to the parser."""
    parser.add_argument('input_file', help='Input OSM XML file')
    parser.add_argument('--lat', type=float, required=True,
                        help='Center latitude for analysis')
    parser.add_argument('--lon', type=float, required=True,
                        help='Center longitude for analysis')
    parser.add_argument('--radius', '-r', type=int, default=1000,
                        help='Analysis radius in meters (default: 1000)')
    parser.add_argument('-o', '--output', default='bikeability_map.html',
                        help='Output HTML file (default: bikeability_map.html)')
    parser.add_argument('--no-open', action='store_true',
                        help='Do not open the map in browser')


def haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    # Clamp to prevent floating point errors
    a = min(1.0, a)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def escape_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS."""
    if not text:
        return ''
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))


def run(args: argparse.Namespace) -> int:
    """Execute render-bikeability command."""
    import tempfile
    from osm_core.parsing.mmap_parser import UltraFastOSMParser

    osm_file = args.input_file
    center_lat = args.lat
    center_lon = args.lon
    radius = args.radius
    output_file = args.output

    # Find osmfast.py relative to this file's location
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    osmfast_path = os.path.join(script_dir, 'osmfast.py')

    # Create temp file for bikeability results
    temp_fd, temp_path = tempfile.mkstemp(suffix='.json', prefix='bikeability_')
    os.close(temp_fd)

    try:
        # Run bikeability analysis
        print("Running bikeability analysis...")
        result = subprocess.run([
            sys.executable, osmfast_path, 'bikeability', osm_file,
            '--lat', str(center_lat),
            '--lon', str(center_lon),
            '--radius', str(radius),
            '-f', 'json',
            '-o', temp_path
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error running bikeability analysis: {result.stderr}")
            return 1

        # Load results
        try:
            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            print("Error: bikeability analysis did not produce output")
            return 1
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

    # Parse OSM to get visual features
    print("Extracting cycling features...")
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(osm_file)

    # Build coordinate lookup
    node_coords = {}
    for node_id, (lat, lon) in parser.node_coordinates.items():
        node_coords[node_id] = (float(lat), float(lon))

    # Extract cycling features within radius
    bike_ways = []
    intersections = []
    pois = []

    # Track nodes for intersection detection
    bike_nodes = set()
    car_road_nodes = set()

    car_roads = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'motorway_link', 'trunk_link', 'primary_link'}
    cycleway_tags = ('lane', 'track', 'opposite', 'opposite_lane', 'opposite_track')

    # First pass - identify bike and car nodes
    for way in ways:
        highway = way.tags.get('highway')
        if not highway:
            continue

        is_bike = (
            highway == 'cycleway' or
            way.tags.get('bicycle_road') == 'yes' or
            way.tags.get('cycleway') in cycleway_tags or
            way.tags.get('bicycle') in ('designated', 'yes')
        )

        is_car = highway in car_roads

        for ref in way.node_refs:
            if ref not in node_coords:
                continue
            lat, lon = node_coords[ref]
            if haversine(center_lon, center_lat, lon, lat) > radius:
                continue

            if is_bike:
                bike_nodes.add(ref)
            if is_car:
                car_road_nodes.add(ref)

    # Find dangerous intersections (bike meets car)
    dangerous_intersections = bike_nodes & car_road_nodes

    # Process ways for visualization
    for way in ways:
        highway = way.tags.get('highway')
        if not highway:
            continue

        coords = []
        for ref in way.node_refs:
            if ref in node_coords:
                coords.append(node_coords[ref])

        if len(coords) < 2:
            continue

        # Check if within radius
        avg_lat = sum(c[0] for c in coords) / len(coords)
        avg_lon = sum(c[1] for c in coords) / len(coords)
        if haversine(center_lon, center_lat, avg_lon, avg_lat) > radius:
            continue

        # Classify cycling infrastructure
        way_type = 'other'
        color = '#888888'

        cycleway = way.tags.get('cycleway')
        bicycle = way.tags.get('bicycle')
        bicycle_road = way.tags.get('bicycle_road')

        if highway == 'cycleway':
            way_type = 'cycleway'
            color = BIKE_COLORS['cycleway']
        elif bicycle_road == 'yes':
            way_type = 'bike_road'
            color = BIKE_COLORS['bike_road']
        elif cycleway in cycleway_tags:
            way_type = 'bike_lane'
            color = BIKE_COLORS['bike_lane']
        elif highway == 'path' and bicycle in ('yes', 'designated'):
            way_type = 'shared'
            color = BIKE_COLORS['shared']
        elif highway in car_roads:
            way_type = 'main_road'
            color = BIKE_COLORS['main_road']
        elif highway in ('residential', 'living_street', 'service'):
            way_type = 'residential'
            color = BIKE_COLORS['residential']

        bike_ways.append({
            'coords': [[c[0], c[1]] for c in coords],
            'type': way_type,
            'highway': escape_html(highway),
            'color': color,
            'name': escape_html(way.tags.get('name', '')),
            'cycleway': escape_html(cycleway or ''),
            'surface': escape_html(way.tags.get('surface', ''))
        })

    # Process nodes for POIs and intersections
    for node in nodes:
        if node.id not in node_coords:
            continue

        lat, lon = node_coords[node.id]
        if haversine(center_lon, center_lat, lon, lat) > radius:
            continue

        # Check for dangerous intersections
        if node.id in dangerous_intersections:
            crossing = node.tags.get('crossing')
            has_signals = (
                node.tags.get('highway') == 'traffic_signals' or
                crossing == 'traffic_signals' or
                node.tags.get('crossing:signals') == 'yes'
            )
            intersections.append({
                'lat': lat,
                'lon': lon,
                'safe': has_signals,
                'symbol': '🚦' if has_signals else '⚠️',
                'label': 'Signalized Crossing' if has_signals else 'Dangerous Intersection'
            })

        # Check for bike amenities
        amenity = node.tags.get('amenity')
        shop = node.tags.get('shop')

        poi_type = None
        if amenity in ('bicycle_parking', 'bicycle_rental', 'bicycle_repair_station', 'compressed_air'):
            poi_type = amenity
        elif shop in ('bicycle', 'bike'):
            poi_type = 'bicycle_shop'

        if poi_type:
            if poi_type in BIKE_POI_SYMBOLS:
                symbol, color, category = BIKE_POI_SYMBOLS[poi_type]
            else:
                symbol, color, category = '🚲', '#607D8B', 'other'

            pois.append({
                'lat': lat,
                'lon': lon,
                'name': escape_html(node.tags.get('name', poi_type.replace('_', ' ').title())),
                'type': escape_html(poi_type),
                'category': category,
                'symbol': symbol,
                'color': color,
                'capacity': escape_html(node.tags.get('capacity', ''))
            })

    print(f"  Found {len(bike_ways)} road segments")
    print(f"  Found {len(intersections)} bike-car intersections")
    print(f"  Found {len(pois)} bike facilities")

    # Generate HTML
    html = generate_html(data, center_lat, center_lon, radius,
                         bike_ways, intersections, pois)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\nCreated {output_file}")
    print(f"  Center: {center_lat}, {center_lon}")
    print(f"  Radius: {radius}m")

    # Open in browser if requested
    if not args.no_open:
        import webbrowser
        # Use absolute path for reliable browser opening
        abs_path = os.path.abspath(output_file)
        webbrowser.open(f'file://{abs_path}')

    return 0


def generate_html(data: dict, center_lat: float, center_lon: float, radius: int,
                  roads: list, intersections: list, pois: list) -> str:
    """Generate the HTML visualization."""
    html = '''<!DOCTYPE html>
<html>
<head>
    <title>OSMFast - Bikeability Analysis</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Segoe UI', Arial, sans-serif; }
        #map { position: absolute; top: 0; bottom: 0; left: 0; right: 380px; }

        .sidebar {
            position: absolute;
            top: 0; right: 0; bottom: 0;
            width: 380px;
            background: #1a1a2e;
            padding: 25px;
            overflow-y: auto;
            color: #f5f5f5;
            border-left: 4px solid #00C853;
        }

        .sidebar h1 { font-size: 24px; margin-bottom: 5px; color: #fff; }
        .sidebar .subtitle { color: #999; font-size: 13px; margin-bottom: 25px; }

        .score-display {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            text-align: center;
            border: 2px solid #00C853;
        }

        .score-value {
            font-size: 48px;
            font-weight: bold;
            color: #00C853;
        }

        .score-grade {
            font-size: 24px;
            color: #fff;
            margin-top: 5px;
        }

        .component-section {
            background: #16213e;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }

        .component-title {
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #00C853;
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #1a1a2e;
        }
        .metric-row:last-child { border-bottom: none; }
        .metric-label { color: #aaa; font-size: 13px; }
        .metric-value { color: #fff; font-weight: bold; font-size: 13px; }

        .bar-container {
            background: #1a1a2e;
            border-radius: 4px;
            height: 8px;
            margin-top: 4px;
            overflow: hidden;
        }

        .bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }

        .layer-control {
            position: absolute;
            bottom: 25px;
            left: 15px;
            background: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 15px rgba(0,0,0,0.15);
            z-index: 1000;
            min-width: 200px;
        }

        .layer-title { font-size: 12px; font-weight: 600; margin-bottom: 10px; color: #333; }

        .layer-item {
            display: flex;
            align-items: center;
            margin: 6px 0;
            font-size: 12px;
            color: #666;
            cursor: pointer;
        }

        .layer-item input[type="checkbox"] { margin-right: 8px; cursor: pointer; }

        .layer-line {
            width: 20px;
            height: 4px;
            border-radius: 2px;
            margin-right: 8px;
        }

        .layer-symbol {
            width: 22px;
            text-align: center;
            font-size: 14px;
            margin-right: 6px;
        }

        .layer-count {
            margin-left: auto;
            color: #999;
            font-size: 11px;
        }

        .poi-marker {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            font-size: 16px;
            background: white;
            border-radius: 50%;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            border: 2px solid;
        }

        .intersection-marker {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            font-size: 14px;
            background: white;
            border-radius: 50%;
            box-shadow: 0 1px 4px rgba(0,0,0,0.25);
        }

        .legend {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #333;
        }

        .legend-title {
            font-size: 11px;
            color: #888;
            margin-bottom: 8px;
            text-transform: uppercase;
        }

        .legend-item {
            display: flex;
            align-items: center;
            margin: 4px 0;
            font-size: 11px;
            color: #ccc;
        }

        .legend-color {
            width: 16px;
            height: 4px;
            border-radius: 2px;
            margin-right: 8px;
        }
    </style>
</head>
<body>
    <div id="map"></div>

    <div class="sidebar">
        <h1>Bikeability Analysis</h1>
        <div class="subtitle">DESCRIPTION</div>

        <div class="score-display">
            <div class="score-value">SCORE</div>
            <div class="score-grade">Grade: GRADE</div>
        </div>

        <div class="component-section">
            <div class="component-title">Component Scores</div>
            COMPONENT_BARS
        </div>

        <div class="component-section">
            <div class="component-title">Cycling Infrastructure</div>
            <div class="metric-row">
                <span class="metric-label">Total network</span>
                <span class="metric-value">TOTAL_KM km</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Dedicated cycleways</span>
                <span class="metric-value">CYCLEWAY_KM km</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Bike lanes</span>
                <span class="metric-value">BIKELANE_KM km</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Bike roads</span>
                <span class="metric-value">BIKEROAD_KM km</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Separated from traffic</span>
                <span class="metric-value">SEPARATED_KM km</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Dedicated ratio</span>
                <span class="metric-value">DEDICATED_PCT%</span>
            </div>
        </div>

        <div class="component-section">
            <div class="component-title">Intersection Safety</div>
            <div class="metric-row">
                <span class="metric-label">Bike-car intersections</span>
                <span class="metric-value">TOTAL_INTERSECTIONS</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Safe (signalized)</span>
                <span class="metric-value" style="color:#4CAF50">SAFE_INTERSECTIONS</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Dangerous</span>
                <span class="metric-value" style="color:#F44336">DANGEROUS_INTERSECTIONS</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Safety score</span>
                <span class="metric-value">INTERSECTION_SAFETY/100</span>
            </div>
        </div>

        <div class="component-section">
            <div class="component-title">Facilities</div>
            <div class="metric-row">
                <span class="metric-label">Bike parking</span>
                <span class="metric-value">PARKING_COUNT</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Bike rental</span>
                <span class="metric-value">RENTAL_COUNT</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Repair stations</span>
                <span class="metric-value">REPAIR_COUNT</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Bike shops</span>
                <span class="metric-value">SHOP_COUNT</span>
            </div>
        </div>

        <div class="legend">
            <div class="legend-title">Map Legend</div>
            <div class="legend-item">
                <div class="legend-color" style="background:#00C853"></div> Dedicated cycleway
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background:#7C4DFF"></div> Bike lane
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background:#00BCD4"></div> Bike road
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background:#FF9800"></div> Shared path
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background:#F44336"></div> Main road (caution)
            </div>
        </div>
    </div>

    <div class="layer-control">
        <div class="layer-title">Infrastructure</div>
        <label class="layer-item">
            <input type="checkbox" id="layer-cycleway" checked onchange="toggleLayer('cycleway')">
            <div class="layer-line" style="background:#00C853"></div> Cycleways
            <span class="layer-count" id="count-cycleway"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-bike_lane" checked onchange="toggleLayer('bike_lane')">
            <div class="layer-line" style="background:#7C4DFF"></div> Bike lanes
            <span class="layer-count" id="count-bike_lane"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-bike_road" checked onchange="toggleLayer('bike_road')">
            <div class="layer-line" style="background:#00BCD4"></div> Bike roads
            <span class="layer-count" id="count-bike_road"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-shared" checked onchange="toggleLayer('shared')">
            <div class="layer-line" style="background:#FF9800"></div> Shared paths
            <span class="layer-count" id="count-shared"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-main_road" checked onchange="toggleLayer('main_road')">
            <div class="layer-line" style="background:#F44336"></div> Main roads
            <span class="layer-count" id="count-main_road"></span>
        </label>

        <div class="layer-title" style="margin-top:12px">Safety</div>
        <label class="layer-item">
            <input type="checkbox" id="layer-dangerous" checked onchange="toggleLayer('dangerous')">
            <span class="layer-symbol">⚠️</span> Dangerous intersections
            <span class="layer-count" id="count-dangerous"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-safe" checked onchange="toggleLayer('safe')">
            <span class="layer-symbol">🚦</span> Safe crossings
            <span class="layer-count" id="count-safe"></span>
        </label>

        <div class="layer-title" style="margin-top:12px">Facilities</div>
        <label class="layer-item">
            <input type="checkbox" id="layer-parking" checked onchange="toggleLayer('parking')">
            <span class="layer-symbol">🅿️</span> Bike parking
            <span class="layer-count" id="count-parking"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-rental" checked onchange="toggleLayer('rental')">
            <span class="layer-symbol">🚲</span> Bike rental
            <span class="layer-count" id="count-rental"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-shop" checked onchange="toggleLayer('shop')">
            <span class="layer-symbol">🏪</span> Bike shops
            <span class="layer-count" id="count-shop"></span>
        </label>
    </div>

    <script>
        var center = [CENTER_LAT, CENTER_LON];
        var radius = RADIUS;
        var roads = ROADS_JSON;
        var intersectionsData = INTERSECTIONS_JSON;
        var pois = POIS_JSON;

        var map = L.map('map').setView(center, 14);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OSM, CARTO | OSMFast Bikeability',
            maxZoom: 22
        }).addTo(map);

        // Layer groups
        var layers = {
            cycleway: L.layerGroup().addTo(map),
            bike_lane: L.layerGroup().addTo(map),
            bike_road: L.layerGroup().addTo(map),
            shared: L.layerGroup().addTo(map),
            main_road: L.layerGroup().addTo(map),
            residential: L.layerGroup().addTo(map),
            other: L.layerGroup().addTo(map),
            dangerous: L.layerGroup().addTo(map),
            safe: L.layerGroup().addTo(map),
            parking: L.layerGroup().addTo(map),
            rental: L.layerGroup().addTo(map),
            repair: L.layerGroup().addTo(map),
            shop: L.layerGroup().addTo(map)
        };

        var counts = {};
        for (var key in layers) counts[key] = 0;

        // Draw roads
        roads.forEach(function(road) {
            var weight = road.type === 'cycleway' ? 5 : (road.type === 'bike_lane' ? 4 : 2);
            var opacity = road.type === 'main_road' ? 0.4 : 0.8;

            var popup = '<b>' + (road.name || road.highway) + '</b><br>' +
                        'Type: ' + road.type + '<br>' +
                        (road.cycleway ? 'Cycleway: ' + road.cycleway + '<br>' : '') +
                        (road.surface ? 'Surface: ' + road.surface : '');

            var line = L.polyline(road.coords, {
                color: road.color,
                weight: weight,
                opacity: opacity
            }).bindPopup(popup);

            if (layers[road.type]) {
                layers[road.type].addLayer(line);
                counts[road.type]++;
            } else {
                layers.other.addLayer(line);
            }
        });

        // Draw intersections
        intersectionsData.forEach(function(i) {
            var icon = L.divIcon({
                className: 'intersection-icon',
                html: '<div class="intersection-marker" style="border:2px solid ' +
                      (i.safe ? '#4CAF50' : '#F44336') + '">' + i.symbol + '</div>',
                iconSize: [24, 24],
                iconAnchor: [12, 12]
            });

            var marker = L.marker([i.lat, i.lon], {icon: icon})
                .bindPopup('<b>' + i.label + '</b><br>' + i.lat.toFixed(6) + ', ' + i.lon.toFixed(6));

            if (i.safe) {
                layers.safe.addLayer(marker);
                counts.safe++;
            } else {
                layers.dangerous.addLayer(marker);
                counts.dangerous++;
            }
        });

        // Draw POIs
        pois.forEach(function(poi) {
            var icon = L.divIcon({
                className: 'poi-icon',
                html: '<div class="poi-marker" style="border-color:' + poi.color + '">' + poi.symbol + '</div>',
                iconSize: [28, 28],
                iconAnchor: [14, 14]
            });

            var popup = '<b>' + poi.name + '</b><br>Type: ' + poi.type.replace(/_/g, ' ') +
                        (poi.capacity ? '<br>Capacity: ' + poi.capacity : '');
            var marker = L.marker([poi.lat, poi.lon], {icon: icon}).bindPopup(popup);

            if (layers[poi.category]) {
                layers[poi.category].addLayer(marker);
                counts[poi.category]++;
            }
        });

        // Update counts
        for (var key in counts) {
            var el = document.getElementById('count-' + key);
            if (el && counts[key] > 0) el.textContent = counts[key];
        }

        function toggleLayer(layerKey) {
            var checkbox = document.getElementById('layer-' + layerKey);
            if (checkbox && layers[layerKey]) {
                if (checkbox.checked) {
                    map.addLayer(layers[layerKey]);
                } else {
                    map.removeLayer(layers[layerKey]);
                }
            }
        }

        // Center marker
        L.marker(center, {
            icon: L.divIcon({
                className: 'center-marker',
                html: '<div style="width:20px;height:20px;background:#00C853;border:3px solid white;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.3)"></div>',
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            })
        }).addTo(map).bindPopup('<b>Analysis Center</b>');

        // Radius circle
        L.circle(center, {
            radius: radius,
            color: '#00C853',
            fillColor: '#00C853',
            fillOpacity: 0.05,
            weight: 2,
            dashArray: '5,5'
        }).addTo(map);
    </script>
</body>
</html>'''

    # Fill template - replace longer/more specific strings first to avoid substring issues
    html = html.replace('DESCRIPTION', escape_html(data.get('description', 'Bikeability Analysis')))
    html = html.replace('CENTER_LAT', str(center_lat))
    html = html.replace('CENTER_LON', str(center_lon))

    # Intersection metrics (replace INTERSECTION_SAFETY before SCORE to avoid substring issue)
    intersect = data.get('intersections', {})
    html = html.replace('TOTAL_INTERSECTIONS', str(intersect.get('total_bike_car_intersections', 0)))
    html = html.replace('SAFE_INTERSECTIONS', str(intersect.get('safe_intersections', 0)))
    html = html.replace('DANGEROUS_INTERSECTIONS', str(intersect.get('dangerous_intersections', 0)))
    html = html.replace('INTERSECTION_SAFETY', f"{intersect.get('avg_intersection_safety', 0):.1f}")

    # Score (after INTERSECTION_SAFETY to avoid corrupting it)
    html = html.replace('SCORE', str(round(data.get('bikeability_score', 0), 1)))
    html = html.replace('GRADE', escape_html(data.get('grade', 'N/A')))
    html = html.replace('RADIUS', str(radius))

    # Component scores bars
    components = data.get('component_scores', {})
    component_html = ''
    colors = {
        'dedicated_infrastructure': '#00C853',
        'intersection_safety': '#FF5722',
        'road_quality': '#2196F3',
        'network_connectivity': '#9C27B0',
        'traffic_separation': '#00BCD4',
        'bike_facilities': '#FF9800',
        'traffic_calming': '#795548',
        'topography': '#607D8B'
    }
    for comp, score in components.items():
        color = colors.get(comp, '#888')
        label = comp.replace('_', ' ').title()
        component_html += f'''
            <div class="metric-row">
                <span class="metric-label">{escape_html(label)}</span>
                <span class="metric-value">{score:.1f}</span>
            </div>
            <div class="bar-container">
                <div class="bar-fill" style="width:{min(100, score)}%;background:{color}"></div>
            </div>'''

    html = html.replace('COMPONENT_BARS', component_html)

    # Infrastructure metrics
    infra = data.get('infrastructure', {})
    html = html.replace('TOTAL_KM', f"{infra.get('total_road_length_m', 0) / 1000:.1f}")
    html = html.replace('CYCLEWAY_KM', f"{infra.get('cycleway_length_m', 0) / 1000:.2f}")
    html = html.replace('BIKELANE_KM', f"{infra.get('bike_lane_length_m', 0) / 1000:.2f}")
    html = html.replace('BIKEROAD_KM', f"{infra.get('bike_road_length_m', 0) / 1000:.2f}")
    html = html.replace('SEPARATED_KM', f"{infra.get('separated_length_m', 0) / 1000:.2f}")
    html = html.replace('DEDICATED_PCT', f"{infra.get('dedicated_ratio', 0) * 100:.1f}")

    # Facilities
    facilities = data.get('facilities', {})
    html = html.replace('PARKING_COUNT', str(facilities.get('parking_locations', 0)))
    html = html.replace('RENTAL_COUNT', str(facilities.get('rental_locations', 0)))
    html = html.replace('REPAIR_COUNT', str(facilities.get('repair_stations', 0)))
    html = html.replace('SHOP_COUNT', str(facilities.get('bike_shops', 0)))

    # JSON data - escape </script> to prevent script injection
    def safe_json(data):
        """Escape JSON for safe embedding in <script> tags."""
        return json.dumps(data).replace('</script>', '<\\/script>').replace('<!--', '<\\!--')

    html = html.replace('ROADS_JSON', safe_json(roads))
    html = html.replace('INTERSECTIONS_JSON', safe_json(intersections))
    html = html.replace('POIS_JSON', safe_json(pois))

    return html
