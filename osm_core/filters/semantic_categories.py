"""Externalized semantic category definitions.

These frozensets define the recognized feature types for semantic extraction.
They can be extended or customized without modifying core code.
"""
from typing import FrozenSet

# Food & Drink amenities
FOOD_DRINK_AMENITIES: FrozenSet[str] = frozenset({
    'restaurant', 'fast_food', 'cafe', 'pub', 'bar', 'food_court', 'ice_cream',
    'biergarten', 'juice_bar', 'coffee_shop'
})

# Shopping amenities
SHOPPING_AMENITIES: FrozenSet[str] = frozenset({
    'marketplace', 'supermarket', 'convenience', 'department_store', 'mall',
    'vending_machine', 'kiosk'
})

# Service amenities
SERVICE_AMENITIES: FrozenSet[str] = frozenset({
    'bank', 'atm', 'post_office', 'pharmacy', 'hospital', 'clinic', 'dentist',
    'doctors', 'veterinary', 'social_facility', 'childcare', 'nursing_home',
    'bureau_de_change', 'money_transfer', 'lawyer', 'insurance', 'estate_agent'
})

# Education amenities
EDUCATION_AMENITIES: FrozenSet[str] = frozenset({
    'school', 'university', 'college', 'library', 'kindergarten',
    'language_school', 'music_school', 'driving_school', 'training', 'research_institute'
})

# Transportation amenities
TRANSPORT_AMENITIES: FrozenSet[str] = frozenset({
    'fuel', 'charging_station', 'car_wash', 'car_rental', 'taxi',
    'bus_station', 'parking', 'parking_space', 'parking_entrance',
    'bicycle_parking', 'bicycle_rental', 'bicycle_repair_station',
    'motorcycle_parking', 'boat_rental', 'ferry_terminal', 'car_sharing'
})

# Entertainment amenities
ENTERTAINMENT_AMENITIES: FrozenSet[str] = frozenset({
    'cinema', 'theatre', 'nightclub', 'casino', 'arts_centre',
    'community_centre', 'social_centre', 'events_venue', 'conference_centre',
    'exhibition_centre', 'planetarium', 'studio', 'gambling', 'dive_centre'
})

# Tourism amenities
TOURISM_AMENITIES: FrozenSet[str] = frozenset({
    'hotel', 'guest_house', 'hostel', 'motel', 'attraction',
    'camp_site', 'caravan_site', 'chalet', 'alpine_hut', 'wilderness_hut',
    'information', 'tourism'
})

# Public facilities
PUBLIC_AMENITIES: FrozenSet[str] = frozenset({
    'toilets', 'drinking_water', 'shower', 'bench', 'waste_basket',
    'waste_disposal', 'recycling', 'fountain', 'water_point', 'clock',
    'post_box', 'telephone', 'bbq', 'shelter', 'hunting_stand'
})

# Emergency services
EMERGENCY_AMENITIES: FrozenSet[str] = frozenset({
    'police', 'fire_station', 'ambulance_station', 'rescue_station',
    'coast_guard', 'mountain_rescue', 'lifeguard', 'emergency_phone'
})

# Government & civic
CIVIC_AMENITIES: FrozenSet[str] = frozenset({
    'townhall', 'courthouse', 'embassy', 'prison', 'ranger_station',
    'register_office', 'tax_office', 'customs', 'public_building'
})

# Religious
RELIGIOUS_AMENITIES: FrozenSet[str] = frozenset({
    'place_of_worship', 'monastery', 'grave_yard', 'crematorium', 'funeral_hall'
})

# Healthcare extended
HEALTHCARE_AMENITIES: FrozenSet[str] = frozenset({
    'hospital', 'clinic', 'doctors', 'dentist', 'pharmacy',
    'veterinary', 'blood_donation', 'nursing_home', 'baby_hatch',
    'healthcare', 'optician', 'physiotherapist', 'psychotherapist'
})

# Combined set of all recognized amenity types
ALL_AMENITY_TYPES: FrozenSet[str] = (
    FOOD_DRINK_AMENITIES |
    SHOPPING_AMENITIES |
    SERVICE_AMENITIES |
    EDUCATION_AMENITIES |
    TRANSPORT_AMENITIES |
    ENTERTAINMENT_AMENITIES |
    TOURISM_AMENITIES |
    PUBLIC_AMENITIES |
    EMERGENCY_AMENITIES |
    CIVIC_AMENITIES |
    RELIGIOUS_AMENITIES |
    HEALTHCARE_AMENITIES
)

# Highway types - major roads
MAJOR_HIGHWAY_TYPES: FrozenSet[str] = frozenset({
    'motorway', 'trunk', 'primary', 'secondary', 'tertiary'
})

# Highway types - local roads
LOCAL_HIGHWAY_TYPES: FrozenSet[str] = frozenset({
    'residential', 'unclassified', 'service', 'living_street'
})

# Highway types - pedestrian/cycling
PEDESTRIAN_HIGHWAY_TYPES: FrozenSet[str] = frozenset({
    'pedestrian', 'footway', 'steps', 'path', 'cycleway'
})

# Highway types - special purpose
SPECIAL_HIGHWAY_TYPES: FrozenSet[str] = frozenset({
    'bus_guideway', 'busway', 'raceway', 'track'
})

# Combined set of all recognized highway types
HIGHWAY_TYPES: FrozenSet[str] = (
    MAJOR_HIGHWAY_TYPES |
    LOCAL_HIGHWAY_TYPES |
    PEDESTRIAN_HIGHWAY_TYPES |
    SPECIAL_HIGHWAY_TYPES
)

# Building types - residential
RESIDENTIAL_BUILDING_TYPES: FrozenSet[str] = frozenset({
    'residential', 'apartments', 'house', 'detached', 'terrace',
    'semi', 'semidetached_house', 'semi_detached', 'bungalow', 'dormitory',
    'flats', 'flat', 'cabin', 'hut', 'static_caravan', 'home', 'villa',
    'townhouse', 'townhouses', 'units', 'unit', 'duplex', 'triplex'
})

# Building types - commercial
COMMERCIAL_BUILDING_TYPES: FrozenSet[str] = frozenset({
    'commercial', 'office', 'industrial', 'retail', 'warehouse',
    'supermarket', 'kiosk', 'hotel', 'motel', 'service', 'store', 'shop',
    'storage_tank', 'factory', 'manufacture'
})

# Building types - public/civic
PUBLIC_BUILDING_TYPES: FrozenSet[str] = frozenset({
    'public', 'school', 'hospital', 'government', 'civic', 'college',
    'university', 'kindergarten', 'library', 'fire_station', 'police',
    'train_station', 'transportation', 'sports_centre', 'stadium',
    'community_centre', 'prison', 'military', 'toilets', 'museum',
    'sports_hall', 'swimming_pool', 'theatre', 'cinema', 'courthouse',
    'hall', 'clubhouse', 'pub', 'mixed', 'civic_centre', 'arena'
})

# Building types - religious
RELIGIOUS_BUILDING_TYPES: FrozenSet[str] = frozenset({
    'religious', 'church', 'mosque', 'temple', 'synagogue', 'chapel',
    'cathedral', 'shrine', 'monastery', 'convent'
})

# Building types - agricultural/rural
AGRICULTURAL_BUILDING_TYPES: FrozenSet[str] = frozenset({
    'farm', 'farm_auxiliary', 'barn', 'stable', 'sty', 'cowshed',
    'greenhouse', 'glasshouse', 'slurry_tank', 'silo', 'granary'
})

# Building types - other/generic
OTHER_BUILDING_TYPES: FrozenSet[str] = frozenset({
    'yes', 'building', 'other', 'garage', 'garages', 'carport', 'shed',
    'roof', 'canopy', 'construction', 'ruins', 'abandoned',
    'hangar', 'pavilion', 'grandstand', 'bunker', 'shelter',
    'boathouse', 'houseboat', 'annexe', 'outbuilding', 'container',
    'kiosk', 'cabin', 'gatehouse', 'guardhouse', 'tower', 'bridge',
    'transformer_tower', 'water_tower', 'tank', 'storage', 'parking',
    'portable', 'demountable', 'prefabricated', 'modular', 'tent',
    'gazebo', 'pergola', 'veranda', 'porch', 'deckhouse', 'utility'
})

# Combined set of all recognized building types
BUILDING_TYPES: FrozenSet[str] = (
    RESIDENTIAL_BUILDING_TYPES |
    COMMERCIAL_BUILDING_TYPES |
    PUBLIC_BUILDING_TYPES |
    RELIGIOUS_BUILDING_TYPES |
    AGRICULTURAL_BUILDING_TYPES |
    OTHER_BUILDING_TYPES
)

# Important tags to preserve in feature properties
IMPORTANT_TAGS: FrozenSet[str] = frozenset({
    # Name and address
    'name', 'addr:street', 'addr:housenumber', 'addr:city', 'addr:postcode',
    'addr:country', 'alt_name', 'official_name',
    # Contact info
    'website', 'phone', 'email', 'opening_hours',
    # Classification
    'cuisine', 'brand', 'operator', 'network',
    # Road attributes
    'surface', 'maxspeed', 'lanes', 'oneway', 'lit', 'sidewalk',
    # Building attributes
    'height', 'levels', 'building:levels', 'roof:material', 'roof:shape',
    # General
    'description', 'note', 'access', 'wheelchair'
})

# Core road attributes for focused export
ROAD_ATTRIBUTES: FrozenSet[str] = frozenset({
    'name',           # Road name
    'ref',            # Road reference number (e.g., M1, A1)
    'maxspeed',       # Speed limit
    'lanes',          # Number of lanes
    'surface',        # Road surface (asphalt, concrete, etc.)
    'oneway',         # One-way indicator
    'lit',            # Street lighting
    'sidewalk',       # Sidewalk presence
    'access',         # Access restrictions
    'toll',           # Toll road
    'bridge',         # Bridge indicator
    'tunnel',         # Tunnel indicator
    'width',          # Road width
    'layer',          # Vertical layer for bridges/tunnels
})

# Default speed limits by road type (km/h) - used when maxspeed not tagged
DEFAULT_SPEEDS: dict = {
    'motorway': 110,
    'motorway_link': 80,
    'trunk': 80,
    'trunk_link': 60,
    'primary': 60,
    'primary_link': 50,
    'secondary': 50,
    'secondary_link': 40,
    'tertiary': 50,
    'tertiary_link': 40,
    'residential': 40,
    'unclassified': 40,
    'service': 20,
    'living_street': 20,
    'pedestrian': 10,
    'footway': 5,
    'cycleway': 20,
    'path': 10,
    'track': 30,
}

# Road geometry attributes (calculated fields, not OSM tags)
# These are added during extraction when --road-geometry is enabled
ROAD_GEOMETRY_FIELDS: FrozenSet[str] = frozenset({
    'length_m',       # Segment length in meters
    'length_km',      # Segment length in kilometers
    'sinuosity',      # Curvature ratio (1.0 = straight)
    'bearing',        # Direction in degrees (0-360)
    'speed_kph',      # Speed (from maxspeed or default)
    'travel_min',     # Estimated travel time in minutes
    'lane_km',        # lanes × length_km
    'has_sidewalk',   # Boolean: sidewalk present
    'is_lit',         # Boolean: street lighting
    'is_oneway',      # Boolean: one-way street
})

# Core building attributes for focused export
BUILDING_ATTRIBUTES: FrozenSet[str] = frozenset({
    'name',           # Building name
    'height',         # Building height in meters
    'levels',         # Number of floors (alias)
    'building:levels',  # Number of floors
    'building:material',  # Construction material
    'roof:shape',     # Roof shape
    'roof:material',  # Roof material
    'addr:street',    # Street address
    'addr:housenumber',  # House number
    'addr:postcode',  # Postal code
    'addr:city',      # City
    'start_date',     # Construction date
    'architect',      # Architect name
    'operator',       # Building operator
})

# Core amenity attributes for focused export
AMENITY_ATTRIBUTES: FrozenSet[str] = frozenset({
    'name',           # Amenity name
    'brand',          # Brand name
    'operator',       # Operator/owner
    'opening_hours',  # Operating hours
    'phone',          # Phone number
    'website',        # Website URL
    'email',          # Email address
    'cuisine',        # Type of cuisine (restaurants)
    'addr:street',    # Street address
    'addr:housenumber',  # House number
    'addr:postcode',  # Postal code
    'addr:city',      # City
    'wheelchair',     # Wheelchair accessibility
    'capacity',       # Capacity (parking, etc.)
    'fee',            # Fee required
    'access',         # Access restrictions
    'description',    # Description
})

# Amenity categories for grouping
AMENITY_CATEGORIES: dict = {
    'food_drink': FOOD_DRINK_AMENITIES,
    'shopping': SHOPPING_AMENITIES,
    'services': SERVICE_AMENITIES,
    'education': EDUCATION_AMENITIES,
    'transport': TRANSPORT_AMENITIES,
    'entertainment': ENTERTAINMENT_AMENITIES,
    'tourism': TOURISM_AMENITIES,
    'public': PUBLIC_AMENITIES,
    'emergency': EMERGENCY_AMENITIES,
    'civic': CIVIC_AMENITIES,
    'religious': RELIGIOUS_AMENITIES,
    'healthcare': HEALTHCARE_AMENITIES,
}

# Highway categories for grouping
HIGHWAY_CATEGORIES: dict = {
    'major': MAJOR_HIGHWAY_TYPES,
    'local': LOCAL_HIGHWAY_TYPES,
    'pedestrian': PEDESTRIAN_HIGHWAY_TYPES,
    'special': SPECIAL_HIGHWAY_TYPES
}

# Building categories for grouping
BUILDING_CATEGORIES: dict = {
    'residential': RESIDENTIAL_BUILDING_TYPES,
    'commercial': COMMERCIAL_BUILDING_TYPES,
    'public': PUBLIC_BUILDING_TYPES,
    'religious': RELIGIOUS_BUILDING_TYPES,
    'other': OTHER_BUILDING_TYPES
}

# =============================================================================
# TRAFFIC SAFETY CATEGORIES
# =============================================================================

# Traffic control point features (highway=*)
TRAFFIC_CONTROL_TYPES: FrozenSet[str] = frozenset({
    'traffic_signals', 'give_way', 'stop', 'speed_camera',
    'toll_gantry', 'motorway_junction', 'crossing', 'street_lamp'
})

# Traffic calming features (traffic_calming=*)
TRAFFIC_CALMING_TYPES: FrozenSet[str] = frozenset({
    'table', 'hump', 'bump', 'island', 'cushion', 'choker', 'chicane',
    'rumble_strip', 'dip', 'mini_bumps', 'pinch', 'yes'
})

# Crossing types (crossing=*)
CROSSING_TYPES: FrozenSet[str] = frozenset({
    'traffic_signals', 'zebra', 'uncontrolled', 'marked', 'unmarked',
    'island', 'pelican', 'toucan', 'pegasus', 'informal', 'no'
})

# Safety barrier types (barrier=*)
SAFETY_BARRIER_TYPES: FrozenSet[str] = frozenset({
    'bollard', 'guard_rail', 'jersey_barrier', 'block', 'chain',
    'height_restrictor', 'cycle_barrier', 'lift_gate', 'swing_gate'
})

# Emergency/safety features (emergency=*)
EMERGENCY_FEATURE_TYPES: FrozenSet[str] = frozenset({
    'phone', 'defibrillator', 'fire_hydrant', 'life_ring',
    'lifeguard', 'fire_hose', 'fire_extinguisher', 'water_tank'
})

# Surveillance types (man_made=surveillance)
SURVEILLANCE_ZONES: FrozenSet[str] = frozenset({
    'traffic', 'parking', 'area', 'entrance', 'public'
})

# Core traffic safety attributes for focused export
TRAFFIC_SAFETY_ATTRIBUTES: FrozenSet[str] = frozenset({
    'name',               # Feature name
    'ref',                # Reference number
    'direction',          # Direction of application
    'maxspeed',           # Associated speed limit
    'crossing',           # Crossing type
    'crossing:markings',  # Marking type (zebra, lines, etc.)
    'crossing:signals',   # Has signals
    'crossing:island',    # Has refuge island
    'traffic_calming',    # Calming type
    'traffic_signals',    # Signal type
    'traffic_signals:sound',      # Audible signals
    'traffic_signals:vibration',  # Tactile signals
    'button_operated',    # Pedestrian button
    'supervised',         # Supervised crossing
    'tactile_paving',     # Tactile paving present
    'lit',                # Illuminated
    'flashing',           # Flashing lights
    'school_zone',        # In school zone
    'operator',           # Operator/owner
    'surveillance:type',  # Camera type
    'surveillance:zone',  # What is monitored
    'camera:type',        # Camera type
    'description',        # Description
})

# Traffic safety categories for grouping
TRAFFIC_SAFETY_CATEGORIES: dict = {
    'traffic_signals': frozenset({'traffic_signals'}),
    'crossings': frozenset({'crossing'}),
    'stop_give_way': frozenset({'stop', 'give_way'}),
    'speed_cameras': frozenset({'speed_camera'}),
    'street_lamps': frozenset({'street_lamp'}),
    'traffic_calming': TRAFFIC_CALMING_TYPES,
    'safety_barriers': SAFETY_BARRIER_TYPES,
    'emergency_features': EMERGENCY_FEATURE_TYPES,
}

# =============================================================================
# CYCLING INFRASTRUCTURE CATEGORIES
# =============================================================================

# Cycling road types (highway=*)
CYCLING_HIGHWAY_TYPES: FrozenSet[str] = frozenset({
    'cycleway', 'path', 'bridleway'
})

# Cycleway types on roads (cycleway=*)
CYCLEWAY_TYPES: FrozenSet[str] = frozenset({
    'lane', 'track', 'shared_lane', 'share_busway', 'shared',
    'shoulder', 'separate', 'crossing'
})

# Bicycle access values (bicycle=*)
BICYCLE_ACCESS_TYPES: FrozenSet[str] = frozenset({
    'designated', 'yes', 'permissive', 'destination'
})

# Cycling amenities (amenity=*)
CYCLING_AMENITY_TYPES: FrozenSet[str] = frozenset({
    'bicycle_parking', 'bicycle_rental', 'bicycle_repair_station'
})

# Cycling shops (shop=*)
CYCLING_SHOP_TYPES: FrozenSet[str] = frozenset({
    'bicycle'
})

# Cycling infrastructure attributes for focused export
CYCLING_ATTRIBUTES: FrozenSet[str] = frozenset({
    'name',               # Feature name
    'ref',                # Route reference
    'bicycle',            # Bicycle access
    'cycleway',           # Cycleway type
    'cycleway:left',      # Left side cycleway
    'cycleway:right',     # Right side cycleway
    'cycleway:both',      # Both sides cycleway
    'cycleway:lane',      # Lane type
    'cycleway:width',     # Cycleway width
    'cycleway:surface',   # Cycleway surface
    'segregated',         # Segregated from pedestrians
    'oneway:bicycle',     # Bicycle one-way
    'surface',            # Road/path surface
    'smoothness',         # Surface smoothness
    'width',              # Path width
    'lit',                # Lighting
    'incline',            # Slope/grade
    'mtb:scale',          # Mountain bike difficulty
    'network',            # Cycle network
    'route',              # Route type
    'operator',           # Operator
    'capacity',           # Parking capacity
    'covered',            # Covered parking
    'fee',                # Fee required
    'access',             # Access restrictions
})

# Cycling categories for grouping
CYCLING_CATEGORIES: dict = {
    'cycleways': CYCLING_HIGHWAY_TYPES,
    'cycleway_lanes': CYCLEWAY_TYPES,
    'bicycle_access': BICYCLE_ACCESS_TYPES,
    'cycling_amenities': CYCLING_AMENITY_TYPES,
    'bicycle_shops': CYCLING_SHOP_TYPES,
}

# =============================================================================
# ROAD HIERARCHY AND INFRASTRUCTURE OVERLAYS
# =============================================================================

# Road hierarchy levels (1=highest priority, 5=lowest)
# Level 1: Freeways/Expressways - high speed, limited access
ROAD_LEVEL_1: FrozenSet[str] = frozenset({
    'motorway', 'motorway_link'
})

# Level 2: Major arterials - high capacity, through traffic
ROAD_LEVEL_2: FrozenSet[str] = frozenset({
    'trunk', 'trunk_link', 'primary', 'primary_link'
})

# Level 3: Minor arterials and collectors
ROAD_LEVEL_3: FrozenSet[str] = frozenset({
    'secondary', 'secondary_link', 'tertiary', 'tertiary_link'
})

# Level 4: Local roads - neighborhood access
ROAD_LEVEL_4: FrozenSet[str] = frozenset({
    'residential', 'unclassified', 'living_street'
})

# Level 5: Service and access roads
ROAD_LEVEL_5: FrozenSet[str] = frozenset({
    'service', 'track', 'road'
})

# Level 6: Non-motorized paths
ROAD_LEVEL_6: FrozenSet[str] = frozenset({
    'pedestrian', 'footway', 'cycleway', 'path', 'steps', 'bridleway'
})

# Combined road levels dictionary for easy lookup
ROAD_LEVELS: dict = {
    1: ROAD_LEVEL_1,
    2: ROAD_LEVEL_2,
    3: ROAD_LEVEL_3,
    4: ROAD_LEVEL_4,
    5: ROAD_LEVEL_5,
    6: ROAD_LEVEL_6,
}

# Named road level presets
ROAD_LEVEL_PRESETS: dict = {
    'motorway': ROAD_LEVEL_1,
    'arterial': ROAD_LEVEL_1 | ROAD_LEVEL_2,
    'main': ROAD_LEVEL_1 | ROAD_LEVEL_2 | ROAD_LEVEL_3,
    'driveable': ROAD_LEVEL_1 | ROAD_LEVEL_2 | ROAD_LEVEL_3 | ROAD_LEVEL_4 | ROAD_LEVEL_5,
    'all': ROAD_LEVEL_1 | ROAD_LEVEL_2 | ROAD_LEVEL_3 | ROAD_LEVEL_4 | ROAD_LEVEL_5 | ROAD_LEVEL_6,
}

# =============================================================================
# INFRASTRUCTURE OVERLAY TYPES (bridge, tunnel, ford, etc.)
# =============================================================================

# Bridge types (bridge=*)
BRIDGE_TYPES: FrozenSet[str] = frozenset({
    'yes', 'viaduct', 'aqueduct', 'cantilever', 'covered', 'movable',
    'trestle', 'suspension', 'simple', 'arch', 'boardwalk', 'low_water_crossing'
})

# Tunnel types (tunnel=*)
TUNNEL_TYPES: FrozenSet[str] = frozenset({
    'yes', 'culvert', 'building_passage', 'covered', 'avalanche_protector'
})

# Ford types (ford=*)
FORD_TYPES: FrozenSet[str] = frozenset({
    'yes', 'stepping_stones', 'boat'
})

# Embankment/cutting (embankment=yes, cutting=yes)
EMBANKMENT_TYPES: FrozenSet[str] = frozenset({
    'yes'
})

# Covered ways (covered=*)
COVERED_TYPES: FrozenSet[str] = frozenset({
    'yes', 'arcade', 'colonnade', 'pergola'
})

# Infrastructure overlay attributes for export
INFRASTRUCTURE_ATTRIBUTES: FrozenSet[str] = frozenset({
    'bridge',             # Bridge indicator
    'bridge:name',        # Bridge name
    'bridge:structure',   # Structure type
    'bridge:movable',     # Movable bridge type
    'tunnel',             # Tunnel indicator
    'tunnel:name',        # Tunnel name
    'ford',               # Ford indicator
    'embankment',         # On embankment
    'cutting',            # In cutting
    'covered',            # Covered way
    'layer',              # Vertical layer (-5 to +5)
    'level',              # Level for indoor mapping
    'location',           # underground, overground, etc.
    'man_made',           # For piers, bridges, etc.
})

# Infrastructure categories for filtering
INFRASTRUCTURE_CATEGORIES: dict = {
    'bridges': BRIDGE_TYPES,
    'tunnels': TUNNEL_TYPES,
    'fords': FORD_TYPES,
    'embankments': EMBANKMENT_TYPES,
    'covered': COVERED_TYPES,
}

# =============================================================================
# COMBINED NETWORK ATTRIBUTES (for comprehensive extraction)
# =============================================================================

# All network attributes for full extraction
NETWORK_ATTRIBUTES: FrozenSet[str] = (
    ROAD_ATTRIBUTES |
    INFRASTRUCTURE_ATTRIBUTES |
    ROAD_GEOMETRY_FIELDS |
    frozenset({
        'junction',           # Roundabout, circular, etc.
        'turn:lanes',         # Turn lane configuration
        'destination',        # Destination signage
        'destination:ref',    # Destination route refs
        'destination:symbol', # Destination symbols
        'hazard',             # Road hazard
        'overtaking',         # Overtaking rules
        'passing_places',     # Passing places on single track
        'smoothness',         # Surface condition
        'tracktype',          # Track grade (grade1-5)
        'incline',            # Road gradient
        'ford',               # Ford present
        'mountain_pass',      # Mountain pass
    })
)
