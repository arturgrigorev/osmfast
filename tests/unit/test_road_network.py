"""Tests for road network extraction and infrastructure filtering."""
import pytest
import math
from typing import Set, Dict

from osm_core.filters.semantic_categories import (
    ROAD_LEVELS, ROAD_LEVEL_PRESETS, ROAD_LEVEL_1, ROAD_LEVEL_2, ROAD_LEVEL_3,
    ROAD_LEVEL_4, ROAD_LEVEL_5, ROAD_LEVEL_6,
    BRIDGE_TYPES, TUNNEL_TYPES, FORD_TYPES, EMBANKMENT_TYPES, COVERED_TYPES,
    INFRASTRUCTURE_CATEGORIES, INFRASTRUCTURE_ATTRIBUTES, NETWORK_ATTRIBUTES,
    DEFAULT_SPEEDS, ROAD_GEOMETRY_FIELDS,
    CYCLING_HIGHWAY_TYPES, CYCLEWAY_TYPES, BICYCLE_ACCESS_TYPES,
    CYCLING_AMENITY_TYPES, CYCLING_SHOP_TYPES, CYCLING_ATTRIBUTES,
    TRAFFIC_CONTROL_TYPES, TRAFFIC_CALMING_TYPES, CROSSING_TYPES,
    SAFETY_BARRIER_TYPES, EMERGENCY_FEATURE_TYPES, TRAFFIC_SAFETY_ATTRIBUTES
)
from osm_core.utils.geo_utils import (
    haversine_distance, calculate_line_length, calculate_sinuosity,
    calculate_bearing, calculate_line_bearing, calculate_line_midpoint
)


class TestRoadHierarchyLevels:
    """Tests for road hierarchy level definitions."""

    def test_road_level_1_contains_motorways(self):
        """Test level 1 contains motorway types."""
        assert 'motorway' in ROAD_LEVEL_1
        assert 'motorway_link' in ROAD_LEVEL_1
        assert len(ROAD_LEVEL_1) == 2

    def test_road_level_2_contains_arterials(self):
        """Test level 2 contains trunk and primary roads."""
        assert 'trunk' in ROAD_LEVEL_2
        assert 'trunk_link' in ROAD_LEVEL_2
        assert 'primary' in ROAD_LEVEL_2
        assert 'primary_link' in ROAD_LEVEL_2

    def test_road_level_3_contains_collectors(self):
        """Test level 3 contains secondary and tertiary roads."""
        assert 'secondary' in ROAD_LEVEL_3
        assert 'secondary_link' in ROAD_LEVEL_3
        assert 'tertiary' in ROAD_LEVEL_3
        assert 'tertiary_link' in ROAD_LEVEL_3

    def test_road_level_4_contains_local_roads(self):
        """Test level 4 contains local roads."""
        assert 'residential' in ROAD_LEVEL_4
        assert 'unclassified' in ROAD_LEVEL_4
        assert 'living_street' in ROAD_LEVEL_4

    def test_road_level_5_contains_service_roads(self):
        """Test level 5 contains service roads."""
        assert 'service' in ROAD_LEVEL_5
        assert 'track' in ROAD_LEVEL_5

    def test_road_level_6_contains_paths(self):
        """Test level 6 contains non-motorized paths."""
        assert 'pedestrian' in ROAD_LEVEL_6
        assert 'footway' in ROAD_LEVEL_6
        assert 'cycleway' in ROAD_LEVEL_6
        assert 'path' in ROAD_LEVEL_6
        assert 'steps' in ROAD_LEVEL_6

    def test_road_levels_dict_has_all_levels(self):
        """Test ROAD_LEVELS dict contains all 6 levels."""
        assert len(ROAD_LEVELS) == 6
        for level in range(1, 7):
            assert level in ROAD_LEVELS

    def test_road_level_presets_motorway(self):
        """Test motorway preset contains only level 1."""
        assert ROAD_LEVEL_PRESETS['motorway'] == ROAD_LEVEL_1

    def test_road_level_presets_arterial(self):
        """Test arterial preset contains levels 1-2."""
        expected = ROAD_LEVEL_1 | ROAD_LEVEL_2
        assert ROAD_LEVEL_PRESETS['arterial'] == expected

    def test_road_level_presets_main(self):
        """Test main preset contains levels 1-3."""
        expected = ROAD_LEVEL_1 | ROAD_LEVEL_2 | ROAD_LEVEL_3
        assert ROAD_LEVEL_PRESETS['main'] == expected

    def test_road_level_presets_all(self):
        """Test all preset contains all levels."""
        all_types = set()
        for level in range(1, 7):
            all_types.update(ROAD_LEVELS[level])
        assert ROAD_LEVEL_PRESETS['all'] == all_types


class TestInfrastructureTypes:
    """Tests for infrastructure type definitions."""

    def test_bridge_types_contains_common_values(self):
        """Test bridge types contain common values."""
        assert 'yes' in BRIDGE_TYPES
        assert 'viaduct' in BRIDGE_TYPES
        assert 'aqueduct' in BRIDGE_TYPES

    def test_tunnel_types_contains_common_values(self):
        """Test tunnel types contain common values."""
        assert 'yes' in TUNNEL_TYPES
        assert 'culvert' in TUNNEL_TYPES
        assert 'building_passage' in TUNNEL_TYPES

    def test_ford_types_contains_common_values(self):
        """Test ford types contain common values."""
        assert 'yes' in FORD_TYPES
        assert 'stepping_stones' in FORD_TYPES

    def test_infrastructure_categories_mapping(self):
        """Test infrastructure categories mapping."""
        assert INFRASTRUCTURE_CATEGORIES['bridges'] == BRIDGE_TYPES
        assert INFRASTRUCTURE_CATEGORIES['tunnels'] == TUNNEL_TYPES
        assert INFRASTRUCTURE_CATEGORIES['fords'] == FORD_TYPES

    def test_infrastructure_attributes_contains_key_fields(self):
        """Test infrastructure attributes contain key fields."""
        assert 'bridge' in INFRASTRUCTURE_ATTRIBUTES
        assert 'tunnel' in INFRASTRUCTURE_ATTRIBUTES
        assert 'ford' in INFRASTRUCTURE_ATTRIBUTES
        assert 'layer' in INFRASTRUCTURE_ATTRIBUTES


class TestDefaultSpeeds:
    """Tests for default speed definitions."""

    def test_default_speeds_motorway(self):
        """Test motorway has highest default speed."""
        assert DEFAULT_SPEEDS['motorway'] == 110
        assert DEFAULT_SPEEDS['motorway_link'] == 80

    def test_default_speeds_residential(self):
        """Test residential has moderate speed."""
        assert DEFAULT_SPEEDS['residential'] == 40

    def test_default_speeds_footway(self):
        """Test footway has lowest speed."""
        assert DEFAULT_SPEEDS['footway'] == 5

    def test_default_speeds_cycleway(self):
        """Test cycleway speed."""
        assert DEFAULT_SPEEDS['cycleway'] == 20

    def test_all_road_levels_have_speeds(self):
        """Test all road types in levels have default speeds."""
        # Exceptions: types that don't have meaningful speeds
        exceptions = {'road', 'bridleway', 'steps'}
        for level in range(1, 7):
            for road_type in ROAD_LEVELS[level]:
                if road_type not in exceptions:
                    assert road_type in DEFAULT_SPEEDS, f"Missing speed for {road_type}"


class TestRoadGeometryFields:
    """Tests for road geometry field definitions."""

    def test_geometry_fields_contain_length(self):
        """Test geometry fields contain length measurements."""
        assert 'length_m' in ROAD_GEOMETRY_FIELDS
        assert 'length_km' in ROAD_GEOMETRY_FIELDS

    def test_geometry_fields_contain_sinuosity(self):
        """Test geometry fields contain sinuosity."""
        assert 'sinuosity' in ROAD_GEOMETRY_FIELDS

    def test_geometry_fields_contain_bearing(self):
        """Test geometry fields contain bearing."""
        assert 'bearing' in ROAD_GEOMETRY_FIELDS

    def test_geometry_fields_contain_travel_time(self):
        """Test geometry fields contain travel time."""
        assert 'travel_min' in ROAD_GEOMETRY_FIELDS
        assert 'speed_kph' in ROAD_GEOMETRY_FIELDS

    def test_geometry_fields_contain_lane_metrics(self):
        """Test geometry fields contain lane metrics."""
        assert 'lane_km' in ROAD_GEOMETRY_FIELDS

    def test_geometry_fields_contain_infrastructure_flags(self):
        """Test geometry fields contain infrastructure flags."""
        assert 'has_sidewalk' in ROAD_GEOMETRY_FIELDS
        assert 'is_lit' in ROAD_GEOMETRY_FIELDS
        assert 'is_oneway' in ROAD_GEOMETRY_FIELDS


class TestLineGeometryCalculations:
    """Tests for line geometry calculation functions."""

    def test_haversine_distance_same_point(self):
        """Test haversine distance between same point is zero."""
        dist = haversine_distance(0, 0, 0, 0)
        assert dist == 0.0

    def test_haversine_distance_known_distance(self):
        """Test haversine distance for known coordinates."""
        # London to Paris is approximately 344 km
        lon1, lat1 = -0.1276, 51.5074  # London
        lon2, lat2 = 2.3522, 48.8566   # Paris
        dist = haversine_distance(lon1, lat1, lon2, lat2)
        # Should be approximately 344 km (344,000 m)
        assert 340000 < dist < 350000

    def test_calculate_line_length_empty(self):
        """Test line length of empty coordinates."""
        assert calculate_line_length([]) == 0.0

    def test_calculate_line_length_single_point(self):
        """Test line length of single point."""
        assert calculate_line_length([[0, 0]]) == 0.0

    def test_calculate_line_length_straight_line(self):
        """Test line length of straight line."""
        # ~1 degree at equator is about 111 km
        coords = [[0, 0], [1, 0]]
        length = calculate_line_length(coords)
        assert 110000 < length < 112000

    def test_calculate_line_length_multi_segment(self):
        """Test line length with multiple segments."""
        coords = [[0, 0], [1, 0], [1, 1]]
        length = calculate_line_length(coords)
        # Should be approximately 2 * 111 km
        assert 220000 < length < 224000

    def test_calculate_sinuosity_straight_line(self):
        """Test sinuosity of straight line is 1.0."""
        coords = [[0, 0], [1, 0], [2, 0]]
        sinuosity = calculate_sinuosity(coords)
        assert abs(sinuosity - 1.0) < 0.01

    def test_calculate_sinuosity_curved_line(self):
        """Test sinuosity of curved line is > 1.0."""
        # A line that goes around
        coords = [[0, 0], [1, 1], [2, 0]]
        sinuosity = calculate_sinuosity(coords)
        assert sinuosity > 1.0

    def test_calculate_sinuosity_insufficient_points(self):
        """Test sinuosity with insufficient points."""
        assert calculate_sinuosity([]) == 1.0
        assert calculate_sinuosity([[0, 0]]) == 1.0

    def test_calculate_bearing_north(self):
        """Test bearing pointing north is 0 degrees."""
        bearing = calculate_bearing(0, 0, 0, 1)
        assert abs(bearing - 0) < 1

    def test_calculate_bearing_east(self):
        """Test bearing pointing east is 90 degrees."""
        bearing = calculate_bearing(0, 0, 1, 0)
        assert abs(bearing - 90) < 1

    def test_calculate_bearing_south(self):
        """Test bearing pointing south is 180 degrees."""
        bearing = calculate_bearing(0, 1, 0, 0)
        assert abs(bearing - 180) < 1

    def test_calculate_bearing_west(self):
        """Test bearing pointing west is 270 degrees."""
        bearing = calculate_bearing(1, 0, 0, 0)
        assert abs(bearing - 270) < 1

    def test_calculate_line_bearing_from_start_to_end(self):
        """Test line bearing uses start and end points."""
        coords = [[0, 0], [0.5, 0.5], [1, 0]]  # Goes NE then SE
        bearing = calculate_line_bearing(coords)
        # Overall bearing should be east (90 degrees)
        assert abs(bearing - 90) < 5

    def test_calculate_line_midpoint(self):
        """Test line midpoint calculation."""
        coords = [[0, 0], [2, 0]]
        midpoint = calculate_line_midpoint(coords)
        assert abs(midpoint[0] - 1.0) < 0.01  # lon
        assert abs(midpoint[1] - 0.0) < 0.01  # lat


class TestCyclingInfrastructure:
    """Tests for cycling infrastructure category definitions."""

    def test_cycling_highway_types(self):
        """Test cycling highway types."""
        assert 'cycleway' in CYCLING_HIGHWAY_TYPES
        assert 'path' in CYCLING_HIGHWAY_TYPES

    def test_cycleway_types(self):
        """Test cycleway tag values."""
        assert 'lane' in CYCLEWAY_TYPES
        assert 'track' in CYCLEWAY_TYPES
        assert 'shared_lane' in CYCLEWAY_TYPES

    def test_bicycle_access_types(self):
        """Test bicycle access values."""
        assert 'designated' in BICYCLE_ACCESS_TYPES
        assert 'yes' in BICYCLE_ACCESS_TYPES
        assert 'permissive' in BICYCLE_ACCESS_TYPES

    def test_cycling_amenity_types(self):
        """Test cycling amenity types."""
        assert 'bicycle_parking' in CYCLING_AMENITY_TYPES
        assert 'bicycle_rental' in CYCLING_AMENITY_TYPES
        assert 'bicycle_repair_station' in CYCLING_AMENITY_TYPES

    def test_cycling_shop_types(self):
        """Test cycling shop types."""
        assert 'bicycle' in CYCLING_SHOP_TYPES

    def test_cycling_attributes_completeness(self):
        """Test cycling attributes contain key fields."""
        assert 'bicycle' in CYCLING_ATTRIBUTES
        assert 'cycleway' in CYCLING_ATTRIBUTES
        assert 'segregated' in CYCLING_ATTRIBUTES
        assert 'surface' in CYCLING_ATTRIBUTES
        assert 'lit' in CYCLING_ATTRIBUTES


class TestTrafficSafetyCategories:
    """Tests for traffic safety category definitions."""

    def test_traffic_control_types(self):
        """Test traffic control types."""
        assert 'traffic_signals' in TRAFFIC_CONTROL_TYPES
        assert 'stop' in TRAFFIC_CONTROL_TYPES
        assert 'give_way' in TRAFFIC_CONTROL_TYPES
        assert 'crossing' in TRAFFIC_CONTROL_TYPES
        assert 'speed_camera' in TRAFFIC_CONTROL_TYPES

    def test_traffic_calming_types(self):
        """Test traffic calming types."""
        assert 'hump' in TRAFFIC_CALMING_TYPES
        assert 'bump' in TRAFFIC_CALMING_TYPES
        assert 'table' in TRAFFIC_CALMING_TYPES
        assert 'chicane' in TRAFFIC_CALMING_TYPES

    def test_crossing_types(self):
        """Test crossing types."""
        assert 'zebra' in CROSSING_TYPES
        assert 'traffic_signals' in CROSSING_TYPES
        assert 'marked' in CROSSING_TYPES
        assert 'uncontrolled' in CROSSING_TYPES

    def test_safety_barrier_types(self):
        """Test safety barrier types."""
        assert 'bollard' in SAFETY_BARRIER_TYPES
        assert 'guard_rail' in SAFETY_BARRIER_TYPES
        assert 'jersey_barrier' in SAFETY_BARRIER_TYPES

    def test_emergency_feature_types(self):
        """Test emergency feature types."""
        assert 'phone' in EMERGENCY_FEATURE_TYPES
        assert 'defibrillator' in EMERGENCY_FEATURE_TYPES
        assert 'fire_hydrant' in EMERGENCY_FEATURE_TYPES

    def test_traffic_safety_attributes_completeness(self):
        """Test traffic safety attributes contain key fields."""
        assert 'crossing' in TRAFFIC_SAFETY_ATTRIBUTES
        assert 'traffic_calming' in TRAFFIC_SAFETY_ATTRIBUTES
        assert 'lit' in TRAFFIC_SAFETY_ATTRIBUTES
        assert 'tactile_paving' in TRAFFIC_SAFETY_ATTRIBUTES


class TestNetworkAttributes:
    """Tests for combined network attribute definitions."""

    def test_network_attributes_includes_road_attributes(self):
        """Test network attributes include road attributes."""
        from osm_core.filters.semantic_categories import ROAD_ATTRIBUTES
        for attr in ROAD_ATTRIBUTES:
            assert attr in NETWORK_ATTRIBUTES

    def test_network_attributes_includes_infrastructure(self):
        """Test network attributes include infrastructure."""
        for attr in INFRASTRUCTURE_ATTRIBUTES:
            assert attr in NETWORK_ATTRIBUTES

    def test_network_attributes_includes_extra_fields(self):
        """Test network attributes include extra network fields."""
        assert 'junction' in NETWORK_ATTRIBUTES
        assert 'smoothness' in NETWORK_ATTRIBUTES
        assert 'incline' in NETWORK_ATTRIBUTES
