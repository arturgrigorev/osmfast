"""Merge command implementation."""
from osm_core.api import OSMFast


def cmd_merge(args) -> int:
    """Handle merge command.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code
    """
    input_files = args.input_files
    output_file = args.output

    # Validate minimum files
    if len(input_files) < 2:
        print("osmfast: error: Merge requires at least 2 input files")
        print("Usage: osmfast merge FILE1 FILE2 [FILE3...] -o OUTPUT")
        return 2

    # Perform merge
    result = OSMFast.merge_osm_files(input_files, output_file)

    # Print summary unless quiet
    if not args.quiet:
        metadata = result.get('metadata', {})
        elements = metadata.get('elements_merged', {})
        processing_time = metadata.get('processing_time_seconds', 0)

        print(f"\nMerge complete:")
        print(f"  Input files: {len(input_files)}")
        print(f"  Nodes: {elements.get('nodes', 0)}")
        print(f"  Ways: {elements.get('ways', 0)}")
        print(f"  Total: {elements.get('total', 0)}")
        print(f"  Time: {processing_time:.3f}s")
        print(f"  Output: {output_file}")

    return 0
