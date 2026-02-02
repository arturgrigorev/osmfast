"""Extract detailed amenity types to separate shapefiles."""
import os
import sys

from osm_core.api import OSMFast
from osm_core.filters.osm_filter import OSMFilter
from osm_core.filters.semantic_categories import AMENITY_ATTRIBUTES

# High-volume amenity types to extract separately
DETAILED_AMENITIES = [
    'restaurant',
    'cafe',
    'fast_food',
    'pub',
    'bar',
    'school',
    'parking',
    'parking_space',
    'bicycle_parking',
    'fuel',
    'bank',
    'atm',
    'pharmacy',
    'hospital',
    'clinic',
    'doctors',
    'dentist',
    'place_of_worship',
    'toilets',
    'bench',
    'shelter',
    'post_box',
    'charging_station',
    'supermarket',
    'convenience',
    'kindergarten',
    'library',
    'police',
    'fire_station',
]

def extract_amenity(osm_file: str, output_dir: str, amenity_type: str, include_ways: bool = False):
    """Extract a single amenity type."""
    osm_filter = OSMFilter()

    if include_ways:
        osm_filter.add_accept_filter('nodes', 'amenity', amenity_type)
        osm_filter.add_accept_filter('ways', 'amenity', amenity_type)
    else:
        osm_filter.set_global_rejection(reject_ways=True, reject_relations=True)
        osm_filter.add_accept_filter('nodes', 'amenity', amenity_type)

    extractor = OSMFast(osm_filter)
    output_base = os.path.join(output_dir, f"amenity_{amenity_type}")

    try:
        result = extractor.extract_to_shapefile(
            osm_file, output_base,
            tag_filter=AMENITY_ATTRIBUTES
        )
        metadata = result.get('metadata', {})
        points = metadata.get('points_exported', 0)
        lines = metadata.get('lines_exported', 0)
        polygons = metadata.get('polygons_exported', 0)
        return points, lines, polygons
    except Exception as e:
        print(f"  ERROR extracting {amenity_type}: {e}")
        return 0, 0, 0


def main():
    osm_file = sys.argv[1] if len(sys.argv) > 1 else 'sydney.osm'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'sydney_amenities'

    os.makedirs(output_dir, exist_ok=True)

    print(f"Extracting detailed amenities from {osm_file}")
    print(f"Output directory: {output_dir}")
    print("=" * 70)
    print(f"{'Amenity Type':30} {'Points':>10} {'Lines':>10} {'Polygons':>10}")
    print("-" * 70)

    total_points = 0
    total_lines = 0
    total_polygons = 0

    for amenity_type in DETAILED_AMENITIES:
        points, lines, polygons = extract_amenity(osm_file, output_dir, amenity_type, include_ways=True)
        total_points += points
        total_lines += lines
        total_polygons += polygons

        if points + lines + polygons > 0:
            print(f"  {amenity_type:28} {points:>10,} {lines:>10,} {polygons:>10,}")

            # Clean up empty shapefiles
            output_base = os.path.join(output_dir, f"amenity_{amenity_type}")
            for geom_type in ['points', 'lines', 'polygons']:
                count = {'points': points, 'lines': lines, 'polygons': polygons}[geom_type]
                if count == 0:
                    for ext in ['.shp', '.shx', '.dbf', '.prj']:
                        try:
                            os.unlink(f"{output_base}_{geom_type}{ext}")
                        except FileNotFoundError:
                            pass

    print("=" * 70)
    print(f"{'TOTAL':30} {total_points:>10,} {total_lines:>10,} {total_polygons:>10,}")


if __name__ == '__main__':
    main()
