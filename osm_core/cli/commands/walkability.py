"""Walkability Index command - calculate walkability scores for areas."""
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


# Walkability factor weights (sum to 1.0)
WALKABILITY_WEIGHTS = {
    'pedestrian_infrastructure': 0.25,  # Sidewalks, footways, pedestrian zones
    'intersection_density': 0.20,        # More intersections = more route choices
    'amenity_access': 0.25,              # Nearby shops, restaurants, services
    'transit_access': 0.10,              # Public transport stops
    'greenspace': 0.10,                  # Parks, gardens
    'safety_features': 0.10,             # Crossings, traffic lights
}

# Amenity categories that improve walkability
WALKABLE_AMENITIES = {
    'food': {'restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'bakery', 'ice_cream'},
    'shopping': {'supermarket', 'convenience', 'clothes', 'shoes', 'department_store'},
    'services': {'bank', 'atm', 'post_office', 'pharmacy', 'doctors', 'dentist', 'hospital', 'toilets'},
    'education': {'school', 'kindergarten', 'library', 'college', 'university'},
    'leisure': {'park', 'playground', 'sports_centre', 'fitness_centre', 'cinema', 'theatre'},
    'transit': {'bus_stop', 'tram_stop', 'subway_entrance', 'train_station', 'bus_station'},
    'furniture': {'bench', 'waste_basket', 'drinking_water'},
    'cycling': {'bicycle_parking'},
    'worship': {'place_of_worship'},
}

# Pedestrian infrastructure types
PEDESTRIAN_WAYS = frozenset({
    'footway', 'pedestrian', 'path', 'steps', 'living_street'
})

# All walkable road types
WALKABLE_ROADS = frozenset({
    'primary', 'secondary', 'tertiary', 'residential', 'living_street',
    'unclassified', 'service', 'pedestrian', 'footway', 'path', 'steps', 'track'
})


def setup_parser(subparsers):
    """Setup the walkability subcommand parser."""
    parser = subparsers.add_parser(
        'walkability',
        help='Calculate walkability index for an area',
        description='Analyze pedestrian infrastructure and calculate walkability scores'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file (JSON/GeoJSON)')
    parser.add_argument(
        '--lat',
        type=float,
        help='Center latitude for analysis (default: map center)'
    )
    parser.add_argument(
        '--lon',
        type=float,
        help='Center longitude for analysis (default: map center)'
    )
    parser.add_argument(
        '--radius',
        type=float,
        default=1000,
        help='Analysis radius in meters (default: 1000)'
    )
    parser.add_argument(
        '--grid',
        action='store_true',
        help='Calculate walkability for a grid of points'
    )
    parser.add_argument(
        '--grid-size',
        type=int,
        default=100,
        help='Grid cell size in meters (default: 100)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['text', 'json', 'geojson'],
        default='text',
        help='Output format (default: text)'
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


def meters_to_degrees(meters, lat):
    """Convert meters to approximate degrees at given latitude."""
    lat_deg = meters / 111320  # 1 degree latitude ~ 111.32 km
    lon_deg = meters / (111320 * math.cos(math.radians(lat)))
    return lat_deg, lon_deg


def build_pedestrian_network(ways, node_coords):
    """Build pedestrian network graph."""
    graph = defaultdict(list)
    total_length = 0
    pedestrian_length = 0
    road_lengths = defaultdict(float)  # Track length by road type

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in WALKABLE_ROADS:
            continue

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

            total_length += distance
            road_lengths[highway] += distance
            if highway in PEDESTRIAN_WAYS:
                pedestrian_length += distance

            graph[from_id].append((to_id, distance))
            graph[to_id].append((from_id, distance))

    return graph, total_length, pedestrian_length, road_lengths


def count_intersections(graph, node_coords, center_lon, center_lat, radius):
    """Count intersections (nodes with 3+ connections) within radius."""
    intersections = 0
    dead_ends = 0
    total_nodes = 0
    total_edges = 0

    for node_id, neighbors in graph.items():
        if node_id not in node_coords:
            continue

        lon, lat = node_coords[node_id]
        dist = haversine_distance(center_lon, center_lat, lon, lat)

        if dist <= radius:
            total_nodes += 1
            total_edges += len(neighbors)
            if len(neighbors) >= 3:
                intersections += 1
            elif len(neighbors) == 1:
                dead_ends += 1

    # Each edge counted twice (once from each end)
    total_edges = total_edges // 2
    # Connectivity index: edges / nodes (higher = more connected)
    connectivity_index = total_edges / total_nodes if total_nodes > 0 else 0

    return intersections, dead_ends, total_nodes, total_edges, connectivity_index


def count_amenities_by_category(nodes, center_lon, center_lat, radius, node_coords_lookup):
    """Count amenities within radius by category."""
    counts = defaultdict(int)
    type_counts = defaultdict(int)  # Track individual types
    amenities_found = []

    for node in nodes:
        if node.id not in node_coords_lookup:
            continue

        lon, lat = node_coords_lookup[node.id]
        dist = haversine_distance(center_lon, center_lat, lon, lat)

        if dist > radius:
            continue

        # Check amenity tag
        amenity = node.tags.get('amenity')
        shop = node.tags.get('shop')
        leisure = node.tags.get('leisure')
        public_transport = node.tags.get('public_transport')
        highway = node.tags.get('highway')

        for category, types in WALKABLE_AMENITIES.items():
            if amenity in types or shop in types or leisure in types:
                counts[category] += 1
                item_type = amenity or shop or leisure
                type_counts[item_type] += 1
                amenities_found.append({
                    'category': category,
                    'type': item_type,
                    'name': node.tags.get('name', 'Unnamed'),
                    'distance': dist,
                    'lon': lon,
                    'lat': lat
                })
            elif category == 'transit' and (
                public_transport in ('stop_position', 'platform', 'station') or
                highway == 'bus_stop'
            ):
                counts['transit'] += 1
                item_type = public_transport or 'bus_stop'
                type_counts[item_type] += 1
                amenities_found.append({
                    'category': 'transit',
                    'type': item_type,
                    'name': node.tags.get('name', 'Unnamed'),
                    'distance': dist,
                    'lon': lon,
                    'lat': lat
                })

    return counts, type_counts, amenities_found


def count_safety_features(nodes, ways, center_lon, center_lat, radius, node_coords_lookup):
    """Count pedestrian safety features."""
    crossings = 0
    traffic_signals = 0
    lighting = 0

    for node in nodes:
        if node.id not in node_coords_lookup:
            continue

        lon, lat = node_coords_lookup[node.id]
        dist = haversine_distance(center_lon, center_lat, lon, lat)

        if dist > radius:
            continue

        highway = node.tags.get('highway')
        if highway == 'crossing':
            crossings += 1
        elif highway == 'traffic_signals':
            traffic_signals += 1

        if node.tags.get('lit') == 'yes':
            lighting += 1

    return crossings, traffic_signals, lighting


def calculate_polygon_area(coords):
    """Calculate polygon area in square meters using shoelace formula."""
    if len(coords) < 3:
        return 0

    # Use average latitude for projection
    avg_lat = sum(c[1] for c in coords) / len(coords)

    # Convert to approximate meters
    lat_to_m = 111320  # meters per degree latitude
    lon_to_m = 111320 * math.cos(math.radians(avg_lat))

    # Shoelace formula
    n = len(coords)
    area = 0
    for i in range(n):
        j = (i + 1) % n
        x1 = coords[i][0] * lon_to_m
        y1 = coords[i][1] * lat_to_m
        x2 = coords[j][0] * lon_to_m
        y2 = coords[j][1] * lat_to_m
        area += x1 * y2 - x2 * y1

    return abs(area) / 2


def count_greenspace(ways, center_lon, center_lat, radius, node_coords):
    """Count parks and green areas."""
    greenspace_count = 0
    greenspace_area = 0

    for way in ways:
        leisure = way.tags.get('leisure')
        landuse = way.tags.get('landuse')

        if leisure in ('park', 'garden', 'playground') or landuse in ('grass', 'forest'):
            # Check if way centroid is within radius
            coords = []
            for ref in way.node_refs:
                if ref in node_coords:
                    coords.append(node_coords[ref])

            if coords:
                avg_lon = sum(c[0] for c in coords) / len(coords)
                avg_lat = sum(c[1] for c in coords) / len(coords)
                dist = haversine_distance(center_lon, center_lat, avg_lon, avg_lat)

                if dist <= radius:
                    greenspace_count += 1
                    # Calculate area if it's a closed polygon
                    if len(coords) >= 3:
                        greenspace_area += calculate_polygon_area(coords)

    return greenspace_count, greenspace_area


def calculate_pedestrian_zone_area(ways, center_lon, center_lat, radius, node_coords):
    """Calculate total area of pedestrian-only zones."""
    ped_zone_area = 0
    ped_zone_count = 0

    for way in ways:
        highway = way.tags.get('highway')
        if highway == 'pedestrian':
            coords = []
            for ref in way.node_refs:
                if ref in node_coords:
                    coords.append(node_coords[ref])

            if coords:
                avg_lon = sum(c[0] for c in coords) / len(coords)
                avg_lat = sum(c[1] for c in coords) / len(coords)
                dist = haversine_distance(center_lon, center_lat, avg_lon, avg_lat)

                if dist <= radius:
                    ped_zone_count += 1
                    if len(coords) >= 3:
                        ped_zone_area += calculate_polygon_area(coords)

    return ped_zone_count, ped_zone_area


def calculate_sidewalk_coverage(ways, center_lon, center_lat, radius, node_coords):
    """Calculate percentage of roads with sidewalks."""
    total_road_length = 0
    sidewalk_length = 0

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in WALKABLE_ROADS:
            continue

        # Skip pedestrian-only ways (they don't need sidewalks)
        if highway in ('footway', 'pedestrian', 'path', 'steps'):
            continue

        coords = []
        for ref in way.node_refs:
            if ref in node_coords:
                coords.append(node_coords[ref])

        if len(coords) < 2:
            continue

        avg_lon = sum(c[0] for c in coords) / len(coords)
        avg_lat = sum(c[1] for c in coords) / len(coords)
        if haversine_distance(center_lon, center_lat, avg_lon, avg_lat) > radius:
            continue

        # Calculate segment length
        length = 0
        for i in range(len(coords) - 1):
            length += haversine_distance(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])

        total_road_length += length

        # Check for sidewalk tags
        sidewalk = way.tags.get('sidewalk', 'no')
        if sidewalk in ('yes', 'both', 'left', 'right', 'separate'):
            sidewalk_length += length

    coverage = (sidewalk_length / total_road_length * 100) if total_road_length > 0 else 0
    return total_road_length, sidewalk_length, coverage


def analyze_speed_limits(ways, center_lon, center_lat, radius, node_coords):
    """Analyze speed limits on roads."""
    speed_limits = defaultdict(float)  # speed -> length in meters

    for way in ways:
        highway = way.tags.get('highway')
        if highway not in WALKABLE_ROADS:
            continue

        maxspeed = way.tags.get('maxspeed', 'unknown')

        coords = []
        for ref in way.node_refs:
            if ref in node_coords:
                coords.append(node_coords[ref])

        if len(coords) < 2:
            continue

        avg_lon = sum(c[0] for c in coords) / len(coords)
        avg_lat = sum(c[1] for c in coords) / len(coords)
        if haversine_distance(center_lon, center_lat, avg_lon, avg_lat) > radius:
            continue

        # Calculate segment length
        length = 0
        for i in range(len(coords) - 1):
            length += haversine_distance(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])

        speed_limits[maxspeed] += length

    return dict(speed_limits)


def count_buildings(ways, center_lon, center_lat, radius, node_coords):
    """Count buildings within radius."""
    building_count = 0
    total_building_area = 0

    for way in ways:
        building = way.tags.get('building')
        if not building:
            continue

        coords = []
        for ref in way.node_refs:
            if ref in node_coords:
                coords.append(node_coords[ref])

        if coords:
            avg_lon = sum(c[0] for c in coords) / len(coords)
            avg_lat = sum(c[1] for c in coords) / len(coords)
            dist = haversine_distance(center_lon, center_lat, avg_lon, avg_lat)

            if dist <= radius:
                building_count += 1
                if len(coords) >= 3:
                    total_building_area += calculate_polygon_area(coords)

    return building_count, total_building_area


def calculate_avg_distance_to_amenity(nodes, center_lon, center_lat, radius, node_coords, amenity_types):
    """Calculate average distance to nearest amenity of given types."""
    # Find all amenities of the given types
    amenity_locations = []

    for node in nodes:
        if node.id not in node_coords:
            continue

        lon, lat = node_coords[node.id]
        dist_from_center = haversine_distance(center_lon, center_lat, lon, lat)

        if dist_from_center > radius * 1.5:  # Look slightly beyond radius
            continue

        amenity = node.tags.get('amenity')
        shop = node.tags.get('shop')
        public_transport = node.tags.get('public_transport')
        highway = node.tags.get('highway')

        if amenity in amenity_types or shop in amenity_types:
            amenity_locations.append((lon, lat))
        elif 'transit' in amenity_types and (
            public_transport in ('stop_position', 'platform', 'station') or
            highway == 'bus_stop'
        ):
            amenity_locations.append((lon, lat))

    if not amenity_locations:
        return None, 0

    # Calculate distance from center to nearest amenity
    min_dist = float('inf')
    for lon, lat in amenity_locations:
        dist = haversine_distance(center_lon, center_lat, lon, lat)
        if dist < min_dist:
            min_dist = dist

    return min_dist, len(amenity_locations)


def calculate_walkability_score(
    pedestrian_ratio,
    intersection_density,
    amenity_score,
    transit_score,
    greenspace_score,
    safety_score
):
    """Calculate overall walkability index (0-100)."""
    # Normalize scores to 0-100 range
    scores = {
        'pedestrian_infrastructure': min(100, pedestrian_ratio * 200),  # 50% pedestrian = 100
        'intersection_density': min(100, intersection_density * 2000),  # 50 per km2 = 100
        'amenity_access': min(100, amenity_score * 5),  # 20 amenities = 100
        'transit_access': min(100, transit_score * 20),  # 5 stops = 100
        'greenspace': min(100, greenspace_score * 20),  # 5 parks = 100
        'safety_features': min(100, safety_score * 10),  # 10 crossings = 100
    }

    # Calculate weighted average
    total = sum(scores[k] * WALKABILITY_WEIGHTS[k] for k in WALKABILITY_WEIGHTS)

    return total, scores


def get_walkability_grade(score):
    """Convert numeric score to letter grade."""
    if score >= 90:
        return 'A+', 'Walker\'s Paradise'
    elif score >= 80:
        return 'A', 'Very Walkable'
    elif score >= 70:
        return 'B', 'Walkable'
    elif score >= 60:
        return 'C', 'Somewhat Walkable'
    elif score >= 50:
        return 'D', 'Car-Dependent'
    else:
        return 'F', 'Very Car-Dependent'


def run(args):
    """Execute the walkability command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse the file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Use parser's coordinate cache (includes ALL nodes)
    node_coords = {}
    for node_id, (lat, lon) in parser.node_coordinates.items():
        node_coords[node_id] = (float(lon), float(lat))

    if not node_coords:
        print("Error: No coordinates found in file", file=sys.stderr)
        return 1

    # Determine center point
    if args.lat is not None and args.lon is not None:
        center_lat, center_lon = args.lat, args.lon
    else:
        # Use centroid of all coordinates
        all_lons = [c[0] for c in node_coords.values()]
        all_lats = [c[1] for c in node_coords.values()]
        center_lon = sum(all_lons) / len(all_lons)
        center_lat = sum(all_lats) / len(all_lats)

    print(f"Analyzing walkability around ({center_lat:.6f}, {center_lon:.6f})", file=sys.stderr)
    print(f"Radius: {args.radius}m", file=sys.stderr)

    # Build pedestrian network
    graph, total_length, pedestrian_length, road_lengths = build_pedestrian_network(ways, node_coords)

    # Calculate pedestrian infrastructure ratio
    pedestrian_ratio = pedestrian_length / total_length if total_length > 0 else 0

    # Count intersections, dead ends, connectivity
    intersections, dead_ends, total_nodes, total_edges, connectivity_index = count_intersections(
        graph, node_coords, center_lon, center_lat, args.radius
    )

    # Intersection density (per km2)
    area_km2 = math.pi * (args.radius / 1000) ** 2
    intersection_density = intersections / area_km2 if area_km2 > 0 else 0

    # Count amenities
    amenity_counts, type_counts, amenities_found = count_amenities_by_category(
        nodes, center_lon, center_lat, args.radius, node_coords
    )
    total_amenities = sum(amenity_counts.values())

    # Count safety features
    crossings, traffic_signals, lighting = count_safety_features(
        nodes, ways, center_lon, center_lat, args.radius, node_coords
    )

    # Count greenspace
    greenspace_count, greenspace_area = count_greenspace(ways, center_lon, center_lat, args.radius, node_coords)

    # Pedestrian zones
    ped_zone_count, ped_zone_area = calculate_pedestrian_zone_area(
        ways, center_lon, center_lat, args.radius, node_coords
    )

    # Sidewalk coverage
    road_length_for_sidewalks, sidewalk_length, sidewalk_coverage = calculate_sidewalk_coverage(
        ways, center_lon, center_lat, args.radius, node_coords
    )

    # Speed limits
    speed_limits = analyze_speed_limits(ways, center_lon, center_lat, args.radius, node_coords)

    # Buildings
    building_count, building_area = count_buildings(ways, center_lon, center_lat, args.radius, node_coords)

    # Distance to nearest amenities
    food_types = {'restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'bakery'}
    shop_types = {'supermarket', 'convenience'}
    dist_to_food, food_count = calculate_avg_distance_to_amenity(
        nodes, center_lon, center_lat, args.radius, node_coords, food_types
    )
    dist_to_shop, shop_count = calculate_avg_distance_to_amenity(
        nodes, center_lon, center_lat, args.radius, node_coords, shop_types
    )
    dist_to_transit, transit_count = calculate_avg_distance_to_amenity(
        nodes, center_lon, center_lat, args.radius, node_coords, {'transit'}
    )

    # Calculate scores
    walkability_score, component_scores = calculate_walkability_score(
        pedestrian_ratio=pedestrian_ratio,
        intersection_density=intersection_density,
        amenity_score=total_amenities,
        transit_score=amenity_counts.get('transit', 0),
        greenspace_score=greenspace_count,
        safety_score=crossings + traffic_signals
    )

    grade, description = get_walkability_grade(walkability_score)

    elapsed = time.time() - start_time

    # Prepare output data
    result = {
        'center': {'lat': center_lat, 'lon': center_lon},
        'radius_m': args.radius,
        'area_km2': round(area_km2, 3),
        'walkability_score': round(walkability_score, 1),
        'grade': grade,
        'description': description,
        'component_scores': {k: round(v, 1) for k, v in component_scores.items()},
        'road_network': {
            'total_length_m': round(total_length, 0),
            'pedestrian_length_m': round(pedestrian_length, 0),
            'pedestrian_ratio': round(pedestrian_ratio, 3),
            'intersections': intersections,
            'dead_ends': dead_ends,
            'intersection_density_per_km2': round(intersection_density, 1),
            'network_nodes': total_nodes,
            'network_edges': total_edges,
            'connectivity_index': round(connectivity_index, 2),
            'road_types': {k: round(v, 1) for k, v in road_lengths.items()},
            'sidewalk_coverage_pct': round(sidewalk_coverage, 1),
            'pedestrian_zones': ped_zone_count,
            'pedestrian_zone_area_m2': round(ped_zone_area, 0),
        },
        'amenities': {
            'total': total_amenities,
            'density_per_km2': round(total_amenities / area_km2, 1) if area_km2 > 0 else 0,
            'by_category': dict(amenity_counts),
            'by_type': dict(type_counts),
        },
        'accessibility': {
            'nearest_food_m': round(dist_to_food, 0) if dist_to_food else None,
            'nearest_shop_m': round(dist_to_shop, 0) if dist_to_shop else None,
            'nearest_transit_m': round(dist_to_transit, 0) if dist_to_transit else None,
        },
        'safety': {
            'crossings': crossings,
            'traffic_signals': traffic_signals,
            'street_lighting': lighting,
            'crossings_per_km': round(crossings / (total_length/1000), 2) if total_length > 0 else 0,
            'speed_limits': {k: round(v, 0) for k, v in speed_limits.items()},
        },
        'greenspaces': {
            'count': greenspace_count,
            'total_area_m2': round(greenspace_area, 0),
            'total_area_ha': round(greenspace_area / 10000, 2),
            'pct_of_analysis_area': round(greenspace_area / (area_km2 * 1000000) * 100, 1) if area_km2 > 0 else 0,
        },
        'buildings': {
            'count': building_count,
            'density_per_km2': round(building_count / area_km2, 0) if area_km2 > 0 else 0,
            'total_area_m2': round(building_area, 0),
            'total_area_ha': round(building_area / 10000, 2),
        },
        'analysis_time_s': round(elapsed, 3)
    }

    # Output
    if args.format == 'json':
        output = json.dumps(result, indent=2)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"Results saved to {args.output}")
        else:
            print(output)

    elif args.format == 'geojson':
        geojson = {
            'type': 'FeatureCollection',
            'features': [
                {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [center_lon, center_lat]
                    },
                    'properties': {
                        'type': 'analysis_center',
                        'walkability_score': result['walkability_score'],
                        'grade': grade,
                        'description': description,
                        **result['component_scores']
                    }
                }
            ]
        }

        # Add amenities as features
        for amenity in amenities_found[:50]:  # Limit to 50
            geojson['features'].append({
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [amenity['lon'], amenity['lat']]
                },
                'properties': {
                    'category': amenity['category'],
                    'type': amenity['type'],
                    'name': amenity['name'],
                    'distance': amenity['distance']
                }
            })

        output = json.dumps(geojson, indent=2)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"GeoJSON saved to {args.output}")
        else:
            print(output)

    else:  # text format
        print(f"\n{'='*70}")
        print(f"WALKABILITY ANALYSIS")
        print(f"{'='*70}")
        print(f"Location: {center_lat:.6f}, {center_lon:.6f}")
        print(f"Radius: {args.radius}m  |  Area: {area_km2:.2f} km2")
        print(f"Grade: {grade} - {description}")

        print(f"\n{'-'*70}")
        print(f"ROAD NETWORK")
        print(f"{'-'*70}")
        print(f"  Total network:       {total_length/1000:.2f} km")
        print(f"  Pedestrian paths:    {pedestrian_length/1000:.2f} km ({pedestrian_ratio*100:.0f}%)")
        print(f"  Intersections:       {intersections} ({intersection_density:.0f}/km2)")
        print(f"  Dead ends:           {dead_ends}")
        print(f"  Network nodes:       {total_nodes}")
        print(f"  Network edges:       {total_edges}")
        print(f"  Connectivity index:  {connectivity_index:.2f} (edges/nodes)")
        print(f"  Sidewalk coverage:   {sidewalk_coverage:.1f}%")
        if ped_zone_count > 0:
            print(f"  Pedestrian zones:    {ped_zone_count} ({ped_zone_area/10000:.2f} ha)")
        print()
        print(f"  Road type breakdown:")
        for road_type, length in sorted(road_lengths.items(), key=lambda x: -x[1]):
            pct = (length / total_length * 100) if total_length > 0 else 0
            print(f"    {road_type:18} {length/1000:>6.2f} km  ({pct:>4.1f}%)")

        print(f"\n{'-'*70}")
        print(f"AMENITIES ({total_amenities} total, {total_amenities/area_km2:.0f}/km2)")
        print(f"{'-'*70}")
        # Sort by count descending
        for cat, count in sorted(amenity_counts.items(), key=lambda x: -x[1]):
            density = count / area_km2 if area_km2 > 0 else 0
            print(f"  {cat.title():15} {count:>4}  ({density:>5.1f}/km2)")

        print(f"\n  Top amenity types:")
        for item_type, count in sorted(type_counts.items(), key=lambda x: -x[1])[:15]:
            print(f"    {item_type.replace('_', ' '):20} {count:>4}")
        if len(type_counts) > 15:
            print(f"    ... and {len(type_counts) - 15} more types")

        print(f"\n{'-'*70}")
        print(f"ACCESSIBILITY")
        print(f"{'-'*70}")
        if dist_to_food:
            print(f"  Nearest food/dining: {dist_to_food:.0f} m")
        else:
            print(f"  Nearest food/dining: N/A")
        if dist_to_shop:
            print(f"  Nearest shop:        {dist_to_shop:.0f} m")
        else:
            print(f"  Nearest shop:        N/A")
        if dist_to_transit:
            print(f"  Nearest transit:     {dist_to_transit:.0f} m")
        else:
            print(f"  Nearest transit:     N/A")

        print(f"\n{'-'*70}")
        print(f"SAFETY")
        print(f"{'-'*70}")
        crossings_density = crossings / area_km2 if area_km2 > 0 else 0
        signals_density = traffic_signals / area_km2 if area_km2 > 0 else 0
        print(f"  Pedestrian crossings:  {crossings:>4}  ({crossings_density:.0f}/km2)")
        print(f"  Traffic signals:       {traffic_signals:>4}  ({signals_density:.0f}/km2)")
        print(f"  Street lighting:       {lighting:>4}")
        crossing_per_km = crossings / (total_length/1000) if total_length > 0 else 0
        print(f"  Crossings per km road: {crossing_per_km:.1f}")
        print()
        print(f"  Speed limits:")
        for speed, length in sorted(speed_limits.items(), key=lambda x: -x[1])[:8]:
            pct = (length / total_length * 100) if total_length > 0 else 0
            print(f"    {speed:12} {length/1000:>6.2f} km  ({pct:>4.1f}%)")

        print(f"\n{'-'*70}")
        print(f"GREEN SPACES")
        print(f"{'-'*70}")
        print(f"  Parks & gardens:       {greenspace_count:>4}")
        print(f"  Total area:            {greenspace_area/10000:.2f} ha ({greenspace_area:.0f} m2)")
        greenspace_pct = (greenspace_area / (area_km2 * 1000000) * 100) if area_km2 > 0 else 0
        print(f"  Coverage:              {greenspace_pct:.1f}% of analysis area")

        print(f"\n{'-'*70}")
        print(f"BUILDINGS")
        print(f"{'-'*70}")
        print(f"  Building count:        {building_count:>4}  ({building_count/area_km2:.0f}/km2)")
        print(f"  Total footprint:       {building_area/10000:.2f} ha ({building_area:.0f} m2)")
        building_pct = (building_area / (area_km2 * 1000000) * 100) if area_km2 > 0 else 0
        print(f"  Coverage:              {building_pct:.1f}% of analysis area")

        print(f"\n{'='*70}")
        print(f"[{elapsed:.3f}s]")

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
            print(f"\nResults saved to {args.output}")

    return 0
