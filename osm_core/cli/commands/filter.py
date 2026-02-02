"""Filter command implementation."""
from osm_core.api import OSMFast
from osm_core.filters.osm_filter import OSMFilter


def cmd_filter(args) -> int:
    """Handle filter command.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    input_file = args.input_file
    output_file = args.output

    # Build filter from arguments
    osm_filter = _build_filter(args)

    # Create extractor with filter
    extractor = OSMFast(osm_filter)

    # Export to OSM XML
    result = extractor.extract_to_xml(input_file, output_file)

    # Print summary unless quiet
    if not args.quiet:
        metadata = result.get('metadata', {})
        elements = metadata.get('elements', {})
        processing_time = metadata.get('processing_time_seconds', 0)

        print(f"\nFilter complete:")
        print(f"  Nodes: {elements.get('nodes', 0)}")
        print(f"  Ways: {elements.get('ways', 0)}")
        print(f"  Time: {processing_time:.3f}s")
        print(f"  Output: {output_file}")

    return 0


def _build_filter(args) -> OSMFilter:
    """Build OSMFilter from command line arguments."""
    bbox = None
    if args.bbox:
        bbox = {
            'top': args.bbox[0],
            'left': args.bbox[1],
            'bottom': args.bbox[2],
            'right': args.bbox[3]
        }

    return OSMFilter.from_osmosis_args(
        accept_ways=args.accept_ways,
        reject_ways=args.reject_ways,
        accept_nodes=args.accept_nodes,
        reject_nodes=args.reject_nodes,
        used_node=args.used_node,
        reject_ways_global=args.reject_ways_global,
        reject_relations_global=args.reject_relations,
        reject_nodes_global=args.reject_nodes_global,
        bounding_box=bbox
    )
