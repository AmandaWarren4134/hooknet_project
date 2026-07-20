"""
Extract MPP (microns-per-pixel) from a converted .tif and save to a
small JSON sidecar file.

Usage:
    python extract_mpp.py --tif /path/to/slide.tif --output /path/to/slide_mpp.json

Output JSON format:
    {"slide": "219076", "mpp_x": 0.504, "mpp_y": 0.504}
"""

import argparse
import json
from pathlib import Path

import tifffile


def _frac_to_float(tag_value):
    if isinstance(tag_value, tuple) and len(tag_value) == 2:
        num, den = tag_value
        return num / den if den != 0 else float("nan")
    return float(tag_value)


def get_mpp(tif_path: str):
    with tifffile.TiffFile(tif_path) as tf:
        page = tf.pages[0]
        tags = page.tags
        if "XResolution" not in tags or "YResolution" not in tags:
            raise ValueError(
                f"No XResolution/YResolution tags found in {tif_path}."
            )
        xres = _frac_to_float(tags["XResolution"].value)
        yres = _frac_to_float(tags["YResolution"].value)
        return 10000.0 / xres, 10000.0 / yres


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tif",    required=True, help="Path to converted .tif")
    p.add_argument("--slide",  required=True, help="Slide ID")
    p.add_argument("--output", required=True, help="Path to output .json sidecar")
    args = p.parse_args()

    mpp_x, mpp_y = get_mpp(args.tif)
    print(f"  {args.slide}: mpp_x={mpp_x:.6f}, mpp_y={mpp_y:.6f} um/px")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({"slide": args.slide, "mpp_x": mpp_x, "mpp_y": mpp_y}, f, indent=2)
    print(f"  Saved: {out}")


if __name__ == "__main__":
    main()
