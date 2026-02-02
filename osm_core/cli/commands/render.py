"""
Render command - Generate map visualizations from OSM data.

Supports:
- PNG: Pure Python rendered static images
- HTML: Interactive Leaflet.js maps
"""

import os
import sys
from argparse import Namespace
from typing import Dict, Tuple, Optional

from ...parsing.mmap_parser import UltraFastOSMParser
from ...rendering import MapRenderer, LeafletRenderer, MapPDFRenderer, WebGLRenderer, get_available_styles


def add_arguments(parser):
    """Add render command arguments."""
    parser.add_argument(
        'input',
        help='Input OSM file'
    )
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Output file (.png or .html)'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['png', 'pdf', 'html', 'leaflet', 'webgl', '3d'],
        help='Output format (default: auto-detect from extension)'
    )
    parser.add_argument(
        '--width',
        type=int,
        default=1024,
        help='Image width in pixels (PNG only, default: 1024)'
    )
    parser.add_argument(
        '--height',
        type=int,
        default=768,
        help='Image height in pixels (PNG only, default: 768)'
    )
    parser.add_argument(
        '--page-size',
        choices=['letter', 'a4', 'a3', 'a2', 'legal'],
        default='letter',
        help='Page size for PDF (default: letter)'
    )
    parser.add_argument(
        '--orientation',
        choices=['portrait', 'landscape'],
        default='landscape',
        help='Page orientation for PDF (default: landscape)'
    )
    parser.add_argument(
        '--dpi',
        type=int,
        default=300,
        help='DPI for PDF (default: 300, publication standard)'
    )
    parser.add_argument(
        '--style',
        choices=get_available_styles(),
        default='default',
        help='Color style (default: default)'
    )
    parser.add_argument(
        '--title',
        help='Map title'
    )
    parser.add_argument(
        '--filter',
        dest='tag_filter',
        help='Filter by tag (e.g., highway=*, amenity=restaurant)'
    )
    parser.add_argument(
        '--bbox',
        nargs=4,
        type=float,
        metavar=('MIN_LAT', 'MAX_LAT', 'MIN_LON', 'MAX_LON'),
        help='Bounding box to render'
    )
    parser.add_argument(
        '--no-legend',
        action='store_true',
        help='Hide legend (PNG only)'
    )
    parser.add_argument(
        '--no-scale',
        action='store_true',
        help='Hide scale bar (PNG only)'
    )
    parser.add_argument(
        '--tiles',
        choices=['osm', 'carto-light', 'carto-dark', 'esri-satellite'],
        default='osm',
        help='Tile provider for HTML maps (default: osm)'
    )
    parser.add_argument(
        '--layer',
        choices=['all', 'roads', 'buildings', 'water', 'pois', 'landuse'],
        default='all',
        help='Render specific layer only'
    )


def execute(args: Namespace) -> int:
    """Execute render command."""
    input_file = args.input
    output_file = args.output

    # Validate input
    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}", file=sys.stderr)
        return 1

    # Determine output format
    output_format = args.format
    if not output_format:
        ext = os.path.splitext(output_file)[1].lower()
        if ext == '.png':
            output_format = 'png'
        elif ext == '.pdf':
            output_format = 'pdf'
        elif ext in ('.html', '.htm'):
            output_format = 'html'
        else:
            print(f"Error: Cannot determine format from extension '{ext}'. Use --format.", file=sys.stderr)
            return 1

    if output_format == 'leaflet':
        output_format = 'html'
    if output_format == '3d':
        output_format = 'webgl'

    # Parse OSM data
    print(f"Parsing {input_file}...")
    parser = UltraFastOSMParser()

    # Parse file
    nodes, ways = parser.parse_file_ultra_fast(input_file)

    # Apply filter if specified
    if args.tag_filter:
        if '=' in args.tag_filter:
            key, value = args.tag_filter.split('=', 1)
            if value == '*':
                # Wildcard - just check key exists
                nodes = [n for n in nodes if key in n.tags]
                ways = [w for w in ways if key in w.tags]
            else:
                # Exact match
                nodes = [n for n in nodes if n.tags.get(key) == value]
                ways = [w for w in ways if w.tags.get(key) == value]

    # Apply bbox filter if specified
    if args.bbox:
        min_lat, max_lat, min_lon, max_lon = args.bbox
        nodes = [n for n in nodes if min_lat <= n.lat <= max_lat and min_lon <= n.lon <= max_lon]
        # For ways, keep if any node is within bbox
        node_set = {n.id for n in nodes}
        ways = [w for w in ways if any(ref in node_set for ref in w.node_refs)]

    # Build node coordinate lookup
    node_coords: Dict[str, Tuple[float, float]] = {}
    for node in nodes:
        node_coords[node.id] = (node.lat, node.lon)

    # Also get coordinates from parser cache (for way nodes without tags)
    if hasattr(parser, 'node_coordinates'):
        node_coords.update(parser.node_coordinates)

    # Filter by layer if specified
    if args.layer != 'all':
        nodes, ways = _filter_by_layer(nodes, ways, args.layer)

    print(f"Found {len(nodes)} nodes, {len(ways)} ways")

    if len(nodes) == 0 and len(ways) == 0:
        print("Warning: No features to render", file=sys.stderr)

    # Determine title
    title = args.title or os.path.splitext(os.path.basename(input_file))[0]

    # Render based on format
    if output_format == 'png':
        return _render_png(
            nodes, ways, node_coords, output_file,
            width=args.width,
            height=args.height,
            style=args.style,
            title=title if args.title else None,
            show_legend=not args.no_legend,
            show_scale=not args.no_scale,
            bbox=tuple(args.bbox) if args.bbox else None
        )
    elif output_format == 'pdf':
        return _render_pdf(
            nodes, ways, node_coords, output_file,
            page_size=args.page_size,
            orientation=args.orientation,
            style=args.style,
            title=title if args.title else None,
            show_legend=not args.no_legend,
            show_scale=not args.no_scale,
            bbox=tuple(args.bbox) if args.bbox else None
        )
    elif output_format == 'html':
        return _render_html(
            nodes, ways, node_coords, output_file,
            style=args.style,
            title=title,
            tile_provider=args.tiles
        )
    else:  # webgl
        return _render_webgl(
            nodes, ways, node_coords, output_file,
            style=args.style,
            title=title if args.title else None
        )


def _filter_by_layer(nodes, ways, layer: str):
    """Filter features by layer type."""
    if layer == 'roads':
        ways = [w for w in ways if 'highway' in w.tags]
        nodes = []
    elif layer == 'buildings':
        ways = [w for w in ways if 'building' in w.tags]
        nodes = []
    elif layer == 'water':
        ways = [w for w in ways if 'water' in w.tags or w.tags.get('natural') == 'water' or 'waterway' in w.tags]
        nodes = []
    elif layer == 'pois':
        nodes = [n for n in nodes if any(k in n.tags for k in ['amenity', 'shop', 'tourism', 'leisure'])]
        ways = []
    elif layer == 'landuse':
        ways = [w for w in ways if 'landuse' in w.tags or 'natural' in w.tags]
        nodes = []

    return nodes, ways


def _render_png(nodes, ways, node_coords, output_file, width, height, style,
                title, show_legend, show_scale, bbox) -> int:
    """Render to PNG file."""
    print(f"Rendering PNG ({width}x{height}, style: {style})...")

    try:
        renderer = MapRenderer(width, height, style)
        renderer.render(
            nodes, ways, node_coords,
            bbox=bbox,
            show_legend=show_legend,
            show_scale=show_scale,
            title=title
        )
        renderer.save(output_file)
        print(f"Saved: {output_file}")

        # Print file size
        size = os.path.getsize(output_file)
        if size > 1024 * 1024:
            print(f"Size: {size / (1024 * 1024):.1f} MB")
        else:
            print(f"Size: {size / 1024:.1f} KB")

        return 0
    except Exception as e:
        print(f"Error rendering PNG: {e}", file=sys.stderr)
        return 1


def _render_pdf(nodes, ways, node_coords, output_file, page_size, orientation,
                style, title, show_legend, show_scale, bbox) -> int:
    """Render to publication-ready PDF file."""
    print(f"Rendering PDF ({page_size} {orientation}, style: {style})...")
    print("Using Type 1 fonts only (no Type 3) - publication ready")

    try:
        renderer = MapPDFRenderer(page_size, orientation, style)
        renderer.render(
            nodes, ways, node_coords,
            bbox=bbox,
            title=title,
            show_legend=show_legend,
            show_scale=show_scale,
            show_title=title is not None,
            show_frame=True
        )
        renderer.save(output_file, title or "OSMFast Map")
        print(f"Saved: {output_file}")

        # Print file size
        size = os.path.getsize(output_file)
        if size > 1024 * 1024:
            print(f"Size: {size / (1024 * 1024):.1f} MB")
        else:
            print(f"Size: {size / 1024:.1f} KB")

        print("\nPublication notes:")
        print("  - Vector graphics (infinitely scalable)")
        print("  - Type 1 fonts only (Helvetica, Times)")
        print("  - No embedded bitmap fonts")
        print("  - Suitable for journal submission")

        return 0
    except Exception as e:
        print(f"Error rendering PDF: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def _render_html(nodes, ways, node_coords, output_file, style, title, tile_provider) -> int:
    """Render to HTML file."""
    print(f"Generating HTML map (style: {style}, tiles: {tile_provider})...")

    try:
        renderer = LeafletRenderer(style, tile_provider)
        html_content = renderer.render(nodes, ways, node_coords, title)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"Saved: {output_file}")

        # Print file size
        size = os.path.getsize(output_file)
        print(f"Size: {size / 1024:.1f} KB")
        print(f"Features: {len(renderer.geojson_features)}")
        print(f"\nOpen in browser: file://{os.path.abspath(output_file)}")

        return 0
    except Exception as e:
        print(f"Error generating HTML: {e}", file=sys.stderr)
        return 1


def _render_webgl(nodes, ways, node_coords, output_file, style, title) -> int:
    """Render to WebGL 3D HTML file."""
    print(f"Generating WebGL 3D map (style: {style})...")

    try:
        renderer = WebGLRenderer(style)
        html_content = renderer.render(nodes, ways, node_coords, title or "OSMFast 3D Map")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"Saved: {output_file}")

        # Print file size
        size = os.path.getsize(output_file)
        print(f"Size: {size / 1024:.1f} KB")
        print(f"Buildings: {len(renderer.buildings)}")
        print(f"Roads: {len(renderer.roads)}")
        print(f"\nOpen in browser: file://{os.path.abspath(output_file)}")
        print("Note: WebGL requires a modern browser with hardware acceleration")

        return 0
    except Exception as e:
        print(f"Error generating WebGL: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


# Command metadata
COMMAND_HELP = "Render OSM data to PNG, PDF, HTML, or WebGL 3D"
COMMAND_DESCRIPTION = """
Render OSM data as visual maps.

Supports four output formats:
  - PNG: Static raster image (pure Python, no dependencies)
  - PDF: Publication-ready vector graphics (no Type 3 fonts)
  - HTML: Interactive Leaflet.js map (opens in browser)
  - WebGL: 3D visualization with building wireframes (Three.js)

Examples:
  # Render to PNG
  osmfast render city.osm -o map.png
  osmfast render city.osm -o map.png --width 1920 --height 1080 --style dark

  # Render to publication-ready PDF (suitable for journals)
  osmfast render city.osm -o map.pdf
  osmfast render city.osm -o map.pdf --page-size a4 --orientation portrait
  osmfast render city.osm -o figure.pdf --style light --title "Study Area"

  # Render to interactive HTML
  osmfast render city.osm -o map.html
  osmfast render city.osm -o map.html --tiles carto-dark

  # Filter specific features
  osmfast render city.osm -o roads.pdf --filter "highway=*"
  osmfast render city.osm -o restaurants.html --filter "amenity=restaurant"

  # Render specific layer
  osmfast render city.osm -o buildings.pdf --layer buildings

  # Render to 3D WebGL (buildings as wireframes)
  osmfast render city.osm -o city3d.html --format webgl
  osmfast render city.osm -o city3d.html --format 3d --title "City Model"

PDF Publication Notes:
  - Uses only Type 1 fonts (Helvetica, Times) - no Type 3 bitmap fonts
  - All graphics are vector paths (infinitely scalable)
  - Suitable for IEEE, Elsevier, Springer journal submissions
  - Page sizes: letter, a4, a3, a2, legal

Available styles: default, dark, light, blueprint
Available tiles (HTML): osm, carto-light, carto-dark, esri-satellite
"""
