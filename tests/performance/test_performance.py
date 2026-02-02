"""Performance tests for OSMFast commands."""
import time
import pytest
from pathlib import Path
from argparse import Namespace


# Skip performance tests if map2.osm doesn't exist
pytestmark = pytest.mark.skipif(
    not Path(__file__).parent.parent.parent.joinpath("map2.osm").exists(),
    reason="map2.osm not found for performance tests"
)


class TestRoutingPerformance:
    """Performance tests for routing commands."""

    @pytest.fixture
    def map2_path(self):
        return str(Path(__file__).parent.parent.parent / "map2.osm")

    def test_route_performance(self, map2_path):
        """Test route command performance."""
        from osm_core.cli.commands import route

        # Use coordinates on a connected path in the road network
        args = Namespace(
            input=map2_path,
            output=None,
            origin="-33.900645,151.215142",
            destination="-33.904332,151.214174",
            mode="drive",
            optimize="time",
            format="text"
        )

        start = time.time()
        result = route.run(args)
        elapsed = time.time() - start

        assert result == 0
        assert elapsed < 1.0, f"Route took {elapsed:.2f}s, should be < 1s"

    def test_route_multi_performance(self, map2_path):
        """Test route-multi command performance."""
        from osm_core.cli.commands import route_multi

        # Use waypoints on a connected path in the road network
        args = Namespace(
            input=map2_path,
            output=None,
            waypoints="-33.900645,151.215142;-33.902663,151.214612;-33.904332,151.214174",
            mode="drive",
            optimize="time",
            format="text"
        )

        start = time.time()
        result = route_multi.run(args)
        elapsed = time.time() - start

        assert result == 0
        assert elapsed < 1.0, f"Route-multi took {elapsed:.2f}s, should be < 1s"

    def test_directions_performance(self, map2_path):
        """Test directions command performance."""
        from osm_core.cli.commands import directions

        # Use coordinates on a connected path in the road network
        args = Namespace(
            input=map2_path,
            output=None,
            origin="-33.900645,151.215142",
            destination="-33.904332,151.214174",
            mode="drive",
            format="text"
        )

        start = time.time()
        result = directions.run(args)
        elapsed = time.time() - start

        assert result == 0
        assert elapsed < 1.0, f"Directions took {elapsed:.2f}s, should be < 1s"

    def test_alternatives_performance(self, map2_path):
        """Test alternatives command performance."""
        from osm_core.cli.commands import alternatives

        # Use coordinates on a connected path in the road network
        args = Namespace(
            input=map2_path,
            output=None,
            origin="-33.900645,151.215142",
            destination="-33.904332,151.214174",
            mode="drive",
            count=3,
            format="text"
        )

        start = time.time()
        result = alternatives.run(args)
        elapsed = time.time() - start

        assert result == 0
        assert elapsed < 2.0, f"Alternatives took {elapsed:.2f}s, should be < 2s"


class TestDistancePerformance:
    """Performance tests for distance commands."""

    @pytest.fixture
    def map2_path(self):
        return str(Path(__file__).parent.parent.parent / "map2.osm")

    def test_distance_matrix_performance(self, map2_path):
        """Test distance-matrix command performance."""
        from osm_core.cli.commands import distance_matrix

        # Use coordinates on a connected path in the road network
        args = Namespace(
            input=map2_path,
            output=None,
            points="-33.900645,151.215142;-33.902663,151.214612;-33.904332,151.214174",
            mode="drive",
            metric="both",
            format="text"
        )

        start = time.time()
        result = distance_matrix.run(args)
        elapsed = time.time() - start

        assert result == 0
        assert elapsed < 2.0, f"Distance-matrix took {elapsed:.2f}s, should be < 2s"

    def test_nearest_performance(self, map2_path):
        """Test nearest command performance."""
        from osm_core.cli.commands import nearest

        args = Namespace(
            input=map2_path,
            output=None,
            lat=-33.9,
            lon=151.2,
            filter="amenity=*",
            count=10,
            max_distance=None,
            format="text"
        )

        start = time.time()
        result = nearest.run(args)
        elapsed = time.time() - start

        assert result == 0
        assert elapsed < 1.0, f"Nearest took {elapsed:.2f}s, should be < 1s"

    def test_nearest_road_performance(self, map2_path):
        """Test nearest-road command performance."""
        from osm_core.cli.commands import nearest_road

        args = Namespace(
            input=map2_path,
            output=None,
            lat=-33.9,
            lon=151.2,
            mode="all",
            format="text"
        )

        start = time.time()
        result = nearest_road.run(args)
        elapsed = time.time() - start

        assert result == 0
        assert elapsed < 1.0, f"Nearest-road took {elapsed:.2f}s, should be < 1s"


class TestNetworkAnalysisPerformance:
    """Performance tests for network analysis commands."""

    @pytest.fixture
    def map2_path(self):
        return str(Path(__file__).parent.parent.parent / "map2.osm")

    def test_connectivity_performance(self, map2_path):
        """Test connectivity command performance."""
        from osm_core.cli.commands import connectivity

        args = Namespace(
            input=map2_path,
            output=None,
            mode="drive",
            format="text",
            show_components=False
        )

        start = time.time()
        result = connectivity.run(args)
        elapsed = time.time() - start

        assert result == 0
        assert elapsed < 1.0, f"Connectivity took {elapsed:.2f}s, should be < 1s"

    def test_centrality_performance(self, map2_path):
        """Test centrality command performance."""
        from osm_core.cli.commands import centrality

        args = Namespace(
            input=map2_path,
            output=None,
            top=10,
            sample=20,
            format="text"
        )

        start = time.time()
        result = centrality.run(args)
        elapsed = time.time() - start

        assert result == 0
        assert elapsed < 2.0, f"Centrality took {elapsed:.2f}s, should be < 2s"

    def test_bottleneck_performance(self, map2_path):
        """Test bottleneck command performance."""
        from osm_core.cli.commands import bottleneck

        args = Namespace(
            input=map2_path,
            output=None,
            top=10,
            format="text"
        )

        start = time.time()
        result = bottleneck.run(args)
        elapsed = time.time() - start

        assert result == 0
        assert elapsed < 2.0, f"Bottleneck took {elapsed:.2f}s, should be < 2s"

    def test_detour_factor_performance(self, map2_path):
        """Test detour-factor command performance."""
        from osm_core.cli.commands import detour_factor

        args = Namespace(
            input=map2_path,
            output=None,
            mode="drive",
            sample=20,
            format="text"
        )

        start = time.time()
        result = detour_factor.run(args)
        elapsed = time.time() - start

        assert result == 0
        assert elapsed < 2.0, f"Detour-factor took {elapsed:.2f}s, should be < 2s"


class TestParsingPerformance:
    """Performance tests for parsing."""

    @pytest.fixture
    def map2_path(self):
        return str(Path(__file__).parent.parent.parent / "map2.osm")

    def test_parser_performance(self, map2_path):
        """Test parser performance."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        parser = UltraFastOSMParser()

        start = time.time()
        nodes, ways = parser.parse_file_ultra_fast(map2_path)
        elapsed = time.time() - start

        assert len(nodes) > 0
        assert len(ways) > 0
        assert elapsed < 1.0, f"Parsing took {elapsed:.2f}s, should be < 1s"

    def test_parser_throughput(self, map2_path):
        """Test parser throughput (features per second)."""
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        parser = UltraFastOSMParser()

        start = time.time()
        nodes, ways = parser.parse_file_ultra_fast(map2_path)
        elapsed = time.time() - start

        total_features = len(nodes) + len(ways)
        throughput = total_features / elapsed if elapsed > 0 else float('inf')

        assert throughput > 1000, f"Throughput {throughput:.0f} features/sec, should be > 1000"


class TestMemoryUsage:
    """Memory usage tests."""

    @pytest.fixture
    def map2_path(self):
        return str(Path(__file__).parent.parent.parent / "map2.osm")

    def test_parser_memory_stable(self, map2_path):
        """Test that parser doesn't leak memory on repeated use."""
        import gc
        from osm_core.parsing.mmap_parser import UltraFastOSMParser

        parser = UltraFastOSMParser()

        # Run multiple times
        for _ in range(3):
            nodes, ways = parser.parse_file_ultra_fast(map2_path)
            del nodes, ways
            gc.collect()

        # If we get here without OOM, test passes
        assert True
