"""Utility functions for OSM processing."""

from osm_core.utils.xml_utils import xml_escape
from osm_core.utils.geo_utils import calculate_polygon_area

__all__ = ['xml_escape', 'calculate_polygon_area']
