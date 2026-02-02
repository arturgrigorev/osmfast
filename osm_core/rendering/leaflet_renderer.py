"""
Leaflet HTML map generator.

Generates self-contained HTML files with interactive Leaflet.js maps.
"""

import json
import html
from typing import List, Dict, Any, Optional, Tuple

from .styles import StyleManager, color_to_css


class LeafletRenderer:
    """
    Generates interactive HTML maps using Leaflet.js.

    Creates self-contained HTML files that can be opened in any browser.
    Uses CDN-hosted Leaflet library (requires internet for first load).
    """

    # Leaflet CDN URLs
    LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"

    # Tile providers
    TILE_PROVIDERS = {
        "osm": {
            "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            "maxZoom": 19,
        },
        "carto-light": {
            "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            "maxZoom": 20,
        },
        "carto-dark": {
            "url": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
            "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            "maxZoom": 20,
        },
        "esri-satellite": {
            "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            "attribution": 'Tiles &copy; Esri',
            "maxZoom": 18,
        },
    }

    def __init__(self, style: str = "default", tile_provider: str = "osm"):
        """
        Initialize Leaflet renderer.

        Args:
            style: Color style for features
            tile_provider: Tile provider name (osm, carto-light, carto-dark, esri-satellite)
        """
        self.style_manager = StyleManager(style)
        self.tile_provider = tile_provider if tile_provider in self.TILE_PROVIDERS else "osm"
        self.geojson_features: List[Dict[str, Any]] = []

    def add_node(self, node: Any):
        """Add a node as a point feature."""
        # Skip nodes without significant tags
        if not any(k in node.tags for k in ['amenity', 'shop', 'tourism', 'leisure', 'historic', 'name']):
            return

        color = color_to_css(self.style_manager.get_poi_color(node.tags))

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [node.lon, node.lat]
            },
            "properties": {
                "id": node.id,
                "type": "node",
                "tags": dict(node.tags),
                "name": node.tags.get("name", ""),
                "color": color,
                "category": self._get_category(node.tags),
            }
        }
        self.geojson_features.append(feature)

    def add_way(self, way: Any, node_coords: Dict[str, Tuple[float, float]]):
        """Add a way as a line or polygon feature."""
        # Get coordinates
        coords = []
        for ref in way.node_refs:
            if ref in node_coords:
                lat, lon = node_coords[ref]
                coords.append([lon, lat])

        if len(coords) < 2:
            return

        # Determine geometry type and styling
        is_area = way.is_closed and len(coords) >= 4
        tags = way.tags

        # Determine category and colors
        if tags.get('highway') == 'cycleway' or 'cycleway' in tags:
            category = "bikelane"
            fill_color = (255, 0, 255)  # Magenta
            outline_color = fill_color
            width = 3
            is_area = False
        elif 'highway' in tags:
            category = "highway"
            highway_type = tags['highway']
            # High contrast road colors
            highway_colors = {
                'motorway': (220, 50, 50),      # Red
                'trunk': (230, 100, 40),        # Orange
                'primary': (40, 80, 180),       # Blue
                'secondary': (60, 140, 60),     # Green
                'tertiary': (140, 100, 60),     # Brown
                'residential': (80, 80, 80),    # Dark gray
                'service': (100, 100, 100),     # Gray
                'footway': (180, 120, 80),      # Tan
                'path': (160, 140, 100),        # Light brown
                'cycleway': (255, 0, 255),      # Magenta (fallback)
            }
            fill_color = highway_colors.get(highway_type, (90, 90, 90))
            outline_color = fill_color
            width = self.style_manager.get_highway_width(highway_type)
            is_area = False  # Highways are always lines
        elif 'building' in tags:
            category = "building"
            fill_color = (100, 90, 80)  # Dark brownish gray
            outline_color = (60, 55, 50)  # Darker outline
            width = 1
        elif 'landuse' in tags:
            category = "landuse"
            fill_color = self.style_manager.get_landuse_color(tags['landuse'])
            outline_color = fill_color
            width = 1
        elif 'natural' in tags:
            category = "natural"
            if tags['natural'] == 'water':
                fill_color = self.style_manager.get_water_color()
            else:
                fill_color = self.style_manager.get_natural_color(tags['natural'])
            outline_color = fill_color
            width = 1
        elif 'waterway' in tags:
            category = "waterway"
            fill_color = self.style_manager.get_waterway_color(tags['waterway'])
            outline_color = fill_color
            width = 2 if tags['waterway'] == 'river' else 1
            is_area = False
        elif 'railway' in tags:
            category = "railway"
            fill_color = self.style_manager.get_railway_color(tags['railway'])
            outline_color = fill_color
            width = 2
            is_area = False
        elif 'water' in tags or tags.get('natural') == 'water':
            category = "water"
            fill_color = self.style_manager.get_water_color()
            outline_color = fill_color
            width = 1
        elif 'leisure' in tags:
            category = "leisure"
            fill_color = self.style_manager.style["leisure"]
            outline_color = fill_color
            width = 1
        else:
            category = "other"
            fill_color = (200, 200, 200)
            outline_color = (150, 150, 150)
            width = 1

        # Create geometry
        if is_area:
            geometry = {
                "type": "Polygon",
                "coordinates": [coords]
            }
        else:
            geometry = {
                "type": "LineString",
                "coordinates": coords
            }

        feature = {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id": way.id,
                "type": "way",
                "tags": dict(tags),
                "name": tags.get("name", ""),
                "category": category,
                "fillColor": color_to_css(fill_color),
                "color": color_to_css(outline_color),
                "weight": width,
            }
        }
        self.geojson_features.append(feature)

    def _get_category(self, tags: Dict[str, str]) -> str:
        """Determine feature category from tags."""
        if 'amenity' in tags:
            return 'amenity'
        elif 'shop' in tags:
            return 'shop'
        elif 'tourism' in tags:
            return 'tourism'
        elif 'leisure' in tags:
            return 'leisure'
        elif 'historic' in tags:
            return 'historic'
        return 'other'

    def generate_html(self, title: str = "OSMFast Map",
                      show_layer_control: bool = True,
                      show_fullscreen: bool = True) -> str:
        """
        Generate HTML content for the map.

        Args:
            title: Page title
            show_layer_control: Show layer toggle control
            show_fullscreen: Enable fullscreen button

        Returns:
            Complete HTML document as string
        """
        # Get GeoJSON data
        geojson_data = json.dumps({
            "type": "FeatureCollection",
            "features": self.geojson_features
        })

        # Get tile provider settings
        tile = self.TILE_PROVIDERS[self.tile_provider]

        # Calculate bounds from features
        bounds_js = "null"
        if self.geojson_features:
            lats = []
            lons = []
            for feature in self.geojson_features:
                geom = feature["geometry"]
                if geom["type"] == "Point":
                    lons.append(geom["coordinates"][0])
                    lats.append(geom["coordinates"][1])
                elif geom["type"] == "LineString":
                    for coord in geom["coordinates"]:
                        lons.append(coord[0])
                        lats.append(coord[1])
                elif geom["type"] == "Polygon":
                    for coord in geom["coordinates"][0]:
                        lons.append(coord[0])
                        lats.append(coord[1])

            if lats and lons:
                bounds_js = f"[[{min(lats)}, {min(lons)}], [{max(lats)}, {max(lons)}]]"

        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <link rel="stylesheet" href="{self.LEAFLET_CSS}" />
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ height: 100%; }}
        #map {{ height: 100%; width: 100%; }}
        .info-popup {{ max-width: 350px; min-width: 250px; }}
        .info-popup h4 {{ margin: 0 0 8px 0; color: #333; font-size: 15px; }}
        .info-popup .popup-section {{ margin-bottom: 10px; }}
        .info-popup .popup-section-title {{ font-weight: bold; color: #666; font-size: 11px; text-transform: uppercase; margin-bottom: 4px; border-bottom: 1px solid #ddd; padding-bottom: 2px; }}
        .info-popup .popup-row {{ display: flex; justify-content: space-between; padding: 3px 0; font-size: 12px; }}
        .info-popup .popup-row .label {{ color: #666; }}
        .info-popup .popup-row .value {{ color: #333; font-weight: 500; text-align: right; max-width: 180px; word-wrap: break-word; }}
        .info-popup .coords-row {{ display: flex; align-items: center; gap: 8px; background: #f5f5f5; padding: 6px 8px; border-radius: 4px; margin: 4px 0; }}
        .info-popup .coords-text {{ font-family: monospace; font-size: 11px; flex: 1; }}
        .info-popup .copy-btn {{ background: #4a90d9; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 11px; white-space: nowrap; }}
        .info-popup .copy-btn:hover {{ background: #357abd; }}
        .info-popup .copy-btn.copied {{ background: #5cb85c; }}
        .info-popup .address-box {{ background: #fff8e7; padding: 6px 8px; border-radius: 4px; margin: 4px 0; border-left: 3px solid #f0ad4e; }}
        .info-popup .address-text {{ font-size: 12px; margin-bottom: 4px; }}
        .info-popup table {{ border-collapse: collapse; width: 100%; font-size: 11px; }}
        .info-popup td {{ padding: 2px 5px; border-bottom: 1px solid #eee; }}
        .info-popup td:first-child {{ font-weight: bold; color: #666; width: 40%; }}
        .info-popup .osm-link {{ font-size: 11px; color: #4a90d9; text-decoration: none; }}
        .info-popup .osm-link:hover {{ text-decoration: underline; }}
        .legend {{
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
        }}
        .legend h4 {{ margin: 0 0 10px 0; font-size: 14px; }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
            font-size: 12px;
        }}
        .legend-color {{
            width: 20px;
            height: 12px;
            margin-right: 8px;
            border: 1px solid #999;
        }}
        .feature-count {{
            background: white;
            padding: 8px 12px;
            border-radius: 4px;
            box-shadow: 0 0 10px rgba(0,0,0,0.2);
            font-size: 13px;
        }}
        .leaflet-control-layers {{
            background: white;
            padding: 8px 12px;
            border-radius: 6px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.25);
        }}
        .leaflet-control-layers-list {{
            font-size: 13px;
        }}
        .leaflet-control-layers-overlays label {{
            display: flex;
            align-items: center;
            padding: 3px 0;
            cursor: pointer;
        }}
        .leaflet-control-layers-overlays label:hover {{
            background: #f0f0f0;
        }}
        .leaflet-control-layers-separator {{
            display: none;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script src="{self.LEAFLET_JS}"></script>
    <script>
        // Initialize map
        var map = L.map('map');

        // Add tile layer
        L.tileLayer('{tile["url"]}', {{
            attribution: '{tile["attribution"]}',
            maxZoom: {tile["maxZoom"]}
        }}).addTo(map);

        // GeoJSON data
        var geojsonData = {geojson_data};

        // Style function
        function getStyle(feature) {{
            var props = feature.properties;
            if (feature.geometry.type === 'Point') {{
                return {{}};  // Points styled via pointToLayer
            }}
            return {{
                color: props.color || '#3388ff',
                fillColor: props.fillColor || props.color || '#3388ff',
                weight: props.weight || 2,
                opacity: 1,
                fillOpacity: feature.geometry.type === 'Polygon' ? 0.5 : 1
            }};
        }}

        // Point style (markers)
        function pointToLayer(feature, latlng) {{
            var props = feature.properties;
            return L.circleMarker(latlng, {{
                radius: 6,
                fillColor: props.color || '#ff6b6b',
                color: '#fff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9
            }});
        }}

        // Copy to clipboard function
        function copyToClipboard(text, btn) {{
            navigator.clipboard.writeText(text).then(function() {{
                var original = btn.textContent;
                btn.textContent = 'Copied!';
                btn.classList.add('copied');
                setTimeout(function() {{
                    btn.textContent = original;
                    btn.classList.remove('copied');
                }}, 1500);
            }});
        }}

        // Popup content
        function createPopup(feature, latlng) {{
            var props = feature.properties;
            var tags = props.tags || {{}};
            var geom = feature.geometry;
            var html = '<div class="info-popup">';

            // Title
            var title = props.name || tags.name || props.category || 'Feature';
            var categoryIcon = {{
                'highway': '🛣️', 'bikelane': '🚴', 'building': '🏢', 'amenity': '📍',
                'shop': '🛒', 'tourism': '🎯', 'leisure': '⛳', 'historic': '🏛️',
                'natural': '🌲', 'water': '💧', 'railway': '🚂'
            }}[props.category] || '📌';
            html += '<h4>' + categoryIcon + ' ' + title + '</h4>';

            // Coordinates
            var lat, lon;
            if (latlng) {{
                lat = latlng.lat.toFixed(6);
                lon = latlng.lng.toFixed(6);
            }} else if (geom.type === 'Point') {{
                lon = geom.coordinates[0].toFixed(6);
                lat = geom.coordinates[1].toFixed(6);
            }} else if (geom.type === 'Polygon') {{
                var coords = geom.coordinates[0];
                var sumLat = 0, sumLon = 0;
                coords.forEach(function(c) {{ sumLon += c[0]; sumLat += c[1]; }});
                lon = (sumLon / coords.length).toFixed(6);
                lat = (sumLat / coords.length).toFixed(6);
            }} else if (geom.type === 'LineString') {{
                var mid = Math.floor(geom.coordinates.length / 2);
                lon = geom.coordinates[mid][0].toFixed(6);
                lat = geom.coordinates[mid][1].toFixed(6);
            }}

            if (lat && lon) {{
                var coordsText = lat + ', ' + lon;
                html += '<div class="popup-section">';
                html += '<div class="popup-section-title">Location</div>';
                html += '<div class="coords-row">';
                html += '<span class="coords-text">' + coordsText + '</span>';
                html += '<button class="copy-btn" onclick="copyToClipboard(\\'' + coordsText + '\\', this)">📋 Copy</button>';
                html += '</div>';
                html += '</div>';
            }}

            // Address (if available)
            var addrParts = [];
            if (tags['addr:housenumber']) addrParts.push(tags['addr:housenumber']);
            if (tags['addr:street']) addrParts.push(tags['addr:street']);
            if (tags['addr:suburb']) addrParts.push(tags['addr:suburb']);
            if (tags['addr:city']) addrParts.push(tags['addr:city']);
            if (tags['addr:postcode']) addrParts.push(tags['addr:postcode']);

            if (addrParts.length > 0) {{
                var address = addrParts.join(', ');
                html += '<div class="popup-section">';
                html += '<div class="popup-section-title">Address</div>';
                html += '<div class="address-box">';
                html += '<div class="address-text">' + address + '</div>';
                html += '<button class="copy-btn" onclick="copyToClipboard(\\'' + address.replace(/'/g, "\\\\'") + '\\', this)">📋 Copy Address</button>';
                html += '</div>';
                html += '</div>';
            }}

            // Key info section
            var keyInfo = [];
            var infoKeys = ['phone', 'website', 'email', 'opening_hours', 'cuisine', 'wheelchair', 'operator', 'brand'];
            infoKeys.forEach(function(key) {{
                if (tags[key]) {{
                    var value = tags[key];
                    if (key === 'website' || key === 'email') {{
                        value = '<a href="' + (key === 'email' ? 'mailto:' : '') + value + '" target="_blank" class="osm-link">' + value + '</a>';
                    }}
                    keyInfo.push([key, value]);
                }}
            }});

            if (keyInfo.length > 0) {{
                html += '<div class="popup-section">';
                html += '<div class="popup-section-title">Details</div>';
                keyInfo.forEach(function(item) {{
                    html += '<div class="popup-row"><span class="label">' + item[0] + '</span><span class="value">' + item[1] + '</span></div>';
                }});
                html += '</div>';
            }}

            // All tags (collapsible)
            var tagCount = Object.keys(tags).length;
            if (tagCount > 0) {{
                html += '<div class="popup-section">';
                html += '<details><summary class="popup-section-title" style="cursor:pointer;">All Tags (' + tagCount + ')</summary>';
                html += '<table>';
                for (var key in tags) {{
                    if (tags.hasOwnProperty(key)) {{
                        html += '<tr><td>' + key + '</td><td>' + tags[key] + '</td></tr>';
                    }}
                }}
                html += '</table>';
                html += '</details>';
                html += '</div>';
            }}

            // OSM link
            var osmType = props.type === 'node' ? 'node' : 'way';
            html += '<a href="https://www.openstreetmap.org/' + osmType + '/' + props.id + '" target="_blank" class="osm-link">View on OpenStreetMap →</a>';

            html += '</div>';
            return html;
        }}

        // Create layers by category
        var layers = {{}};
        var categories = ['highway', 'bikelane', 'building', 'landuse', 'natural', 'water', 'waterway', 'railway', 'amenity', 'shop', 'tourism', 'leisure', 'historic', 'other'];

        categories.forEach(function(cat) {{
            layers[cat] = L.geoJSON(null, {{
                style: getStyle,
                pointToLayer: pointToLayer,
                onEachFeature: function(feature, layer) {{
                    layer.on('click', function(e) {{
                        var latlng = e.latlng;
                        layer.bindPopup(createPopup(feature, latlng)).openPopup();
                    }});
                }}
            }});
        }});

        // Add features to appropriate layers
        geojsonData.features.forEach(function(feature) {{
            var cat = feature.properties.category || 'other';
            if (layers[cat]) {{
                layers[cat].addData(feature);
            }} else {{
                layers['other'].addData(feature);
            }}
        }});

        // Add layers to map (in order)
        ['landuse', 'natural', 'water', 'waterway', 'building', 'railway', 'highway', 'bikelane', 'amenity', 'shop', 'tourism', 'leisure', 'historic', 'other'].forEach(function(cat) {{
            if (layers[cat].getLayers().length > 0) {{
                layers[cat].addTo(map);
            }}
        }});

        // Layer control with better labels
        var layerLabels = {{
            'highway': '🛣️ Roads',
            'bikelane': '🚴 Bike Lanes',
            'building': '🏢 Buildings',
            'landuse': '🌍 Land Use',
            'natural': '🌲 Natural',
            'water': '💧 Water',
            'waterway': '🌊 Waterways',
            'railway': '🚂 Railways',
            'amenity': '📍 Amenities',
            'shop': '🛒 Shops',
            'tourism': '🎯 Tourism',
            'leisure': '⛳ Leisure',
            'historic': '🏛️ Historic',
            'other': '📦 Other'
        }};

        var overlays = {{}};
        categories.forEach(function(cat) {{
            if (layers[cat].getLayers().length > 0) {{
                var label = layerLabels[cat] || cat;
                var count = layers[cat].getLayers().length;
                overlays[label + ' (' + count + ')'] = layers[cat];
            }}
        }});

        {"L.control.layers(null, overlays, {collapsed: false, position: 'topright'}).addTo(map);" if show_layer_control else ""}

        // Fit bounds
        var bounds = {bounds_js};
        if (bounds) {{
            map.fitBounds(bounds, {{padding: [20, 20]}});
        }} else {{
            map.setView([0, 0], 2);
        }}

        // Feature count display
        var countControl = L.control({{position: 'bottomleft'}});
        countControl.onAdd = function(map) {{
            var div = L.DomUtil.create('div', 'feature-count');
            div.innerHTML = 'Features: ' + geojsonData.features.length;
            return div;
        }};
        countControl.addTo(map);

        // Legend
        var legend = L.control({{position: 'bottomright'}});
        legend.onAdd = function(map) {{
            var div = L.DomUtil.create('div', 'legend');
            div.innerHTML = '<h4>Legend</h4>';

            var items = [
                ['highway', 'Roads', '#5a5a5a'],
                ['bikelane', 'Bike Lanes', '#ff00ff'],
                ['building', 'Buildings', '#645a50'],
                ['water', 'Water', '#aad3df'],
                ['amenity', 'Amenities', '#ff6b6b'],
                ['shop', 'Shops', '#ac39ac'],
                ['tourism', 'Tourism', '#0099ff'],
                ['leisure', 'Leisure', '#8bc34a'],
                ['historic', 'Historic', '#8b4513']
            ];

            items.forEach(function(item) {{
                if (layers[item[0]] && layers[item[0]].getLayers().length > 0) {{
                    div.innerHTML += '<div class="legend-item"><div class="legend-color" style="background:' + item[2] + '"></div>' + item[1] + '</div>';
                }}
            }});

            return div;
        }};
        legend.addTo(map);
    </script>
</body>
</html>'''
        return html_content

    def save(self, filename: str, title: str = "OSMFast Map"):
        """
        Save map to HTML file.

        Args:
            filename: Output filename
            title: Page title
        """
        html_content = self.generate_html(title)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def render(self, nodes: List[Any], ways: List[Any],
               node_coords: Dict[str, Tuple[float, float]],
               title: str = "OSMFast Map") -> str:
        """
        Render OSM data to HTML.

        Args:
            nodes: List of OSM nodes
            ways: List of OSM ways
            node_coords: Dictionary mapping node IDs to (lat, lon)
            title: Page title

        Returns:
            HTML content as string
        """
        # Clear previous features
        self.geojson_features = []

        # Add ways first (so they're below points)
        for way in ways:
            self.add_way(way, node_coords)

        # Add nodes
        for node in nodes:
            self.add_node(node)

        return self.generate_html(title)
