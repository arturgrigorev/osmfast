"""Render walkability analysis visualization with map features."""
import argparse
import heapq
import json
import math
import subprocess
import sys
from pathlib import Path


# Walking speeds in km/h for different road types
WALK_SPEEDS = {
    'default': 5,
    'steps': 3,
    'path': 4,
    'footway': 5,
    'pedestrian': 5,
    'residential': 5,
    'living_street': 5,
    'primary': 4,
    'secondary': 4,
    'tertiary': 5,
    'service': 5,
    'unclassified': 5,
    'track': 4
}

WALKABLE_ROADS = frozenset({
    'primary', 'secondary', 'tertiary', 'residential', 'living_street',
    'unclassified', 'service', 'pedestrian', 'footway', 'path', 'steps', 'track'
})


COMMAND_HELP = 'Generate interactive walkability visualization map'
COMMAND_DESCRIPTION = '''Generate an interactive HTML map showing walkability analysis results.

Runs walkability analysis and creates a Leaflet-based visualization showing:
- Road network with color-coded types (pedestrian, residential, main roads)
- Points of interest with emoji markers
- Pedestrian crossings and traffic signals
- Detailed metrics in sidebar

Examples:
  osmfast render-walkability map.osm --lat -33.9 --lon 151.207
  osmfast render-walkability map.osm --lat 51.5 --lon -0.1 --radius 500
  osmfast render-walkability map.osm --lat 40.7 --lon -74.0 -o mymap.html
'''

# Symbol mappings for POIs
POI_SYMBOLS = {
    # Food & Dining
    'restaurant': ('🍽️', '#FF5722', 'food'),
    'cafe': ('☕', '#795548', 'food'),
    'fast_food': ('🍔', '#FF9800', 'food'),
    'bar': ('🍺', '#FFC107', 'food'),
    'pub': ('🍺', '#FFC107', 'food'),
    'bakery': ('🥐', '#8D6E63', 'food'),
    'ice_cream': ('🍦', '#E91E63', 'food'),
    # Services
    'bank': ('🏦', '#3F51B5', 'services'),
    'atm': ('💳', '#5C6BC0', 'services'),
    'post_office': ('✉️', '#F44336', 'services'),
    'pharmacy': ('💊', '#4CAF50', 'services'),
    'hospital': ('🏥', '#F44336', 'services'),
    'doctors': ('⚕️', '#2196F3', 'services'),
    'dentist': ('🦷', '#00BCD4', 'services'),
    # Street furniture & utilities
    'bench': ('🪑', '#795548', 'furniture'),
    'bicycle_parking': ('🚲', '#607D8B', 'cycling'),
    'toilets': ('🚻', '#5D4037', 'services'),
    'drinking_water': ('🚰', '#0288D1', 'services'),
    'waste_basket': ('🗑️', '#455A64', 'furniture'),
    # Places of worship
    'place_of_worship': ('⛪', '#6D4C41', 'worship'),
    # Shopping
    'supermarket': ('🛒', '#9C27B0', 'shopping'),
    'convenience': ('🏪', '#AB47BC', 'shopping'),
    'clothes': ('👕', '#7B1FA2', 'shopping'),
    'shoes': ('👟', '#6A1B9A', 'shopping'),
    # Education
    'school': ('🏫', '#3F51B5', 'education'),
    'kindergarten': ('💒', '#5C6BC0', 'education'),
    'library': ('📚', '#1976D2', 'books'),
    'public_bookcase': ('📖', '#42A5F5', 'books'),
    'college': ('🎓', '#303F9F', 'education'),
    'university': ('🎓', '#1A237E', 'education'),
    # Leisure
    'park': ('🌳', '#4CAF50', 'leisure'),
    'playground': ('🎠', '#8BC34A', 'leisure'),
    'garden': ('🌷', '#66BB6A', 'leisure'),
    'sports_centre': ('🏋️', '#FF5722', 'leisure'),
    'fitness_centre': ('💪', '#FF7043', 'leisure'),
    'cinema': ('🎬', '#9C27B0', 'leisure'),
    'theatre': ('🎭', '#7B1FA2', 'leisure'),
    # Transit
    'bus_stop': ('🚌', '#00BCD4', 'transit'),
    'bus_station': ('🚌', '#00ACC1', 'transit'),
    'tram_stop': ('🚊', '#0097A7', 'transit'),
    'subway_entrance': ('🚇', '#00838F', 'transit'),
    'train_station': ('🚆', '#006064', 'transit'),
}

# Default symbols by category
CATEGORY_DEFAULTS = {
    'food': ('🍴', '#FF5722'),
    'services': ('🏢', '#3F51B5'),
    'shopping': ('🛍️', '#9C27B0'),
    'education': ('📖', '#3F51B5'),
    'leisure': ('⛱️', '#4CAF50'),
    'transit': ('🚏', '#00BCD4'),
    'amenity': ('📍', '#E91E63'),
}


def setup_parser(subparsers) -> None:
    """Add render-walkability subcommand parser."""
    parser = subparsers.add_parser(
        'render-walkability',
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
    parser.add_argument('--radius', '-r', type=int, default=800,
                        help='Analysis radius in meters (default: 800)')
    parser.add_argument('-o', '--output', default='walkability_map.html',
                        help='Output HTML file (default: walkability_map.html)')
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
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def build_walk_graph(ways, node_coords):
    """Build walking network graph from ways."""
    graph = {}  # node_id -> [(neighbor_id, travel_time_seconds), ...]

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in WALKABLE_ROADS:
            continue

        speed = WALK_SPEEDS.get(highway, WALK_SPEEDS['default'])
        refs = way.node_refs

        for i in range(len(refs) - 1):
            from_id = refs[i]
            to_id = refs[i + 1]

            if from_id not in node_coords or to_id not in node_coords:
                continue

            from_lat, from_lon = node_coords[from_id]
            to_lat, to_lon = node_coords[to_id]

            distance = haversine(from_lon, from_lat, to_lon, to_lat)
            travel_time = (distance / 1000) / speed * 3600  # seconds

            if from_id not in graph:
                graph[from_id] = []
            if to_id not in graph:
                graph[to_id] = []

            # Walking is bidirectional
            graph[from_id].append((to_id, travel_time))
            graph[to_id].append((from_id, travel_time))

    return graph


def find_nearest_node(target_lat, target_lon, node_coords, graph):
    """Find the nearest graph node to target coordinates."""
    min_dist = float('inf')
    nearest = None

    for node_id in graph.keys():
        if node_id not in node_coords:
            continue
        lat, lon = node_coords[node_id]
        dist = haversine(target_lon, target_lat, lon, lat)
        if dist < min_dist:
            min_dist = dist
            nearest = node_id

    return nearest, min_dist


def dijkstra(graph, start, max_time_seconds):
    """Run Dijkstra to find all reachable nodes within max_time."""
    distances = {start: 0}
    heap = [(0, start)]

    while heap:
        curr_dist, curr_node = heapq.heappop(heap)

        if curr_dist > max_time_seconds:
            continue

        if curr_dist > distances.get(curr_node, float('inf')):
            continue

        for neighbor, travel_time in graph.get(curr_node, []):
            new_dist = curr_dist + travel_time
            if new_dist < distances.get(neighbor, float('inf')) and new_dist <= max_time_seconds:
                distances[neighbor] = new_dist
                heapq.heappush(heap, (new_dist, neighbor))

    return distances


def get_reachable_points(node_coords, reachable_nodes):
    """Get all reachable node coordinates."""
    points = []
    for node_id in reachable_nodes.keys():
        if node_id in node_coords:
            lat, lon = node_coords[node_id]
            points.append((lat, lon))
    return points


def create_buffered_polygon(points, origin_lat, origin_lon, buffer_m=50, resolution=72):
    """Create a smooth polygon around points using radial buffer approach."""
    if len(points) < 3:
        return None

    # Convert buffer from meters to approximate degrees
    buffer_deg = buffer_m / 111000  # rough conversion

    # Find points in each angular bin, with buffer
    bin_size = 2 * math.pi / resolution
    bins = {}  # bin_idx -> (max_dist, lat, lon)

    for lat, lon in points:
        angle = math.atan2(lat - origin_lat, lon - origin_lon)
        dist = haversine(origin_lon, origin_lat, lon, lat)

        # Add buffer to distance
        buffered_dist = dist + buffer_m

        bin_idx = int((angle + math.pi) / bin_size) % resolution

        # Update this bin and neighboring bins for smoothness
        for offset in [-1, 0, 1]:
            idx = (bin_idx + offset) % resolution
            if idx not in bins or buffered_dist > bins[idx][0]:
                bins[idx] = (buffered_dist, lat, lon)

    # Create polygon points
    polygon = []
    for i in range(resolution):
        angle = (i * bin_size) - math.pi
        if i in bins:
            dist_m = bins[i][0]
        else:
            # Interpolate from neighbors
            prev_idx = (i - 1) % resolution
            next_idx = (i + 1) % resolution
            if prev_idx in bins and next_idx in bins:
                dist_m = (bins[prev_idx][0] + bins[next_idx][0]) / 2
            elif prev_idx in bins:
                dist_m = bins[prev_idx][0]
            elif next_idx in bins:
                dist_m = bins[next_idx][0]
            else:
                continue

        # Convert polar to cartesian (approximate for small areas)
        dist_deg = dist_m / 111000
        lat = origin_lat + dist_deg * math.sin(angle)
        lon = origin_lon + dist_deg * math.cos(angle) / math.cos(math.radians(origin_lat))
        polygon.append([lat, lon])

    if len(polygon) < 3:
        return None

    # Apply Chaikin smoothing for rounded corners
    polygon = chaikin_smooth(polygon, iterations=3)

    # Close the polygon
    if polygon[0] != polygon[-1]:
        polygon.append(polygon[0])

    return polygon


def chaikin_smooth(points, iterations=2):
    """Apply Chaikin's corner-cutting algorithm for smooth curves."""
    for _ in range(iterations):
        if len(points) < 3:
            return points
        new_points = []
        for i in range(len(points)):
            p0 = points[i]
            p1 = points[(i + 1) % len(points)]

            # Q = 3/4 * P0 + 1/4 * P1
            q = [0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1]]
            # R = 1/4 * P0 + 3/4 * P1
            r = [0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1]]

            new_points.append(q)
            new_points.append(r)
        points = new_points
    return points


def compute_isochrones(ways, node_coords, center_lat, center_lon, times_minutes=[5, 10, 15]):
    """Compute walking isochrones for given times."""
    print("  Building pedestrian network...")
    graph = build_walk_graph(ways, node_coords)

    if not graph:
        print("  Warning: No walkable roads found")
        return {}

    origin_node, origin_dist = find_nearest_node(center_lat, center_lon, node_coords, graph)

    if origin_node is None:
        print("  Warning: No road network near origin")
        return {}

    print(f"  Origin node {origin_dist:.0f}m from center")

    isochrones = {}
    for mins in times_minutes:
        max_time = mins * 60  # seconds
        reachable = dijkstra(graph, origin_node, max_time)
        points = get_reachable_points(node_coords, reachable)

        # Create smooth buffered polygon around reachable points
        polygon = create_buffered_polygon(points, center_lat, center_lon, buffer_m=40)
        if polygon:
            isochrones[mins] = polygon
            print(f"  {mins} min: {len(reachable)} nodes")

    return isochrones


def run(args: argparse.Namespace) -> int:
    """Execute render-walkability command."""
    from osm_core.parsing.mmap_parser import UltraFastOSMParser

    osm_file = args.input_file
    center_lat = args.lat
    center_lon = args.lon
    radius = args.radius
    output_file = args.output

    # Run walkability analysis
    print("Running walkability analysis...")
    result = subprocess.run([
        sys.executable, 'osmfast.py', 'walkability', osm_file,
        '--lat', str(center_lat),
        '--lon', str(center_lon),
        '--radius', str(radius),
        '-f', 'json',
        '-o', 'walkability_result.json'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error running walkability analysis: {result.stderr}")
        return 1

    # Load results
    try:
        with open('walkability_result.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: walkability_result.json not found")
        return 1

    # Parse OSM to get visual features
    print("Extracting map features...")
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(osm_file)

    # Build coordinate lookup
    node_coords = {}
    for node_id, (lat, lon) in parser.node_coordinates.items():
        node_coords[node_id] = (float(lat), float(lon))

    # Extract features within radius
    pedestrian_ways = []
    crossings = []
    pois = []

    # Process ways
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

        way_type = 'other'
        color = '#888888'

        if highway in ('footway', 'pedestrian', 'path'):
            way_type = 'pedestrian'
            color = '#4CAF50'
        elif highway == 'steps':
            way_type = 'steps'
            color = '#8BC34A'
        elif highway in ('living_street', 'residential'):
            way_type = 'residential'
            color = '#2196F3'
        elif highway in ('primary', 'secondary', 'tertiary'):
            way_type = 'main_road'
            color = '#FF9800'

        pedestrian_ways.append({
            'coords': [[c[0], c[1]] for c in coords],
            'type': way_type,
            'highway': highway,
            'color': color,
            'name': way.tags.get('name', '')
        })

    # Process nodes for POIs and crossings
    for node in nodes:
        if node.id not in node_coords:
            continue

        lat, lon = node_coords[node.id]
        if haversine(center_lon, center_lat, lon, lat) > radius:
            continue

        highway = node.tags.get('highway')
        if highway == 'crossing':
            crossings.append({'lat': lat, 'lon': lon, 'symbol': '🚶', 'label': 'Pedestrian Crossing'})
        elif highway == 'traffic_signals':
            crossings.append({'lat': lat, 'lon': lon, 'signal': True, 'symbol': '🚦', 'label': 'Traffic Signal'})

        amenity = node.tags.get('amenity')
        shop = node.tags.get('shop')
        leisure = node.tags.get('leisure')
        public_transport = node.tags.get('public_transport')

        poi_type = amenity or shop or leisure
        if not poi_type and public_transport:
            poi_type = public_transport

        if poi_type:
            # Look up symbol
            if poi_type in POI_SYMBOLS:
                symbol, color, category = POI_SYMBOLS[poi_type]
            elif shop:
                symbol, color = CATEGORY_DEFAULTS['shopping']
                category = 'shopping'
            elif leisure:
                symbol, color = CATEGORY_DEFAULTS['leisure']
                category = 'leisure'
            elif public_transport:
                symbol, color = CATEGORY_DEFAULTS['transit']
                category = 'transit'
            else:
                symbol, color = CATEGORY_DEFAULTS['amenity']
                category = 'amenity'

            pois.append({
                'lat': lat,
                'lon': lon,
                'name': node.tags.get('name', poi_type.replace('_', ' ').title()),
                'type': poi_type,
                'category': category,
                'symbol': symbol,
                'color': color
            })

    print(f"  Found {len(pedestrian_ways)} road segments")
    print(f"  Found {len(crossings)} crossings")
    print(f"  Found {len(pois)} POIs")

    # Compute network-based isochrones
    print("Computing walking isochrones...")
    isochrones = compute_isochrones(ways, node_coords, center_lat, center_lon, [5, 10, 15])

    # Generate HTML
    html = generate_html(data, center_lat, center_lon, radius,
                         pedestrian_ways, crossings, pois, isochrones)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\nCreated {output_file}")
    print(f"  Center: {center_lat}, {center_lon}")
    print(f"  Radius: {radius}m | Area: {data['area_km2']:.2f} km2")

    # Open in browser if requested
    if not args.no_open:
        import webbrowser
        webbrowser.open(output_file)

    return 0


def generate_html(data: dict, center_lat: float, center_lon: float, radius: int,
                  roads: list, crossings: list, pois: list, isochrones: dict = None) -> str:
    """Generate the HTML visualization."""
    html = '''<!DOCTYPE html>
<html>
<head>
    <title>OSMFast - Walkability Analysis</title>
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
            top: 0;
            right: 0;
            bottom: 0;
            width: 380px;
            background: #1a1a1a;
            padding: 25px;
            overflow-y: auto;
            color: #f5f5f5;
            border-left: 4px solid #C74634;
        }

        .sidebar h1 { font-size: 24px; margin-bottom: 5px; color: #fff; }
        .sidebar .subtitle { color: #999; font-size: 13px; margin-bottom: 25px; }

        .component-section {
            background: #262626;
            border-radius: 4px;
            padding: 15px;
            margin-bottom: 15px;
            border: 1px solid #333;
        }

        .component-title {
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #C74634;
        }

        .metric-row {
            display: flex;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #333;
        }
        .metric-row:last-child { border-bottom: none; }
        .metric-text { color: #ccc; font-size: 14px; }
        .metric-text strong { color: #fff; }

        .amenity-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }
        .amenity-item {
            display: flex;
            align-items: center;
            padding: 6px 8px;
            background: #1a1a1a;
            border-radius: 4px;
            border: 1px solid #333;
        }
        .amenity-icon { font-size: 16px; margin-right: 8px; }
        .amenity-count { font-weight: bold; color: #fff; margin-right: 4px; }
        .amenity-label { color: #999; font-size: 12px; }

        .layer-control {
            position: absolute;
            bottom: 25px;
            left: 15px;
            background: white;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 15px rgba(0,0,0,0.15);
            z-index: 1000;
            max-height: calc(100vh - 80px);
            overflow-y: auto;
            min-width: 180px;
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

        .layer-item:hover { color: #333; }

        .layer-item input[type="checkbox"] {
            margin-right: 8px;
            cursor: pointer;
        }

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
            font-size: 18px;
            background: white;
            border-radius: 50%;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            border: 2px solid;
        }

        .crossing-marker {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 22px;
            height: 22px;
            font-size: 14px;
            background: white;
            border-radius: 50%;
            box-shadow: 0 1px 4px rgba(0,0,0,0.25);
        }

        .coords {
            font-family: monospace;
            font-size: 11px;
            color: #666;
            display: block;
            margin: 4px 0;
        }

        .copy-btn {
            background: #C74634;
            color: white;
            border: none;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 11px;
            cursor: pointer;
            margin-top: 4px;
        }

        .copy-btn:hover {
            background: #a33a2a;
        }
    </style>
</head>
<body>
    <div id="map"></div>

    <div class="sidebar">
        <h1>Walkability Analysis</h1>
        <div class="subtitle">DESCRIPTION</div>

        <div class="component-section">
            <div class="component-title">Road Network</div>
            <div class="metric-row">
                <span class="metric-text">Total network: <strong>TOTAL_NETWORK_KM km</strong></span>
            </div>
            <div class="metric-row">
                <span class="metric-text">Pedestrian paths: <strong>PEDESTRIAN_KM km</strong> (PEDESTRIAN_PCT%)</span>
            </div>
            <div class="metric-row">
                <span class="metric-text">Intersections: <strong>INTERSECTIONS_COUNT</strong> (INTERSECTION_DENSITY/km2)</span>
            </div>
            <div class="metric-row">
                <span class="metric-text">Dead ends: <strong>DEAD_ENDS</strong></span>
            </div>
            <div class="metric-row">
                <span class="metric-text">Connectivity: <strong>CONNECTIVITY_INDEX</strong></span>
            </div>
            <div class="metric-row">
                <span class="metric-text">Sidewalk coverage: <strong>SIDEWALK_PCT%</strong></span>
            </div>
        </div>

        <div class="component-section">
            <div class="component-title">Amenities (TOTAL_AMENITIES)</div>
            <div class="amenity-grid">
                AMENITY_ITEMS
            </div>
        </div>

        <div class="component-section">
            <div class="component-title">Accessibility</div>
            <div class="metric-row">
                <span class="metric-text">Nearest food: <strong>DIST_FOOD m</strong></span>
            </div>
            <div class="metric-row">
                <span class="metric-text">Nearest shop: <strong>DIST_SHOP m</strong></span>
            </div>
            <div class="metric-row">
                <span class="metric-text">Nearest transit: <strong>DIST_TRANSIT m</strong></span>
            </div>
        </div>

        <div class="component-section">
            <div class="component-title">Safety</div>
            <div class="metric-row">
                <span class="metric-text">Crossings: <strong>CROSSINGS_VAL</strong> (CROSSINGS_DENSITY/km2)</span>
            </div>
            <div class="metric-row">
                <span class="metric-text">Traffic signals: <strong>SIGNALS_VAL</strong></span>
            </div>
            <div class="metric-row">
                <span class="metric-text">Street lighting: <strong>LIGHTING_VAL</strong></span>
            </div>
        </div>

        <div class="component-section">
            <div class="component-title">Green Spaces</div>
            <div class="metric-row">
                <span class="metric-text">Parks: <strong>GREENSPACES_VAL</strong></span>
            </div>
            <div class="metric-row">
                <span class="metric-text">Area: <strong>GREENSPACE_HA ha</strong> (GREENSPACE_PCT%)</span>
            </div>
        </div>

        <div class="component-section">
            <div class="component-title">Buildings</div>
            <div class="metric-row">
                <span class="metric-text">Count: <strong>BUILDING_COUNT</strong> (BUILDING_DENSITY/km2)</span>
            </div>
            <div class="metric-row">
                <span class="metric-text">Footprint: <strong>BUILDING_HA ha</strong> (BUILDING_PCT%)</span>
            </div>
        </div>
    </div>

    <div class="layer-control" autocomplete="off">
        <div class="layer-title">Road Types</div>
        <label class="layer-item">
            <input type="checkbox" id="layer-pedestrian" checked onchange="toggleLayer('pedestrian')">
            <div class="layer-line" style="background:#4CAF50"></div> Footway/Path
            <span class="layer-count" id="count-pedestrian"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-residential" checked onchange="toggleLayer('residential')">
            <div class="layer-line" style="background:#2196F3"></div> Residential
            <span class="layer-count" id="count-residential"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-main_road" checked onchange="toggleLayer('main_road')">
            <div class="layer-line" style="background:#FF9800"></div> Main Road
            <span class="layer-count" id="count-main_road"></span>
        </label>

        <div class="layer-title" style="margin-top:12px">Amenities</div>
        <label class="layer-item">
            <input type="checkbox" id="layer-food" checked onchange="toggleLayer('food')">
            <span class="layer-symbol">🍽️</span> Food
            <span class="layer-count" id="count-food"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-shopping" checked onchange="toggleLayer('shopping')">
            <span class="layer-symbol">🛒</span> Shopping
            <span class="layer-count" id="count-shopping"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-services" checked onchange="toggleLayer('services')">
            <span class="layer-symbol">🏦</span> Services
            <span class="layer-count" id="count-services"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-transit" checked onchange="toggleLayer('transit')">
            <span class="layer-symbol">🚌</span> Transit
            <span class="layer-count" id="count-transit"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-leisure" checked onchange="toggleLayer('leisure')">
            <span class="layer-symbol">🌳</span> Leisure
            <span class="layer-count" id="count-leisure"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-education" checked onchange="toggleLayer('education')">
            <span class="layer-symbol">🎓</span> Education
            <span class="layer-count" id="count-education"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-books" checked onchange="toggleLayer('books')">
            <span class="layer-symbol">📖</span> Books
            <span class="layer-count" id="count-books"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-furniture" checked onchange="toggleLayer('furniture')">
            <span class="layer-symbol">🪑</span> Furniture
            <span class="layer-count" id="count-furniture"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-cycling" checked onchange="toggleLayer('cycling')">
            <span class="layer-symbol">🚲</span> Cycling
            <span class="layer-count" id="count-cycling"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-worship" checked onchange="toggleLayer('worship')">
            <span class="layer-symbol">⛪</span> Worship
            <span class="layer-count" id="count-worship"></span>
        </label>

        <div class="layer-title" style="margin-top:12px">Walking Time</div>
        <label class="layer-item">
            <input type="checkbox" id="layer-iso5" checked onchange="toggleLayer('iso5')">
            <span class="layer-symbol" style="color:#4CAF50">●</span> 5 min (~400m)
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-iso10" checked onchange="toggleLayer('iso10')">
            <span class="layer-symbol" style="color:#FFC107">●</span> 10 min (~800m)
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-iso15" checked onchange="toggleLayer('iso15')">
            <span class="layer-symbol" style="color:#F44336">●</span> 15 min (~1.2km)
        </label>

        <div class="layer-title" style="margin-top:12px">Safety</div>
        <label class="layer-item">
            <input type="checkbox" id="layer-crossings" checked onchange="toggleLayer('crossings')">
            <span class="layer-symbol">🚶</span> Crossings
            <span class="layer-count" id="count-crossings"></span>
        </label>
        <label class="layer-item">
            <input type="checkbox" id="layer-signals" checked onchange="toggleLayer('signals')">
            <span class="layer-symbol">🚦</span> Signals
            <span class="layer-count" id="count-signals"></span>
        </label>
    </div>

    <script>
        var center = [CENTER_LAT, CENTER_LON];
        var radius = RADIUS;
        var roads = ROADS_JSON;
        var crossingsData = CROSSINGS_JSON;
        var pois = POIS_JSON;

        var map = L.map('map').setView(center, 15);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OSM, CARTO | OSMFast',
            maxZoom: 22
        }).addTo(map);

        // Layer groups
        var layers = {
            pedestrian: L.layerGroup().addTo(map),
            residential: L.layerGroup().addTo(map),
            main_road: L.layerGroup().addTo(map),
            other: L.layerGroup().addTo(map),
            steps: L.layerGroup().addTo(map),
            food: L.layerGroup().addTo(map),
            shopping: L.layerGroup().addTo(map),
            services: L.layerGroup().addTo(map),
            transit: L.layerGroup().addTo(map),
            leisure: L.layerGroup().addTo(map),
            education: L.layerGroup().addTo(map),
            books: L.layerGroup().addTo(map),
            furniture: L.layerGroup().addTo(map),
            cycling: L.layerGroup().addTo(map),
            worship: L.layerGroup().addTo(map),
            amenity: L.layerGroup().addTo(map),
            crossings: L.layerGroup().addTo(map),
            signals: L.layerGroup().addTo(map),
            iso5: L.layerGroup().addTo(map),
            iso10: L.layerGroup().addTo(map),
            iso15: L.layerGroup().addTo(map)
        };

        // Network-based walking isochrones (smooth buffered polygons)
        var isochrones = ISOCHRONES_JSON;

        // Draw 15 min first (underneath), then 10, then 5 on top
        if (isochrones['15']) {
            L.polygon(isochrones['15'], {
                color: '#C62828',
                fillColor: '#EF5350',
                fillOpacity: 0.15,
                weight: 2,
                smoothFactor: 1
            }).addTo(layers.iso15);
        }

        if (isochrones['10']) {
            L.polygon(isochrones['10'], {
                color: '#F9A825',
                fillColor: '#FFCA28',
                fillOpacity: 0.2,
                weight: 2,
                smoothFactor: 1
            }).addTo(layers.iso10);
        }

        if (isochrones['5']) {
            L.polygon(isochrones['5'], {
                color: '#2E7D32',
                fillColor: '#66BB6A',
                fillOpacity: 0.25,
                weight: 2,
                smoothFactor: 1
            }).addTo(layers.iso5);
        }

        // Count items per layer
        var counts = {};
        for (var key in layers) counts[key] = 0;

        // Copy to clipboard function
        function copyCoords(lat, lon) {
            var text = lat.toFixed(6) + ', ' + lon.toFixed(6);
            navigator.clipboard.writeText(text).then(function() {
                var btn = event.target;
                var orig = btn.textContent;
                btn.textContent = 'Copied!';
                btn.style.background = '#4CAF50';
                setTimeout(function() { btn.textContent = orig; btn.style.background = ''; }, 1000);
            });
        }

        // Draw roads into layer groups
        roads.forEach(function(road) {
            var weight = road.type === 'pedestrian' ? 4 : (road.type === 'main_road' ? 3 : 2);
            var line = L.polyline(road.coords, {
                color: road.color,
                weight: weight,
                opacity: 0.8
            }).bindPopup('<b>' + (road.name || road.highway) + '</b><br>Type: ' + road.highway);

            var layerKey = road.type;
            if (layers[layerKey]) {
                layers[layerKey].addLayer(line);
                counts[layerKey]++;
            } else {
                layers.other.addLayer(line);
            }
        });

        // Draw crossings with symbols into layer groups
        crossingsData.forEach(function(c) {
            var icon = L.divIcon({
                className: 'crossing-icon',
                html: '<div class="crossing-marker">' + c.symbol + '</div>',
                iconSize: [22, 22],
                iconAnchor: [11, 11]
            });
            var popup = '<b>' + c.label + '</b><br>' +
                '<span class="coords">' + c.lat.toFixed(6) + ', ' + c.lon.toFixed(6) + '</span>' +
                '<button class="copy-btn" onclick="copyCoords(' + c.lat + ',' + c.lon + ')">Copy</button>';
            var marker = L.marker([c.lat, c.lon], {icon: icon}).bindPopup(popup);

            if (c.signal) {
                layers.signals.addLayer(marker);
                counts.signals++;
            } else {
                layers.crossings.addLayer(marker);
                counts.crossings++;
            }
        });

        // Draw POIs with symbols into layer groups
        pois.forEach(function(poi) {
            var icon = L.divIcon({
                className: 'poi-icon',
                html: '<div class="poi-marker" style="border-color:' + poi.color + '">' + poi.symbol + '</div>',
                iconSize: [28, 28],
                iconAnchor: [14, 14]
            });
            var popup = '<b>' + poi.name + '</b><br>Type: ' + poi.type.replace(/_/g, ' ') + '<br>' +
                '<span class="coords">' + poi.lat.toFixed(6) + ', ' + poi.lon.toFixed(6) + '</span>' +
                '<button class="copy-btn" onclick="copyCoords(' + poi.lat + ',' + poi.lon + ')">Copy</button>';
            var marker = L.marker([poi.lat, poi.lon], {icon: icon}).bindPopup(popup);

            var layerKey = poi.category;
            if (layers[layerKey]) {
                layers[layerKey].addLayer(marker);
                counts[layerKey]++;
            } else {
                layers.amenity.addLayer(marker);
            }
        });

        // Update count displays
        for (var key in counts) {
            var el = document.getElementById('count-' + key);
            if (el && counts[key] > 0) el.textContent = counts[key];
        }

        // Toggle layer visibility
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
                html: '<div style="width:24px;height:24px;background:#C74634;border:3px solid white;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.3)"></div>',
                iconSize: [24, 24],
                iconAnchor: [12, 12]
            })
        }).addTo(map).bindPopup('<b>Analysis Center</b>');

        // Reset all checkboxes on page load (prevent browser state persistence)
        document.querySelectorAll('.layer-control input[type="checkbox"]').forEach(function(cb) {
            cb.checked = true;
        });
    </script>
</body>
</html>'''

    # Fill template
    html = html.replace('DESCRIPTION', data.get('description', 'Walkability Analysis'))
    html = html.replace('CENTER_LAT', str(center_lat))
    html = html.replace('CENTER_LON', str(center_lon))
    html = html.replace('RADIUS', str(radius))

    # Extract metrics from JSON structure
    road_net = data.get('road_network', {})
    amenities = data.get('amenities', {})
    accessibility = data.get('accessibility', {})
    safety = data.get('safety', {})
    greenspaces = data.get('greenspaces', {})
    buildings = data.get('buildings', {})
    area_km2 = data.get('area_km2', 1)

    # Road network metrics
    total_network_km = road_net.get('total_length_m', 0) / 1000
    pedestrian_km = road_net.get('pedestrian_length_m', 0) / 1000
    pedestrian_pct = int(road_net.get('pedestrian_ratio', 0) * 100)
    intersections_count = road_net.get('intersections', 0)
    intersection_density = int(road_net.get('intersection_density_per_km2', 0))
    dead_ends = road_net.get('dead_ends', 0)
    connectivity_index = road_net.get('connectivity_index', 0)
    sidewalk_pct = road_net.get('sidewalk_coverage_pct', 0)

    html = html.replace('TOTAL_NETWORK_KM', f"{total_network_km:.1f}")
    html = html.replace('PEDESTRIAN_KM', f"{pedestrian_km:.1f}")
    html = html.replace('PEDESTRIAN_PCT', str(pedestrian_pct))
    html = html.replace('INTERSECTIONS_COUNT', str(intersections_count))
    html = html.replace('INTERSECTION_DENSITY', str(intersection_density))
    html = html.replace('DEAD_ENDS', str(dead_ends))
    html = html.replace('CONNECTIVITY_INDEX', str(connectivity_index))
    html = html.replace('SIDEWALK_PCT', f"{sidewalk_pct:.1f}")

    # Accessibility
    dist_food = accessibility.get('nearest_food_m')
    dist_shop = accessibility.get('nearest_shop_m')
    dist_transit = accessibility.get('nearest_transit_m')
    html = html.replace('DIST_FOOD', str(int(dist_food)) if dist_food else 'N/A')
    html = html.replace('DIST_SHOP', str(int(dist_shop)) if dist_shop else 'N/A')
    html = html.replace('DIST_TRANSIT', str(int(dist_transit)) if dist_transit else 'N/A')

    # Safety
    crossings_count = safety.get('crossings', 0)
    signals_count = safety.get('traffic_signals', 0)
    lighting_count = safety.get('street_lighting', 0)
    crossings_density = int(crossings_count / area_km2) if area_km2 > 0 else 0

    html = html.replace('CROSSINGS_DENSITY', str(crossings_density))
    html = html.replace('CROSSINGS_VAL', str(crossings_count))
    html = html.replace('SIGNALS_VAL', str(signals_count))
    html = html.replace('LIGHTING_VAL', str(lighting_count))

    # Green spaces
    greenspaces_count = greenspaces.get('count', 0)
    greenspace_ha = greenspaces.get('total_area_ha', 0)
    greenspace_pct = greenspaces.get('pct_of_analysis_area', 0)

    html = html.replace('GREENSPACES_VAL', str(greenspaces_count))
    html = html.replace('GREENSPACE_HA', f"{greenspace_ha:.2f}")
    html = html.replace('GREENSPACE_PCT', f"{greenspace_pct:.1f}")

    # Buildings
    building_count = buildings.get('count', 0)
    building_density = buildings.get('density_per_km2', 0)
    building_ha = buildings.get('total_area_ha', 0)
    building_pct = round(buildings.get('total_area_m2', 0) / (area_km2 * 1000000) * 100, 1) if area_km2 > 0 else 0

    html = html.replace('BUILDING_COUNT', str(building_count))
    html = html.replace('BUILDING_DENSITY', str(int(building_density)))
    html = html.replace('BUILDING_HA', f"{building_ha:.2f}")
    html = html.replace('BUILDING_PCT', f"{building_pct:.1f}")

    # Amenities
    amenity_cats = amenities.get('by_category', {})
    total_amenities = amenities.get('total', 0)
    html = html.replace('TOTAL_AMENITIES', str(total_amenities))

    # Amenity items with icons
    amenity_icons = {
        'food': '🍽️',
        'shopping': '🛒',
        'services': '🏦',
        'transit': '🚌',
        'leisure': '🌳',
        'education': '🎓',
        'furniture': '🪑',
        'cycling': '🚲',
        'worship': '⛪',
    }
    amenity_labels = {
        'food': 'Food',
        'shopping': 'Shops',
        'services': 'Services',
        'transit': 'Transit',
        'leisure': 'Leisure',
        'education': 'Education',
        'furniture': 'Furniture',
        'cycling': 'Bike Parking',
        'worship': 'Worship',
    }

    amenity_html = ''
    for cat, count in amenity_cats.items():
        icon = amenity_icons.get(cat, '📍')
        label = amenity_labels.get(cat, cat.title())
        amenity_html += f'''
                <div class="amenity-item">
                    <span class="amenity-icon">{icon}</span>
                    <span class="amenity-count">{count}</span>
                    <span class="amenity-label">{label}</span>
                </div>'''

    html = html.replace('AMENITY_ITEMS', amenity_html)

    # JSON data
    html = html.replace('ROADS_JSON', json.dumps(roads))
    html = html.replace('CROSSINGS_JSON', json.dumps(crossings))
    html = html.replace('POIS_JSON', json.dumps(pois))

    # Isochrones (convert int keys to strings for JSON)
    iso_data = {str(k): v for k, v in (isochrones or {}).items()}
    html = html.replace('ISOCHRONES_JSON', json.dumps(iso_data))

    return html
