"""Pytest fixtures for OSMFast tests."""
import pytest
from pathlib import Path


@pytest.fixture
def small_osm_file(tmp_path):
    """Create minimal valid OSM file."""
    content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="51.5" lon="-0.1">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="Test Cafe"/>
  </node>
  <node id="2" lat="51.51" lon="-0.11"/>
  <node id="3" lat="51.52" lon="-0.12"/>
  <node id="4" lat="51.53" lon="-0.13">
    <tag k="amenity" v="bank"/>
    <tag k="name" v="Test Bank"/>
  </node>
  <way id="100">
    <nd ref="1"/>
    <nd ref="2"/>
    <nd ref="3"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Main Street"/>
  </way>
  <way id="101">
    <nd ref="1"/>
    <nd ref="2"/>
    <nd ref="3"/>
    <nd ref="1"/>
    <tag k="building" v="residential"/>
    <tag k="name" v="Test Building"/>
  </way>
</osm>'''
    file = tmp_path / "small.osm"
    file.write_text(content)
    return file


@pytest.fixture
def empty_osm_file(tmp_path):
    """Create empty OSM file."""
    content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
</osm>'''
    file = tmp_path / "empty.osm"
    file.write_text(content)
    return file


@pytest.fixture
def osm_filter():
    """Create empty OSMFilter."""
    from osm_core.filters.osm_filter import OSMFilter
    return OSMFilter()


@pytest.fixture
def parser():
    """Create UltraFastOSMParser."""
    from osm_core.parsing.mmap_parser import UltraFastOSMParser
    return UltraFastOSMParser()


@pytest.fixture
def sample_node():
    """Create sample OSMNode."""
    from osm_core.models.elements import OSMNode
    return OSMNode(
        id="12345",
        lat=51.5,
        lon=-0.1,
        tags={"amenity": "restaurant", "name": "Test Restaurant"}
    )


@pytest.fixture
def sample_way():
    """Create sample OSMWay."""
    from osm_core.models.elements import OSMWay
    return OSMWay(
        id="67890",
        node_refs=["1", "2", "3", "1"],
        tags={"building": "residential", "name": "Test Building"}
    )


@pytest.fixture
def road_network_osm(tmp_path):
    """Create OSM file with connected road network for routing tests."""
    # Note: All nodes need at least one tag to be parsed by UltraFastOSMParser
    content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <node id="2" lat="-33.901" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <node id="3" lat="-33.902" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <node id="4" lat="-33.901" lon="151.201">
    <tag k="junction" v="yes"/>
  </node>
  <node id="5" lat="-33.901" lon="151.202">
    <tag k="amenity" v="restaurant"/>
    <tag k="name" v="Test Restaurant"/>
  </node>
  <node id="6" lat="-33.900" lon="151.201">
    <tag k="shop" v="supermarket"/>
    <tag k="name" v="Test Shop"/>
  </node>
  <node id="7" lat="-33.902" lon="151.201">
    <tag k="junction" v="yes"/>
  </node>
  <node id="8" lat="-33.900" lon="151.202">
    <tag k="junction" v="yes"/>
  </node>
  <node id="9" lat="-33.902" lon="151.202">
    <tag k="junction" v="yes"/>
  </node>
  <node id="10" lat="-33.903" lon="151.201">
    <tag k="junction" v="yes"/>
  </node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Main Street"/>
  </way>
  <way id="101">
    <nd ref="2"/><nd ref="4"/><nd ref="5"/>
    <tag k="highway" v="secondary"/>
    <tag k="name" v="Side Street"/>
  </way>
  <way id="102">
    <nd ref="1"/><nd ref="6"/><nd ref="4"/>
    <tag k="highway" v="tertiary"/>
    <tag k="name" v="Cross Street"/>
  </way>
  <way id="103">
    <nd ref="4"/><nd ref="3"/>
    <tag k="highway" v="residential"/>
    <tag k="name" v="Residential Ave"/>
  </way>
  <way id="104">
    <nd ref="3"/><nd ref="7"/><nd ref="10"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="South Road"/>
  </way>
  <way id="105">
    <nd ref="6"/><nd ref="8"/><nd ref="5"/>
    <tag k="highway" v="secondary"/>
    <tag k="name" v="North Road"/>
  </way>
  <way id="106">
    <nd ref="5"/><nd ref="9"/><nd ref="7"/>
    <tag k="highway" v="tertiary"/>
    <tag k="name" v="East Road"/>
  </way>
  <way id="107">
    <nd ref="7"/><nd ref="4"/>
    <tag k="highway" v="residential"/>
    <tag k="name" v="Center Lane"/>
  </way>
</osm>'''
    file = tmp_path / "road_network.osm"
    file.write_text(content)
    return file


@pytest.fixture
def disconnected_network_osm(tmp_path):
    """Create OSM file with disconnected road components."""
    # Note: All nodes need at least one tag to be parsed by UltraFastOSMParser
    content = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6">
  <node id="1" lat="-33.900" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <node id="2" lat="-33.901" lon="151.200">
    <tag k="junction" v="yes"/>
  </node>
  <node id="3" lat="-33.910" lon="151.210">
    <tag k="junction" v="yes"/>
  </node>
  <node id="4" lat="-33.911" lon="151.210">
    <tag k="junction" v="yes"/>
  </node>
  <way id="100">
    <nd ref="1"/><nd ref="2"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Road A"/>
  </way>
  <way id="101">
    <nd ref="3"/><nd ref="4"/>
    <tag k="highway" v="primary"/>
    <tag k="name" v="Road B"/>
  </way>
</osm>'''
    file = tmp_path / "disconnected.osm"
    file.write_text(content)
    return file


@pytest.fixture
def map2_osm():
    """Return path to map2.osm test file."""
    return Path(__file__).parent.parent / "map2.osm"
