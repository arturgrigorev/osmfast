"""Extract all amenity categories to separate shapefiles."""
import os
import sys

from osm_core.api import OSMFast
from osm_core.filters.osm_filter import OSMFilter
from osm_core.filters.semantic_categories import (
    AMENITY_CATEGORIES, AMENITY_ATTRIBUTES
)

def extract_amenities(osm_file: str, output_dir: str):
    """Extract all amenity categories to separate shapefiles.

    Args:
        osm_file: Input OSM file path
        output_dir: Output directory for shapefiles
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"Extracting amenities from {osm_file}")
    print(f"Output directory: {output_dir}")
    print("=" * 60)

    total_extracted = 0

    for category_name, amenity_types in AMENITY_CATEGORIES.items():
        # Build filter for this category
        osm_filter = OSMFilter()
        osm_filter.set_global_rejection(reject_ways=True, reject_relations=True)

        # Add accept filters for each amenity type in this category
        for amenity_type in amenity_types:
            osm_filter.add_accept_filter('nodes', 'amenity', amenity_type)

        # Create extractor
        extractor = OSMFast(osm_filter)

        # Output path
        output_base = os.path.join(output_dir, f"amenities_{category_name}")

        try:
            result = extractor.extract_to_shapefile(
                osm_file, output_base,
                tag_filter=AMENITY_ATTRIBUTES
            )

            metadata = result.get('metadata', {})
            points = metadata.get('points_exported', 0)
            total_extracted += points

            if points > 0:
                print(f"  {category_name:20} {points:>8} points")
            else:
                print(f"  {category_name:20} {'(empty)':>8}")
                # Remove empty shapefiles
                for ext in ['.shp', '.shx', '.dbf', '.prj']:
                    try:
                        os.unlink(f"{output_base}_points{ext}")
                    except FileNotFoundError:
                        pass

        except Exception as e:
            print(f"  {category_name:20} ERROR: {e}")

    print("=" * 60)
    print(f"Total amenities extracted: {total_extracted}")

    # List created files
    print(f"\nFiles created in {output_dir}:")
    for f in sorted(os.listdir(output_dir)):
        if f.endswith('.shp'):
            size = os.path.getsize(os.path.join(output_dir, f))
            print(f"  {f:40} {size:>10,} bytes")


if __name__ == '__main__':
    osm_file = sys.argv[1] if len(sys.argv) > 1 else 'sydney.osm'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'sydney_amenities'

    extract_amenities(osm_file, output_dir)
