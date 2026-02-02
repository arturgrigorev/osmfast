"""Bikeability Score command - analyze cycling infrastructure quality."""
import json
import math
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

from ...parsing.mmap_parser import UltraFastOSMParser


# Bikeability factor weights (sum to 1.0)
BIKEABILITY_WEIGHTS = {
    'dedicated_infrastructure': 0.25,  # Bike lanes, cycleways, bike roads
    'intersection_safety': 0.15,       # Safe crossings of car roads
    'road_quality': 0.15,              # Surface type, width
    'network_connectivity': 0.15,      # Connected routes, cycle networks
    'traffic_separation': 0.10,        # Separation from car traffic
    'bike_facilities': 0.10,           # Parking, repair stations
    'traffic_calming': 0.05,           # Speed limits, residential streets
    'topography': 0.05,                # Elevation changes (proxy)
}

# Cycling infrastructure types with quality scores (0-100)
BIKE_INFRASTRUCTURE = {
    'cycleway': 100,           # Dedicated bike path
    'path': 70,                # Shared use path
    'living_street': 80,       # Traffic-calmed street
    'pedestrian': 60,          # Often allows bikes
    'residential': 50,         # Low traffic
    'tertiary': 40,            # Medium traffic
    'secondary': 25,           # Higher traffic
    'primary': 15,             # High traffic, less safe
    'trunk': 5,                # Very high traffic
    'motorway': 0,             # Not bikeable
}

# Bike lane types and quality
BIKE_LANE_TYPES = {
    'lane': 80,                # On-road bike lane
    'track': 95,               # Separated bike track
    'share_busway': 60,        # Shared bus lane
    'shared_lane': 40,         # Sharrows
    'shoulder': 30,            # Road shoulder
    'opposite': 70,            # Contraflow bike lane
    'opposite_lane': 75,       # Contraflow dedicated lane
    'opposite_track': 90,      # Contraflow separated track
}

# Bike road/street types - reference scores (detection uses simplified logic)
BIKE_ROAD_TAGS = {
    'bicycle_road': {'yes': 100, 'designated': 95},
    'cyclestreet': {'yes': 100},
    'bicycle': {'designated': 80, 'official': 75},
}

# Car road types for intersection danger analysis
CAR_ROAD_HIERARCHY = {
    'motorway': 100,      # Most dangerous
    'motorway_link': 95,
    'trunk': 90,
    'trunk_link': 85,
    'primary': 80,
    'primary_link': 75,
    'secondary': 60,
    'secondary_link': 55,
    'tertiary': 40,
    'tertiary_link': 35,
    'unclassified': 25,
    'residential': 15,
    'service': 10,
    'living_street': 5,
}

# Intersection safety features - reference scores for crossing types
CROSSING_SAFETY = {
    'traffic_signals': 90,     # Signalized crossing
    'marked': 70,              # Marked/zebra crossing
    'uncontrolled': 40,        # Uncontrolled crossing
    'unmarked': 30,
    'island': 60,              # Refuge island
}

# Separation quality from car traffic - reference scores
SEPARATION_TYPES = {
    'separate': 100,           # Physically separate path
    'segregated': 90,          # Segregated from pedestrians
    'kerb': 80,                # Kerb separation
    'bollard': 75,             # Bollard separation
    'painted': 50,             # Paint only
    'none': 20,                # No separation
}

# Surface quality for cycling
SURFACE_QUALITY = {
    'asphalt': 100,
    'paved': 95,
    'concrete': 90,
    'paving_stones': 75,
    'compacted': 60,
    'fine_gravel': 50,
    'gravel': 40,
    'dirt': 30,
    'grass': 20,
    'sand': 10,
    'cobblestone': 35,
}

# Bike facilities
BIKE_FACILITIES = {
    'bicycle_parking': {'capacity_default': 10},
    'bicycle_rental': {'capacity_default': 20},
    'bicycle_repair_station': {'capacity_default': 5},
    'compressed_air': {'capacity_default': 2},
}

# Barrier types that impede cycling (penalty scores 0-100, higher = worse)
BARRIER_PENALTIES = {
    'gate': 30,              # May be locked
    'lift_gate': 25,
    'swing_gate': 25,
    'bollard': 10,           # Usually passable
    'cycle_barrier': 15,     # Designed to slow bikes
    'block': 40,             # Often impassable
    'jersey_barrier': 50,
    'fence': 60,
    'wall': 80,
    'kerb': 5,               # Minor obstacle
    'cattle_grid': 35,       # Dangerous for bikes
    'stile': 70,             # Requires dismount
    'turnstile': 60,
    'chain': 20,
    'step': 50,              # Steps require carrying bike
    'debris': 40,
}

# Bicycle parking quality scores (0-100)
PARKING_TYPE_SCORES = {
    'stands': 60,            # Basic bike stands
    'rack': 55,
    'wall_loops': 50,
    'wide_stands': 70,
    'building': 95,          # Indoor parking
    'shed': 85,              # Covered shed
    'lockers': 90,           # Secure lockers
    'garage': 90,
    'two-tier': 65,          # Two-tier racks
    'floor': 40,             # Just floor space
    'informal': 20,
    'anchors': 45,           # Ground anchors only
}

# Kerb types and their impact on cycling (lower = better)
KERB_PENALTIES = {
    'flush': 0,              # Ideal
    'lowered': 5,
    'raised': 30,
    'rolled': 15,
    'regular': 40,           # Standard kerb height
}

# HGV (Heavy Goods Vehicle) route danger levels
HGV_DANGER = {
    'designated': 80,        # Official truck route
    'yes': 60,
    'delivery': 40,
    'destination': 30,
    'agricultural': 20,
    'no': 0,
}


def setup_parser(subparsers):
    """Setup the bikeability subcommand parser."""
    parser = subparsers.add_parser(
        'bikeability',
        help='Calculate bikeability score for an area',
        description='Analyze cycling infrastructure and calculate bikeability scores'
    )

    parser.add_argument('input', help='Input OSM file')
    parser.add_argument('-o', '--output', help='Output file')
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
    # Clamp 'a' to prevent floating point errors causing sqrt of negative
    a = min(1.0, a)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def analyze_road_network(ways, node_coords, center_lon, center_lat, radius):
    """Analyze road network for cycling quality."""
    total_length = 0
    cycleway_length = 0
    bike_lane_length = 0
    bike_road_length = 0
    separated_length = 0
    low_traffic_length = 0
    surface_weighted_length = 0
    surface_total_length = 0
    contraflow_length = 0

    road_types = defaultdict(float)
    surface_types = defaultdict(float)
    separation_types = defaultdict(float)

    for way in ways:
        highway = way.tags.get('highway')
        if not highway:
            continue

        # Calculate way length within radius
        coords = []
        for ref in way.node_refs:
            if ref in node_coords:
                coords.append(node_coords[ref])

        if len(coords) < 2:
            continue

        # Check if way is within radius
        avg_lon = sum(c[0] for c in coords) / len(coords)
        avg_lat = sum(c[1] for c in coords) / len(coords)
        dist = haversine_distance(center_lon, center_lat, avg_lon, avg_lat)

        if dist > radius:
            continue

        # Calculate way length
        way_length = 0
        for i in range(len(coords) - 1):
            way_length += haversine_distance(
                coords[i][0], coords[i][1],
                coords[i+1][0], coords[i+1][1]
            )

        total_length += way_length
        road_types[highway] += way_length

        # Check for cycling infrastructure
        if highway == 'cycleway':
            cycleway_length += way_length

        # Check for bike roads (Fahrradstraße / cycle streets)
        bicycle_road = way.tags.get('bicycle_road')
        cyclestreet = way.tags.get('cyclestreet')
        if bicycle_road in ('yes', 'designated') or cyclestreet == 'yes':
            bike_road_length += way_length

        # Check for bike lanes - avoid double counting
        cycleway_tag = way.tags.get('cycleway')
        cycleway_left = way.tags.get('cycleway:left')
        cycleway_right = way.tags.get('cycleway:right')
        cycleway_both = way.tags.get('cycleway:both')

        # Use most specific tags: cycleway:both > cycleway:left/right > cycleway
        if cycleway_both in BIKE_LANE_TYPES:
            bike_lane_length += way_length * 2
            if 'opposite' in cycleway_both:
                contraflow_length += way_length * 2
        elif cycleway_left in BIKE_LANE_TYPES or cycleway_right in BIKE_LANE_TYPES:
            # Count each side separately
            if cycleway_left in BIKE_LANE_TYPES:
                bike_lane_length += way_length
                if 'opposite' in cycleway_left:
                    contraflow_length += way_length
            if cycleway_right in BIKE_LANE_TYPES:
                bike_lane_length += way_length
                if 'opposite' in cycleway_right:
                    contraflow_length += way_length
        elif cycleway_tag in BIKE_LANE_TYPES:
            bike_lane_length += way_length
            if 'opposite' in cycleway_tag:
                contraflow_length += way_length

        # Check for bicycle=yes/designated (only if no cycleway infrastructure already counted)
        bicycle = way.tags.get('bicycle')
        has_cycleway_infra = (
            highway == 'cycleway' or
            cycleway_tag in BIKE_LANE_TYPES or
            cycleway_left in BIKE_LANE_TYPES or
            cycleway_right in BIKE_LANE_TYPES or
            cycleway_both in BIKE_LANE_TYPES
        )
        if bicycle in ('yes', 'designated', 'official') and not has_cycleway_infra:
            bike_lane_length += way_length * 0.3  # Partial credit

        # Check for footway with bicycle=yes (shared paths)
        # Note: path with bicycle access is common but lower quality than dedicated cycleway
        if highway == 'footway' and bicycle in ('yes', 'designated') and not has_cycleway_infra:
            bike_lane_length += way_length * 0.5

        # Check for oneway exceptions for bicycles
        oneway = way.tags.get('oneway')
        oneway_bicycle = way.tags.get('oneway:bicycle')
        if oneway == 'yes' and oneway_bicycle == 'no':
            contraflow_length += way_length

        # Check separation from car traffic
        segregated = way.tags.get('segregated')
        separation = way.tags.get('cycleway:separation')
        separation_left = way.tags.get('cycleway:left:separation')
        separation_right = way.tags.get('cycleway:right:separation')

        if highway == 'cycleway' or segregated == 'yes':
            separated_length += way_length
            separation_types['segregated'] += way_length
        elif separation or separation_left or separation_right:
            sep_val = separation or separation_left or separation_right
            separation_types[sep_val] += way_length
            if sep_val in ('kerb', 'bollard', 'fence', 'vertical_panel'):
                separated_length += way_length

        # Low traffic streets
        if highway in ('living_street', 'residential', 'pedestrian', 'path'):
            low_traffic_length += way_length

        # Surface analysis
        surface = way.tags.get('surface')
        if surface:
            surface_types[surface] += way_length
            quality = SURFACE_QUALITY.get(surface, 50)
            surface_weighted_length += way_length * quality
            surface_total_length += way_length

    return {
        'total_length': total_length,
        'cycleway_length': cycleway_length,
        'bike_lane_length': bike_lane_length,
        'bike_road_length': bike_road_length,
        'separated_length': separated_length,
        'contraflow_length': contraflow_length,
        'low_traffic_length': low_traffic_length,
        'surface_weighted_length': surface_weighted_length,
        'surface_total_length': surface_total_length,
        'road_types': dict(road_types),
        'surface_types': dict(surface_types),
        'separation_types': dict(separation_types)
    }


def analyze_bike_facilities(nodes, center_lon, center_lat, radius, node_coords):
    """Analyze bike-related facilities."""
    facilities = defaultdict(list)

    for node in nodes:
        if node.id not in node_coords:
            continue

        lon, lat = node_coords[node.id]
        dist = haversine_distance(center_lon, center_lat, lon, lat)

        if dist > radius:
            continue

        amenity = node.tags.get('amenity')

        if amenity == 'bicycle_parking':
            try:
                capacity = int(node.tags.get('capacity', 10))
            except (ValueError, TypeError):
                capacity = 10
            facilities['parking'].append({
                'name': node.tags.get('name', 'Bike Parking'),
                'capacity': capacity,
                'covered': node.tags.get('covered') == 'yes',
                'distance': dist
            })

        elif amenity == 'bicycle_rental':
            try:
                capacity = int(node.tags.get('capacity', 20))
            except (ValueError, TypeError):
                capacity = 20
            facilities['rental'].append({
                'name': node.tags.get('name', 'Bike Rental'),
                'operator': node.tags.get('operator', 'Unknown'),
                'capacity': capacity,
                'distance': dist
            })

        elif amenity == 'bicycle_repair_station':
            facilities['repair'].append({
                'name': node.tags.get('name', 'Repair Station'),
                'distance': dist
            })

        elif amenity == 'compressed_air':
            facilities['air_pump'].append({
                'distance': dist
            })

        # Check for bike shops
        shop = node.tags.get('shop')
        if shop == 'bicycle':
            facilities['shops'].append({
                'name': node.tags.get('name', 'Bike Shop'),
                'distance': dist
            })

    return dict(facilities)


def analyze_barriers_and_obstacles(nodes, ways, node_coords, center_lon, center_lat, radius):
    """Analyze barriers and obstacles that impede cycling."""
    barriers = defaultdict(int)
    dismount_sections = 0
    dismount_length = 0
    kerb_issues = defaultdict(int)
    total_barrier_penalty = 0

    # Node-based barriers
    for node in nodes:
        if node.id not in node_coords:
            continue

        lon, lat = node_coords[node.id]
        dist = haversine_distance(center_lon, center_lat, lon, lat)
        if dist > radius:
            continue

        barrier = node.tags.get('barrier')
        if barrier:
            barriers[barrier] += 1
            total_barrier_penalty += BARRIER_PENALTIES.get(barrier, 20)

        # Kerb analysis at crossings
        kerb = node.tags.get('kerb')
        if kerb:
            kerb_issues[kerb] += 1

    # Way-based obstacles
    for way in ways:
        bicycle = way.tags.get('bicycle')

        # Check for dismount sections
        if bicycle == 'dismount':
            coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
            if len(coords) >= 2:
                avg_lon = sum(c[0] for c in coords) / len(coords)
                avg_lat = sum(c[1] for c in coords) / len(coords)
                dist = haversine_distance(center_lon, center_lat, avg_lon, avg_lat)
                if dist <= radius:
                    dismount_sections += 1
                    for i in range(len(coords) - 1):
                        dismount_length += haversine_distance(
                            coords[i][0], coords[i][1],
                            coords[i+1][0], coords[i+1][1]
                        )

        # Way-based barriers (e.g., barrier=fence along a way)
        barrier = way.tags.get('barrier')
        if barrier:
            coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
            if len(coords) >= 2:
                avg_lon = sum(c[0] for c in coords) / len(coords)
                avg_lat = sum(c[1] for c in coords) / len(coords)
                dist = haversine_distance(center_lon, center_lat, avg_lon, avg_lat)
                if dist <= radius:
                    barriers[barrier] += 1
                    total_barrier_penalty += BARRIER_PENALTIES.get(barrier, 20)

    # Calculate kerb penalty score
    kerb_penalty = sum(
        count * KERB_PENALTIES.get(kerb_type, 20)
        for kerb_type, count in kerb_issues.items()
    )

    return {
        'barriers': dict(barriers),
        'total_barriers': sum(barriers.values()),
        'total_barrier_penalty': total_barrier_penalty,
        'dismount_sections': dismount_sections,
        'dismount_length_m': dismount_length,
        'kerb_issues': dict(kerb_issues),
        'kerb_penalty': kerb_penalty,
    }


def analyze_parking_quality(nodes, center_lon, center_lat, radius, node_coords):
    """Analyze bicycle parking quality in detail."""
    parking_spots = []

    for node in nodes:
        if node.id not in node_coords:
            continue

        lon, lat = node_coords[node.id]
        dist = haversine_distance(center_lon, center_lat, lon, lat)
        if dist > radius:
            continue

        amenity = node.tags.get('amenity')
        if amenity != 'bicycle_parking':
            continue

        parking_type = node.tags.get('bicycle_parking', 'unknown')
        covered = node.tags.get('covered') == 'yes'
        access = node.tags.get('access', 'yes')
        surveillance = node.tags.get('surveillance')
        fee = node.tags.get('fee', 'no')

        try:
            capacity = int(node.tags.get('capacity', 10))
        except (ValueError, TypeError):
            capacity = 10

        # Calculate quality score for this parking
        base_score = PARKING_TYPE_SCORES.get(parking_type, 50)
        if covered:
            base_score += 15
        if surveillance in ('yes', 'cctv', 'guard'):
            base_score += 10
        if access == 'private':
            base_score -= 20
        if fee == 'yes':
            base_score -= 5

        quality_score = max(0, min(100, base_score))

        parking_spots.append({
            'type': parking_type,
            'capacity': capacity,
            'covered': covered,
            'access': access,
            'surveillance': surveillance,
            'fee': fee,
            'quality_score': quality_score,
            'distance': dist
        })

    # Calculate aggregate metrics
    total_capacity = sum(p['capacity'] for p in parking_spots)
    covered_capacity = sum(p['capacity'] for p in parking_spots if p['covered'])
    secure_spots = sum(1 for p in parking_spots if p.get('surveillance') in ('yes', 'cctv', 'guard'))

    if parking_spots and total_capacity > 0:
        avg_quality = sum(p['quality_score'] * p['capacity'] for p in parking_spots) / total_capacity
    elif parking_spots:
        # All spots have 0 capacity - use unweighted average
        avg_quality = sum(p['quality_score'] for p in parking_spots) / len(parking_spots)
    else:
        avg_quality = 0

    return {
        'parking_spots': parking_spots,
        'total_locations': len(parking_spots),
        'total_capacity': total_capacity,
        'covered_capacity': covered_capacity,
        'covered_ratio': covered_capacity / total_capacity if total_capacity > 0 else 0,
        'secure_locations': secure_spots,
        'avg_quality_score': avg_quality,
    }


def analyze_cycling_amenities(nodes, center_lon, center_lat, radius, node_coords):
    """Analyze additional cycling-friendly amenities."""
    amenities = {
        'drinking_water': [],
        'toilets': [],
        'benches': [],
        'shelters': [],
    }

    for node in nodes:
        if node.id not in node_coords:
            continue

        lon, lat = node_coords[node.id]
        dist = haversine_distance(center_lon, center_lat, lon, lat)
        if dist > radius:
            continue

        amenity = node.tags.get('amenity')

        if amenity == 'drinking_water':
            amenities['drinking_water'].append({
                'name': node.tags.get('name', 'Water Fountain'),
                'distance': dist
            })
        elif amenity == 'toilets':
            amenities['toilets'].append({
                'name': node.tags.get('name', 'Public Toilet'),
                'fee': node.tags.get('fee', 'unknown'),
                'distance': dist
            })
        elif amenity == 'bench':
            amenities['benches'].append({'distance': dist})
        elif amenity == 'shelter':
            amenities['shelters'].append({
                'name': node.tags.get('name', 'Shelter'),
                'distance': dist
            })

    return {
        'drinking_water': len(amenities['drinking_water']),
        'toilets': len(amenities['toilets']),
        'benches': len(amenities['benches']),
        'shelters': len(amenities['shelters']),
        'details': amenities
    }


def analyze_traffic_context(ways, node_coords, center_lon, center_lat, radius):
    """Analyze traffic context factors affecting cycling."""
    busway_bike_length = 0
    hgv_route_length = 0
    hgv_danger_weighted = 0
    oneway_exemptions = 0
    oneway_exemption_length = 0
    total_oneway_length = 0

    for way in ways:
        highway = way.tags.get('highway')
        if not highway:
            continue

        coords = [node_coords[ref] for ref in way.node_refs if ref in node_coords]
        if len(coords) < 2:
            continue

        avg_lon = sum(c[0] for c in coords) / len(coords)
        avg_lat = sum(c[1] for c in coords) / len(coords)
        dist = haversine_distance(center_lon, center_lat, avg_lon, avg_lat)
        if dist > radius:
            continue

        way_length = sum(
            haversine_distance(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])
            for i in range(len(coords) - 1)
        )

        # Busway with bicycle access
        busway = way.tags.get('busway')
        bus_lanes = way.tags.get('lanes:bus') or way.tags.get('lanes:psv')
        bicycle_on_bus = way.tags.get('bicycle') in ('yes', 'designated')

        if (busway or bus_lanes) and bicycle_on_bus:
            busway_bike_length += way_length

        # HGV (truck) routes
        hgv = way.tags.get('hgv')
        if hgv and hgv != 'no':
            hgv_route_length += way_length
            hgv_danger_weighted += way_length * HGV_DANGER.get(hgv, 40)

        # One-way exemptions for cyclists
        oneway = way.tags.get('oneway')
        if oneway == 'yes':
            total_oneway_length += way_length
            oneway_bicycle = way.tags.get('oneway:bicycle')
            cycleway = way.tags.get('cycleway')

            if oneway_bicycle == 'no' or (cycleway and 'opposite' in cycleway):
                oneway_exemptions += 1
                oneway_exemption_length += way_length

    # Calculate HGV danger score (0-100, lower is better)
    if hgv_route_length > 0:
        avg_hgv_danger = hgv_danger_weighted / hgv_route_length
    else:
        avg_hgv_danger = 0

    return {
        'busway_bike_access_m': busway_bike_length,
        'hgv_route_length_m': hgv_route_length,
        'hgv_danger_score': avg_hgv_danger,
        'oneway_total_length_m': total_oneway_length,
        'oneway_exemptions': oneway_exemptions,
        'oneway_exemption_length_m': oneway_exemption_length,
        'oneway_exemption_ratio': oneway_exemption_length / total_oneway_length if total_oneway_length > 0 else 0,
    }


def analyze_network_connectivity(ways, node_coords, center_lon, center_lat, radius):
    """Analyze cycling network connectivity."""
    # Build graph of bikeable roads
    graph = defaultdict(set)
    bikeable_nodes = set()

    for way in ways:
        highway = way.tags.get('highway')
        if BIKE_INFRASTRUCTURE.get(highway, 0) < 20:
            continue

        refs = way.node_refs
        for i in range(len(refs) - 1):
            from_id, to_id = refs[i], refs[i + 1]
            if from_id in node_coords and to_id in node_coords:
                graph[from_id].add(to_id)
                graph[to_id].add(from_id)
                bikeable_nodes.add(from_id)
                bikeable_nodes.add(to_id)

    # Filter to radius
    nodes_in_radius = set()
    for node_id in bikeable_nodes:
        if node_id in node_coords:
            lon, lat = node_coords[node_id]
            dist = haversine_distance(center_lon, center_lat, lon, lat)
            if dist <= radius:
                nodes_in_radius.add(node_id)

    # Count intersections (3+ connections)
    intersections = 0
    for node_id in nodes_in_radius:
        if len(graph[node_id]) >= 3:
            intersections += 1

    # Find connected components (simple BFS)
    visited = set()
    components = []

    for start in nodes_in_radius:
        if start in visited:
            continue

        component = set()
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            if node in nodes_in_radius:
                component.add(node)
                for neighbor in graph[node]:
                    if neighbor not in visited:
                        queue.append(neighbor)

        if component:
            components.append(component)

    # Calculate connectivity ratio
    if components:
        largest = max(len(c) for c in components)
        connectivity = largest / len(nodes_in_radius) if nodes_in_radius else 0
    else:
        largest = 0
        connectivity = 0

    return {
        'bikeable_nodes': len(nodes_in_radius),
        'intersections': intersections,
        'components': len(components),
        'largest_component': largest,
        'connectivity_ratio': connectivity
    }


def analyze_safety_features(nodes, ways, center_lon, center_lat, radius, node_coords):
    """Analyze cycling safety features."""
    crossings = 0
    traffic_signals = 0
    speed_limits = defaultdict(float)

    # Node-based features
    for node in nodes:
        if node.id not in node_coords:
            continue

        lon, lat = node_coords[node.id]
        dist = haversine_distance(center_lon, center_lat, lon, lat)

        if dist > radius:
            continue

        highway = node.tags.get('highway')
        if highway == 'crossing':
            crossings += 1
        elif highway == 'traffic_signals':
            traffic_signals += 1

    # Way-based features (speed limits)
    for way in ways:
        highway = way.tags.get('highway')
        if not highway:
            continue

        maxspeed = way.tags.get('maxspeed')
        if not maxspeed:
            continue

        # Parse speed limit
        try:
            if 'mph' in maxspeed:
                speed = int(maxspeed.replace('mph', '').strip()) * 1.6
            else:
                speed = int(maxspeed.replace('km/h', '').strip())
        except ValueError:
            continue

        # Calculate way length
        coords = []
        for ref in way.node_refs:
            if ref in node_coords:
                coords.append(node_coords[ref])

        if len(coords) < 2:
            continue

        avg_lon = sum(c[0] for c in coords) / len(coords)
        avg_lat = sum(c[1] for c in coords) / len(coords)
        dist = haversine_distance(center_lon, center_lat, avg_lon, avg_lat)

        if dist > radius:
            continue

        way_length = sum(
            haversine_distance(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])
            for i in range(len(coords) - 1)
        )

        if speed <= 30:
            speed_limits['low'] += way_length
        elif speed <= 50:
            speed_limits['medium'] += way_length
        else:
            speed_limits['high'] += way_length

    return {
        'crossings': crossings,
        'traffic_signals': traffic_signals,
        'speed_limits': dict(speed_limits)
    }


def analyze_intersection_danger(ways, nodes, node_coords, center_lon, center_lat, radius):
    """Analyze dangerous intersections where bike routes cross car roads."""
    # Build node usage map - which ways use each node
    node_ways = defaultdict(list)
    way_info = {}

    for way in ways:
        highway = way.tags.get('highway')
        if not highway:
            continue

        # Determine if this is a bike-friendly way or car road
        is_bike_way = (
            highway == 'cycleway' or
            highway == 'path' or
            way.tags.get('bicycle_road') == 'yes' or
            way.tags.get('cycleway') in BIKE_LANE_TYPES or
            way.tags.get('bicycle') in ('designated', 'yes')
        )

        is_car_road = highway in CAR_ROAD_HIERARCHY and CAR_ROAD_HIERARCHY[highway] >= 25

        way_info[way.id] = {
            'highway': highway,
            'is_bike': is_bike_way,
            'is_car': is_car_road,
            'danger_level': CAR_ROAD_HIERARCHY.get(highway, 0)
        }

        for ref in way.node_refs:
            node_ways[ref].append(way.id)

    # Find bicycle crossing nodes AND all traffic signal nodes
    bike_crossings = {}
    signal_locations = []  # Store all traffic signal locations for proximity search

    for node in nodes:
        if node.id not in node_coords:
            continue

        lon, lat = node_coords[node.id]
        dist = haversine_distance(center_lon, center_lat, lon, lat)
        if dist > radius:
            continue

        highway = node.tags.get('highway')
        crossing = node.tags.get('crossing')
        bicycle = node.tags.get('bicycle')

        # Track all traffic signals for proximity search
        if highway == 'traffic_signals' or crossing == 'traffic_signals':
            signal_locations.append((lon, lat, node.id))

        # Check if it's a bike crossing
        is_bike_crossing = (
            (highway == 'crossing' and bicycle in ('yes', 'designated')) or
            crossing == 'traffic_signals' or
            node.tags.get('crossing:island') == 'yes'
        )

        if is_bike_crossing:
            has_signals = (
                highway == 'traffic_signals' or
                crossing == 'traffic_signals' or
                node.tags.get('crossing:signals') == 'yes'
            )
            bike_crossings[node.id] = {
                'type': crossing or 'unknown',
                'traffic_signals': has_signals,
                'island': node.tags.get('crossing:island') == 'yes',
                'marked': crossing in ('marked', 'zebra', 'controlled')
            }

    # Analyze intersections where bike ways meet car roads
    dangerous_intersections = []
    safe_intersections = []

    for node_id, way_ids in node_ways.items():
        if len(way_ids) < 2:
            continue

        if node_id not in node_coords:
            continue

        lon, lat = node_coords[node_id]
        dist = haversine_distance(center_lon, center_lat, lon, lat)
        if dist > radius:
            continue

        # Check if bike way meets car road
        has_bike_way = False
        max_car_danger = 0

        for wid in way_ids:
            if wid in way_info:
                info = way_info[wid]
                if info['is_bike']:
                    has_bike_way = True
                if info['is_car']:
                    max_car_danger = max(max_car_danger, info['danger_level'])

        if has_bike_way and max_car_danger > 0:
            # This is a bike-car intersection
            crossing_info = bike_crossings.get(node_id, {})
            has_signals = crossing_info.get('traffic_signals', False)
            has_island = crossing_info.get('island', False)

            # If no direct signal tag, check for nearby traffic signals (within 25m)
            if not has_signals and signal_locations:
                for sig_lon, sig_lat, sig_id in signal_locations:
                    if haversine_distance(lon, lat, sig_lon, sig_lat) <= 25:
                        has_signals = True
                        break

            # Calculate safety score for this intersection
            safety_score = 100 - max_car_danger
            if has_signals:
                safety_score += 40
            if has_island:
                safety_score += 20
            if crossing_info.get('marked', False):
                safety_score += 10

            safety_score = max(0, min(100, safety_score))

            intersection = {
                'node_id': node_id,
                'car_danger_level': max_car_danger,
                'has_signals': has_signals,
                'has_island': has_island,
                'safety_score': safety_score
            }

            if safety_score >= 60:
                safe_intersections.append(intersection)
            else:
                dangerous_intersections.append(intersection)

    # Calculate overall intersection safety score
    total_intersections = len(dangerous_intersections) + len(safe_intersections)
    if total_intersections > 0:
        avg_safety = (
            sum(i['safety_score'] for i in dangerous_intersections) +
            sum(i['safety_score'] for i in safe_intersections)
        ) / total_intersections
        safe_ratio = len(safe_intersections) / total_intersections
    else:
        avg_safety = 70  # Default if no intersections
        safe_ratio = 1.0

    # Count actually signalized crossings
    signalized_count = sum(1 for c in bike_crossings.values() if c.get('traffic_signals'))

    return {
        'total_bike_car_intersections': total_intersections,
        'dangerous_intersections': len(dangerous_intersections),
        'safe_intersections': len(safe_intersections),
        'signalized_crossings': signalized_count,
        'avg_intersection_safety': avg_safety,
        'safe_ratio': safe_ratio
    }


def calculate_bikeability_score(
    road_analysis,
    facilities,
    connectivity,
    safety,
    intersection_analysis
):
    """Calculate overall bikeability score (0-100)."""
    scores = {}

    # Dedicated infrastructure (25%) - cycleways, bike lanes, bike roads
    if road_analysis['total_length'] > 0:
        dedicated_ratio = (
            road_analysis['cycleway_length'] +
            road_analysis['bike_lane_length'] +
            road_analysis['bike_road_length']
        ) / road_analysis['total_length']
        # Add bonus for contraflow cycling
        contraflow_bonus = min(10, road_analysis['contraflow_length'] / road_analysis['total_length'] * 100)
        scores['dedicated_infrastructure'] = min(100, dedicated_ratio * 400 + contraflow_bonus)  # 25% = 100
    else:
        scores['dedicated_infrastructure'] = 0

    # Intersection safety (15%) - safe crossings of car roads
    scores['intersection_safety'] = intersection_analysis['avg_intersection_safety']

    # Road quality (15%)
    if road_analysis['surface_total_length'] > 0:
        avg_surface_quality = (
            road_analysis['surface_weighted_length'] /
            road_analysis['surface_total_length']
        )
        scores['road_quality'] = avg_surface_quality
    else:
        scores['road_quality'] = 50  # Assume average

    # Network connectivity (15%)
    scores['network_connectivity'] = min(100, connectivity['connectivity_ratio'] * 120)

    # Traffic separation (10%) - physical separation from cars
    if road_analysis['total_length'] > 0:
        separated_ratio = road_analysis['separated_length'] / road_analysis['total_length']
        scores['traffic_separation'] = min(100, separated_ratio * 500)  # 20% = 100
    else:
        scores['traffic_separation'] = 0

    # Bike facilities (10%)
    parking_score = min(50, len(facilities.get('parking', [])) * 10)
    rental_score = min(30, len(facilities.get('rental', [])) * 15)
    other_score = min(20, (
        len(facilities.get('repair', [])) * 10 +
        len(facilities.get('shops', [])) * 5 +
        len(facilities.get('air_pump', [])) * 5
    ))
    scores['bike_facilities'] = parking_score + rental_score + other_score

    # Traffic calming (5%)
    if road_analysis['total_length'] > 0:
        low_traffic_ratio = road_analysis['low_traffic_length'] / road_analysis['total_length']
        # Also consider speed limits
        total_speed_length = sum(safety['speed_limits'].values())
        if total_speed_length > 0:
            low_speed_ratio = safety['speed_limits'].get('low', 0) / total_speed_length
        else:
            low_speed_ratio = 0.3  # Assume some low speed
        scores['traffic_calming'] = min(100, (low_traffic_ratio + low_speed_ratio) * 100)
    else:
        scores['traffic_calming'] = 0

    # Topography (5%) - proxy based on road types (assume flat if no data)
    scores['topography'] = 70  # Default to moderate

    # Calculate weighted total
    total = sum(scores[k] * BIKEABILITY_WEIGHTS[k] for k in BIKEABILITY_WEIGHTS)

    return total, scores


def get_bikeability_grade(score):
    """Convert numeric score to grade."""
    if score >= 90:
        return 'A+', 'Cyclist\'s Paradise'
    elif score >= 80:
        return 'A', 'Excellent for Cycling'
    elif score >= 70:
        return 'B', 'Very Bikeable'
    elif score >= 60:
        return 'C', 'Bikeable'
    elif score >= 50:
        return 'D', 'Somewhat Bikeable'
    else:
        return 'F', 'Not Bike-Friendly'


def run(args):
    """Execute the bikeability command."""
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: File not found: {args.input}", file=sys.stderr)
        return 1

    start_time = time.time()

    # Parse file
    parser = UltraFastOSMParser()
    nodes, ways = parser.parse_file_ultra_fast(str(input_path))

    # Use parser's coordinate cache
    node_coords = {}
    for node_id, (lat, lon) in parser.node_coordinates.items():
        node_coords[node_id] = (float(lon), float(lat))

    if not node_coords:
        print("Error: No coordinates found", file=sys.stderr)
        return 1

    # Determine center
    if args.lat is not None and args.lon is not None:
        center_lat, center_lon = args.lat, args.lon
    else:
        all_lons = [c[0] for c in node_coords.values()]
        all_lats = [c[1] for c in node_coords.values()]
        center_lon = sum(all_lons) / len(all_lons)
        center_lat = sum(all_lats) / len(all_lats)

    print(f"Analyzing bikeability around ({center_lat:.6f}, {center_lon:.6f})", file=sys.stderr)
    print(f"Radius: {args.radius}m", file=sys.stderr)

    # Analyze components
    road_analysis = analyze_road_network(ways, node_coords, center_lon, center_lat, args.radius)
    facilities = analyze_bike_facilities(nodes, center_lon, center_lat, args.radius, node_coords)
    connectivity = analyze_network_connectivity(ways, node_coords, center_lon, center_lat, args.radius)
    safety = analyze_safety_features(nodes, ways, center_lon, center_lat, args.radius, node_coords)
    intersection_analysis = analyze_intersection_danger(ways, nodes, node_coords, center_lon, center_lat, args.radius)

    # New enhanced analyses
    barriers = analyze_barriers_and_obstacles(nodes, ways, node_coords, center_lon, center_lat, args.radius)
    parking_quality = analyze_parking_quality(nodes, center_lon, center_lat, args.radius, node_coords)
    cycling_amenities = analyze_cycling_amenities(nodes, center_lon, center_lat, args.radius, node_coords)
    traffic_context = analyze_traffic_context(ways, node_coords, center_lon, center_lat, args.radius)

    # Calculate score
    bikeability_score, component_scores = calculate_bikeability_score(
        road_analysis, facilities, connectivity, safety, intersection_analysis
    )

    grade, description = get_bikeability_grade(bikeability_score)

    elapsed = time.time() - start_time

    # Prepare output
    total_dedicated = (
        road_analysis['cycleway_length'] +
        road_analysis['bike_lane_length'] +
        road_analysis['bike_road_length']
    )
    result = {
        'center': {'lat': center_lat, 'lon': center_lon},
        'radius_m': args.radius,
        'bikeability_score': round(bikeability_score, 1),
        'grade': grade,
        'description': description,
        'component_scores': {k: round(v, 1) for k, v in component_scores.items()},
        'infrastructure': {
            'total_road_length_m': round(road_analysis['total_length'], 0),
            'cycleway_length_m': round(road_analysis['cycleway_length'], 0),
            'bike_lane_length_m': round(road_analysis['bike_lane_length'], 0),
            'bike_road_length_m': round(road_analysis['bike_road_length'], 0),
            'separated_length_m': round(road_analysis['separated_length'], 0),
            'contraflow_length_m': round(road_analysis['contraflow_length'], 0),
            'low_traffic_length_m': round(road_analysis['low_traffic_length'], 0),
            'dedicated_ratio': round(
                total_dedicated / road_analysis['total_length'] if road_analysis['total_length'] > 0 else 0,
                3
            ),
            'separation_ratio': round(
                road_analysis['separated_length'] / road_analysis['total_length'] if road_analysis['total_length'] > 0 else 0,
                3
            )
        },
        'intersections': {
            'total_bike_car_intersections': intersection_analysis['total_bike_car_intersections'],
            'dangerous_intersections': intersection_analysis['dangerous_intersections'],
            'safe_intersections': intersection_analysis['safe_intersections'],
            'signalized_crossings': intersection_analysis['signalized_crossings'],
            'avg_intersection_safety': round(intersection_analysis['avg_intersection_safety'], 1),
            'safe_ratio': round(intersection_analysis['safe_ratio'], 3)
        },
        'connectivity': connectivity,
        'facilities': {
            'parking_locations': len(facilities.get('parking', [])),
            'rental_locations': len(facilities.get('rental', [])),
            'repair_stations': len(facilities.get('repair', [])),
            'bike_shops': len(facilities.get('shops', []))
        },
        'parking_quality': {
            'total_capacity': parking_quality['total_capacity'],
            'covered_capacity': parking_quality['covered_capacity'],
            'covered_ratio': round(parking_quality['covered_ratio'], 3),
            'secure_locations': parking_quality['secure_locations'],
            'avg_quality_score': round(parking_quality['avg_quality_score'], 1),
        },
        'barriers': {
            'total_barriers': barriers['total_barriers'],
            'barrier_types': barriers['barriers'],
            'dismount_sections': barriers['dismount_sections'],
            'dismount_length_m': round(barriers['dismount_length_m'], 1),
            'kerb_issues': barriers['kerb_issues'],
        },
        'cycling_amenities': {
            'drinking_water': cycling_amenities['drinking_water'],
            'toilets': cycling_amenities['toilets'],
            'benches': cycling_amenities['benches'],
            'shelters': cycling_amenities['shelters'],
        },
        'traffic_context': {
            'busway_bike_access_m': round(traffic_context['busway_bike_access_m'], 1),
            'hgv_route_length_m': round(traffic_context['hgv_route_length_m'], 1),
            'hgv_danger_score': round(traffic_context['hgv_danger_score'], 1),
            'oneway_total_length_m': round(traffic_context['oneway_total_length_m'], 1),
            'oneway_exemptions': traffic_context['oneway_exemptions'],
            'oneway_exemption_ratio': round(traffic_context['oneway_exemption_ratio'], 3),
        },
        'safety': safety,
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
                        'bikeability_score': result['bikeability_score'],
                        'grade': grade,
                        'description': description,
                        **result['component_scores']
                    }
                }
            ]
        }

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(geojson, f, indent=2)
            print(f"GeoJSON saved to {args.output}")
        else:
            print(json.dumps(geojson, indent=2))

    else:  # text
        print(f"\n{'='*60}")
        print(f"BIKEABILITY INDEX ANALYSIS")
        print(f"{'='*60}")
        print(f"Location: {center_lat:.6f}, {center_lon:.6f}")
        print(f"Radius: {args.radius}m")
        print(f"\n{'-'*60}")
        print(f"OVERALL SCORE: {bikeability_score:.1f}/100  Grade: {grade}")
        print(f"Assessment: {description}")
        print(f"{'-'*60}")

        print(f"\nComponent Scores:")
        for component, score in component_scores.items():
            filled = min(20, max(0, int(score / 5)))
            bar = '#' * filled + '-' * (20 - filled)
            print(f"  {component.replace('_', ' ').title():30} [{bar}] {score:.1f}")

        print(f"\n{'-'*60}")
        print(f"Cycling Infrastructure:")
        print(f"  Total road network: {road_analysis['total_length']/1000:.2f} km")
        print(f"  Dedicated cycleways: {road_analysis['cycleway_length']/1000:.2f} km")
        print(f"  Bike lanes: {road_analysis['bike_lane_length']/1000:.2f} km")
        print(f"  Bike roads (cycle streets): {road_analysis['bike_road_length']/1000:.2f} km")
        print(f"  Separated from traffic: {road_analysis['separated_length']/1000:.2f} km")
        print(f"  Contraflow cycling: {road_analysis['contraflow_length']/1000:.2f} km")
        if road_analysis['total_length'] > 0:
            print(f"  Dedicated cycling ratio: {100*total_dedicated/road_analysis['total_length']:.1f}%")
            print(f"  Traffic separation ratio: {100*road_analysis['separated_length']/road_analysis['total_length']:.1f}%")

        print(f"\nIntersection Safety (bike-car crossings):")
        print(f"  Total bike-car intersections: {intersection_analysis['total_bike_car_intersections']}")
        print(f"  Safe intersections: {intersection_analysis['safe_intersections']}")
        print(f"  Dangerous intersections: {intersection_analysis['dangerous_intersections']}")
        print(f"  Signalized crossings: {intersection_analysis['signalized_crossings']}")
        print(f"  Average safety score: {intersection_analysis['avg_intersection_safety']:.1f}/100")

        print(f"\nNetwork Connectivity:")
        print(f"  Bikeable nodes: {connectivity['bikeable_nodes']}")
        print(f"  Bike network intersections: {connectivity['intersections']}")
        print(f"  Connected components: {connectivity['components']}")
        print(f"  Network connectivity: {connectivity['connectivity_ratio']*100:.1f}%")

        print(f"\nFacilities:")
        print(f"  Bike parking: {len(facilities.get('parking', []))} locations")
        print(f"  Bike rental: {len(facilities.get('rental', []))} stations")
        print(f"  Repair stations: {len(facilities.get('repair', []))}")
        print(f"  Bike shops: {len(facilities.get('shops', []))}")

        print(f"\nParking Quality:")
        print(f"  Total capacity: {parking_quality['total_capacity']} spaces")
        print(f"  Covered parking: {parking_quality['covered_capacity']} spaces ({parking_quality['covered_ratio']*100:.1f}%)")
        print(f"  Secure locations: {parking_quality['secure_locations']}")
        if parking_quality['avg_quality_score'] > 0:
            print(f"  Average quality score: {parking_quality['avg_quality_score']:.1f}/100")

        print(f"\nBarriers & Obstacles:")
        print(f"  Total barriers: {barriers['total_barriers']}")
        if barriers['barriers']:
            top_barriers = sorted(barriers['barriers'].items(), key=lambda x: -x[1])[:5]
            print(f"  Types: {', '.join(f'{k}({v})' for k, v in top_barriers)}")
        print(f"  Dismount sections: {barriers['dismount_sections']} ({barriers['dismount_length_m']:.0f}m)")
        if barriers['kerb_issues']:
            print(f"  Kerb types: {', '.join(f'{k}({v})' for k, v in barriers['kerb_issues'].items())}")

        print(f"\nCycling Amenities:")
        print(f"  Drinking water: {cycling_amenities['drinking_water']} fountains")
        print(f"  Public toilets: {cycling_amenities['toilets']}")
        print(f"  Benches: {cycling_amenities['benches']}")
        print(f"  Shelters: {cycling_amenities['shelters']}")

        print(f"\nTraffic Context:")
        print(f"  Busway with bike access: {traffic_context['busway_bike_access_m']/1000:.2f} km")
        print(f"  HGV/Truck routes: {traffic_context['hgv_route_length_m']/1000:.2f} km (danger: {traffic_context['hgv_danger_score']:.0f})")
        print(f"  One-way streets: {traffic_context['oneway_total_length_m']/1000:.2f} km")
        print(f"  One-way exemptions: {traffic_context['oneway_exemptions']} ({traffic_context['oneway_exemption_ratio']*100:.1f}%)")

        print(f"\nTraffic Calming:")
        print(f"  Low-traffic streets: {road_analysis['low_traffic_length']/1000:.2f} km")
        print(f"  Crossings: {safety['crossings']}")
        print(f"  Traffic signals: {safety['traffic_signals']}")

        print(f"\n[{elapsed:.3f}s]")

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
            print(f"\nResults saved to {args.output}")

    return 0
