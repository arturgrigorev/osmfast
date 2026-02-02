"""CLI main entry point with subcommand structure."""
import argparse
import sys
from typing import Optional

from osm_core import __version__


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with subcommands.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog='osmfast',
        description='OSMFast - Ultra-High Performance OpenStreetMap Data Extractor',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  osmfast extract map.osm features.json
  osmfast extract --accept-nodes amenity=restaurant map.osm food.geojson
  osmfast merge area1.osm area2.osm -o combined.osm
  osmfast stats map.osm
  osmfast buildings map.osm -o buildings.geojson
  osmfast roads --stats map.osm
  osmfast search "starbucks" map.osm
  osmfast lookup --lat 51.5 --lon -0.1 map.osm
  osmfast poi --category food map.osm
  osmfast tags --key highway map.osm
  osmfast count --filter amenity=* map.osm

Performance: 7,000+ features/sec | Memory: Constant | Osmosis-compatible
'''
    )

    # Global options
    parser.add_argument('--version', '-V', action='version',
                        version=f'osmfast {__version__}')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress non-error output')
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help='Increase verbosity')

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', title='commands',
                                        description='Available commands')

    # Help subcommand (detailed documentation)
    help_parser = subparsers.add_parser(
        'help',
        help='Show detailed help for a command',
        description='Show detailed documentation for a specific command.'
    )
    help_parser.add_argument(
        'command_name',
        nargs='?',
        help='Command to get help for'
    )

    # Extract subcommand
    _add_extract_parser(subparsers)

    # Merge subcommand
    _add_merge_parser(subparsers)

    # Stats subcommand
    _add_stats_parser(subparsers)

    # Filter subcommand
    _add_filter_parser(subparsers)

    # Buildings subcommand
    from osm_core.cli.commands.buildings import setup_parser as setup_buildings
    setup_buildings(subparsers)

    # Roads subcommand
    from osm_core.cli.commands.roads import setup_parser as setup_roads
    setup_roads(subparsers)

    # Search subcommand
    from osm_core.cli.commands.search import setup_parser as setup_search
    setup_search(subparsers)

    # Lookup subcommand
    from osm_core.cli.commands.lookup import setup_parser as setup_lookup
    setup_lookup(subparsers)

    # POI subcommand
    from osm_core.cli.commands.poi import setup_parser as setup_poi
    setup_poi(subparsers)

    # Tags subcommand
    from osm_core.cli.commands.tags import setup_parser as setup_tags
    setup_tags(subparsers)

    # Count subcommand
    from osm_core.cli.commands.count import setup_parser as setup_count
    setup_count(subparsers)

    # Data operations
    from osm_core.cli.commands.split import setup_parser as setup_split
    setup_split(subparsers)

    from osm_core.cli.commands.convert import setup_parser as setup_convert
    setup_convert(subparsers)

    # Specialized extraction
    from osm_core.cli.commands.address import setup_parser as setup_address
    setup_address(subparsers)

    from osm_core.cli.commands.boundary import setup_parser as setup_boundary
    setup_boundary(subparsers)

    from osm_core.cli.commands.water import setup_parser as setup_water
    setup_water(subparsers)

    from osm_core.cli.commands.landuse import setup_parser as setup_landuse
    setup_landuse(subparsers)

    from osm_core.cli.commands.transit import setup_parser as setup_transit
    setup_transit(subparsers)

    from osm_core.cli.commands.railway import setup_parser as setup_railway
    setup_railway(subparsers)

    from osm_core.cli.commands.power import setup_parser as setup_power
    setup_power(subparsers)

    from osm_core.cli.commands.names import setup_parser as setup_names
    setup_names(subparsers)

    from osm_core.cli.commands.parking import setup_parser as setup_parking
    setup_parking(subparsers)

    from osm_core.cli.commands.trees import setup_parser as setup_trees
    setup_trees(subparsers)

    # Spatial operations
    from osm_core.cli.commands.clip import setup_parser as setup_clip
    setup_clip(subparsers)

    from osm_core.cli.commands.buffer import setup_parser as setup_buffer
    setup_buffer(subparsers)

    from osm_core.cli.commands.nearby_features import setup_parser as setup_nearby
    setup_nearby(subparsers)

    from osm_core.cli.commands.within import setup_parser as setup_within
    setup_within(subparsers)

    from osm_core.cli.commands.centroid import setup_parser as setup_centroid
    setup_centroid(subparsers)

    from osm_core.cli.commands.simplify import setup_parser as setup_simplify
    setup_simplify(subparsers)

    from osm_core.cli.commands.densify import setup_parser as setup_densify
    setup_densify(subparsers)

    # Network analysis
    from osm_core.cli.commands.network import setup_parser as setup_network
    setup_network(subparsers)

    from osm_core.cli.commands.isochrone import setup_parser as setup_isochrone
    setup_isochrone(subparsers)

    # Urban planning analysis commands
    from osm_core.cli.commands.walkability import setup_parser as setup_walkability
    setup_walkability(subparsers)

    from osm_core.cli.commands.catchment import setup_parser as setup_catchment
    setup_catchment(subparsers)

    from osm_core.cli.commands.bikeability import setup_parser as setup_bikeability
    setup_bikeability(subparsers)

    # More extraction commands
    from osm_core.cli.commands.amenity import setup_parser as setup_amenity
    setup_amenity(subparsers)

    from osm_core.cli.commands.shop import setup_parser as setup_shop
    setup_shop(subparsers)

    from osm_core.cli.commands.leisure import setup_parser as setup_leisure
    setup_leisure(subparsers)

    from osm_core.cli.commands.natural import setup_parser as setup_natural
    setup_natural(subparsers)

    from osm_core.cli.commands.historic import setup_parser as setup_historic
    setup_historic(subparsers)

    from osm_core.cli.commands.emergency import setup_parser as setup_emergency
    setup_emergency(subparsers)

    # More extraction commands
    from osm_core.cli.commands.tourism import setup_parser as setup_tourism
    setup_tourism(subparsers)

    from osm_core.cli.commands.food import setup_parser as setup_food
    setup_food(subparsers)

    from osm_core.cli.commands.healthcare import setup_parser as setup_healthcare
    setup_healthcare(subparsers)

    from osm_core.cli.commands.education import setup_parser as setup_education
    setup_education(subparsers)

    from osm_core.cli.commands.sport import setup_parser as setup_sport
    setup_sport(subparsers)

    from osm_core.cli.commands.barrier import setup_parser as setup_barrier
    setup_barrier(subparsers)

    from osm_core.cli.commands.surface import setup_parser as setup_surface
    setup_surface(subparsers)

    # Data manipulation commands
    from osm_core.cli.commands.sample import setup_parser as setup_sample
    setup_sample(subparsers)

    from osm_core.cli.commands.head import setup_parser as setup_head
    setup_head(subparsers)

    from osm_core.cli.commands.sort import setup_parser as setup_sort
    setup_sort(subparsers)

    from osm_core.cli.commands.unique import setup_parser as setup_unique
    setup_unique(subparsers)

    from osm_core.cli.commands.join import setup_parser as setup_join
    setup_join(subparsers)

    # Utility commands
    from osm_core.cli.commands.info import setup_parser as setup_info
    setup_info(subparsers)

    from osm_core.cli.commands.bbox import setup_parser as setup_bbox
    setup_bbox(subparsers)

    # Routing commands
    from osm_core.cli.commands.route import setup_parser as setup_route
    setup_route(subparsers)

    from osm_core.cli.commands.route_multi import setup_parser as setup_route_multi
    setup_route_multi(subparsers)

    from osm_core.cli.commands.directions import setup_parser as setup_directions
    setup_directions(subparsers)

    from osm_core.cli.commands.alternatives import setup_parser as setup_alternatives
    setup_alternatives(subparsers)

    # Distance & accessibility commands
    from osm_core.cli.commands.distance_matrix import setup_parser as setup_distance_matrix
    setup_distance_matrix(subparsers)

    from osm_core.cli.commands.nearest import setup_parser as setup_nearest
    setup_nearest(subparsers)

    from osm_core.cli.commands.nearest_road import setup_parser as setup_nearest_road
    setup_nearest_road(subparsers)

    # Network analysis commands
    from osm_core.cli.commands.centrality import setup_parser as setup_centrality
    setup_centrality(subparsers)

    from osm_core.cli.commands.connectivity import setup_parser as setup_connectivity
    setup_connectivity(subparsers)

    from osm_core.cli.commands.bottleneck import setup_parser as setup_bottleneck
    setup_bottleneck(subparsers)

    from osm_core.cli.commands.detour_factor import setup_parser as setup_detour_factor
    setup_detour_factor(subparsers)

    # Visualization/rendering commands
    from osm_core.cli.commands.render import add_arguments as add_render_args
    from osm_core.cli.commands.render import COMMAND_HELP, COMMAND_DESCRIPTION
    render_parser = subparsers.add_parser(
        'render',
        help=COMMAND_HELP,
        description=COMMAND_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_render_args(render_parser)

    from osm_core.cli.commands.render_walkability import setup_parser as setup_render_walkability
    setup_render_walkability(subparsers)

    from osm_core.cli.commands.render_bikeability import setup_parser as setup_render_bikeability
    setup_render_bikeability(subparsers)

    return parser


def _add_extract_parser(subparsers) -> None:
    """Add extract subcommand parser."""
    extract_parser = subparsers.add_parser(
        'extract',
        help='Extract semantic features from OSM files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Extract amenities, highways, and buildings from OSM files.',
        epilog='''
Examples:
  osmfast extract map.osm features.json
  osmfast extract --format geojson map.osm output.geojson
  osmfast extract --accept-nodes amenity=restaurant map.osm restaurants.csv
  osmfast extract --bbox 49.5 10.9 49.3 11.2 germany.osm region.json
'''
    )

    extract_parser.add_argument('input_file', help='Input OSM XML file')
    extract_parser.add_argument('output_file', nargs='?', default=None,
                                 help='Output file (default: auto-named)')

    # Output options
    output_group = extract_parser.add_argument_group('output options')
    output_group.add_argument('-f', '--format',
                               choices=['json', 'geojson', 'csv', 'xml', 'osm', 'shapefile'],
                               help='Output format (default: auto-detect from extension)')
    output_group.add_argument('--include-metadata', action='store_true',
                               help='Include metadata columns in CSV')
    output_group.add_argument('--include-all-tags', action='store_true',
                               help='Include all OSM tags in shapefile DBF fields')
    output_group.add_argument('--road-attributes', action='store_true',
                               help='Include core road attributes only (maxspeed, lanes, surface, etc.)')
    output_group.add_argument('--building-attributes', action='store_true',
                               help='Include core building attributes only (height, levels, address, etc.)')
    output_group.add_argument('--amenity-attributes', action='store_true',
                               help='Include core amenity attributes only (name, brand, opening_hours, etc.)')
    output_group.add_argument('--traffic-safety-attributes', action='store_true',
                               help='Include traffic safety attributes (crossing type, signals, calming, etc.)')
    output_group.add_argument('--cycling-attributes', action='store_true',
                               help='Include cycling infrastructure attributes (cycleway type, surface, etc.)')
    output_group.add_argument('--road-geometry', action='store_true',
                               help='Calculate road geometry (length, lane_km, sidewalk, etc.)')
    output_group.add_argument('--road-levels', metavar='LEVELS',
                               help='Road levels: 1-6, presets (motorway/arterial/main/driveable/all), or comma-separated')
    output_group.add_argument('--infrastructure', metavar='TYPES',
                               help='Infrastructure filter: bridges,tunnels,fords,embankments,covered,all')
    output_group.add_argument('--only-infrastructure', action='store_true',
                               help='Only extract roads with specified infrastructure')
    output_group.add_argument('--compact', action='store_true',
                               help='Compact JSON output')

    # Filtering options
    _add_filter_options(extract_parser)


def _add_merge_parser(subparsers) -> None:
    """Add merge subcommand parser."""
    merge_parser = subparsers.add_parser(
        'merge',
        help='Merge multiple OSM files',
        description='Merge multiple OSM XML files into one.',
        epilog='''
Examples:
  osmfast merge file1.osm file2.osm -o combined.osm
  osmfast merge area1.osm area2.osm area3.osm --output merged.osm
'''
    )

    merge_parser.add_argument('input_files', nargs='+',
                               help='Input OSM files to merge')
    merge_parser.add_argument('-o', '--output', required=True,
                               help='Output file path')


def _add_stats_parser(subparsers) -> None:
    """Add stats subcommand parser."""
    stats_parser = subparsers.add_parser(
        'stats',
        help='Analyze OSM file statistics',
        description='Analyze OSM file and display statistics.',
        epilog='''
Examples:
  osmfast stats map.osm
  osmfast stats --summary map.osm
  osmfast stats --json map.osm > stats.json
'''
    )

    stats_parser.add_argument('input_file', help='Input OSM XML file')
    stats_parser.add_argument('-s', '--summary', action='store_true',
                               help='Brief summary output')
    stats_parser.add_argument('-d', '--detailed', action='store_true',
                               help='Full detailed analysis (default)')
    stats_parser.add_argument('--json', action='store_true',
                               help='Output as JSON')
    stats_parser.add_argument('--suggest-bbox', action='store_true',
                               help='Show suggested bounding boxes')


def _add_filter_parser(subparsers) -> None:
    """Add filter subcommand parser."""
    filter_parser = subparsers.add_parser(
        'filter',
        help='Apply filters and output filtered OSM',
        description='Apply filters and output filtered OSM data.',
        epilog='''
Examples:
  osmfast filter --accept-ways highway=* --used-node city.osm -o roads.osm
  osmfast filter --bbox 49.5 10.9 49.3 11.2 large.osm -o region.osm
'''
    )

    filter_parser.add_argument('input_file', help='Input OSM XML file')
    filter_parser.add_argument('-o', '--output', required=True,
                                help='Output file path')

    _add_filter_options(filter_parser)


def _add_filter_options(parser) -> None:
    """Add common filter options to a parser."""
    filter_group = parser.add_argument_group('filtering options')

    filter_group.add_argument('--accept-ways', action='append', default=[],
                               metavar='FILTER',
                               help='Accept ways (e.g., highway=*)')
    filter_group.add_argument('--reject-ways', action='append', default=[],
                               metavar='FILTER',
                               help='Reject ways')
    filter_group.add_argument('--accept-nodes', action='append', default=[],
                               metavar='FILTER',
                               help='Accept nodes (e.g., amenity=restaurant)')
    filter_group.add_argument('--reject-nodes', action='append', default=[],
                               metavar='FILTER',
                               help='Reject nodes')
    filter_group.add_argument('--used-node', action='store_true',
                               help='Only nodes referenced by filtered ways')
    filter_group.add_argument('--reject-ways-global', action='store_true',
                               help='Reject all ways')
    filter_group.add_argument('--reject-nodes-global', action='store_true',
                               help='Reject all nodes')
    filter_group.add_argument('--reject-relations', action='store_true',
                               help='Reject all relations')
    filter_group.add_argument('--bbox', '--bounding-box', nargs=4, type=float,
                               metavar=('TOP', 'LEFT', 'BOTTOM', 'RIGHT'),
                               help='Bounding box filter')


def main(args: Optional[list] = None) -> int:
    """Main CLI entry point.

    Args:
        args: Command line arguments (defaults to sys.argv)

    Returns:
        Exit code
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # No command specified - show help
    if not parsed_args.command:
        parser.print_help()
        return 0

    try:
        # Route to appropriate command handler
        if parsed_args.command == 'help':
            from osm_core.cli.commands.help_cmd import run as cmd_help
            return cmd_help(parsed_args)
        elif parsed_args.command == 'extract':
            from osm_core.cli.commands.extract import cmd_extract
            return cmd_extract(parsed_args)
        elif parsed_args.command == 'merge':
            from osm_core.cli.commands.merge import cmd_merge
            return cmd_merge(parsed_args)
        elif parsed_args.command == 'stats':
            from osm_core.cli.commands.stats import cmd_stats
            return cmd_stats(parsed_args)
        elif parsed_args.command == 'filter':
            from osm_core.cli.commands.filter import cmd_filter
            return cmd_filter(parsed_args)
        elif parsed_args.command == 'buildings':
            from osm_core.cli.commands.buildings import run as cmd_buildings
            return cmd_buildings(parsed_args)
        elif parsed_args.command == 'roads':
            from osm_core.cli.commands.roads import run as cmd_roads
            return cmd_roads(parsed_args)
        elif parsed_args.command == 'search':
            from osm_core.cli.commands.search import run as cmd_search
            return cmd_search(parsed_args)
        elif parsed_args.command == 'lookup':
            from osm_core.cli.commands.lookup import run as cmd_lookup
            return cmd_lookup(parsed_args)
        elif parsed_args.command == 'poi':
            from osm_core.cli.commands.poi import run as cmd_poi
            return cmd_poi(parsed_args)
        elif parsed_args.command == 'tags':
            from osm_core.cli.commands.tags import run as cmd_tags
            return cmd_tags(parsed_args)
        elif parsed_args.command == 'count':
            from osm_core.cli.commands.count import run as cmd_count
            return cmd_count(parsed_args)
        # Data operations
        elif parsed_args.command == 'split':
            from osm_core.cli.commands.split import run as cmd_split
            return cmd_split(parsed_args)
        elif parsed_args.command == 'convert':
            from osm_core.cli.commands.convert import run as cmd_convert
            return cmd_convert(parsed_args)
        # Specialized extraction
        elif parsed_args.command == 'address':
            from osm_core.cli.commands.address import run as cmd_address
            return cmd_address(parsed_args)
        elif parsed_args.command == 'boundary':
            from osm_core.cli.commands.boundary import run as cmd_boundary
            return cmd_boundary(parsed_args)
        elif parsed_args.command == 'water':
            from osm_core.cli.commands.water import run as cmd_water
            return cmd_water(parsed_args)
        elif parsed_args.command == 'landuse':
            from osm_core.cli.commands.landuse import run as cmd_landuse
            return cmd_landuse(parsed_args)
        elif parsed_args.command == 'transit':
            from osm_core.cli.commands.transit import run as cmd_transit
            return cmd_transit(parsed_args)
        elif parsed_args.command == 'railway':
            from osm_core.cli.commands.railway import run as cmd_railway
            return cmd_railway(parsed_args)
        elif parsed_args.command == 'power':
            from osm_core.cli.commands.power import run as cmd_power
            return cmd_power(parsed_args)
        elif parsed_args.command == 'names':
            from osm_core.cli.commands.names import run as cmd_names
            return cmd_names(parsed_args)
        elif parsed_args.command == 'parking':
            from osm_core.cli.commands.parking import run as cmd_parking
            return cmd_parking(parsed_args)
        elif parsed_args.command == 'trees':
            from osm_core.cli.commands.trees import run as cmd_trees
            return cmd_trees(parsed_args)
        # Spatial operations
        elif parsed_args.command == 'clip':
            from osm_core.cli.commands.clip import run as cmd_clip
            return cmd_clip(parsed_args)
        elif parsed_args.command == 'buffer':
            from osm_core.cli.commands.buffer import run as cmd_buffer
            return cmd_buffer(parsed_args)
        elif parsed_args.command == 'nearby':
            from osm_core.cli.commands.nearby_features import run as cmd_nearby
            return cmd_nearby(parsed_args)
        elif parsed_args.command == 'within':
            from osm_core.cli.commands.within import run as cmd_within
            return cmd_within(parsed_args)
        elif parsed_args.command == 'centroid':
            from osm_core.cli.commands.centroid import run as cmd_centroid
            return cmd_centroid(parsed_args)
        elif parsed_args.command == 'simplify':
            from osm_core.cli.commands.simplify import run as cmd_simplify
            return cmd_simplify(parsed_args)
        elif parsed_args.command == 'densify':
            from osm_core.cli.commands.densify import run as cmd_densify
            return cmd_densify(parsed_args)
        # Network analysis
        elif parsed_args.command == 'network':
            from osm_core.cli.commands.network import run as cmd_network
            return cmd_network(parsed_args)
        elif parsed_args.command == 'isochrone':
            from osm_core.cli.commands.isochrone import run as cmd_isochrone
            return cmd_isochrone(parsed_args)
        # Urban planning analysis commands
        elif parsed_args.command == 'walkability':
            from osm_core.cli.commands.walkability import run as cmd_walkability
            return cmd_walkability(parsed_args)
        elif parsed_args.command == 'catchment':
            from osm_core.cli.commands.catchment import run as cmd_catchment
            return cmd_catchment(parsed_args)
        elif parsed_args.command == 'bikeability':
            from osm_core.cli.commands.bikeability import run as cmd_bikeability
            return cmd_bikeability(parsed_args)
        # More extraction commands
        elif parsed_args.command == 'amenity':
            from osm_core.cli.commands.amenity import run as cmd_amenity
            return cmd_amenity(parsed_args)
        elif parsed_args.command == 'shop':
            from osm_core.cli.commands.shop import run as cmd_shop
            return cmd_shop(parsed_args)
        elif parsed_args.command == 'leisure':
            from osm_core.cli.commands.leisure import run as cmd_leisure
            return cmd_leisure(parsed_args)
        elif parsed_args.command == 'natural':
            from osm_core.cli.commands.natural import run as cmd_natural
            return cmd_natural(parsed_args)
        elif parsed_args.command == 'historic':
            from osm_core.cli.commands.historic import run as cmd_historic
            return cmd_historic(parsed_args)
        elif parsed_args.command == 'emergency':
            from osm_core.cli.commands.emergency import run as cmd_emergency
            return cmd_emergency(parsed_args)
        # More extraction commands
        elif parsed_args.command == 'tourism':
            from osm_core.cli.commands.tourism import run as cmd_tourism
            return cmd_tourism(parsed_args)
        elif parsed_args.command == 'food':
            from osm_core.cli.commands.food import run as cmd_food
            return cmd_food(parsed_args)
        elif parsed_args.command == 'healthcare':
            from osm_core.cli.commands.healthcare import run as cmd_healthcare
            return cmd_healthcare(parsed_args)
        elif parsed_args.command == 'education':
            from osm_core.cli.commands.education import run as cmd_education
            return cmd_education(parsed_args)
        elif parsed_args.command == 'sport':
            from osm_core.cli.commands.sport import run as cmd_sport
            return cmd_sport(parsed_args)
        elif parsed_args.command == 'barrier':
            from osm_core.cli.commands.barrier import run as cmd_barrier
            return cmd_barrier(parsed_args)
        elif parsed_args.command == 'surface':
            from osm_core.cli.commands.surface import run as cmd_surface
            return cmd_surface(parsed_args)
        # Data manipulation commands
        elif parsed_args.command == 'sample':
            from osm_core.cli.commands.sample import run as cmd_sample
            return cmd_sample(parsed_args)
        elif parsed_args.command == 'head':
            from osm_core.cli.commands.head import run as cmd_head
            return cmd_head(parsed_args)
        elif parsed_args.command == 'sort':
            from osm_core.cli.commands.sort import run as cmd_sort
            return cmd_sort(parsed_args)
        elif parsed_args.command == 'unique':
            from osm_core.cli.commands.unique import run as cmd_unique
            return cmd_unique(parsed_args)
        elif parsed_args.command == 'join':
            from osm_core.cli.commands.join import run as cmd_join
            return cmd_join(parsed_args)
        # Utility commands
        elif parsed_args.command == 'info':
            from osm_core.cli.commands.info import run as cmd_info
            return cmd_info(parsed_args)
        elif parsed_args.command == 'bbox':
            from osm_core.cli.commands.bbox import run as cmd_bbox
            return cmd_bbox(parsed_args)
        # Routing commands
        elif parsed_args.command == 'route':
            from osm_core.cli.commands.route import run as cmd_route
            return cmd_route(parsed_args)
        elif parsed_args.command == 'route-multi':
            from osm_core.cli.commands.route_multi import run as cmd_route_multi
            return cmd_route_multi(parsed_args)
        elif parsed_args.command == 'directions':
            from osm_core.cli.commands.directions import run as cmd_directions
            return cmd_directions(parsed_args)
        elif parsed_args.command == 'alternatives':
            from osm_core.cli.commands.alternatives import run as cmd_alternatives
            return cmd_alternatives(parsed_args)
        # Distance & accessibility commands
        elif parsed_args.command == 'distance-matrix':
            from osm_core.cli.commands.distance_matrix import run as cmd_distance_matrix
            return cmd_distance_matrix(parsed_args)
        elif parsed_args.command == 'nearest':
            from osm_core.cli.commands.nearest import run as cmd_nearest
            return cmd_nearest(parsed_args)
        elif parsed_args.command == 'nearest-road':
            from osm_core.cli.commands.nearest_road import run as cmd_nearest_road
            return cmd_nearest_road(parsed_args)
        # Network analysis commands
        elif parsed_args.command == 'centrality':
            from osm_core.cli.commands.centrality import run as cmd_centrality
            return cmd_centrality(parsed_args)
        elif parsed_args.command == 'connectivity':
            from osm_core.cli.commands.connectivity import run as cmd_connectivity
            return cmd_connectivity(parsed_args)
        elif parsed_args.command == 'bottleneck':
            from osm_core.cli.commands.bottleneck import run as cmd_bottleneck
            return cmd_bottleneck(parsed_args)
        elif parsed_args.command == 'detour-factor':
            from osm_core.cli.commands.detour_factor import run as cmd_detour_factor
            return cmd_detour_factor(parsed_args)
        # Visualization/rendering
        elif parsed_args.command == 'render':
            from osm_core.cli.commands.render import execute as cmd_render
            return cmd_render(parsed_args)
        elif parsed_args.command == 'render-walkability':
            from osm_core.cli.commands.render_walkability import run as cmd_render_walkability
            return cmd_render_walkability(parsed_args)
        elif parsed_args.command == 'render-bikeability':
            from osm_core.cli.commands.render_bikeability import run as cmd_render_bikeability
            return cmd_render_bikeability(parsed_args)
        else:
            parser.print_help()
            return 0

    except FileNotFoundError as e:
        print(f"osmfast: error: File not found: {e}", file=sys.stderr)
        return 3
    except PermissionError as e:
        print(f"osmfast: error: Permission denied: {e}", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"osmfast: error: {e}", file=sys.stderr)
        if parsed_args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
