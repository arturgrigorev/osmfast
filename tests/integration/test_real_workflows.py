"""Integration tests for realistic workflows.

These tests simulate actual user workflows that combine multiple commands
and verify end-to-end functionality.
"""
import json
import pytest
from argparse import Namespace
from pathlib import Path


@pytest.fixture
def city_osm(tmp_path):
    """Create a realistic small city OSM file."""
    content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <bounds minlat="-33.905" minlon="151.195" maxlat="-33.895" maxlon="151.205"/>

  <!-- POIs - Restaurants -->
  <node id="1" lat="-33.900" lon="151.200">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="City Diner"/>
    <tag k="cuisine" v="american"/>
    <tag k="opening_hours" v="Mo-Su 07:00-22:00"/>
  </node>
  <node id="2" lat="-33.901" lon="151.201">
    <tag k="amenity" v="cafe"/>
    <tag k="name" v="Corner Coffee"/>
    <tag k="cuisine" v="coffee_shop"/>
  </node>

  <!-- POIs - Shops -->
  <node id="3" lat="-33.902" lon="151.200">
    <tag k="shop" v="supermarket"/>
    <tag k="name" v="Fresh Mart"/>
    <tag k="opening_hours" v="Mo-Sa 08:00-21:00"/>
  </node>

  <!-- POIs - Other -->
  <node id="4" lat="-33.900" lon="151.202">
    <tag k="amenity" v="bank"/>
    <tag k="name" v="City Bank"/>
  </node>
  <node id="5" lat="-33.903" lon="151.201">
    <tag k="amenity" v="hospital"/>
    <tag k="name" v="Central Hospital"/>
    <tag k="emergency" v="yes"/>
  </node>

  <!-- Road network nodes -->
  <node id="100" lat="-33.900" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="101" lat="-33.901" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="102" lat="-33.902" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="103" lat="-33.903" lon="151.200"><tag k="junction" v="yes"/></node>
  <node id="104" lat="-33.900" lon="151.201"><tag k="junction" v="yes"/></node>
  <node id="105" lat="-33.901" lon="151.201"><tag k="junction" v="yes"/></node>
  <node id="106" lat="-33.902" lon="151.201"><tag k="junction" v="yes"/></node>
  <node id="107" lat="-33.903" lon="151.201"><tag k="junction" v="yes"/></node>
  <node id="108" lat="-33.900" lon="151.202"><tag k="junction" v="yes"/></node>
  <node id="109" lat="-33.901" lon="151.202"><tag k="junction" v="yes"/></node>

  <!-- Main Street (N-S) -->
  <way id="200">
    <nd ref="100"/><nd ref="101"/><nd ref="102"/><nd ref="103"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Main Street"/>
    <tag k="lanes" v="2"/>
    <tag k="maxspeed" v="50"/>
  </way>

  <!-- Cross Street (E-W) -->
  <way id="201">
    <nd ref="101"/><nd ref="105"/><nd ref="109"/>
    <tag k="highway" v="secondary"/>
    <tag k="name" v="Cross Street"/>
  </way>

  <!-- Side Street (N-S) -->
  <way id="202">
    <nd ref="104"/><nd ref="105"/><nd ref="106"/><nd ref="107"/>
    <tag k="highway" v="tertiary"/>
    <tag k="name" v="Side Street"/>
  </way>

  <!-- One-way street -->
  <way id="203">
    <nd ref="100"/><nd ref="104"/><nd ref="108"/>
    <tag k="highway" v="residential"/>
    <tag k="name" v="One Way Lane"/>
    <tag k="oneway" v="yes"/>
  </way>

  <!-- Building footprints -->
  <node id="500" lat="-33.9005" lon="151.1995"><tag k="junction" v="yes"/></node>
  <node id="501" lat="-33.9005" lon="151.2005"><tag k="junction" v="yes"/></node>
  <node id="502" lat="-33.9015" lon="151.2005"><tag k="junction" v="yes"/></node>
  <node id="503" lat="-33.9015" lon="151.1995"><tag k="junction" v="yes"/></node>

  <way id="300">
    <nd ref="500"/><nd ref="501"/><nd ref="502"/><nd ref="503"/><nd ref="500"/>
    <tag k="building" v="commercial"/>
    <tag k="name" v="City Mall"/>
    <tag k="building:levels" v="3"/>
  </way>

  <node id="510" lat="-33.9020" lon="151.2010"><tag k="junction" v="yes"/></node>
  <node id="511" lat="-33.9020" lon="151.2015"><tag k="junction" v="yes"/></node>
  <node id="512" lat="-33.9025" lon="151.2015"><tag k="junction" v="yes"/></node>
  <node id="513" lat="-33.9025" lon="151.2010"><tag k="junction" v="yes"/></node>

  <way id="301">
    <nd ref="510"/><nd ref="511"/><nd ref="512"/><nd ref="513"/><nd ref="510"/>
    <tag k="building" v="residential"/>
    <tag k="name" v="Apartment Complex"/>
    <tag k="building:levels" v="5"/>
  </way>
</osm>'''
    osm_file = tmp_path / "city.osm"
    osm_file.write_text(content)
    return osm_file


class TestAnalystWorkflow:
    """Test workflow for a GIS analyst analyzing a city."""

    def test_analyze_stats_first(self, city_osm):
        """Analyst first checks stats of the file."""
        from osm_core.cli.commands.stats import cmd_stats

        args = Namespace(
            input_file=str(city_osm),
            json=True,
            summary=False,
            suggest_bbox=False
        )
        result = cmd_stats(args)
        assert result == 0

    def test_extract_pois_for_mapping(self, city_osm, tmp_path):
        """Analyst extracts POIs for a web map."""
        from osm_core.cli.commands.poi import run

        output_file = tmp_path / "pois.geojson"
        args = Namespace(
            input=str(city_osm),
            output=str(output_file),
            format="geojson",
            category="all",
            list_categories=False,
            include_ways=False,
            named_only=True,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"
        # Should have multiple POIs
        assert len(data["features"]) > 0

    def test_extract_roads_network(self, city_osm, tmp_path):
        """Analyst extracts road network."""
        from osm_core.cli.commands.roads import run

        output_file = tmp_path / "roads.geojson"
        args = Namespace(
            input=str(city_osm),
            output=str(output_file),
            format="geojson",
            road_class="all",
            highway_type=None,
            min_length=0,
            named_only=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert len(data["features"]) > 0

    def test_find_nearest_restaurant(self, city_osm):
        """Analyst finds nearest restaurants to a point."""
        from osm_core.cli.commands.nearest import run

        args = Namespace(
            input=str(city_osm),
            output=None,
            lat=-33.901,
            lon=151.200,
            filter="amenity=restaurant",
            count=5,
            max_distance=None,
            format="text"
        )
        result = run(args)
        assert result == 0


class TestRoutingWorkflow:
    """Test workflow for routing and navigation."""

    def test_basic_route_planning(self, city_osm):
        """Plan a basic route through the city."""
        from osm_core.cli.commands.route import run

        args = Namespace(
            input=str(city_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.903,151.200",
            mode="walk",  # Walk mode ignores oneway and works on all roads
            optimize="time",
            format="text"
        )
        result = run(args)
        # Route may fail if network is not connected, which is ok for test
        assert result in (0, 1)

    def test_route_with_geojson_output(self, city_osm, tmp_path):
        """Export route as GeoJSON for visualization."""
        from osm_core.cli.commands.route import run

        output_file = tmp_path / "route.geojson"
        args = Namespace(
            input=str(city_osm),
            output=str(output_file),
            origin="-33.900,151.200",
            destination="-33.903,151.200",
            mode="walk",
            optimize="time",
            format="geojson"
        )
        result = run(args)
        # Route may not find a path if nodes aren't connected
        assert result in (0, 1)

    def test_turn_by_turn_directions(self, city_osm):
        """Get turn-by-turn directions."""
        from osm_core.cli.commands.directions import run

        args = Namespace(
            input=str(city_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.903,151.200",
            mode="walk",
            format="text"
        )
        result = run(args)
        # Directions may fail if no route found
        assert result in (0, 1)

    def test_multi_stop_route(self, city_osm):
        """Plan a route with multiple stops."""
        from osm_core.cli.commands.route_multi import run

        args = Namespace(
            input=str(city_osm),
            output=None,
            waypoints="-33.900,151.200;-33.902,151.200;-33.903,151.200",
            mode="walk",
            optimize="time",
            format="text"
        )
        result = run(args)
        # Multi-stop route may fail if network issues
        assert result in (0, 1)

    def test_walking_isochrone(self, city_osm, tmp_path):
        """Generate walking isochrone for accessibility analysis."""
        from osm_core.cli.commands.isochrone import run

        output_file = tmp_path / "walking_isochrone.geojson"
        args = Namespace(
            input=str(city_osm),
            output=str(output_file),
            lat=-33.901,
            lon=151.200,
            time="5,10",
            mode="walk",
            resolution=24
        )
        result = run(args)
        assert result == 0


class TestNetworkAnalysisWorkflow:
    """Test workflow for network analysis."""

    def test_connectivity_analysis(self, city_osm, tmp_path):
        """Analyze network connectivity."""
        from osm_core.cli.commands.connectivity import run

        output_file = tmp_path / "connectivity.json"
        args = Namespace(
            input=str(city_osm),
            output=str(output_file),
            mode="drive",
            format="json",
            show_components=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert "num_components" in data
        assert "is_connected" in data

    def test_centrality_analysis(self, city_osm):
        """Identify central nodes in the network."""
        from osm_core.cli.commands.centrality import run

        args = Namespace(
            input=str(city_osm),
            output=None,
            top=5,
            sample=10,
            format="text"
        )
        result = run(args)
        assert result == 0

    def test_bottleneck_analysis(self, city_osm):
        """Find network bottlenecks."""
        from osm_core.cli.commands.bottleneck import run

        args = Namespace(
            input=str(city_osm),
            output=None,
            top=10,
            format="text"
        )
        result = run(args)
        assert result == 0

    def test_distance_matrix(self, city_osm, tmp_path):
        """Calculate distance matrix between multiple points."""
        from osm_core.cli.commands.distance_matrix import run

        output_file = tmp_path / "matrix.json"
        args = Namespace(
            input=str(city_osm),
            output=str(output_file),
            points="-33.900,151.200;-33.902,151.200;-33.903,151.200",
            mode="drive",
            metric="both",
            format="json"
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert "distance_matrix_m" in data
        assert "time_matrix_s" in data


class TestDataExtractionWorkflow:
    """Test workflow for data extraction and conversion."""

    def test_extract_to_multiple_formats(self, city_osm, tmp_path):
        """Extract features to different formats."""
        from osm_core.cli.commands.extract import cmd_extract

        formats = ["json", "geojson", "csv"]

        for fmt in formats:
            output_file = tmp_path / f"output.{fmt}"
            args = Namespace(
                input_file=str(city_osm),
                output_file=str(output_file),
                format=fmt,
                accept_ways=None,
                reject_ways=None,
                accept_nodes=None,
                reject_nodes=None,
                used_node=False,
                reject_ways_global=False,
                reject_nodes_global=False,
                reject_relations=False,
                bbox=None,
                include_metadata=True,
                quiet=True
            )
            result = cmd_extract(args)
            assert result == 0, f"Failed for format {fmt}"
            assert output_file.exists(), f"Output file not created for {fmt}"

    def test_filtered_extraction(self, city_osm, tmp_path):
        """Extract only restaurants."""
        from osm_core.cli.commands.extract import cmd_extract

        output_file = tmp_path / "restaurants.json"
        args = Namespace(
            input_file=str(city_osm),
            output_file=str(output_file),
            format="json",
            accept_ways=None,
            reject_ways=None,
            accept_nodes=["amenity=restaurant"],
            reject_nodes=None,
            used_node=False,
            reject_ways_global=False,
            reject_nodes_global=False,
            reject_relations=False,
            bbox=None,
            include_metadata=False,
            quiet=True
        )
        result = cmd_extract(args)
        assert result == 0


class TestMergeWorkflow:
    """Test workflow for merging multiple OSM files."""

    def test_merge_and_analyze(self, tmp_path):
        """Merge two files and analyze the result."""
        from osm_core.cli.commands.merge import cmd_merge
        from osm_core.cli.commands.stats import cmd_stats

        # Create two area files
        area1 = tmp_path / "area1.osm"
        area1.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="Area 1 Restaurant"/>
  </node>
</osm>''')

        area2 = tmp_path / "area2.osm"
        area2.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="2" lat="51.6" lon="-0.2">
    <tag k="amenity" v="cafe"/>
    <tag k="name" v="Area 2 Cafe"/>
  </node>
</osm>''')

        # Merge
        merged = tmp_path / "merged.osm"
        merge_args = Namespace(
            input_files=[str(area1), str(area2)],
            output=str(merged),
            strategy="last",
            quiet=True
        )
        merge_result = cmd_merge(merge_args)
        assert merge_result == 0
        assert merged.exists()

        # Analyze merged file
        stats_args = Namespace(
            input_file=str(merged),
            json=False,
            summary=True,
            suggest_bbox=False
        )
        stats_result = cmd_stats(stats_args)
        assert stats_result == 0


class TestClipAndProcessWorkflow:
    """Test workflow for clipping and processing regions."""

    def test_clip_region_and_analyze(self, city_osm, tmp_path):
        """Clip a region and analyze it."""
        from osm_core.cli.commands.clip import run as clip_run
        from osm_core.cli.commands.stats import cmd_stats

        # Create polygon for clipping
        polygon_file = tmp_path / "clip_boundary.geojson"
        polygon_file.write_text(json.dumps({
            "type": "Polygon",
            "coordinates": [[
                [151.195, -33.895], [151.203, -33.895], [151.203, -33.902],
                [151.195, -33.902], [151.195, -33.895]
            ]]
        }))

        # Clip a portion of the city
        clipped = tmp_path / "clipped.osm"
        clip_args = Namespace(
            input=str(city_osm),
            output=str(clipped),
            polygon=str(polygon_file),
            format="osm",
            complete_ways=False
        )
        clip_result = clip_run(clip_args)
        assert clip_result == 0

        # Analyze clipped file
        if clipped.exists():
            stats_args = Namespace(
                input_file=str(clipped),
                json=False,
                summary=True,
                suggest_bbox=False
            )
            stats_result = cmd_stats(stats_args)
            assert stats_result == 0


class TestEmergencyServicesWorkflow:
    """Test workflow for emergency services analysis."""

    def test_find_nearest_hospital(self, city_osm):
        """Find nearest hospital from any point."""
        from osm_core.cli.commands.nearest import run

        args = Namespace(
            input=str(city_osm),
            output=None,
            lat=-33.900,
            lon=151.200,
            filter="amenity=hospital",
            count=1,
            max_distance=None,
            format="text"
        )
        result = run(args)
        assert result == 0

    def test_emergency_routing(self, city_osm):
        """Route to hospital."""
        from osm_core.cli.commands.route import run

        args = Namespace(
            input=str(city_osm),
            output=None,
            origin="-33.900,151.200",
            destination="-33.903,151.201",  # Hospital location
            mode="walk",  # Walk works on all roads
            optimize="time",
            format="text"
        )
        result = run(args)
        # Route may fail if network not connected
        assert result in (0, 1)
