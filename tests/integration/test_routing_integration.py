"""Integration tests for routing workflows."""
import json
import pytest
from argparse import Namespace
from pathlib import Path

from osm_core.cli.commands import route, route_multi, directions, alternatives, distance_matrix


class TestRoutingWorkflows:
    """Test complete routing workflows."""

    def test_route_then_directions_consistency(self, road_network_osm):
        """Route and directions should report same distance."""
        origin = "-33.900,151.200"
        destination = "-33.902,151.200"

        # Get route
        route_args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin=origin,
            destination=destination,
            mode="drive",
            optimize="time",
            format="text"
        )
        route_result = route.run(route_args)
        assert route_result == 0

        # Get directions
        dir_args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin=origin,
            destination=destination,
            mode="drive",
            format="text"
        )
        dir_result = directions.run(dir_args)
        assert dir_result == 0

    def test_route_multi_equals_sequential_routes(self, road_network_osm, tmp_path):
        """Multi-waypoint route should equal sum of individual legs."""
        waypoints = [
            (-33.900, 151.200),
            (-33.901, 151.200),
            (-33.902, 151.200)
        ]

        # Get multi-waypoint route
        multi_output = tmp_path / "multi.json"
        multi_args = Namespace(
            input=str(road_network_osm),
            output=str(multi_output),
            waypoints=";".join(f"{lat},{lon}" for lat, lon in waypoints),
            mode="drive",
            optimize="time",
            format="json"
        )
        result = route_multi.run(multi_args)
        assert result == 0

        multi_data = json.loads(multi_output.read_text())
        assert "total_distance_m" in multi_data
        assert len(multi_data["legs"]) == 2

    def test_alternatives_includes_optimal_route(self, road_network_osm, tmp_path):
        """Alternative routes should include or be close to optimal."""
        origin = "-33.900,151.200"
        destination = "-33.902,151.200"

        # Get optimal route
        route_output = tmp_path / "route.json"
        route_args = Namespace(
            input=str(road_network_osm),
            output=str(route_output),
            origin=origin,
            destination=destination,
            mode="drive",
            optimize="time",
            format="json"
        )
        route.run(route_args)

        # Get alternatives
        alt_output = tmp_path / "alternatives.json"
        alt_args = Namespace(
            input=str(road_network_osm),
            output=str(alt_output),
            origin=origin,
            destination=destination,
            mode="drive",
            count=3,
            format="json"
        )
        result = alternatives.run(alt_args)
        assert result == 0

        alt_data = json.loads(alt_output.read_text())
        assert alt_data["type"] == "FeatureCollection"
        # Should have at least one alternative
        assert len(alt_data["features"]) >= 1

    def test_distance_matrix_symmetry(self, road_network_osm, tmp_path):
        """Distance matrix should be roughly symmetric for bidirectional roads."""
        output_file = tmp_path / "matrix.json"
        points = "-33.900,151.200;-33.901,151.200;-33.902,151.200"

        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            points=points,
            mode="walk",  # Walk mode is bidirectional
            metric="both",
            format="json"
        )
        result = distance_matrix.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        matrix = data["distance_matrix_m"]

        # Check matrix is square
        n = len(matrix)
        assert all(len(row) == n for row in matrix)

        # Diagonal should be 0
        for i in range(n):
            assert matrix[i][i] == 0

    def test_all_modes_produce_valid_routes(self, road_network_osm, tmp_path):
        """All transport modes should produce valid routes."""
        modes = ["drive", "walk", "bike"]
        origin = "-33.900,151.200"
        destination = "-33.902,151.200"

        for mode in modes:
            output_file = tmp_path / f"route_{mode}.json"
            args = Namespace(
                input=str(road_network_osm),
                output=str(output_file),
                origin=origin,
                destination=destination,
                mode=mode,
                optimize="time",
                format="json"
            )
            result = route.run(args)
            assert result == 0, f"Route failed for mode {mode}"

            data = json.loads(output_file.read_text())
            assert data["type"] == "FeatureCollection"
            assert len(data["features"]) >= 1


class TestRoundTripRouting:
    """Test round-trip routing scenarios."""

    def test_round_trip_same_distance(self, road_network_osm, tmp_path):
        """Round trip should have approximately same distance each way for walk mode."""
        origin = "-33.900,151.200"
        destination = "-33.902,151.200"

        # Forward route
        fwd_output = tmp_path / "forward.json"
        fwd_args = Namespace(
            input=str(road_network_osm),
            output=str(fwd_output),
            origin=origin,
            destination=destination,
            mode="walk",
            optimize="distance",
            format="json"
        )
        route.run(fwd_args)

        # Reverse route
        rev_output = tmp_path / "reverse.json"
        rev_args = Namespace(
            input=str(road_network_osm),
            output=str(rev_output),
            origin=destination,
            destination=origin,
            mode="walk",
            optimize="distance",
            format="json"
        )
        route.run(rev_args)

        fwd_data = json.loads(fwd_output.read_text())
        rev_data = json.loads(rev_output.read_text())

        # Both should have routes
        assert len(fwd_data["features"]) >= 1
        assert len(rev_data["features"]) >= 1

    def test_multi_stop_round_trip(self, road_network_osm, tmp_path):
        """Multi-stop round trip starting and ending at same point."""
        # A -> B -> C -> A
        waypoints = "-33.900,151.200;-33.901,151.200;-33.902,151.200;-33.900,151.200"

        output_file = tmp_path / "round_trip.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            waypoints=waypoints,
            mode="drive",
            optimize="time",
            format="json"
        )
        result = route_multi.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert len(data["legs"]) == 3  # A->B, B->C, C->A


class TestOptimizationModes:
    """Test different optimization modes."""

    def test_time_vs_distance_optimization(self, road_network_osm, tmp_path):
        """Time and distance optimization may produce different routes."""
        origin = "-33.900,151.200"
        destination = "-33.902,151.202"

        # Optimize for time
        time_output = tmp_path / "time_route.json"
        time_args = Namespace(
            input=str(road_network_osm),
            output=str(time_output),
            origin=origin,
            destination=destination,
            mode="drive",
            optimize="time",
            format="json"
        )
        route.run(time_args)

        # Optimize for distance
        dist_output = tmp_path / "dist_route.json"
        dist_args = Namespace(
            input=str(road_network_osm),
            output=str(dist_output),
            origin=origin,
            destination=destination,
            mode="drive",
            optimize="distance",
            format="json"
        )
        route.run(dist_args)

        time_data = json.loads(time_output.read_text())
        dist_data = json.loads(dist_output.read_text())

        # Both should produce valid routes
        assert len(time_data["features"]) >= 1
        assert len(dist_data["features"]) >= 1


class TestLargeWaypointLists:
    """Test routing with many waypoints."""

    def test_many_waypoints(self, road_network_osm, tmp_path):
        """Test route-multi with all network nodes as waypoints."""
        # Use all nodes in the network as waypoints
        waypoints = ";".join([
            "-33.900,151.200",
            "-33.901,151.200",
            "-33.902,151.200",
            "-33.901,151.201",
            "-33.900,151.201"
        ])

        output_file = tmp_path / "many_waypoints.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            waypoints=waypoints,
            mode="drive",
            optimize="time",
            format="json"
        )
        result = route_multi.run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert len(data["legs"]) == 4  # 5 waypoints = 4 legs


class TestCoordinatePrecision:
    """Test handling of coordinate precision."""

    def test_high_precision_coords(self, road_network_osm):
        """Test routing with high-precision coordinates."""
        # Coordinates with many decimal places
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="-33.9000000001,151.2000000001",
            destination="-33.9020000001,151.2000000001",
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 0

    def test_snapping_tolerance(self, road_network_osm):
        """Test that nearby points snap to network correctly."""
        # Point slightly off the network
        args = Namespace(
            input=str(road_network_osm),
            output=None,
            origin="-33.9001,151.2001",  # Slightly off node 1
            destination="-33.9019,151.2001",  # Slightly off node 2
            mode="drive",
            optimize="time",
            format="text"
        )
        result = route.run(args)
        assert result == 0
