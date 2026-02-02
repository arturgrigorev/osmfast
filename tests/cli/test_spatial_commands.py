"""Tests for spatial CLI commands: nearest, poi, buildings, roads, isochrone."""
import json
import pytest
from argparse import Namespace
from pathlib import Path


class TestNearestCommand:
    """Tests for nearest command."""

    def test_nearest_basic(self, road_network_osm):
        """Test basic nearest feature search."""
        from osm_core.cli.commands.nearest import run

        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.900,
            lon=151.200,
            filter="amenity=*",
            count=5,
            max_distance=None,
            format="text"
        )
        result = run(args)
        assert result == 0

    def test_nearest_json_output(self, road_network_osm, tmp_path):
        """Test nearest with JSON output to file."""
        from osm_core.cli.commands.nearest import run

        output_file = tmp_path / "nearest.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            lat=-33.901,
            lon=151.202,
            filter="amenity=restaurant",
            count=5,
            max_distance=None,
            format="json"
        )
        result = run(args)
        assert result == 0
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        # When output file is specified, command writes GeoJSON format
        assert data["type"] == "FeatureCollection"
        assert "features" in data

    def test_nearest_geojson_output(self, road_network_osm, tmp_path):
        """Test nearest with GeoJSON output."""
        from osm_core.cli.commands.nearest import run

        output_file = tmp_path / "nearest.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            lat=-33.901,
            lon=151.202,
            filter="amenity=*",
            count=3,
            max_distance=None,
            format="geojson"
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"
        # Should have search point feature
        search_point = [f for f in data["features"] if f["properties"].get("type") == "search_point"]
        assert len(search_point) == 1

    def test_nearest_with_max_distance(self, road_network_osm):
        """Test nearest with maximum distance filter."""
        from osm_core.cli.commands.nearest import run

        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.900,
            lon=151.200,
            filter="shop=*",
            count=10,
            max_distance=50,  # 50 meters
            format="text"
        )
        result = run(args)
        assert result == 0

    def test_nearest_wildcard_filter(self, road_network_osm):
        """Test nearest with wildcard filter."""
        from osm_core.cli.commands.nearest import run

        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.900,
            lon=151.200,
            filter="name=*",
            count=5,
            max_distance=None,
            format="text"
        )
        result = run(args)
        assert result == 0

    def test_nearest_missing_file(self, tmp_path):
        """Test nearest with missing file."""
        from osm_core.cli.commands.nearest import run

        args = Namespace(
            input=str(tmp_path / "nonexistent.osm"),
            output=None,
            lat=-33.900,
            lon=151.200,
            filter="amenity=*",
            count=5,
            max_distance=None,
            format="text"
        )
        result = run(args)
        assert result == 1

    def test_nearest_no_matches(self, road_network_osm):
        """Test nearest when no matches found."""
        from osm_core.cli.commands.nearest import run

        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.900,
            lon=151.200,
            filter="nonexistent_tag=value",
            count=5,
            max_distance=None,
            format="text"
        )
        result = run(args)
        assert result == 0  # Should succeed with empty results


class TestNearestRoadCommand:
    """Tests for nearest-road command."""

    def test_nearest_road_basic(self, road_network_osm):
        """Test basic nearest road search."""
        from osm_core.cli.commands.nearest_road import run

        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.901,
            lon=151.2005,
            mode="drive",
            format="text"
        )
        result = run(args)
        assert result == 0

    def test_nearest_road_walk_mode(self, road_network_osm):
        """Test nearest road for walking."""
        from osm_core.cli.commands.nearest_road import run

        args = Namespace(
            input=str(road_network_osm),
            output=None,
            lat=-33.901,
            lon=151.200,
            mode="walk",
            format="text"
        )
        result = run(args)
        assert result == 0

    def test_nearest_road_json(self, road_network_osm, tmp_path):
        """Test nearest road with JSON output."""
        from osm_core.cli.commands.nearest_road import run

        output_file = tmp_path / "nearest_road.json"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            lat=-33.901,
            lon=151.200,
            mode="drive",
            format="json"
        )
        result = run(args)
        assert result == 0
        assert output_file.exists()


class TestPOICommand:
    """Tests for poi command."""

    def test_poi_list_categories(self, capsys):
        """Test listing POI categories."""
        from osm_core.cli.commands.poi import run

        args = Namespace(
            input="dummy.osm",  # Not used when listing
            output=None,
            format="geojson",
            category="all",
            list_categories=True,
            include_ways=False,
            named_only=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "food" in captured.out
        assert "shop" in captured.out
        assert "health" in captured.out

    def test_poi_extract_all(self, small_osm_file, tmp_path):
        """Test extracting all POIs."""
        from osm_core.cli.commands.poi import run

        output_file = tmp_path / "pois.geojson"
        args = Namespace(
            input=str(small_osm_file),
            output=str(output_file),
            format="geojson",
            category="all",
            list_categories=False,
            include_ways=False,
            named_only=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"

    def test_poi_extract_food_category(self, tmp_path):
        """Test extracting food POIs only."""
        from osm_core.cli.commands.poi import run

        # Create OSM with food POIs
        osm_file = tmp_path / "food.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="Pizza Place"/>
  </node>
  <node id="2" lat="51.51" lon="-0.11">
    <tag k="amenity" v="cafe"/>
    <tag k="name" v="Coffee Shop"/>
  </node>
  <node id="3" lat="51.52" lon="-0.12">
    <tag k="amenity" v="bank"/>
    <tag k="name" v="Money Bank"/>
  </node>
</osm>''')

        output_file = tmp_path / "food_pois.geojson"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            format="geojson",
            category="food",
            list_categories=False,
            include_ways=False,
            named_only=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Should have restaurant and cafe but not bank
        categories = [f["properties"]["category"] for f in data["features"]]
        assert all(cat == "food" for cat in categories)

    def test_poi_stats_mode(self, small_osm_file, capsys):
        """Test POI statistics mode."""
        from osm_core.cli.commands.poi import run

        args = Namespace(
            input=str(small_osm_file),
            output=None,
            format="geojson",
            category="all",
            list_categories=False,
            include_ways=False,
            named_only=False,
            stats=True
        )
        result = run(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "POI Statistics" in captured.out

    def test_poi_named_only(self, tmp_path):
        """Test extracting only named POIs."""
        from osm_core.cli.commands.poi import run

        osm_file = tmp_path / "mixed.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="Named Restaurant"/>
  </node>
  <node id="2" lat="51.51" lon="-0.11">
    <tag k="amenity" v="cafe"/>
  </node>
</osm>''')

        output_file = tmp_path / "named_pois.json"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            format="json",
            category="all",
            list_categories=False,
            include_ways=False,
            named_only=True,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Should only include the named restaurant
        assert len(data) == 1
        assert data[0]["name"] == "Named Restaurant"

    def test_poi_csv_format(self, small_osm_file, tmp_path):
        """Test POI CSV output."""
        from osm_core.cli.commands.poi import run

        output_file = tmp_path / "pois.csv"
        args = Namespace(
            input=str(small_osm_file),
            output=str(output_file),
            format="csv",
            category="all",
            list_categories=False,
            include_ways=False,
            named_only=False,
            stats=False
        )
        result = run(args)
        assert result == 0
        assert output_file.exists()

        content = output_file.read_text()
        assert "id,category,subcategory" in content


class TestIsochroneCommand:
    """Tests for isochrone command."""

    def test_isochrone_basic(self, road_network_osm, tmp_path):
        """Test basic isochrone generation."""
        from osm_core.cli.commands.isochrone import run

        output_file = tmp_path / "isochrone.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            lat=-33.900,
            lon=151.200,
            time="5,10",
            mode="walk",
            resolution=18
        )
        result = run(args)
        assert result == 0
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"
        # Should have origin point and isochrone polygons
        assert len(data["features"]) >= 1

    def test_isochrone_drive_mode(self, road_network_osm, tmp_path):
        """Test isochrone with drive mode."""
        from osm_core.cli.commands.isochrone import run

        output_file = tmp_path / "isochrone_drive.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            lat=-33.901,
            lon=151.201,
            time="5",
            mode="drive",
            resolution=12
        )
        result = run(args)
        assert result == 0

    def test_isochrone_bike_mode(self, road_network_osm, tmp_path):
        """Test isochrone with bike mode."""
        from osm_core.cli.commands.isochrone import run

        output_file = tmp_path / "isochrone_bike.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            lat=-33.901,
            lon=151.200,
            time="3",
            mode="bike",
            resolution=24
        )
        result = run(args)
        assert result == 0

    def test_isochrone_multiple_times(self, road_network_osm, tmp_path):
        """Test isochrone with multiple time values."""
        from osm_core.cli.commands.isochrone import run

        output_file = tmp_path / "isochrone_multi.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            lat=-33.901,
            lon=151.200,
            time="5,10,15,20",
            mode="walk",
            resolution=18
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # Should have polygons for each time
        polygons = [f for f in data["features"] if f["geometry"]["type"] == "Polygon"]
        # Number depends on what's reachable, but should have some polygons
        assert len(polygons) >= 1 or len(data["features"]) >= 1

    def test_isochrone_invalid_time(self, road_network_osm, tmp_path):
        """Test isochrone with invalid time format."""
        from osm_core.cli.commands.isochrone import run

        output_file = tmp_path / "isochrone.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            lat=-33.901,
            lon=151.200,
            time="invalid",
            mode="walk",
            resolution=18
        )
        result = run(args)
        assert result == 1

    def test_isochrone_missing_file(self, tmp_path):
        """Test isochrone with missing file."""
        from osm_core.cli.commands.isochrone import run

        output_file = tmp_path / "isochrone.geojson"
        args = Namespace(
            input=str(tmp_path / "nonexistent.osm"),
            output=str(output_file),
            lat=-33.901,
            lon=151.200,
            time="5",
            mode="walk",
            resolution=18
        )
        result = run(args)
        assert result == 1


class TestBuildingsCommand:
    """Tests for buildings command."""

    def test_buildings_basic(self, small_osm_file, tmp_path):
        """Test basic buildings extraction."""
        from osm_core.cli.commands.buildings import run

        output_file = tmp_path / "buildings.geojson"
        args = Namespace(
            input=str(small_osm_file),
            output=str(output_file),
            format="geojson",
            building_type=None,
            min_height=0,
            max_height=None,
            floor_height=3.0,
            no_estimate=False,
            stats=False
        )
        result = run(args)
        assert result == 0

    def test_buildings_filter_by_type(self, tmp_path):
        """Test filtering buildings by type."""
        from osm_core.cli.commands.buildings import run

        osm_file = tmp_path / "buildings.osm"
        osm_file.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1"><tag k="junction" v="yes"/></node>
  <node id="2" lat="51.5" lon="-0.09"><tag k="junction" v="yes"/></node>
  <node id="3" lat="51.51" lon="-0.09"><tag k="junction" v="yes"/></node>
  <node id="4" lat="51.51" lon="-0.1"><tag k="junction" v="yes"/></node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/>
    <tag k="building" v="residential"/>
  </way>
  <way id="101">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/>
    <tag k="building" v="commercial"/>
  </way>
</osm>''')

        output_file = tmp_path / "residential.geojson"
        args = Namespace(
            input=str(osm_file),
            output=str(output_file),
            format="geojson",
            building_type="residential",
            min_height=0,
            max_height=None,
            floor_height=3.0,
            no_estimate=False,
            stats=False
        )
        result = run(args)
        assert result == 0


class TestRoadsCommand:
    """Tests for roads command."""

    def test_roads_basic(self, road_network_osm, tmp_path):
        """Test basic roads extraction."""
        from osm_core.cli.commands.roads import run

        output_file = tmp_path / "roads.geojson"
        args = Namespace(
            input=str(road_network_osm),
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
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) > 0

    def test_roads_filter_by_type(self, road_network_osm, tmp_path):
        """Test filtering roads by type."""
        from osm_core.cli.commands.roads import run

        output_file = tmp_path / "primary_roads.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            format="geojson",
            road_class="all",
            highway_type="primary",
            min_length=0,
            named_only=False,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # All roads should be primary
        for feature in data["features"]:
            assert feature["properties"].get("highway") == "primary"

    def test_roads_named_only(self, road_network_osm, tmp_path):
        """Test extracting only named roads."""
        from osm_core.cli.commands.roads import run

        output_file = tmp_path / "named_roads.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            format="geojson",
            road_class="all",
            highway_type=None,
            min_length=0,
            named_only=True,
            stats=False
        )
        result = run(args)
        assert result == 0

        data = json.loads(output_file.read_text())
        # All roads should have names
        for feature in data["features"]:
            assert feature["properties"].get("name") is not None


class TestCentroidCommand:
    """Tests for centroid command."""

    def test_centroid_basic(self, small_osm_file, tmp_path):
        """Test basic centroid calculation."""
        from osm_core.cli.commands.centroid import run

        output_file = tmp_path / "centroids.geojson"
        args = Namespace(
            input=str(small_osm_file),
            output=str(output_file),
            filter="building=*",
            format="geojson",
            include_nodes=False
        )
        result = run(args)
        assert result == 0


class TestClipCommand:
    """Tests for clip command."""

    def test_clip_basic(self, small_osm_file, tmp_path):
        """Test basic clipping."""
        from osm_core.cli.commands.clip import run

        # Create a polygon GeoJSON for clipping
        polygon_file = tmp_path / "clip_polygon.geojson"
        polygon_file.write_text(json.dumps({
            "type": "Polygon",
            "coordinates": [[
                [-0.15, 51.55], [-0.05, 51.55], [-0.05, 51.45], [-0.15, 51.45], [-0.15, 51.55]
            ]]
        }))

        output_file = tmp_path / "clipped.osm"
        args = Namespace(
            input=str(small_osm_file),
            output=str(output_file),
            polygon=str(polygon_file),
            format="osm",
            complete_ways=False
        )
        result = run(args)
        assert result == 0


class TestBufferCommand:
    """Tests for buffer command."""

    def test_buffer_basic(self, road_network_osm, tmp_path):
        """Test basic buffer generation."""
        from osm_core.cli.commands.buffer import run

        output_file = tmp_path / "buffer.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            radius="100m",
            filter="highway=*",
            segments=16,
            dissolve=False
        )
        result = run(args)
        assert result == 0


class TestWithinCommand:
    """Tests for within command."""

    def test_within_basic(self, road_network_osm, tmp_path):
        """Test basic within query."""
        from osm_core.cli.commands.within import run

        # Create a polygon GeoJSON for within query
        polygon_file = tmp_path / "within_polygon.geojson"
        polygon_file.write_text(json.dumps({
            "type": "Polygon",
            "coordinates": [[
                [151.19, -33.89], [151.21, -33.89], [151.21, -33.91], [151.19, -33.91], [151.19, -33.89]
            ]]
        }))

        output_file = tmp_path / "within.geojson"
        args = Namespace(
            input=str(road_network_osm),
            output=str(output_file),
            polygon=str(polygon_file),
            filter=None,
            format="geojson",
            stats=False
        )
        result = run(args)
        assert result == 0


class TestSampleCommand:
    """Tests for sample command."""

    def test_sample_basic(self, small_osm_file, tmp_path):
        """Test basic sampling."""
        from osm_core.cli.commands.sample import run

        output_file = tmp_path / "sample.geojson"
        args = Namespace(
            input=str(small_osm_file),
            output=str(output_file),
            count=2,
            percent=None,
            type="all",
            seed=42,
            filter=None,
            format="geojson"
        )
        result = run(args)
        assert result == 0


class TestCountCommand:
    """Tests for count command."""

    def test_count_all(self, small_osm_file, capsys):
        """Test counting all elements."""
        from osm_core.cli.commands.count import run

        args = Namespace(
            input=str(small_osm_file),
            filter=None,
            by=None,
            type="all",
            top=20,
            json=False,
            quiet=False
        )
        result = run(args)
        assert result == 0

    def test_count_with_filter(self, small_osm_file, capsys):
        """Test counting filtered elements."""
        from osm_core.cli.commands.count import run

        args = Namespace(
            input=str(small_osm_file),
            filter="amenity=*",
            by=None,
            type="all",
            top=20,
            json=False,
            quiet=False
        )
        result = run(args)
        assert result == 0

    def test_count_json(self, small_osm_file, capsys):
        """Test count with JSON output."""
        from osm_core.cli.commands.count import run

        args = Namespace(
            input=str(small_osm_file),
            filter=None,
            by=None,
            type="all",
            top=20,
            json=True,
            quiet=False
        )
        result = run(args)
        assert result == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "nodes" in data or "count" in data or "total" in data
