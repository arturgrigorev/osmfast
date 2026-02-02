# OSMFast API Documentation

## Overview

OSMFast provides both command-line and Python API interfaces for ultra-high performance OpenStreetMap data extraction. This document covers the complete Python API with examples and best practices.

## Core Classes

### UltraFastOSMParser

The main extraction engine combining memory-mapped I/O with semantic feature filtering.

```python
class UltraFastOSMParser:
    """Ultra-high performance OSM parser with memory-mapped I/O and caching."""
    
    def __init__(self, osm_filter=None, enable_caching=True):
        """
        Initialize the parser.
        
        Args:
            osm_filter (OSMFilter, optional): Filtering rules for elements
            enable_caching (bool): Enable regex pattern caching (default: True)
        """
```

#### Core Methods

##### extract_features()
```python
def extract_features(self, file_path: str) -> Dict[str, Any]:
    """
    Extract semantic features from OSM file.
    
    Args:
        file_path (str): Path to OSM XML file
        
    Returns:
        Dict containing:
        - features: Dict with amenities, highways, buildings lists
        - metadata: Processing statistics and performance metrics
        
    Example:
        parser = UltraFastOSMParser()
        result = parser.extract_features('map.osm')
        amenities = result['features']['amenities']
        processing_time = result['metadata']['processing_time_seconds']
    """
```

##### parse_file()
```python
def parse_file(self, file_path: str) -> ParseResult:
    """
    Parse OSM file and return raw elements.
    
    Args:
        file_path (str): Path to OSM XML file
        
    Returns:
        ParseResult with nodes, ways, and metadata
        
    Example:
        parser = UltraFastOSMParser()
        result = parser.parse_file('map.osm')
        nodes = result.nodes
        ways = result.ways
    """
```

##### extract_to_geojson()
```python
def extract_to_geojson(self, osm_file_path: str, output_file: str):
    """
    Extract features and export to GeoJSON format.
    
    Args:
        osm_file_path (str): Input OSM file path
        output_file (str): Output GeoJSON file path
        
    Example:
        parser = UltraFastOSMParser()
        parser.extract_to_geojson('map.osm', 'features.geojson')
    """
```

##### extract_to_csv()
```python
def extract_to_csv(self, osm_file_path: str, output_file: str, include_metadata: bool = False):
    """
    Extract elements and export to CSV format.
    
    Args:
        osm_file_path (str): Input OSM file path
        output_file (str): Output CSV file path
        include_metadata (bool): Include analysis columns (default: False)
        
    Example:
        parser = UltraFastOSMParser()
        parser.extract_to_csv('map.osm', 'data.csv', include_metadata=True)
    """
```

### OSMFilter

Osmosis-compatible filtering system for element selection.

```python
class OSMFilter:
    """Osmosis-compatible filtering for OSM elements."""
    
    def __init__(self):
        """Initialize empty filter set."""
```

#### Filtering Methods

##### add_accept_filter()
```python
def add_accept_filter(self, element_type: str, tag_key: str, tag_value: str):
    """
    Add acceptance filter for elements.
    
    Args:
        element_type (str): 'nodes' or 'ways'
        tag_key (str): OSM tag key to match
        tag_value (str): Tag value or '*' for any value
        
    Example:
        osm_filter = OSMFilter()
        osm_filter.add_accept_filter('nodes', 'amenity', 'restaurant')
        osm_filter.add_accept_filter('ways', 'highway', '*')
    """
```

##### add_reject_filter()
```python
def add_reject_filter(self, element_type: str, tag_key: str, tag_value: str):
    """
    Add rejection filter for elements.
    
    Args:
        element_type (str): 'nodes' or 'ways'
        tag_key (str): OSM tag key to match
        tag_value (str): Tag value or '*' for any value
        
    Example:
        osm_filter = OSMFilter()
        osm_filter.add_reject_filter('ways', 'highway', 'footway')
    """
```

##### set_bounding_box()
```python
def set_bounding_box(self, top: float, left: float, bottom: float, right: float):
    """
    Set geographic bounding box filter.
    
    Args:
        top (float): Maximum latitude
        left (float): Minimum longitude  
        bottom (float): Minimum latitude
        right (float): Maximum longitude
        
    Example:
        osm_filter = OSMFilter()
        osm_filter.set_bounding_box(49.51, 10.93, 49.38, 11.20)
    """
```

### Data Classes

#### OSMNode
```python
@dataclass
class OSMNode:
    """Represents an OSM node with location and tags."""
    id: str
    lat: float
    lon: float
    tags: Dict[str, str]
```

#### OSMWay
```python
@dataclass  
class OSMWay:
    """Represents an OSM way with node references and tags."""
    id: str
    node_refs: List[str]
    tags: Dict[str, str]
```

#### SemanticFeature
```python
@dataclass
class SemanticFeature:
    """Semantic feature with intelligent categorization."""
    id: str
    feature_type: str           # 'amenity', 'highway', 'building'
    feature_subtype: str        # Specific type (restaurant, primary, residential)
    name: Optional[str]
    geometry_type: str          # 'point', 'linestring', 'polygon'
    coordinates: List[float]
    properties: Dict[str, str]  # All OSM tags
```

## Usage Examples

### Basic Feature Extraction

```python
from osmfast import UltraFastOSMParser

# Initialize parser
parser = UltraFastOSMParser()

# Extract all features
result = parser.extract_features('map.osm')

# Access features by category
amenities = result['features']['amenities']
highways = result['features']['highways'] 
buildings = result['features']['buildings']

# Performance metrics
metadata = result['metadata']
print(f"Processing time: {metadata['processing_time_seconds']:.3f}s")
print(f"Extraction rate: {metadata['extraction_rate_features_per_second']:.1f} features/sec")
```

### Filtered Extraction

```python
from osmfast import UltraFastOSMParser, OSMFilter

# Create filter for restaurants only
osm_filter = OSMFilter()
osm_filter.add_accept_filter('nodes', 'amenity', 'restaurant')

# Initialize parser with filter
parser = UltraFastOSMParser(osm_filter)

# Extract filtered features
result = parser.extract_features('map.osm')
restaurants = result['features']['amenities']

print(f"Found {len(restaurants)} restaurants")
for restaurant in restaurants:
    print(f"- {restaurant.name}: {restaurant.properties.get('cuisine', 'N/A')}")
```

### Geographic Filtering

```python
from osmfast import UltraFastOSMParser, OSMFilter

# Create geographic filter
osm_filter = OSMFilter()
osm_filter.set_bounding_box(-33.90, 151.20, -33.91, 151.21)  # Sydney area
osm_filter.add_accept_filter('nodes', 'amenity', '*')

# Extract amenities in bounding box
parser = UltraFastOSMParser(osm_filter)
result = parser.extract_features('map.osm')

print(f"Found {len(result['features']['amenities'])} amenities in area")
```

### Complex Filtering (Osmosis-Style)

```python
from osmfast import UltraFastOSMParser, OSMFilter

# Complex filter: highways but not footways, with used nodes
osm_filter = OSMFilter()
osm_filter.add_accept_filter('ways', 'highway', '*')
osm_filter.add_reject_filter('ways', 'highway', 'footway')
osm_filter.set_used_node_mode(True)

parser = UltraFastOSMParser(osm_filter)
result = parser.parse_file('map.osm')

print(f"Found {len(result.ways)} highway ways")
print(f"Found {len(result.nodes)} nodes (used by ways)")
```

### Multi-Format Export

```python
from osmfast import UltraFastOSMParser, OSMFilter

parser = UltraFastOSMParser()

# Export to different formats
parser.extract_to_geojson('map.osm', 'features.geojson')
parser.extract_to_csv('map.osm', 'features.csv', include_metadata=True)

# With filtering
osm_filter = OSMFilter()
osm_filter.add_accept_filter('nodes', 'amenity', 'restaurant')

filtered_parser = UltraFastOSMParser(osm_filter)
filtered_parser.extract_to_csv('map.osm', 'restaurants.csv')
```

## Performance Optimization

### Memory-Mapped I/O
```python
# Automatically enabled for files >1MB
parser = UltraFastOSMParser(enable_caching=True)  # Default

# For maximum performance on large files
result = parser.extract_features('large_map.osm')
```

### Pattern Caching
```python
# Enable pattern caching (default)
parser = UltraFastOSMParser(enable_caching=True)

# Disable for memory-constrained environments
parser = UltraFastOSMParser(enable_caching=False)
```

### Streaming Processing
```python
# Streaming is automatic - handles files of any size
parser = UltraFastOSMParser()
result = parser.extract_features('massive_planet.osm')  # Works with GB+ files
```

## Error Handling

### File Handling
```python
from osmfast import UltraFastOSMParser

parser = UltraFastOSMParser()

try:
    result = parser.extract_features('map.osm')
except FileNotFoundError:
    print("OSM file not found")
except PermissionError:
    print("Cannot read OSM file")
except Exception as e:
    print(f"Parsing error: {e}")
```

### Data Validation
```python
from osmfast import UltraFastOSMParser

parser = UltraFastOSMParser()
result = parser.extract_features('map.osm')

# Check for valid extraction
if result['metadata']['features_extracted']['total'] == 0:
    print("No features found - check filters or file content")
    
# Validate geographic bounds
metadata = result['metadata']
if 'geographic_bounds' in metadata:
    bounds = metadata['geographic_bounds']
    print(f"Data covers: {bounds['min_lat']:.4f} to {bounds['max_lat']:.4f} lat")
```

## Integration Patterns

### With Pandas
```python
import pandas as pd
from osmfast import UltraFastOSMParser

# Extract to CSV then load with pandas
parser = UltraFastOSMParser()
parser.extract_to_csv('map.osm', 'data.csv', include_metadata=True)

# Load and analyze
df = pd.read_csv('data.csv')
amenity_counts = df['amenity'].value_counts()
print("Top amenities:")
print(amenity_counts.head())
```

### With GIS Tools
```python
import json
from osmfast import UltraFastOSMParser

# Extract to GeoJSON for GIS tools
parser = UltraFastOSMParser()
parser.extract_to_geojson('map.osm', 'features.geojson')

# Load GeoJSON
with open('features.geojson', 'r') as f:
    geojson_data = json.load(f)

print(f"Exported {len(geojson_data['features'])} features for GIS")
```

### Batch Processing
```python
import os
from osmfast import UltraFastOSMParser, OSMFilter

def process_osm_directory(input_dir, output_dir):
    """Process all OSM files in directory."""
    parser = UltraFastOSMParser()
    
    for filename in os.listdir(input_dir):
        if filename.endswith('.osm'):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename.replace('.osm', '.json'))
            
            result = parser.extract_features(input_path)
            
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2, default=str)
                
            print(f"Processed {filename}: {result['metadata']['features_extracted']['total']} features")

# Usage
process_osm_directory('osm_files/', 'json_output/')
```

## Best Practices

### 1. Choose Appropriate Filters
```python
# Good: Specific filtering
osm_filter = OSMFilter()
osm_filter.add_accept_filter('nodes', 'amenity', 'restaurant')

# Less efficient: No filtering on large files
parser = UltraFastOSMParser()  # Processes everything
```

### 2. Use Streaming for Large Files
```python
# Good: Let parser handle streaming automatically
parser = UltraFastOSMParser()
result = parser.extract_features('large_file.osm')

# Memory usage stays constant regardless of file size
```

### 3. Validate Outputs
```python
# Always check extraction results
result = parser.extract_features('map.osm')
if result['metadata']['features_extracted']['total'] == 0:
    print("Warning: No features extracted")
```

### 4. Choose Output Format Appropriately
```python
# For data analysis
parser.extract_to_csv('map.osm', 'analysis.csv', include_metadata=True)

# For web mapping
parser.extract_to_geojson('map.osm', 'webmap.geojson')

# For osmosis workflows  
filtered_parser.parse_file_to_osm('map.osm', 'filtered.osm')
```

This API provides production-ready OSM data extraction with unmatched performance and complete osmosis compatibility.