"""
WebGL data collector for 3D map rendering.

Collects and processes OSM data (buildings, roads, POIs, etc.) for WebGL visualization.
"""

from typing import List, Dict, Any, Tuple, Optional


class WebGLDataCollector:
    """
    Collects OSM data for WebGL 3D rendering.

    Aggregates buildings, roads, water, POIs, trees, and bike lanes
    with their coordinates and metadata.
    """

    # Default building height in meters
    DEFAULT_BUILDING_HEIGHT = 10

    # Meters per floor (approximate)
    METERS_PER_FLOOR = 3.0

    def __init__(self, style_manager):
        """
        Initialize data collector.

        Args:
            style_manager: StyleManager instance for highway widths
        """
        self.style_manager = style_manager
        self._buildings: List[Dict[str, Any]] = []
        self._roads: List[Dict[str, Any]] = []
        self._water: List[Dict[str, Any]] = []
        self._pois: List[Dict[str, Any]] = []
        self._trees: List[Dict[str, Any]] = []
        self._bikelanes: List[Dict[str, Any]] = []
        self._bounds = {"min_lat": 90, "max_lat": -90, "min_lon": 180, "max_lon": -180}

    def clear(self):
        """Clear all collected data."""
        self._buildings = []
        self._roads = []
        self._water = []
        self._pois = []
        self._trees = []
        self._bikelanes = []
        self._bounds = {"min_lat": 90, "max_lat": -90, "min_lon": 180, "max_lon": -180}

    @property
    def buildings(self) -> List[Dict[str, Any]]:
        """Get collected buildings."""
        return self._buildings

    @property
    def roads(self) -> List[Dict[str, Any]]:
        """Get collected roads."""
        return self._roads

    @property
    def water(self) -> List[Dict[str, Any]]:
        """Get collected water features."""
        return self._water

    @property
    def pois(self) -> List[Dict[str, Any]]:
        """Get collected POIs."""
        return self._pois

    @property
    def trees(self) -> List[Dict[str, Any]]:
        """Get collected trees."""
        return self._trees

    @property
    def bikelanes(self) -> List[Dict[str, Any]]:
        """Get collected bike lanes."""
        return self._bikelanes

    @property
    def bounds(self) -> Dict[str, float]:
        """Get geographic bounds."""
        return self._bounds

    def _update_bounds(self, lat: float, lon: float):
        """Update bounding box."""
        self._bounds["min_lat"] = min(self._bounds["min_lat"], lat)
        self._bounds["max_lat"] = max(self._bounds["max_lat"], lat)
        self._bounds["min_lon"] = min(self._bounds["min_lon"], lon)
        self._bounds["max_lon"] = max(self._bounds["max_lon"], lon)

    def _estimate_building_height(self, tags: Dict[str, str]) -> float:
        """Estimate building height from tags."""
        # Try explicit height
        if "height" in tags:
            try:
                height_str = tags["height"].replace("m", "").strip()
                return float(height_str)
            except ValueError:
                pass

        # Try building:levels
        if "building:levels" in tags:
            try:
                levels = int(tags["building:levels"])
                return levels * self.METERS_PER_FLOOR
            except ValueError:
                pass

        # Estimate by building type
        building_type = tags.get("building", "yes")
        height_estimates = {
            "house": 8,
            "residential": 12,
            "apartments": 20,
            "commercial": 15,
            "retail": 6,
            "industrial": 10,
            "warehouse": 8,
            "garage": 3,
            "shed": 3,
            "roof": 4,
            "church": 15,
            "cathedral": 30,
            "hospital": 18,
            "school": 10,
            "university": 15,
            "office": 25,
            "hotel": 20,
            "skyscraper": 100,
            "tower": 40,
        }
        return height_estimates.get(building_type, self.DEFAULT_BUILDING_HEIGHT)

    def add_building(self, way: Any, node_coords: Dict[str, Tuple[float, float]]):
        """Add a building as 3D solid shape."""
        if not way.is_closed:
            return

        coords = []
        for ref in way.node_refs:
            if ref in node_coords:
                lat, lon = node_coords[ref]
                coords.append([lon, lat])
                self._update_bounds(lat, lon)

        if len(coords) < 4:
            return

        height = self._estimate_building_height(way.tags)

        # Collect all tags for tooltip
        tags = dict(way.tags)

        # Calculate centroid for coordinates display
        lats = [c[1] for c in coords]
        lons = [c[0] for c in coords]
        centroid_lat = sum(lats) / len(lats)
        centroid_lon = sum(lons) / len(lons)

        # Build full address
        addr_parts = []
        if way.tags.get("addr:housenumber"):
            addr_parts.append(way.tags.get("addr:housenumber"))
        if way.tags.get("addr:street"):
            addr_parts.append(way.tags.get("addr:street"))
        if way.tags.get("addr:suburb"):
            addr_parts.append(way.tags.get("addr:suburb"))
        if way.tags.get("addr:city"):
            addr_parts.append(way.tags.get("addr:city"))
        if way.tags.get("addr:postcode"):
            addr_parts.append(way.tags.get("addr:postcode"))

        self._buildings.append({
            "id": way.id,
            "coords": coords,
            "lat": round(centroid_lat, 7),
            "lon": round(centroid_lon, 7),
            "height": height,
            "name": way.tags.get("name", ""),
            "type": way.tags.get("building", "yes"),
            "levels": way.tags.get("building:levels", ""),
            "address": ", ".join(addr_parts) if addr_parts else "",
            "architect": way.tags.get("architect", ""),
            "start_date": way.tags.get("start_date", way.tags.get("year_built", "")),
            "roof_shape": way.tags.get("roof:shape", ""),
            "material": way.tags.get("building:material", way.tags.get("material", "")),
            "colour": way.tags.get("building:colour", way.tags.get("colour", "")),
            "operator": way.tags.get("operator", ""),
            "website": way.tags.get("website", way.tags.get("contact:website", "")),
            "phone": way.tags.get("phone", way.tags.get("contact:phone", "")),
            "opening_hours": way.tags.get("opening_hours", ""),
            "wheelchair": way.tags.get("wheelchair", ""),
            "amenity": way.tags.get("amenity", ""),
            "shop": way.tags.get("shop", ""),
            "office": way.tags.get("office", ""),
            "tourism": way.tags.get("tourism", ""),
            "description": way.tags.get("description", ""),
            "wikidata": way.tags.get("wikidata", ""),
            "wikipedia": way.tags.get("wikipedia", ""),
            "tags": tags,
        })

    def add_road(self, way: Any, node_coords: Dict[str, Tuple[float, float]]):
        """Add a road as a ground-level line."""
        coords = []
        for ref in way.node_refs:
            if ref in node_coords:
                lat, lon = node_coords[ref]
                coords.append([lon, lat])
                self._update_bounds(lat, lon)

        if len(coords) < 2:
            return

        # Calculate midpoint for coordinates display
        mid_idx = len(coords) // 2
        mid_lat = coords[mid_idx][1]
        mid_lon = coords[mid_idx][0]

        highway_type = way.tags.get("highway", "road")
        width = self.style_manager.get_highway_width(highway_type)

        self._roads.append({
            "id": way.id,
            "coords": coords,
            "lat": round(mid_lat, 7),
            "lon": round(mid_lon, 7),
            "type": highway_type,
            "width": width,
            "name": way.tags.get("name", ""),
            "maxspeed": way.tags.get("maxspeed", ""),
            "surface": way.tags.get("surface", ""),
            "lanes": way.tags.get("lanes", ""),
            "oneway": way.tags.get("oneway", ""),
            "tags": dict(way.tags),
        })

    def add_water(self, way: Any, node_coords: Dict[str, Tuple[float, float]]):
        """Add water as a ground-level polygon."""
        if not way.is_closed:
            return

        coords = []
        for ref in way.node_refs:
            if ref in node_coords:
                lat, lon = node_coords[ref]
                coords.append([lon, lat])
                self._update_bounds(lat, lon)

        if len(coords) < 4:
            return

        self._water.append({
            "id": way.id,
            "coords": coords,
        })

    def add_poi(self, node: Any):
        """Add a POI marker."""
        self._update_bounds(node.lat, node.lon)

        # Determine POI category
        if "amenity" in node.tags:
            category = "amenity"
            poi_type = node.tags["amenity"]
        elif "shop" in node.tags:
            category = "shop"
            poi_type = node.tags["shop"]
        elif "tourism" in node.tags:
            category = "tourism"
            poi_type = node.tags["tourism"]
        else:
            category = "other"
            poi_type = "poi"

        self._pois.append({
            "id": node.id,
            "lon": node.lon,
            "lat": node.lat,
            "name": node.tags.get("name", ""),
            "category": category,
            "type": poi_type,
            "tags": dict(node.tags),
        })

    def add_tree(self, node: Any):
        """Add a tree marker."""
        self._update_bounds(node.lat, node.lon)

        # Get tree properties
        tree_type = node.tags.get("natural", "tree")
        species = node.tags.get("species", node.tags.get("genus", ""))
        leaf_type = node.tags.get("leaf_type", "")
        leaf_cycle = node.tags.get("leaf_cycle", "")

        # Estimate tree height
        height = 8  # Default height
        if "height" in node.tags:
            try:
                height_str = node.tags["height"].replace("m", "").strip()
                height = float(height_str)
            except ValueError:
                pass

        # Crown diameter estimate
        crown_diameter = node.tags.get("diameter_crown", "")
        if crown_diameter:
            try:
                crown_diameter = float(crown_diameter.replace("m", "").strip())
            except ValueError:
                crown_diameter = height * 0.6
        else:
            crown_diameter = height * 0.6

        self._trees.append({
            "id": node.id,
            "lon": node.lon,
            "lat": node.lat,
            "name": node.tags.get("name", ""),
            "type": tree_type,
            "species": species,
            "leaf_type": leaf_type,
            "leaf_cycle": leaf_cycle,
            "height": height,
            "crown_diameter": crown_diameter,
            "tags": dict(node.tags),
        })

    def add_bikelane(self, way: Any, node_coords: Dict[str, Tuple[float, float]]):
        """Add a bike lane as a line."""
        coords = []
        for ref in way.node_refs:
            if ref in node_coords:
                lat, lon = node_coords[ref]
                coords.append([lon, lat])
                self._update_bounds(lat, lon)

        if len(coords) < 2:
            return

        # Calculate midpoint for coordinates display
        mid_idx = len(coords) // 2
        mid_lat = coords[mid_idx][1]
        mid_lon = coords[mid_idx][0]

        # Determine bike lane type
        if way.tags.get("highway") == "cycleway":
            lane_type = "cycleway"
        elif way.tags.get("cycleway") in ("lane", "track"):
            lane_type = way.tags.get("cycleway")
        else:
            lane_type = "bike_lane"

        self._bikelanes.append({
            "id": way.id,
            "coords": coords,
            "lat": round(mid_lat, 7),
            "lon": round(mid_lon, 7),
            "type": lane_type,
            "name": way.tags.get("name", ""),
            "surface": way.tags.get("surface", ""),
            "width": way.tags.get("width", ""),
            "oneway": way.tags.get("oneway", ""),
            "tags": dict(way.tags),
        })

    def process_osm_data(self, nodes: List[Any], ways: List[Any],
                         node_coords: Dict[str, Tuple[float, float]]):
        """
        Process OSM data and collect all features.

        Args:
            nodes: List of OSM nodes
            ways: List of OSM ways
            node_coords: Dictionary mapping node IDs to (lat, lon)
        """
        self.clear()

        # Process ways
        for way in ways:
            tags = way.tags

            if 'building' in tags:
                self.add_building(way, node_coords)
            elif tags.get('highway') == 'cycleway' or 'cycleway' in tags:
                self.add_bikelane(way, node_coords)
            elif 'highway' in tags:
                self.add_road(way, node_coords)
            elif tags.get('natural') == 'water' or 'water' in tags:
                self.add_water(way, node_coords)

        # Process POI nodes
        for node in nodes:
            if node.tags.get('natural') == 'tree':
                self.add_tree(node)
            elif any(k in node.tags for k in ['amenity', 'shop', 'tourism']):
                self.add_poi(node)
