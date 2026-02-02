"""
WebGL sun study HTML generator.

Generates 3D visualization with sun position controls and realistic shadows.
"""

import json
import math
from typing import Dict, Any

from .data_collector import WebGLDataCollector
from .styles import WebGL3DStyle, SUN_STUDY_STYLE, rgb_to_hex, generate_road_colors_js


# Three.js CDN URL
THREE_JS = "https://unpkg.com/three@0.160.0/build/three.module.js"


class WebGLSunGenerator:
    """
    Generates interactive 3D WebGL HTML with sun position controls.

    Features:
    - Hour/month/day sliders for sun position
    - Realistic shadow casting from buildings
    - Animate Day button for time-lapse
    """

    def __init__(self, data: WebGLDataCollector, style: WebGL3DStyle = None,
                 style_name: str = "default"):
        """
        Initialize sun study generator.

        Args:
            data: Collected OSM data
            style: Optional style (defaults to SUN_STUDY_STYLE)
            style_name: Name of the style preset
        """
        self.data = data
        self.style = style or SUN_STUDY_STYLE
        self.style_name = style_name

    def generate(self, title: str = "OSMFast 3D Map - Sun Study",
                 latitude: float = None) -> str:
        """
        Generate complete HTML document with sun controls.

        Args:
            title: Page title
            latitude: Latitude for sun position (optional, uses center if not provided)

        Returns:
            Complete HTML document as string
        """
        # Calculate center and scale
        bounds = self.data.bounds
        center_lat = (bounds["min_lat"] + bounds["max_lat"]) / 2
        center_lon = (bounds["min_lon"] + bounds["max_lon"]) / 2

        # Use provided latitude or fall back to center
        sun_latitude = latitude if latitude is not None else center_lat

        lat_range = bounds["max_lat"] - bounds["min_lat"]
        lon_range = bounds["max_lon"] - bounds["min_lon"]

        meters_per_deg_lat = 111320
        meters_per_deg_lon = 111320 * math.cos(math.radians(center_lat))

        scene_width = lon_range * meters_per_deg_lon
        scene_height = lat_range * meters_per_deg_lat
        scale = max(scene_width, scene_height)

        # Prepare data for JavaScript
        buildings_json = json.dumps(self.data.buildings)
        roads_json = json.dumps(self.data.roads)
        water_json = json.dumps(self.data.water)
        pois_json = json.dumps(self.data.pois)
        trees_json = json.dumps(self.data.trees)
        bikelanes_json = json.dumps(self.data.bikelanes)
        bounds_json = json.dumps(bounds)

        # Get style colors
        s = self.style
        bg_color = s.background_color
        building_fill_3d = s.building_fill
        building_edge_3d = s.building_edge
        ground_color = s.ground_color
        grid_color = s.grid_color
        water_color = (170, 211, 223)

        # Road colors
        road_colors_js = generate_road_colors_js(s.road_colors)

        # Counts
        num_buildings = len(self.data.buildings)
        num_roads = len(self.data.roads)
        num_trees = len(self.data.trees)
        num_bikelanes = len(self.data.bikelanes)

        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ height: 100%; overflow: hidden; }}
        #container {{ width: 100%; height: 100%; cursor: grab; }}
        #container:active {{ cursor: grabbing; }}
        #info {{
            position: absolute; top: 10px; left: 10px;
            background: rgba(0,0,0,0.8); color: white;
            padding: 15px; border-radius: 8px;
            font-family: Arial, sans-serif; font-size: 14px;
            max-width: 300px; z-index: 100;
        }}
        #info h3 {{ margin: 0 0 10px 0; }}
        #info p {{ margin: 5px 0; opacity: 0.8; }}
        #controls {{
            position: absolute; bottom: 10px; left: 10px;
            background: rgba(0,0,0,0.7); color: white;
            padding: 10px 15px; border-radius: 8px;
            font-family: Arial, sans-serif; font-size: 12px;
        }}
        #sun-controls {{
            position: absolute; bottom: 10px; right: 10px;
            background: rgba(0,0,0,0.85); color: white;
            padding: 15px 20px; border-radius: 8px;
            font-family: Arial, sans-serif; font-size: 13px;
            z-index: 100; min-width: 280px;
        }}
        #sun-controls h4 {{
            margin: 0 0 12px 0; font-size: 14px; color: #ffd700;
            display: flex; align-items: center; gap: 8px;
        }}
        .slider-group {{ margin: 12px 0; }}
        .slider-group label {{
            display: flex; justify-content: space-between;
            margin-bottom: 6px; font-size: 12px;
        }}
        .slider-group input[type="range"] {{
            width: 100%; height: 6px; border-radius: 3px;
            background: #444; outline: none; -webkit-appearance: none;
        }}
        .slider-group input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none; width: 18px; height: 18px;
            border-radius: 50%; background: #ffd700; cursor: pointer;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        }}
        .sun-info {{
            margin-top: 12px; padding-top: 12px;
            border-top: 1px solid #444; font-size: 11px; color: #aaa;
        }}
        .sun-info div {{ display: flex; justify-content: space-between; margin: 4px 0; }}
        .sun-info span.value {{ color: #ffd700; font-family: monospace; }}
        #tooltip {{
            position: absolute; background: rgba(0,0,0,0.9); color: white;
            padding: 12px 16px; border-radius: 8px;
            font-family: Arial, sans-serif; font-size: 13px;
            pointer-events: none; z-index: 200; display: none;
            max-width: 350px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        #tooltip h4 {{ margin: 0 0 8px 0; color: #4fc3f7; font-size: 15px; }}
        #tooltip .tag-row {{ display: flex; margin: 3px 0; font-size: 12px; }}
        #tooltip .tag-key {{ color: #aaa; min-width: 100px; }}
        #tooltip .tag-value {{ color: #fff; }}
        #tooltip .type-badge {{
            display: inline-block; background: #4fc3f7; color: #000;
            padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-bottom: 8px;
        }}
        #tooltip .coord-row {{
            display: flex; align-items: center; margin: 6px 0; padding: 6px 8px;
            background: rgba(255,255,255,0.1); border-radius: 4px;
            font-family: monospace; font-size: 12px;
        }}
        #tooltip .coord-value {{ flex: 1; color: #4fc3f7; }}
        #tooltip .copy-btn {{
            background: #4fc3f7; color: #000; border: none;
            padding: 4px 10px; border-radius: 4px; cursor: pointer;
            font-size: 11px; font-weight: bold; margin-left: 8px; pointer-events: auto;
        }}
        #tooltip .copy-btn:hover {{ background: #81d4fa; }}
        #tooltip .copy-btn.copied {{ background: #4caf50; color: #fff; }}
        #layer-controls {{
            position: absolute; top: 10px; right: 10px;
            background: rgba(0,0,0,0.8); padding: 12px 15px; border-radius: 8px;
            font-family: Arial, sans-serif; font-size: 13px; color: white; z-index: 100;
        }}
        #layer-controls h4 {{
            margin: 0 0 10px 0; font-size: 12px; color: #888;
            text-transform: uppercase; letter-spacing: 1px;
        }}
        .layer-toggle {{ display: flex; align-items: center; margin: 8px 0; cursor: pointer; }}
        .layer-toggle input {{ display: none; }}
        .toggle-switch {{
            width: 36px; height: 20px; background: #444; border-radius: 10px;
            position: relative; margin-right: 10px; transition: background 0.3s;
        }}
        .toggle-switch::after {{
            content: ''; position: absolute; width: 16px; height: 16px;
            background: #888; border-radius: 50%; top: 2px; left: 2px; transition: all 0.3s;
        }}
        .layer-toggle input:checked + .toggle-switch {{ background: #4fc3f7; }}
        .layer-toggle input:checked + .toggle-switch::after {{ left: 18px; background: #fff; }}
        .layer-label {{ display: flex; align-items: center; flex: 1; }}
        .layer-icon {{ margin-right: 6px; }}
        .layer-count {{ margin-left: auto; color: #888; font-size: 11px; }}
        #animate-btn {{
            width: 100%; margin-top: 10px; padding: 8px 12px;
            background: #ffd700; color: #000; border: none; border-radius: 4px;
            cursor: pointer; font-weight: bold; font-size: 12px;
        }}
        #animate-btn:hover {{ background: #ffed4a; }}
        #animate-btn.playing {{ background: #ff6b6b; }}
    </style>
</head>
<body>
    <div id="container"></div>
    <div id="info">
        <h3>☀️ {title}</h3>
        <p>Buildings: {num_buildings}</p>
        <p>Roads: {num_roads}</p>
        <p>Bike lanes: {num_bikelanes}</p>
        <p>Trees: {num_trees}</p>
        <p style="margin-top: 10px; font-size: 12px; opacity: 0.6;">Adjust sun position with sliders</p>
    </div>
    <div id="controls">🖱️ Drag to rotate | Scroll to zoom | Right-drag to pan</div>
    <div id="layer-controls">
        <h4>Layers</h4>
        <label class="layer-toggle">
            <input type="checkbox" id="toggle-buildings" checked>
            <span class="toggle-switch"></span>
            <span class="layer-label"><span class="layer-icon">🏢</span> Buildings<span class="layer-count">{num_buildings}</span></span>
        </label>
        <label class="layer-toggle">
            <input type="checkbox" id="toggle-roads" checked>
            <span class="toggle-switch"></span>
            <span class="layer-label"><span class="layer-icon">🛣️</span> Roads<span class="layer-count">{num_roads}</span></span>
        </label>
        <label class="layer-toggle">
            <input type="checkbox" id="toggle-bikelanes" checked>
            <span class="toggle-switch"></span>
            <span class="layer-label"><span class="layer-icon">🚴</span> Bike lanes<span class="layer-count">{num_bikelanes}</span></span>
        </label>
        <label class="layer-toggle">
            <input type="checkbox" id="toggle-trees" checked>
            <span class="toggle-switch"></span>
            <span class="layer-label"><span class="layer-icon">🌳</span> Trees<span class="layer-count">{num_trees}</span></span>
        </label>
    </div>
    <div id="sun-controls">
        <h4>☀️ Sun Position</h4>
        <div class="slider-group">
            <label><span>Hour</span><span id="hour-value">12:00</span></label>
            <input type="range" id="hour-slider" min="0" max="24" step="0.25" value="12">
        </div>
        <div class="slider-group">
            <label><span>Month</span><span id="month-value">June</span></label>
            <input type="range" id="month-slider" min="1" max="12" step="1" value="6">
        </div>
        <div class="slider-group">
            <label><span>Day</span><span id="day-value">21</span></label>
            <input type="range" id="day-slider" min="1" max="31" step="1" value="21">
        </div>
        <div class="sun-info">
            <div><span>Azimuth:</span><span class="value" id="azimuth-value">180°</span></div>
            <div><span>Altitude:</span><span class="value" id="altitude-value">60°</span></div>
            <div><span>Location:</span><span class="value">{center_lat:.4f}°, {center_lon:.4f}°</span></div>
        </div>
        <button id="animate-btn">▶ Animate Day</button>
    </div>
    <div id="tooltip"></div>

    <script type="importmap">
    {{
        "imports": {{
            "three": "{THREE_JS}",
            "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
        }}
    }}
    </script>

    <script type="module">
        import * as THREE from 'three';
        import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';

        const buildings = {buildings_json};
        const roads = {roads_json};
        const water = {water_json};
        const trees = {trees_json};
        const bikelanes = {bikelanes_json};
        const bounds = {bounds_json};
        const centerLat = {center_lat};
        const centerLon = {center_lon};
        const sunLatitude = {sun_latitude};
        const metersPerDegLat = {meters_per_deg_lat};
        const metersPerDegLon = {meters_per_deg_lon};
        const sceneScale = {scale};

        function geoToScene(lon, lat) {{
            const x = (lon - centerLon) * metersPerDegLon;
            const z = -(lat - centerLat) * metersPerDegLat;
            return {{ x, z }};
        }}

        // Sun position calculation
        function calculateSunPosition(hour, month, day, latitude) {{
            const daysInMonth = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
            let dayOfYear = day;
            for (let i = 1; i < month; i++) dayOfYear += daysInMonth[i];

            const declination = 23.45 * Math.sin(2 * Math.PI * (284 + dayOfYear) / 365);
            const decRad = declination * Math.PI / 180;
            const latRad = latitude * Math.PI / 180;
            const hourAngle = (hour - 12) * 15;
            const hourRad = hourAngle * Math.PI / 180;

            const sinAlt = Math.sin(latRad) * Math.sin(decRad) +
                           Math.cos(latRad) * Math.cos(decRad) * Math.cos(hourRad);
            const altitude = Math.asin(sinAlt) * 180 / Math.PI;

            const cosAz = (Math.sin(decRad) - Math.sin(latRad) * sinAlt) /
                          (Math.cos(latRad) * Math.cos(Math.asin(sinAlt)));
            let azimuth = Math.acos(Math.max(-1, Math.min(1, cosAz))) * 180 / Math.PI;
            if (hour > 12) azimuth = 360 - azimuth;

            return {{ azimuth, altitude }};
        }}

        const container = document.getElementById('container');
        const scene = new THREE.Scene();
        scene.background = new THREE.Color({rgb_to_hex(*bg_color)});

        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 1, sceneScale * 10);
        camera.position.set(sceneScale * 0.3, sceneScale * 0.4, sceneScale * 0.3);

        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(renderer.domElement);

        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.maxPolarAngle = Math.PI / 2.1;

        // Lighting for sun study
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.2);
        scene.add(ambientLight);

        const hemisphereLight = new THREE.HemisphereLight(0x87ceeb, 0x8b7355, 0.15);
        scene.add(hemisphereLight);

        const sunLight = new THREE.DirectionalLight(0xfff5e6, 2.0);
        sunLight.castShadow = true;
        sunLight.shadow.mapSize.width = 4096;
        sunLight.shadow.mapSize.height = 4096;
        sunLight.shadow.camera.near = 1;
        sunLight.shadow.camera.far = sceneScale * 5;
        const shadowSize = sceneScale * 1.5;
        sunLight.shadow.camera.left = -shadowSize;
        sunLight.shadow.camera.right = shadowSize;
        sunLight.shadow.camera.top = shadowSize;
        sunLight.shadow.camera.bottom = -shadowSize;
        sunLight.shadow.bias = -0.0001;
        scene.add(sunLight);

        // Sun sphere
        const sunSphere = new THREE.Mesh(
            new THREE.SphereGeometry(sceneScale * 0.02, 16, 16),
            new THREE.MeshBasicMaterial({{ color: 0xffdd00 }})
        );
        scene.add(sunSphere);

        // Ground
        const groundGeometry = new THREE.PlaneGeometry(sceneScale * 2, sceneScale * 2);
        const groundMaterial = new THREE.MeshLambertMaterial({{
            color: {rgb_to_hex(*ground_color)}, side: THREE.DoubleSide
        }});
        const ground = new THREE.Mesh(groundGeometry, groundMaterial);
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = -0.5;
        ground.receiveShadow = true;
        scene.add(ground);

        const gridHelper = new THREE.GridHelper(sceneScale, 50, {grid_color}, {grid_color});
        gridHelper.position.y = -0.1;
        scene.add(gridHelper);

        const clickableObjects = [];
        const layers = {{ buildings: [], roads: [], bikelanes: [], trees: [] }};

        const buildingMaterial = new THREE.MeshLambertMaterial({{ color: {rgb_to_hex(*building_fill_3d)}, side: THREE.DoubleSide }});
        const buildingEdgeMaterial = new THREE.LineBasicMaterial({{ color: {rgb_to_hex(*building_edge_3d)}, linewidth: 2 }});
        const highlightMaterial = new THREE.MeshLambertMaterial({{ color: 0x4fc3f7, side: THREE.DoubleSide }});

        buildings.forEach((building, index) => {{
            if (building.coords.length < 4) return;
            const shape = new THREE.Shape();
            const firstPoint = geoToScene(building.coords[0][0], building.coords[0][1]);
            shape.moveTo(firstPoint.x, -firstPoint.z);
            for (let i = 1; i < building.coords.length; i++) {{
                const point = geoToScene(building.coords[i][0], building.coords[i][1]);
                shape.lineTo(point.x, -point.z);
            }}
            shape.closePath();
            const geometry = new THREE.ExtrudeGeometry(shape, {{ depth: building.height, bevelEnabled: false }});
            const mesh = new THREE.Mesh(geometry, buildingMaterial.clone());
            mesh.rotation.x = -Math.PI / 2;
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            mesh.userData = {{ type: 'building', data: building, index }};
            scene.add(mesh);
            clickableObjects.push(mesh);
            const edges = new THREE.EdgesGeometry(geometry);
            const wireframe = new THREE.LineSegments(edges, buildingEdgeMaterial);
            wireframe.rotation.x = -Math.PI / 2;
            wireframe.position.y = 0.01;
            scene.add(wireframe);
            layers.buildings.push(mesh, wireframe);
        }});

        const roadColors = {road_colors_js};
        roads.forEach((road, index) => {{
            if (road.coords.length < 2) return;
            const points = road.coords.map(c => {{
                const pos = geoToScene(c[0], c[1]);
                return new THREE.Vector3(pos.x, 0.5, pos.z);
            }});
            const curve = new THREE.CatmullRomCurve3(points, false);
            const tubeGeometry = new THREE.TubeGeometry(curve, points.length * 2, Math.max(1, road.width * 0.8), 4, false);
            const roadMaterial = new THREE.MeshLambertMaterial({{ color: roadColors[road.type] || roadColors.default }});
            const roadMesh = new THREE.Mesh(tubeGeometry, roadMaterial);
            roadMesh.receiveShadow = true;
            roadMesh.userData = {{ type: 'road', data: road, index }};
            scene.add(roadMesh);
            clickableObjects.push(roadMesh);
            layers.roads.push(roadMesh);
        }});

        const bikeLaneColor = 0xff00ff;
        bikelanes.forEach((lane, index) => {{
            if (lane.coords.length < 2) return;
            const points = lane.coords.map(c => {{
                const pos = geoToScene(c[0], c[1]);
                return new THREE.Vector3(pos.x, 1.0, pos.z);
            }});
            const curve = new THREE.CatmullRomCurve3(points, false);
            const tubeGeometry = new THREE.TubeGeometry(curve, points.length * 2, 1.5, 4, false);
            const laneMaterial = new THREE.MeshLambertMaterial({{ color: bikeLaneColor }});
            const laneMesh = new THREE.Mesh(tubeGeometry, laneMaterial);
            laneMesh.receiveShadow = true;
            laneMesh.castShadow = true;
            laneMesh.userData = {{ type: 'bikelane', data: lane, index }};
            scene.add(laneMesh);
            clickableObjects.push(laneMesh);
            layers.bikelanes.push(laneMesh);
        }});

        function getTreeColor(tree) {{
            if (tree.leaf_type === 'needleleaved') return 0x1a5a2a;
            if (tree.leaf_cycle === 'evergreen') return 0x228b22;
            return 0x32cd32;
        }}

        trees.forEach((tree, index) => {{
            const pos = geoToScene(tree.lon, tree.lat);
            const treeHeight = tree.height || 8;
            const crownDiameter = tree.crown_diameter || treeHeight * 0.6;
            const trunkHeight = treeHeight * 0.3;
            const crownHeight = treeHeight * 0.7;
            const treeColor = getTreeColor(tree);

            const trunkGeometry = new THREE.CylinderGeometry(crownDiameter * 0.07, crownDiameter * 0.1, trunkHeight, 8);
            const trunk = new THREE.Mesh(trunkGeometry, new THREE.MeshLambertMaterial({{ color: 0x8b4513 }}));
            trunk.position.set(pos.x, trunkHeight / 2, pos.z);
            trunk.castShadow = true;
            scene.add(trunk);

            let crown;
            if (tree.leaf_type === 'needleleaved') {{
                const coneGeometry = new THREE.ConeGeometry(crownDiameter / 2, crownHeight, 8);
                crown = new THREE.Mesh(coneGeometry, new THREE.MeshLambertMaterial({{ color: treeColor }}));
                crown.position.set(pos.x, trunkHeight + crownHeight / 2, pos.z);
            }} else {{
                const sphereGeometry = new THREE.SphereGeometry(crownDiameter / 2, 12, 8);
                crown = new THREE.Mesh(sphereGeometry, new THREE.MeshLambertMaterial({{ color: treeColor }}));
                crown.position.set(pos.x, trunkHeight + crownDiameter / 2 * 0.8, pos.z);
            }}
            crown.castShadow = true;
            crown.userData = {{ type: 'tree', data: tree, index }};
            scene.add(crown);
            clickableObjects.push(crown);
            layers.trees.push(trunk, crown);
        }});

        // Interaction
        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2();
        const tooltip = document.getElementById('tooltip');
        let selectedObject = null, originalMaterial = null;

        window.copyToClipboard = function(text, btn) {{
            navigator.clipboard.writeText(text).then(() => {{
                btn.textContent = '✓ Copied!';
                btn.classList.add('copied');
                setTimeout(() => {{ btn.textContent = '📋 Copy'; btn.classList.remove('copied'); }}, 2000);
            }});
        }};
        window.copyCoords = (lat, lon, btn) => copyToClipboard(`${{lat}}, ${{lon}}`, btn);

        function showTooltip(object, event) {{
            const data = object.userData.data;
            const type = object.userData.type;
            let html = '';

            if (type === 'building') {{
                html = `<h4>🏢 ${{data.name || 'Building'}}</h4><span class="type-badge">${{data.type}}</span>`;
                html += `<div style="margin-top:8px;border-top:1px solid #444;padding-top:8px;">`;
                html += `<div class="tag-row"><span class="tag-key">Height:</span><span class="tag-value">${{data.height.toFixed(1)}}m</span></div>`;
                html += `<div class="tag-row"><span class="tag-key">OSM ID:</span><span class="tag-value">${{data.id}}</span></div></div>`;
                html += `<div class="coord-row"><span class="coord-value">📍 ${{data.lat}}, ${{data.lon}}</span>`;
                html += `<button class="copy-btn" onclick="copyCoords(${{data.lat}}, ${{data.lon}}, this)">📋 Copy</button></div>`;
            }} else if (type === 'road') {{
                html = `<h4>🛣️ ${{data.name || 'Road'}}</h4><span class="type-badge">${{data.type}}</span>`;
                html += `<div style="margin-top:8px;border-top:1px solid #444;padding-top:8px;">`;
                html += `<div class="tag-row"><span class="tag-key">OSM ID:</span><span class="tag-value">${{data.id}}</span></div></div>`;
                html += `<div class="coord-row"><span class="coord-value">📍 ${{data.lat}}, ${{data.lon}}</span>`;
                html += `<button class="copy-btn" onclick="copyCoords(${{data.lat}}, ${{data.lon}}, this)">📋 Copy</button></div>`;
            }} else if (type === 'tree') {{
                html = `<h4>🌳 ${{data.name || 'Tree'}}</h4><span class="type-badge" style="background:#228b22;color:#fff">${{data.type}}</span>`;
                html += `<div style="margin-top:8px;border-top:1px solid #444;padding-top:8px;">`;
                html += `<div class="tag-row"><span class="tag-key">Height:</span><span class="tag-value">${{data.height.toFixed(1)}}m</span></div></div>`;
                html += `<div class="coord-row"><span class="coord-value">📍 ${{data.lat}}, ${{data.lon}}</span>`;
                html += `<button class="copy-btn" onclick="copyCoords(${{data.lat}}, ${{data.lon}}, this)">📋 Copy</button></div>`;
            }} else if (type === 'bikelane') {{
                html = `<h4>🚴 ${{data.name || 'Bike Lane'}}</h4><span class="type-badge" style="background:#ff00ff;color:#fff">${{data.type}}</span>`;
                html += `<div style="margin-top:8px;border-top:1px solid #444;padding-top:8px;">`;
                html += `<div class="tag-row"><span class="tag-key">OSM ID:</span><span class="tag-value">${{data.id}}</span></div></div>`;
                html += `<div class="coord-row"><span class="coord-value">📍 ${{data.lat}}, ${{data.lon}}</span>`;
                html += `<button class="copy-btn" onclick="copyCoords(${{data.lat}}, ${{data.lon}}, this)">📋 Copy</button></div>`;
            }}

            tooltip.innerHTML = html;
            tooltip.style.display = 'block';
            tooltip.style.left = (event.clientX + 15) + 'px';
            tooltip.style.top = (event.clientY + 15) + 'px';
        }}

        function hideTooltip() {{ tooltip.style.display = 'none'; }}

        function onClick(event) {{
            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(clickableObjects);
            if (selectedObject && originalMaterial) selectedObject.material = originalMaterial;
            const hit = intersects.find(i => i.object.visible);
            if (hit) {{
                const obj = hit.object;
                originalMaterial = obj.material;
                if (obj.userData.type === 'building') {{
                    obj.material = highlightMaterial.clone();
                }} else {{
                    const c = obj.material.color;
                    const bright = new THREE.Color(Math.min(1, c.r + 0.4), Math.min(1, c.g + 0.4), Math.min(1, c.b + 0.4));
                    obj.material = new THREE.MeshLambertMaterial({{ color: bright, emissive: bright, emissiveIntensity: 0.5 }});
                }}
                selectedObject = obj;
                showTooltip(obj, event);
            }} else {{
                hideTooltip();
                selectedObject = null;
                originalMaterial = null;
            }}
        }}

        container.addEventListener('click', onClick);
        container.addEventListener('mousemove', (e) => {{
            mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
            raycaster.setFromCamera(mouse, camera);
            container.style.cursor = raycaster.intersectObjects(clickableObjects).some(i => i.object.visible) ? 'pointer' : 'grab';
        }});

        // Sun position update
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'June', 'July', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

        function updateSunPosition() {{
            const hour = parseFloat(document.getElementById('hour-slider').value);
            const month = parseInt(document.getElementById('month-slider').value);
            const day = parseInt(document.getElementById('day-slider').value);

            const h = Math.floor(hour);
            const m = Math.round((hour - h) * 60);
            document.getElementById('hour-value').textContent = `${{h.toString().padStart(2, '0')}}:${{m.toString().padStart(2, '0')}}`;
            document.getElementById('month-value').textContent = months[month - 1];
            document.getElementById('day-value').textContent = day;

            const {{ azimuth, altitude }} = calculateSunPosition(hour, month, day, sunLatitude);
            document.getElementById('azimuth-value').textContent = `${{azimuth.toFixed(1)}}°`;
            document.getElementById('altitude-value').textContent = `${{altitude.toFixed(1)}}°`;

            const azRad = azimuth * Math.PI / 180;
            const altRad = Math.max(0, altitude) * Math.PI / 180;
            const dist = sceneScale * 2;
            const x = dist * Math.sin(azRad) * Math.cos(altRad);
            const y = dist * Math.sin(altRad);
            const z = dist * Math.cos(azRad) * Math.cos(altRad);

            sunLight.position.set(x, y, z);
            sunSphere.position.set(x, y, z);

            if (altitude < 0) {{
                sunLight.intensity = 0;
                ambientLight.intensity = 0.1;
                scene.background = new THREE.Color(0x0a0a1a);
            }} else if (altitude < 10) {{
                sunLight.intensity = altitude / 10 * 1.5;
                ambientLight.intensity = 0.15;
                sunLight.color.setHex(0xff8844);
                scene.background = new THREE.Color(0x2a1a1a);
            }} else {{
                sunLight.intensity = 2.0;
                ambientLight.intensity = 0.2;
                sunLight.color.setHex(0xfff5e6);
                scene.background = new THREE.Color({rgb_to_hex(*bg_color)});
            }}
        }}

        document.getElementById('hour-slider').addEventListener('input', updateSunPosition);
        document.getElementById('month-slider').addEventListener('input', updateSunPosition);
        document.getElementById('day-slider').addEventListener('input', updateSunPosition);
        updateSunPosition();

        // Day animation
        let isAnimating = false, animationId = null;
        document.getElementById('animate-btn').addEventListener('click', () => {{
            const btn = document.getElementById('animate-btn');
            if (isAnimating) {{
                isAnimating = false;
                btn.textContent = '▶ Animate Day';
                btn.classList.remove('playing');
                if (animationId) cancelAnimationFrame(animationId);
            }} else {{
                isAnimating = true;
                btn.textContent = '■ Stop';
                btn.classList.add('playing');
                let hour = 5;
                function animateDay() {{
                    if (!isAnimating) return;
                    hour += 0.05;
                    if (hour > 21) hour = 5;
                    document.getElementById('hour-slider').value = hour;
                    updateSunPosition();
                    animationId = requestAnimationFrame(animateDay);
                }}
                animateDay();
            }}
        }});

        // Layer toggles
        function toggleLayer(name, visible) {{ layers[name].forEach(o => o.visible = visible); }}
        document.getElementById('toggle-buildings').addEventListener('change', e => toggleLayer('buildings', e.target.checked));
        document.getElementById('toggle-roads').addEventListener('change', e => toggleLayer('roads', e.target.checked));
        document.getElementById('toggle-bikelanes').addEventListener('change', e => toggleLayer('bikelanes', e.target.checked));
        document.getElementById('toggle-trees').addEventListener('change', e => toggleLayer('trees', e.target.checked));

        function animate() {{
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }}
        animate();

        window.addEventListener('resize', () => {{
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }});
    </script>
</body>
</html>'''
        return html_content
