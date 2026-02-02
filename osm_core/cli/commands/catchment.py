"""Catchment Areas command - enhanced isochrones with POI analysis."""
import argparse
import heapq
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


# Travel mode speeds (km/h)
DEFAULT_SPEEDS = {
    'walk': {
        'default': 5, 'steps': 3, 'path': 4, 'footway': 5, 'pedestrian': 5,
        'residential': 5, 'living_street': 5
    },
    'bike': {
        'default': 15, 'cycleway': 18, 'path': 12, 'residential': 15,
        'tertiary': 18, 'secondary': 20, 'primary': 15
    },
    'drive': {
        'motorway': 110, 'motorway_link': 60, 'trunk': 90, 'trunk_link': 50,
        'primary': 60, 'primary_link': 40, 'secondary': 50, 'secondary_link': 35,
        'tertiary': 40, 'tertiary_link': 30, 'residential': 30, 'living_street': 20,
        'unclassified': 30, 'service': 20, 'default': 30
    }
}

ALLOWED_ROADS = {
    'walk': frozenset({
        'primary', 'secondary', 'tertiary', 'residential', 'living_street',
        'unclassified', 'service', 'pedestrian', 'footway', 'path', 'steps', 'track'
    }),
    'bike': frozenset({
        'primary', 'secondary', 'tertiary', 'residential', 'living_street',
        'unclassified', 'service', 'cycleway', 'path', 'track'
    }),
    'drive': frozenset({
        'motorway', 'motorway_link', 'trunk', 'trunk_link',
        'primary', 'primary_link', 'secondary', 'secondary_link',
        'tertiary', 'tertiary_link', 'residential', 'living_street',
        'unclassified', 'service', 'road'
    })
}

# POI categories for catchment analysis
POI_CATEGORIES = {
    'healthcare': {
        'amenity': {'hospital', 'clinic', 'doctors', 'dentist', 'pharmacy'},
        'healthcare': {'*'}
    },
    'education': {
        'amenity': {'school', 'kindergarten', 'college', 'university', 'library'}
    },
    'food': {
        'amenity': {'restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'food_court'},
        'shop': {'supermarket', 'convenience', 'grocery', 'bakery', 'butcher'}
    },
    'shopping': {
        'shop': {'mall', 'department_store', 'clothes', 'shoes', 'electronics'}
    },
    'services': {
        'amenity': {'bank', 'atm', 'post_office', 'police', 'fire_station'}
    },
    'transit': {
        'amenity': {'bus_station'},
        'railway': {'station', 'halt', 'tram_stop'},
        'public_transport': {'station', 'stop_position', 'platform'}
    },
    'leisure': {
        'leisure': {'park', 'playground', 'sports_centre', 'fitness_centre', 'swimming_pool'},
        'amenity': {'cinema', 'theatre', 'community_centre'}
    }
}


def setup_parser(subparsers):
    """Setup the catchment subcommand parser."""
    parser = subparsers.add_parser(
        'catchment',
        help='Generate catchment areas with POI analysis',
        description='Create catchment zones showing reachable amenities within travel times'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', required=True, help='Output file')
    parser.add_argument(
        '--lat',
        type=float,
        required=True,
        help='Origin latitude'
    )
    parser.add_argument(
        '--lon',
        type=float,
        required=True,
        help='Origin longitude'
    )
    parser.add_argument(
        '--time', '-t',
        default='5,10,15',
        help='Travel times in minutes (comma-separated, default: 5,10,15)'
    )
    parser.add_argument(
        '--mode', '-m',
        choices=['walk', 'bike', 'drive'],
        default='walk',
        help='Travel mode (default: walk)'
    )
    parser.add_argument(
        '--categories', '-c',
        help='POI categories to analyze (comma-separated, default: all)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['json', 'geojson', 'text'],
        default='geojson',
        help='Output format (default: geojson)'
    )
    parser.add_argument(
        '--resolution',
        type=int,
        default=36,
        help='Polygon boundary resolution (default: 36)'
    )

    parser.set_defaults(func=run)
    return parser


def haversine_distance(lon1, lat1, lon2, lat2):
    """Calculate distance in meters."""
    R = 6371000
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (math.sin(delta_lat/2)**2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def find_nearest_node(target_lon, target_lat, node_coords):
    """Find nearest node to target coordinates."""
    min_dist = float('inf')
    nearest = None

    for node_id, (lon, lat) in node_coords.items():
        dist = haversine_distance(target_lon, target_lat, lon, lat)
        if dist < min_dist:
            min_dist = dist
            nearest = node_id

    return nearest, min_dist


def build_graph(ways, node_coords, mode):
    """Build travel time graph."""
    graph = {}
    speeds = DEFAULT_SPEEDS[mode]
    allowed = ALLOWED_ROADS[mode]

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in allowed:
            continue

        speed = speeds.get(highway, speeds.get('default', 5))
        oneway = way.tags.get('oneway') in ('yes', '1', 'true')
        reverse = way.tags.get('oneway') == '-1'

        refs = way.node_refs
        for i in range(len(refs) - 1):
            from_id, to_id = refs[i], refs[i + 1]

            if from_id not in node_coords or to_id not in node_coords:
                continue

            from_coord = node_coords[from_id]
            to_coord = node_coords[to_id]

            distance = haversine_distance(
                from_coord[0], from_coord[1],
                to_coord[0], to_coord[1]
            )
            travel_time = (distance / 1000) / speed * 3600  # seconds

            if from_id not in graph:
                graph[from_id] = []
            if to_id not in graph:
                graph[to_id] = []

            if mode == 'drive':
                if reverse:
                    graph[to_id].append((from_id, travel_time, distance))
                    if not oneway:
                        graph[from_id].append((to_id, travel_time, distance))
                else:
                    graph[from_id].append((to_id, travel_time, distance))
                    if not oneway:
                        graph[to_id].append((from_id, travel_time, distance))
            else:
                graph[from_id].append((to_id, travel_time, distance))
                graph[to_id].append((from_id, travel_time, distance))

    return graph


def dijkstra(graph, start, max_time):
    """Run Dijkstra to find all reachable nodes within max_time seconds."""
    distances = {start: 0}
    heap = [(0, start)]

    while heap:
        curr_time, curr_node = heapq.heappop(heap)

        if curr_time > max_time:
            continue

        if curr_time > distances.get(curr_node, float('inf')):
            continue

        for neighbor, travel_time, _ in graph.get(curr_node, []):
            new_time = curr_time + travel_time
            if new_time < distances.get(neighbor, float('inf')) and new_time <= max_time:
                distances[neighbor] = new_time
                heapq.heappush(heap, (new_time, neighbor))

    return distances


def create_polygon(reachable_nodes, node_coords, origin_lon, origin_lat, resolution):
    """Create polygon boundary from reachable nodes."""
    if not reachable_nodes:
        return None

    points = [(node_coords[n][0], node_coords[n][1])
              for n in reachable_nodes if n in node_coords]

    if len(points) < 3:
        return None

    # Find boundary by angle from origin
    angle_points = []
    for lon, lat in points:
        angle = math.atan2(lat - origin_lat, lon - origin_lon)
        dist = haversine_distance(origin_lon, origin_lat, lon, lat)
        angle_points.append((angle, dist, lon, lat))

    # Bin by angle
    bin_size = 2 * math.pi / resolution
    bins = {}

    for angle, dist, lon, lat in angle_points:
        bin_idx = int((angle + math.pi) / bin_size) % resolution
        if bin_idx not in bins or dist > bins[bin_idx][0]:
            bins[bin_idx] = (dist, lon, lat)

    # Create polygon
    polygon = []
    for i in range(resolution):
        if i in bins:
            _, lon, lat = bins[i]
            polygon.append([lon, lat])
        else:
            # Interpolate
            prev_idx = (i - 1) % resolution
            next_idx = (i + 1) % resolution
            if prev_idx in bins and next_idx in bins:
                lon = (bins[prev_idx][1] + bins[next_idx][1]) / 2
                lat = (bins[prev_idx][2] + bins[next_idx][2]) / 2
                polygon.append([lon, lat])

    if len(polygon) < 3:
        return None

    polygon.append(polygon[0])  # Close polygon
    return polygon


def categorize_poi(node):
    """Categorize a POI node."""
    for category, tag_rules in POI_CATEGORIES.items():
        for tag_key, valid_values in tag_rules.items():
            tag_value = node.tags.get(tag_key)
            if tag_value:
                if '*' in valid_values or tag_value in valid_values:
                    return category, tag_key, tag_value
    return None, None, None


def find_pois_in_catchment(nodes, reachable_nodes, node_coords, travel_times, categories_filter):
    """Find POIs within each catchment zone."""
    # Build node -> travel time lookup
    reachable_set = set(reachable_nodes.keys())

    pois_by_zone = defaultdict(list)
    pois_by_category = defaultdict(lambda: defaultdict(int))

    for node in nodes:
        if node.id not in node_coords:
            continue

        category, tag_key, tag_value = categorize_poi(node)
        if not category:
            continue

        if categories_filter and category not in categories_filter:
            continue

        # Find nearest reachable node
        node_lon, node_lat = node_coords[node.id]
        min_travel_time = float('inf')
        nearest_network_node = None

        for network_node, travel_time in reachable_nodes.items():
            if network_node in node_coords:
                net_lon, net_lat = node_coords[network_node]
                dist = haversine_distance(node_lon, node_lat, net_lon, net_lat)
                # Add walking time to nearest network node (assume 5 km/h)
                extra_time = (dist / 1000) / 5 * 3600
                total_time = travel_time + extra_time

                if total_time < min_travel_time:
                    min_travel_time = total_time
                    nearest_network_node = network_node

        if min_travel_time < float('inf'):
            travel_mins = min_travel_time / 60

            poi_info = {
                'id': node.id,
                'name': node.tags.get('name', 'Unnamed'),
                'category': category,
                'type': tag_value,
                'travel_time_min': round(travel_mins, 1),
                'lat': node_lat,
                'lon': node_lon
            }

            # Assign to zone
            for zone_time in sorted(travel_times):
                if travel_mins <= zone_time:
                    pois_by_zone[zone_time].append(poi_info)
                    pois_by_category[zone_time][category] += 1
                    break

    return pois_by_zone, pois_by_category


def run(args):
    """Execute the catchment command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    # Parse travel times
    try:
        travel_times = sorted([int(t.strip()) for t in args.time.split(',')])
    except ValueError:
        print(f"Error: Invalid travel times: {args.time}", file=sys.stderr)
        return 1

    # Parse categories filter
    categories_filter = None
    if args.categories:
        categories_filter = set(c.strip().lower() for c in args.categories.split(','))

    start_time = time.time()

    # Parse file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Use parser's coordinate cache (includes ALL nodes)
    node_coords = {}
    for node_id, (lat, lon) in parser.node_coordinates.items():
        node_coords[node_id] = (float(lon), float(lat))

    print(f"Building {args.mode} network...", file=sys.stderr)

    # Build graph
    graph = build_graph(ways, node_coords, args.mode)

    if not graph:
        print("Error: No roads found for selected mode", file=sys.stderr)
        return 1

    # Find nearest node to origin
    origin_node, origin_dist = find_nearest_node(args.lon, args.lat, node_coords)

    if origin_node is None:
        print("Error: No road network near origin point", file=sys.stderr)
        return 1

    print(f"Origin: nearest node {origin_dist:.0f}m away", file=sys.stderr)

    # Compute catchment zones
    max_time_secs = max(travel_times) * 60
    reachable = dijkstra(graph, origin_node, max_time_secs)

    print(f"Reachable nodes: {len(reachable)}", file=sys.stderr)

    # Find POIs in catchment
    pois_by_zone, pois_by_category = find_pois_in_catchment(
        nodes, reachable, node_coords, travel_times, categories_filter
    )

    # Generate output
    features = []

    # Origin point
    features.append({
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [args.lon, args.lat]
        },
        'properties': {
            'type': 'origin',
            'mode': args.mode
        }
    })

    # Zone polygons (largest first for proper layering)
    zone_stats = []
    for travel_mins in sorted(travel_times, reverse=True):
        travel_secs = travel_mins * 60

        # Get nodes reachable within this time
        zone_nodes = {k: v for k, v in reachable.items() if v <= travel_secs}

        print(f"Computing {travel_mins} min catchment...", file=sys.stderr)

        polygon = create_polygon(
            zone_nodes.keys(), node_coords,
            args.lon, args.lat, args.resolution
        )

        zone_pois = pois_by_zone.get(travel_mins, [])
        zone_categories = pois_by_category.get(travel_mins, {})

        stats = {
            'time_minutes': travel_mins,
            'reachable_nodes': len(zone_nodes),
            'total_pois': len(zone_pois),
            'pois_by_category': dict(zone_categories)
        }
        zone_stats.append(stats)

        if polygon:
            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [polygon]
                },
                'properties': stats
            })

    # Add POI points
    all_pois = []
    for zone_pois in pois_by_zone.values():
        all_pois.extend(zone_pois)

    for poi in all_pois[:100]:  # Limit to 100 POIs
        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [poi['lon'], poi['lat']]
            },
            'properties': {
                'type': 'poi',
                'name': poi['name'],
                'category': poi['category'],
                'poi_type': poi['type'],
                'travel_time_min': poi['travel_time_min']
            }
        })

    elapsed = time.time() - start_time

    if args.format == 'geojson':
        output = {
            'type': 'FeatureCollection',
            'features': features
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

    elif args.format == 'json':
        output = {
            'origin': {'lat': args.lat, 'lon': args.lon},
            'mode': args.mode,
            'travel_times': travel_times,
            'zones': zone_stats,
            'pois': all_pois,
            'analysis_time_s': round(elapsed, 3)
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

    else:  # text
        print(f"\n{'='*60}")
        print(f"CATCHMENT AREA ANALYSIS")
        print(f"{'='*60}")
        print(f"Origin: {args.lat}, {args.lon}")
        print(f"Mode: {args.mode}")
        print(f"\n{'-'*60}")

        for stats in sorted(zone_stats, key=lambda x: x['time_minutes']):
            print(f"\n{stats['time_minutes']} minute catchment:")
            print(f"  Reachable nodes: {stats['reachable_nodes']}")
            print(f"  Total POIs: {stats['total_pois']}")
            for cat, count in sorted(stats['pois_by_category'].items()):
                print(f"    - {cat}: {count}")

        print(f"\n[{elapsed:.3f}s]")

        # Still save the file
        output = {
            'origin': {'lat': args.lat, 'lon': args.lon},
            'mode': args.mode,
            'zones': zone_stats,
            'pois': all_pois
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

    print(f"\nCatchment analysis complete:")
    print(f"  Origin: {args.lat}, {args.lon}")
    print(f"  Mode: {args.mode}")
    print(f"  Zones: {travel_times} minutes")
    print(f"  Total POIs found: {len(all_pois)}")
    print(f"  Output: {args.output}")
    print(f"  Time: {elapsed:.3f}s")

    return 0
