"""
WebGL HTML generator for standard 3D map visualization.

Generates self-contained HTML files with Three.js WebGL visualization.
"""

import json
import math
from typing import Dict, Any

from .data_collector import WebGLDataCollector
from .styles import WebGL3DStyle, get_3d_style, rgb_to_hex, generate_road_colors_js


# Three.js CDN URL
THREE_JS = "https://unpkg.com/three@0.160.0/build/three.module.js"


class WebGLHTMLGenerator:
    """
    Generates interactive 3D WebGL HTML from collected OSM data.
    """

    def __init__(self, data: WebGLDataCollector, style: WebGL3DStyle,
                 style_name: str = "default"):
        """
        Initialize HTML generator.

        Args:
            data: Collected OSM data
            style: 3D style configuration
            style_name: Name of the style preset
        """
        self.data = data
        self.style = style
        self.style_name = style_name

    def generate(self, title: str = "OSMFast 3D Map") -> str:
        """
        Generate complete HTML document.

        Args:
            title: Page title

        Returns:
            Complete HTML document as string
        """
        # Calculate center and scale
        bounds = self.data.bounds
        center_lat = (bounds["min_lat"] + bounds["max_lat"]) / 2
        center_lon = (bounds["min_lon"] + bounds["max_lon"]) / 2

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
        water_color = (170, 211, 223)  # Default water color

        # Lighting
        ambient_intensity = s.ambient_intensity
        directional_intensity = s.directional_intensity
        hemisphere_intensity = s.hemisphere_intensity
        hemisphere_ground = s.hemisphere_ground

        # Road colors
        road_colors_js = generate_road_colors_js(s.road_colors)

        # Counts
        num_buildings = len(self.data.buildings)
        num_roads = len(self.data.roads)
        num_pois = len(self.data.pois)
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
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-family: Arial, sans-serif;
            font-size: 14px;
            max-width: 300px;
            z-index: 100;
        }}
        #info h3 {{ margin: 0 0 10px 0; }}
        #info p {{ margin: 5px 0; opacity: 0.8; }}
        #controls {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 10px 15px;
            border-radius: 8px;
            font-family: Arial, sans-serif;
            font-size: 12px;
        }}
        #stats {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 10px 15px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 12px;
        }}
        #tooltip {{
            position: absolute;
            background: rgba(0,0,0,0.9);
            color: white;
            padding: 12px 16px;
            border-radius: 8px;
            font-family: Arial, sans-serif;
            font-size: 13px;
            pointer-events: none;
            z-index: 200;
            display: none;
            max-width: 350px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        #tooltip h4 {{
            margin: 0 0 8px 0;
            color: #4fc3f7;
            font-size: 15px;
        }}
        #tooltip .tag-row {{
            display: flex;
            margin: 3px 0;
            font-size: 12px;
        }}
        #tooltip .tag-key {{
            color: #aaa;
            min-width: 100px;
        }}
        #tooltip .tag-value {{
            color: #fff;
        }}
        #tooltip .type-badge {{
            display: inline-block;
            background: #4fc3f7;
            color: #000;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            margin-bottom: 8px;
        }}
        #tooltip .coord-row {{
            display: flex;
            align-items: center;
            margin: 6px 0;
            padding: 6px 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
        }}
        #tooltip .coord-value {{
            flex: 1;
            color: #4fc3f7;
        }}
        #tooltip .copy-btn {{
            background: #4fc3f7;
            color: #000;
            border: none;
            padding: 4px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            font-weight: bold;
            margin-left: 8px;
            pointer-events: auto;
        }}
        #tooltip .copy-btn:hover {{
            background: #81d4fa;
        }}
        #tooltip .copy-btn.copied {{
            background: #4caf50;
            color: #fff;
        }}
        #layer-controls {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(0,0,0,0.8);
            padding: 12px 15px;
            border-radius: 8px;
            font-family: Arial, sans-serif;
            font-size: 13px;
            color: white;
            z-index: 100;
        }}
        #layer-controls h4 {{
            margin: 0 0 10px 0;
            font-size: 12px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .layer-toggle {{
            display: flex;
            align-items: center;
            margin: 8px 0;
            cursor: pointer;
        }}
        .layer-toggle input {{
            display: none;
        }}
        .toggle-switch {{
            width: 36px;
            height: 20px;
            background: #444;
            border-radius: 10px;
            position: relative;
            margin-right: 10px;
            transition: background 0.3s;
        }}
        .toggle-switch::after {{
            content: '';
            position: absolute;
            width: 16px;
            height: 16px;
            background: #888;
            border-radius: 50%;
            top: 2px;
            left: 2px;
            transition: all 0.3s;
        }}
        .layer-toggle input:checked + .toggle-switch {{
            background: #4fc3f7;
        }}
        .layer-toggle input:checked + .toggle-switch::after {{
            left: 18px;
            background: #fff;
        }}
        .layer-label {{
            display: flex;
            align-items: center;
            flex: 1;
        }}
        .layer-icon {{
            margin-right: 6px;
        }}
        .layer-count {{
            margin-left: auto;
            color: #888;
            font-size: 11px;
        }}
        #fly-btn {{
            position: absolute;
            bottom: 60px;
            left: 10px;
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            font-family: Arial, sans-serif;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(17, 153, 142, 0.4);
            transition: all 0.3s;
            z-index: 100;
        }}
        #fly-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(17, 153, 142, 0.5);
        }}
        #fly-btn.active {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        #fly-instructions {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0,0,0,0.9);
            color: white;
            padding: 40px 60px;
            border-radius: 16px;
            font-family: Arial, sans-serif;
            text-align: center;
            z-index: 300;
            display: none;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }}
        #fly-instructions h2 {{
            margin: 0 0 20px 0;
            font-size: 24px;
            color: #38ef7d;
        }}
        #fly-instructions .keys {{
            display: flex;
            justify-content: center;
            gap: 10px;
            margin: 20px 0;
        }}
        #fly-instructions .key {{
            width: 50px;
            height: 50px;
            background: #333;
            border: 2px solid #555;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
        }}
        #fly-instructions .key.wide {{
            width: 100px;
        }}
        #fly-instructions .key-row {{
            display: flex;
            justify-content: center;
            gap: 10px;
            margin: 8px 0;
        }}
        #fly-instructions p {{
            margin: 10px 0;
            opacity: 0.8;
        }}
        #fly-instructions .start-btn {{
            background: #38ef7d;
            color: #000;
            border: none;
            padding: 15px 40px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 20px;
        }}
        #fly-instructions .start-btn:hover {{
            background: #5fff9e;
        }}
        #fly-hud {{
            position: absolute;
            bottom: 60px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 12px;
            display: none;
            z-index: 100;
            white-space: nowrap;
        }}
        #crosshair {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 20px;
            height: 20px;
            display: none;
            z-index: 200;
            pointer-events: none;
        }}
        #crosshair::before, #crosshair::after {{
            content: '';
            position: absolute;
            background: rgba(255,255,255,0.8);
        }}
        #crosshair::before {{
            width: 2px;
            height: 20px;
            left: 9px;
            top: 0;
        }}
        #crosshair::after {{
            width: 20px;
            height: 2px;
            top: 9px;
            left: 0;
        }}
    </style>
</head>
<body>
    <div id="container"></div>
    <div id="info">
        <h3>🏙️ {title}</h3>
        <p>Buildings: {num_buildings}</p>
        <p>Roads: {num_roads}</p>
        <p>Bike lanes: {num_bikelanes}</p>
        <p>POIs: {num_pois}</p>
        <p>Trees: {num_trees}</p>
        <p style="margin-top: 10px; font-size: 12px; opacity: 0.6;">Click objects for details</p>
    </div>
    <div id="controls">
        🖱️ Drag to rotate | Scroll to zoom | Right-drag to pan | Click for info
    </div>
    <div id="layer-controls">
        <h4>Layers</h4>
        <label class="layer-toggle">
            <input type="checkbox" id="toggle-buildings" checked>
            <span class="toggle-switch"></span>
            <span class="layer-label">
                <span class="layer-icon">🏢</span> Buildings
                <span class="layer-count">{num_buildings}</span>
            </span>
        </label>
        <label class="layer-toggle">
            <input type="checkbox" id="toggle-roads" checked>
            <span class="toggle-switch"></span>
            <span class="layer-label">
                <span class="layer-icon">🛣️</span> Roads
                <span class="layer-count">{num_roads}</span>
            </span>
        </label>
        <label class="layer-toggle">
            <input type="checkbox" id="toggle-pois" checked>
            <span class="toggle-switch"></span>
            <span class="layer-label">
                <span class="layer-icon">📍</span> POIs
                <span class="layer-count">{num_pois}</span>
            </span>
        </label>
        <label class="layer-toggle">
            <input type="checkbox" id="toggle-trees" checked>
            <span class="toggle-switch"></span>
            <span class="layer-label">
                <span class="layer-icon">🌳</span> Trees
                <span class="layer-count">{num_trees}</span>
            </span>
        </label>
        <label class="layer-toggle">
            <input type="checkbox" id="toggle-bikelanes" checked>
            <span class="toggle-switch"></span>
            <span class="layer-label">
                <span class="layer-icon">🚴</span> Bike Lanes
                <span class="layer-count">{num_bikelanes}</span>
            </span>
        </label>
    </div>
    <div id="tooltip"></div>
    <button id="fly-btn">✈️ Fly-Through Mode</button>
    <div id="fly-instructions">
        <h2>✈️ Fly-Through Controls</h2>
        <div class="key-row">
            <div class="key">W</div>
        </div>
        <div class="key-row">
            <div class="key">A</div>
            <div class="key">S</div>
            <div class="key">D</div>
        </div>
        <div class="key-row" style="margin-top:15px;">
            <div class="key wide">SPACE</div>
            <div class="key wide">SHIFT</div>
        </div>
        <p>WASD to fly forward/backward/strafe</p>
        <p>SPACE to fly up • SHIFT to fly down</p>
        <p>Mouse to look around • Scroll to adjust speed</p>
        <p>ESC to exit fly-through mode</p>
        <button class="start-btn" id="start-fly">Click to Start Flying</button>
    </div>
    <div id="fly-hud">
        <span id="fly-coords"></span> | Alt: <span id="fly-alt"></span>m | Speed: <span id="fly-speed"></span> | ESC to exit
    </div>
    <div id="crosshair"></div>

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
        import {{ PointerLockControls }} from 'three/addons/controls/PointerLockControls.js';

        // Data
        const buildings = {buildings_json};
        const roads = {roads_json};
        const water = {water_json};
        const pois = {pois_json};
        const trees = {trees_json};
        const bikelanes = {bikelanes_json};

        // Map bounds and center
        const bounds = {bounds_json};
        const centerLat = {center_lat};
        const centerLon = {center_lon};
        const metersPerDegLat = {meters_per_deg_lat};
        const metersPerDegLon = {meters_per_deg_lon};
        const sceneScale = {scale};

        // Convert geo coords to scene coords
        function geoToScene(lon, lat) {{
            const x = (lon - centerLon) * metersPerDegLon;
            const z = -(lat - centerLat) * metersPerDegLat;
            return {{ x, z }};
        }}

        // Setup scene
        const container = document.getElementById('container');
        const scene = new THREE.Scene();
        scene.background = new THREE.Color({rgb_to_hex(*bg_color)});

        // Camera
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 1, sceneScale * 10);
        camera.position.set(sceneScale * 0.3, sceneScale * 0.4, sceneScale * 0.3);

        // Renderer
        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.shadowMap.enabled = true;
        container.appendChild(renderer.domElement);

        // Controls
        const orbitControls = new OrbitControls(camera, renderer.domElement);
        orbitControls.enableDamping = true;
        orbitControls.dampingFactor = 0.05;
        orbitControls.maxPolarAngle = Math.PI / 2.1;

        // Fly-through controls
        const flyControls = new PointerLockControls(camera, document.body);
        let isFlyMode = false;
        let flySpeed = 100;
        const minFlySpeed = 10;
        const maxFlySpeed = 500;

        const moveState = {{
            forward: false,
            backward: false,
            left: false,
            right: false,
            up: false,
            down: false
        }};

        // Fly-through UI elements
        const flyBtn = document.getElementById('fly-btn');
        const flyInstructions = document.getElementById('fly-instructions');
        const startFlyBtn = document.getElementById('start-fly');
        const flyHud = document.getElementById('fly-hud');
        const flyCoords = document.getElementById('fly-coords');
        const flyAlt = document.getElementById('fly-alt');
        const flySpeedDisplay = document.getElementById('fly-speed');
        const crosshair = document.getElementById('crosshair');

        function sceneToGeo(x, z) {{
            const lon = (x / metersPerDegLon) + centerLon;
            const lat = (-z / metersPerDegLat) + centerLat;
            return {{ lat: lat.toFixed(6), lon: lon.toFixed(6) }};
        }}

        function enterFlyMode() {{
            flyInstructions.style.display = 'block';
        }}

        function startFlyMode() {{
            flyInstructions.style.display = 'none';
            flyControls.lock();
        }}

        function exitFlyMode() {{
            isFlyMode = false;
            flyBtn.classList.remove('active');
            flyBtn.textContent = '✈️ Fly-Through Mode';
            flyHud.style.display = 'none';
            crosshair.style.display = 'none';
            orbitControls.enabled = true;

            // Reset camera to orbit view
            camera.position.set(sceneScale * 0.3, sceneScale * 0.4, sceneScale * 0.3);
            camera.lookAt(0, 0, 0);
            orbitControls.target.set(0, 0, 0);
            orbitControls.update();
        }}

        flyBtn.addEventListener('click', enterFlyMode);
        startFlyBtn.addEventListener('click', startFlyMode);

        flyControls.addEventListener('lock', () => {{
            isFlyMode = true;
            flyBtn.classList.add('active');
            flyBtn.textContent = '✈️ Exit (ESC)';
            flyHud.style.display = 'block';
            crosshair.style.display = 'block';
            orbitControls.enabled = false;

            // Start at current camera position or default fly height
            if (camera.position.y < 20) {{
                camera.position.y = 50;
            }}
        }});

        flyControls.addEventListener('unlock', () => {{
            if (isFlyMode) {{
                exitFlyMode();
            }}
        }});

        // Keyboard controls for fly-through
        document.addEventListener('keydown', (e) => {{
            if (!isFlyMode) return;
            e.preventDefault();

            switch (e.code) {{
                case 'KeyW': case 'ArrowUp': moveState.forward = true; break;
                case 'KeyS': case 'ArrowDown': moveState.backward = true; break;
                case 'KeyA': case 'ArrowLeft': moveState.left = true; break;
                case 'KeyD': case 'ArrowRight': moveState.right = true; break;
                case 'Space': moveState.up = true; break;
                case 'ShiftLeft': case 'ShiftRight': moveState.down = true; break;
            }}
        }});

        document.addEventListener('keyup', (e) => {{
            if (!isFlyMode) return;

            switch (e.code) {{
                case 'KeyW': case 'ArrowUp': moveState.forward = false; break;
                case 'KeyS': case 'ArrowDown': moveState.backward = false; break;
                case 'KeyA': case 'ArrowLeft': moveState.left = false; break;
                case 'KeyD': case 'ArrowRight': moveState.right = false; break;
                case 'Space': moveState.up = false; break;
                case 'ShiftLeft': case 'ShiftRight': moveState.down = false; break;
            }}
        }});

        // Scroll to adjust fly speed
        document.addEventListener('wheel', (e) => {{
            if (!isFlyMode) return;
            e.preventDefault();
            flySpeed = Math.max(minFlySpeed, Math.min(maxFlySpeed, flySpeed - e.deltaY * 0.5));
        }}, {{ passive: false }});

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, {ambient_intensity});
        scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, {directional_intensity});
        directionalLight.position.set(sceneScale * 0.5, sceneScale, sceneScale * 0.5);
        directionalLight.castShadow = true;
        scene.add(directionalLight);

        const hemisphereLight = new THREE.HemisphereLight(0xffffff, {hemisphere_ground}, {hemisphere_intensity});
        scene.add(hemisphereLight);

        // Ground plane
        const groundGeometry = new THREE.PlaneGeometry(sceneScale * 2, sceneScale * 2);
        const groundMaterial = new THREE.MeshLambertMaterial({{
            color: {rgb_to_hex(*ground_color)},
            side: THREE.DoubleSide
        }});
        const ground = new THREE.Mesh(groundGeometry, groundMaterial);
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = -0.5;
        ground.receiveShadow = true;
        scene.add(ground);

        // Grid helper
        const gridHelper = new THREE.GridHelper(sceneScale, 50, {grid_color}, {grid_color});
        gridHelper.position.y = -0.1;
        scene.add(gridHelper);

        // Clickable objects array
        const clickableObjects = [];

        // Layer groups for toggling visibility
        const layers = {{
            buildings: [],
            roads: [],
            bikelanes: [],
            pois: [],
            trees: []
        }};

        // Building materials
        const buildingMaterial = new THREE.MeshLambertMaterial({{
            color: {rgb_to_hex(*building_fill_3d)},
            side: THREE.DoubleSide
        }});

        const buildingEdgeMaterial = new THREE.LineBasicMaterial({{
            color: {rgb_to_hex(*building_edge_3d)},
            linewidth: 2
        }});

        const highlightMaterial = new THREE.MeshLambertMaterial({{
            color: 0x4fc3f7,
            side: THREE.DoubleSide
        }});

        // Create buildings
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

            const extrudeSettings = {{
                depth: building.height,
                bevelEnabled: false
            }};

            const geometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);

            const mesh = new THREE.Mesh(geometry, buildingMaterial.clone());
            mesh.rotation.x = -Math.PI / 2;
            mesh.position.y = 0;
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            mesh.userData = {{ type: 'building', data: building, index: index }};
            scene.add(mesh);
            clickableObjects.push(mesh);

            const edges = new THREE.EdgesGeometry(geometry);
            const wireframe = new THREE.LineSegments(edges, buildingEdgeMaterial);
            wireframe.rotation.x = -Math.PI / 2;
            wireframe.position.y = 0.01;
            scene.add(wireframe);

            layers.buildings.push(mesh, wireframe);
        }});

        // Road colors
        const roadColors = {road_colors_js};

        // Create roads
        roads.forEach((road, index) => {{
            if (road.coords.length < 2) return;

            const points = road.coords.map(coord => {{
                const pos = geoToScene(coord[0], coord[1]);
                return new THREE.Vector3(pos.x, 0.5, pos.z);
            }});

            const curve = new THREE.CatmullRomCurve3(points, false);
            const tubeRadius = Math.max(1, road.width * 0.8);
            const tubeGeometry = new THREE.TubeGeometry(curve, points.length * 2, tubeRadius, 4, false);

            const roadColor = roadColors[road.type] || roadColors.default;
            const roadMaterial = new THREE.MeshLambertMaterial({{ color: roadColor }});

            const roadMesh = new THREE.Mesh(tubeGeometry, roadMaterial);
            roadMesh.userData = {{ type: 'road', data: road, index: index }};
            scene.add(roadMesh);
            clickableObjects.push(roadMesh);

            layers.roads.push(roadMesh);
        }});

        // Bike lanes
        const bikeLaneColor = 0xff00ff;
        bikelanes.forEach((lane, index) => {{
            if (lane.coords.length < 2) return;

            const points = lane.coords.map(coord => {{
                const pos = geoToScene(coord[0], coord[1]);
                return new THREE.Vector3(pos.x, 1.0, pos.z);
            }});

            const curve = new THREE.CatmullRomCurve3(points, false);
            const tubeRadius = 1.5;
            const tubeGeometry = new THREE.TubeGeometry(curve, points.length * 2, tubeRadius, 4, false);

            const laneMaterial = new THREE.MeshLambertMaterial({{ color: bikeLaneColor }});
            const laneMesh = new THREE.Mesh(tubeGeometry, laneMaterial);
            laneMesh.userData = {{ type: 'bikelane', data: lane, index: index }};
            scene.add(laneMesh);
            clickableObjects.push(laneMesh);

            layers.bikelanes.push(laneMesh);
        }});

        // Water
        const waterMaterial = new THREE.MeshLambertMaterial({{
            color: {rgb_to_hex(*water_color)},
            transparent: true,
            opacity: 0.7,
            side: THREE.DoubleSide
        }});

        water.forEach(w => {{
            if (w.coords.length < 4) return;

            const shape = new THREE.Shape();
            const firstPoint = geoToScene(w.coords[0][0], w.coords[0][1]);
            shape.moveTo(firstPoint.x, -firstPoint.z);

            for (let i = 1; i < w.coords.length; i++) {{
                const point = geoToScene(w.coords[i][0], w.coords[i][1]);
                shape.lineTo(point.x, -point.z);
            }}
            shape.closePath();

            const geometry = new THREE.ShapeGeometry(shape);
            const mesh = new THREE.Mesh(geometry, waterMaterial);
            mesh.rotation.x = -Math.PI / 2;
            mesh.position.y = 0.05;
            scene.add(mesh);
        }});

        // POI markers
        const poiColors = {{
            amenity: 0xff4444,
            shop: 0xac39ac,
            tourism: 0x0099ff,
            other: 0xffa500
        }};

        function pointInPolygon(x, z, polygon) {{
            let inside = false;
            for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {{
                const xi = polygon[i].x, zi = polygon[i].z;
                const xj = polygon[j].x, zj = polygon[j].z;
                if (((zi > z) !== (zj > z)) && (x < (xj - xi) * (z - zi) / (zj - zi) + xi)) {{
                    inside = !inside;
                }}
            }}
            return inside;
        }}

        const buildingPolygons = buildings.map(b => {{
            const poly = b.coords.map(c => geoToScene(c[0], c[1]));
            return {{ polygon: poly, height: b.height }};
        }});

        pois.forEach((poi, index) => {{
            const pos = geoToScene(poi.lon, poi.lat);

            let baseHeight = 8;
            for (const bp of buildingPolygons) {{
                if (pointInPolygon(pos.x, pos.z, bp.polygon)) {{
                    baseHeight = bp.height + 10;
                    break;
                }}
            }}

            const poiGeometry = new THREE.SphereGeometry(4, 12, 12);
            const color = poiColors[poi.category] || poiColors.other;
            const poiMaterial = new THREE.MeshLambertMaterial({{ color: color }});

            const sphere = new THREE.Mesh(poiGeometry, poiMaterial);
            sphere.position.set(pos.x, baseHeight, pos.z);
            sphere.userData = {{ type: 'poi', data: poi, index: index }};
            scene.add(sphere);
            clickableObjects.push(sphere);

            const poleHeight = baseHeight - 4;
            const poleGeometry = new THREE.CylinderGeometry(0.5, 0.5, poleHeight, 6);
            const poleMaterial = new THREE.MeshLambertMaterial({{ color: 0x666666 }});
            const pole = new THREE.Mesh(poleGeometry, poleMaterial);
            pole.position.set(pos.x, poleHeight / 2, pos.z);
            scene.add(pole);

            layers.pois.push(sphere, pole);
        }});

        // Trees
        function getTreeColor(tree) {{
            if (tree.leaf_type === 'needleleaved') {{
                return 0x1a5a2a;
            }} else if (tree.leaf_cycle === 'evergreen') {{
                return 0x228b22;
            }} else {{
                return 0x32cd32;
            }}
        }}

        trees.forEach((tree, index) => {{
            const pos = geoToScene(tree.lon, tree.lat);
            const treeHeight = tree.height || 8;
            const crownDiameter = tree.crown_diameter || treeHeight * 0.6;
            const trunkHeight = treeHeight * 0.3;
            const crownHeight = treeHeight * 0.7;

            const treeColor = getTreeColor(tree);
            const trunkColor = 0x8b4513;

            const trunkRadius = crownDiameter * 0.1;
            const trunkGeometry = new THREE.CylinderGeometry(trunkRadius * 0.7, trunkRadius, trunkHeight, 8);
            const trunkMaterial = new THREE.MeshLambertMaterial({{ color: trunkColor }});
            const trunk = new THREE.Mesh(trunkGeometry, trunkMaterial);
            trunk.position.set(pos.x, trunkHeight / 2, pos.z);
            trunk.castShadow = true;
            scene.add(trunk);

            let crown;
            if (tree.leaf_type === 'needleleaved') {{
                const coneGeometry = new THREE.ConeGeometry(crownDiameter / 2, crownHeight, 8);
                const coneMaterial = new THREE.MeshLambertMaterial({{ color: treeColor }});
                crown = new THREE.Mesh(coneGeometry, coneMaterial);
                crown.position.set(pos.x, trunkHeight + crownHeight / 2, pos.z);
            }} else {{
                const sphereGeometry = new THREE.SphereGeometry(crownDiameter / 2, 12, 8);
                const sphereMaterial = new THREE.MeshLambertMaterial({{ color: treeColor }});
                crown = new THREE.Mesh(sphereGeometry, sphereMaterial);
                crown.position.set(pos.x, trunkHeight + crownDiameter / 2 * 0.8, pos.z);
            }}
            crown.castShadow = true;
            crown.userData = {{ type: 'tree', data: tree, index: index }};
            scene.add(crown);
            clickableObjects.push(crown);

            layers.trees.push(trunk, crown);
        }});

        // Interaction
        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2();
        const tooltip = document.getElementById('tooltip');
        let selectedObject = null;
        let originalMaterial = null;

        window.copyToClipboard = function(text, btn) {{
            navigator.clipboard.writeText(text).then(() => {{
                btn.textContent = '✓ Copied!';
                btn.classList.add('copied');
                setTimeout(() => {{
                    btn.textContent = '📋 Copy';
                    btn.classList.remove('copied');
                }}, 2000);
            }}).catch(err => {{
                const textarea = document.createElement('textarea');
                textarea.value = text;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                btn.textContent = '✓ Copied!';
                btn.classList.add('copied');
                setTimeout(() => {{
                    btn.textContent = '📋 Copy';
                    btn.classList.remove('copied');
                }}, 2000);
            }});
        }}

        window.copyCoords = function(lat, lon, btn) {{
            copyToClipboard(`${{lat}}, ${{lon}}`, btn);
        }}

        function showTooltip(object, event) {{
            const data = object.userData.data;
            const type = object.userData.type;

            let html = '';

            if (type === 'building') {{
                const name = data.name || 'Unnamed Building';
                html = `<h4>🏢 ${{name}}</h4>`;
                html += `<span class="type-badge">${{data.type}}</span>`;
                if (data.levels) html += `<span class="type-badge">${{data.levels}} floors</span>`;
                if (data.amenity) html += `<span class="type-badge" style="background:#ff6b6b">${{data.amenity}}</span>`;
                if (data.shop) html += `<span class="type-badge" style="background:#ac39ac;color:#fff">${{data.shop}}</span>`;
                if (data.office) html += `<span class="type-badge" style="background:#4a90d9;color:#fff">${{data.office}}</span>`;
                if (data.tourism) html += `<span class="type-badge" style="background:#0099ff;color:#fff">${{data.tourism}}</span>`;

                html += `<div style="margin-top:8px;border-top:1px solid #444;padding-top:8px;">`;
                html += `<div class="tag-row"><span class="tag-key">Height:</span><span class="tag-value">${{data.height.toFixed(1)}}m</span></div>`;
                html += `<div class="tag-row"><span class="tag-key">OSM ID:</span><span class="tag-value">${{data.id}}</span></div>`;

                if (data.address) {{
                    const safeAddr = data.address.replace(/[\\\\'"<>]/g, c => '&#' + c.charCodeAt(0) + ';');
                    html += `<div class="coord-row" style="margin-top:4px;">`;
                    html += `<span style="flex:1;color:#fff;">🏠 ${{safeAddr}}</span>`;
                    html += `<button class="copy-btn" onclick="copyToClipboard('${{safeAddr}}', this)">📋 Copy</button>`;
                    html += `</div>`;
                }}
                if (data.start_date) html += `<div class="tag-row"><span class="tag-key">Built:</span><span class="tag-value">${{data.start_date}}</span></div>`;
                if (data.architect) html += `<div class="tag-row"><span class="tag-key">Architect:</span><span class="tag-value">${{data.architect}}</span></div>`;
                if (data.operator) html += `<div class="tag-row"><span class="tag-key">Operator:</span><span class="tag-value">${{data.operator}}</span></div>`;
                html += `</div>`;

                if (data.material || data.colour || data.roof_shape) {{
                    html += `<div style="margin-top:6px;border-top:1px solid #333;padding-top:6px;">`;
                    if (data.material) html += `<div class="tag-row"><span class="tag-key">Material:</span><span class="tag-value">${{data.material}}</span></div>`;
                    if (data.colour) html += `<div class="tag-row"><span class="tag-key">Colour:</span><span class="tag-value">${{data.colour}}</span></div>`;
                    if (data.roof_shape) html += `<div class="tag-row"><span class="tag-key">Roof:</span><span class="tag-value">${{data.roof_shape}}</span></div>`;
                    html += `</div>`;
                }}

                if (data.phone || data.website || data.opening_hours || data.wheelchair) {{
                    html += `<div style="margin-top:6px;border-top:1px solid #333;padding-top:6px;">`;
                    if (data.phone) html += `<div class="tag-row"><span class="tag-key">Phone:</span><span class="tag-value">${{data.phone}}</span></div>`;
                    if (data.website) {{
                        const shortUrl = data.website.replace(/^https?:\\/\\//, '').substring(0, 35);
                        html += `<div class="tag-row"><span class="tag-key">Web:</span><span class="tag-value">${{shortUrl}}...</span></div>`;
                    }}
                    if (data.opening_hours) html += `<div class="tag-row"><span class="tag-key">Hours:</span><span class="tag-value">${{data.opening_hours}}</span></div>`;
                    if (data.wheelchair) {{
                        const wcIcon = data.wheelchair === 'yes' ? '♿ Yes' : (data.wheelchair === 'no' ? '❌ No' : data.wheelchair);
                        html += `<div class="tag-row"><span class="tag-key">Wheelchair:</span><span class="tag-value">${{wcIcon}}</span></div>`;
                    }}
                    html += `</div>`;
                }}

                if (data.description) {{
                    html += `<div style="margin-top:6px;border-top:1px solid #333;padding-top:6px;font-style:italic;color:#aaa;">${{data.description.substring(0, 100)}}${{data.description.length > 100 ? '...' : ''}}</div>`;
                }}

                if (data.wikipedia || data.wikidata) {{
                    html += `<div style="margin-top:6px;font-size:11px;color:#888;">`;
                    if (data.wikipedia) html += `📖 Wikipedia `;
                    if (data.wikidata) html += `🔗 ${{data.wikidata}}`;
                    html += `</div>`;
                }}

                html += `<div class="coord-row">`;
                html += `<span class="coord-value">📍 ${{data.lat}}, ${{data.lon}}</span>`;
                html += `<button class="copy-btn" onclick="copyCoords(${{data.lat}}, ${{data.lon}}, this)">📋 Copy</button>`;
                html += `</div>`;
            }} else if (type === 'road') {{
                const name = data.name || 'Unnamed Road';
                html = `<h4>🛣️ ${{name}}</h4>`;
                html += `<span class="type-badge">${{data.type}}</span>`;
                if (data.maxspeed) html += `<span class="type-badge">${{data.maxspeed}}</span>`;
                if (data.lanes) html += `<span class="type-badge">${{data.lanes}} lanes</span>`;
                if (data.oneway === 'yes') html += `<span class="type-badge">One-way</span>`;

                html += `<div style="margin-top:8px;border-top:1px solid #444;padding-top:8px;">`;
                html += `<div class="tag-row"><span class="tag-key">OSM ID:</span><span class="tag-value">${{data.id}}</span></div>`;
                if (data.surface) html += `<div class="tag-row"><span class="tag-key">Surface:</span><span class="tag-value">${{data.surface}}</span></div>`;
                html += `</div>`;

                html += `<div class="coord-row">`;
                html += `<span class="coord-value">📍 ${{data.lat}}, ${{data.lon}}</span>`;
                html += `<button class="copy-btn" onclick="copyCoords(${{data.lat}}, ${{data.lon}}, this)">📋 Copy</button>`;
                html += `</div>`;
            }} else if (type === 'poi') {{
                const name = data.name || 'Unnamed POI';
                html = `<h4>📍 ${{name}}</h4>`;
                html += `<span class="type-badge">${{data.category}}</span>`;
                html += `<span class="type-badge">${{data.type}}</span>`;

                html += `<div style="margin-top:8px;border-top:1px solid #444;padding-top:8px;">`;
                html += `<div class="tag-row"><span class="tag-key">OSM ID:</span><span class="tag-value">${{data.id}}</span></div>`;
                html += `</div>`;

                html += `<div class="coord-row">`;
                html += `<span class="coord-value">📍 ${{data.lat}}, ${{data.lon}}</span>`;
                html += `<button class="copy-btn" onclick="copyCoords(${{data.lat}}, ${{data.lon}}, this)">📋 Copy</button>`;
                html += `</div>`;
            }} else if (type === 'tree') {{
                const name = data.name || 'Tree';
                html = `<h4>🌳 ${{name}}</h4>`;
                html += `<span class="type-badge" style="background:#228b22;color:#fff">${{data.type}}</span>`;
                if (data.species) html += `<span class="type-badge" style="background:#2e8b57;color:#fff">${{data.species}}</span>`;
                if (data.leaf_type) html += `<span class="type-badge" style="background:#556b2f;color:#fff">${{data.leaf_type}}</span>`;
                if (data.leaf_cycle) html += `<span class="type-badge" style="background:#6b8e23;color:#fff">${{data.leaf_cycle}}</span>`;

                html += `<div style="margin-top:8px;border-top:1px solid #444;padding-top:8px;">`;
                html += `<div class="tag-row"><span class="tag-key">OSM ID:</span><span class="tag-value">${{data.id}}</span></div>`;
                html += `<div class="tag-row"><span class="tag-key">Height:</span><span class="tag-value">${{data.height.toFixed(1)}}m</span></div>`;
                if (data.crown_diameter) html += `<div class="tag-row"><span class="tag-key">Crown:</span><span class="tag-value">${{data.crown_diameter.toFixed(1)}}m</span></div>`;
                html += `</div>`;

                html += `<div class="coord-row">`;
                html += `<span class="coord-value">📍 ${{data.lat}}, ${{data.lon}}</span>`;
                html += `<button class="copy-btn" onclick="copyCoords(${{data.lat}}, ${{data.lon}}, this)">📋 Copy</button>`;
                html += `</div>`;
            }} else if (type === 'bikelane') {{
                const name = data.name || 'Bike Lane';
                html = `<h4>🚴 ${{name}}</h4>`;
                html += `<span class="type-badge" style="background:#ff00ff;color:#fff">${{data.type}}</span>`;
                if (data.surface) html += `<span class="type-badge">${{data.surface}}</span>`;
                if (data.oneway === 'yes') html += `<span class="type-badge">One-way</span>`;

                html += `<div style="margin-top:8px;border-top:1px solid #444;padding-top:8px;">`;
                html += `<div class="tag-row"><span class="tag-key">OSM ID:</span><span class="tag-value">${{data.id}}</span></div>`;
                if (data.width) html += `<div class="tag-row"><span class="tag-key">Width:</span><span class="tag-value">${{data.width}}</span></div>`;
                html += `</div>`;

                html += `<div class="coord-row">`;
                html += `<span class="coord-value">📍 ${{data.lat}}, ${{data.lon}}</span>`;
                html += `<button class="copy-btn" onclick="copyCoords(${{data.lat}}, ${{data.lon}}, this)">📋 Copy</button>`;
                html += `</div>`;
            }}

            tooltip.innerHTML = html;
            tooltip.style.display = 'block';
            tooltip.style.left = (event.clientX + 15) + 'px';
            tooltip.style.top = (event.clientY + 15) + 'px';

            const rect = tooltip.getBoundingClientRect();
            if (rect.right > window.innerWidth) {{
                tooltip.style.left = (event.clientX - rect.width - 15) + 'px';
            }}
            if (rect.bottom > window.innerHeight) {{
                tooltip.style.top = (event.clientY - rect.height - 15) + 'px';
            }}
        }}

        function hideTooltip() {{
            tooltip.style.display = 'none';
        }}

        function onClick(event) {{
            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(clickableObjects);

            if (selectedObject && originalMaterial) {{
                selectedObject.material = originalMaterial;
            }}

            const visibleIntersect = intersects.find(i => i.object.visible);
            if (visibleIntersect) {{
                const object = visibleIntersect.object;

                if (object.userData.type === 'building') {{
                    originalMaterial = object.material;
                    object.material = highlightMaterial.clone();
                    selectedObject = object;
                }} else if (object.userData.type === 'road' || object.userData.type === 'poi' || object.userData.type === 'tree' || object.userData.type === 'bikelane') {{
                    originalMaterial = object.material;
                    const origColor = object.material.color;
                    const brightColor = new THREE.Color(
                        Math.min(1, origColor.r + 0.4),
                        Math.min(1, origColor.g + 0.4),
                        Math.min(1, origColor.b + 0.4)
                    );
                    const brightMaterial = new THREE.MeshLambertMaterial({{ color: brightColor, emissive: brightColor, emissiveIntensity: 0.5 }});
                    object.material = brightMaterial;
                    selectedObject = object;
                }}

                showTooltip(object, event);
            }} else {{
                hideTooltip();
                selectedObject = null;
                originalMaterial = null;
            }}
        }}

        function onMouseMove(event) {{
            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(clickableObjects);

            const hasVisibleHit = intersects.some(i => i.object.visible);
            container.style.cursor = hasVisibleHit ? 'pointer' : 'grab';
        }}

        container.addEventListener('click', onClick);
        container.addEventListener('mousemove', onMouseMove);

        // Stats
        const statsDiv = document.getElementById('stats');
        let frameCount = 0;
        let lastTime = performance.now();
        let prevTime = performance.now();
        const clock = new THREE.Clock();

        function animate() {{
            requestAnimationFrame(animate);

            const time = performance.now();
            const delta = (time - prevTime) / 1000;
            prevTime = time;

            if (isFlyMode && flyControls.isLocked) {{
                // Get camera direction for forward/backward movement
                const direction = new THREE.Vector3();
                camera.getWorldDirection(direction);

                // Calculate movement
                if (moveState.forward) {{
                    camera.position.addScaledVector(direction, flySpeed * delta);
                }}
                if (moveState.backward) {{
                    camera.position.addScaledVector(direction, -flySpeed * delta);
                }}

                // Strafe left/right
                const right = new THREE.Vector3();
                right.crossVectors(direction, camera.up).normalize();
                if (moveState.right) {{
                    camera.position.addScaledVector(right, flySpeed * delta);
                }}
                if (moveState.left) {{
                    camera.position.addScaledVector(right, -flySpeed * delta);
                }}

                // Fly up/down (world Y axis)
                if (moveState.up) {{
                    camera.position.y += flySpeed * delta;
                }}
                if (moveState.down) {{
                    camera.position.y -= flySpeed * delta;
                    // Don't go below ground
                    if (camera.position.y < 2) camera.position.y = 2;
                }}

                // Update HUD
                const geo = sceneToGeo(camera.position.x, camera.position.z);
                flyCoords.textContent = `📍 ${{geo.lat}}, ${{geo.lon}}`;
                flyAlt.textContent = camera.position.y.toFixed(0);
                flySpeedDisplay.textContent = flySpeed.toFixed(0) + ' m/s';
            }} else {{
                orbitControls.update();
            }}

            renderer.render(scene, camera);

            frameCount++;
            const now = performance.now();
            if (now - lastTime >= 1000) {{
                statsDiv.textContent = `FPS: ${{frameCount}}`;
                frameCount = 0;
                lastTime = now;
            }}
        }}
        animate();

        window.addEventListener('resize', () => {{
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }});

        // Layer toggles
        function toggleLayer(layerName, visible) {{
            layers[layerName].forEach(obj => {{
                obj.visible = visible;
            }});
        }}

        document.getElementById('toggle-buildings').addEventListener('change', (e) => {{
            toggleLayer('buildings', e.target.checked);
        }});

        document.getElementById('toggle-roads').addEventListener('change', (e) => {{
            toggleLayer('roads', e.target.checked);
        }});

        document.getElementById('toggle-pois').addEventListener('change', (e) => {{
            toggleLayer('pois', e.target.checked);
        }});

        document.getElementById('toggle-trees').addEventListener('change', (e) => {{
            toggleLayer('trees', e.target.checked);
        }});

        document.getElementById('toggle-bikelanes').addEventListener('change', (e) => {{
            toggleLayer('bikelanes', e.target.checked);
        }});
    </script>
</body>
</html>'''
        return html_content
