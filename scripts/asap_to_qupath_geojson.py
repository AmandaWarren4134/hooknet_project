"""
ASAP XML → QuPath GeoJSON converter
------------------------------------
Usage:
    python asap_to_qupath_geojson.py input.xml output.geojson

QuPath can then import the .geojson via:
    Annotations menu → Import annotations → Import from GeoJSON
"""

import xml.etree.ElementTree as ET
import json
import sys
from pathlib import Path


# Map ASAP annotation types to GeoJSON geometry types
GEOMETRY_MAP = {
    "Polygon": "Polygon",
    "Rectangle": "Polygon",   # rectangles → closed polygon
    "Dot": "Point",
    "Spline": "Polygon",      # treat splines as polygons
    "PointSet": "MultiPoint",
}

# Add/edit entries to match your project's groups
GROUP_COLORS = {
    "tls":        [0,   0,   0],    # black  (matches XML)
    # add more as needed
}


def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        return [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]
    return [0, 0, 0]


def color_for_group(group: str, fallback_hex: str) -> list:
    lower = group.lower()
    if lower in GROUP_COLORS:
        return GROUP_COLORS[lower]
    # try to parse the XML Color attribute
    fc = fallback_hex.lower()
    if fc == "black":  return [0, 0, 0]
    if fc == "red":    return [255, 0, 0]
    if fc == "green":  return [0, 255, 0]
    if fc == "blue":   return [0, 0, 255]
    if fc == "yellow": return [255, 255, 0]
    if fc.startswith("#"):
        return hex_to_rgb(fc)
    return [0, 0, 0]


def parse_asap_xml(xml_path: str) -> list:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    features = []

    annotations = root.find("Annotations")
    if annotations is None:
        raise ValueError("No <Annotations> element found in XML.")

    for ann in annotations.findall("Annotation"):
        name   = ann.get("Name", "Annotation")
        atype  = ann.get("Type", "Polygon")
        group  = ann.get("PartOfGroup", "")
        color  = ann.get("Color", "#000000")

        coords_el = ann.find("Coordinates")
        if coords_el is None:
            continue

        # Parse and sort coordinates by Order
        raw = []
        for c in coords_el.findall("Coordinate"):
            order = int(c.get("Order", 0))
            x     = float(c.get("X", 0))
            y     = float(c.get("Y", 0))
            raw.append((order, x, y))
        raw.sort(key=lambda t: t[0])
        points = [(x, y) for _, x, y in raw]

        geom_type = GEOMETRY_MAP.get(atype, "Polygon")

        # Build GeoJSON geometry
        if geom_type == "Point":
            geometry = {
                "type": "Point",
                "coordinates": points[0] if points else [0, 0]
            }
        elif geom_type == "MultiPoint":
            geometry = {
                "type": "MultiPoint",
                "coordinates": points
            }
        else:
            # Polygon: GeoJSON requires the ring to be closed
            ring = points[:]
            if ring and ring[0] != ring[-1]:
                ring.append(ring[0])
            geometry = {
                "type": "Polygon",
                "coordinates": [ring]
            }

        rgb = color_for_group(group, color)

        # QuPath reads classification from properties.classification.name
        # and color from properties.classification.colorRGB (packed int)
        packed_color = (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]

        feature = {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "name": name,
                "classification": {
                    "name": group if group else "None",
                    "colorRGB": packed_color
                },
                "isLocked": False,
                "measurements": []
            }
        }
        features.append(feature)

    return features


def convert(xml_path: str, out_path: str):
    print(f"Reading: {xml_path}")
    features = parse_asap_xml(xml_path)
    print(f"  Found {len(features)} annotation(s)")

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(out_path, "w") as f:
        json.dump(geojson, f, indent=2)

    print(f"Written: {out_path}")
    print()
    print("To import into QuPath:")
    print("  Annotations menu → Import annotations → Import from GeoJSON")
    print("  (or drag-and-drop the .geojson file onto the QuPath viewer)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python asap_to_qupath_geojson.py  input.xml  output.geojson")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
