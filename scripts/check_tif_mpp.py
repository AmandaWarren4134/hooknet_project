"""
Diagnostic script: verify MPP (microns-per-pixel) extraction from a
converted .tif produced by save_image_at_spacing_py.py.

Background
----------
save_image_at_spacing_py.py writes resolution via pyvips like this:

    image.write_to_file(
        ...,
        xres=1000.0 / spacing[0],   # spacing in um/px -> pixels/mm
        yres=1000.0 / spacing[1],
        ...
    )

No `resunit` is passed. There's a documented libvips quirk
(https://github.com/libvips/libvips/issues/1421): even though xres/yres
are conceptually pixels/mm internally, libvips writes the TIFF
XResolution/YResolution tags as pixels/CM (multiplying by 10), and the
TIFF ResolutionUnit tag value cannot be trusted to reflect this -- it
may say "inch" while the numbers are actually pixels/cm.

So the correct read-back, regardless of what ResolutionUnit claims, is:

    mpp_x = 10000.0 / XResolution_pixels_per_cm
    mpp_y = 10000.0 / YResolution_pixels_per_cm

This script reads the raw tags, prints everything (including what
ResolutionUnit claims, for comparison), computes MPP under both the
"trust ResolutionUnit" and "assume cm regardless" interpretations, and
flags which one is plausible given the known conversion target (~0.5
um/px, per the `-s 0.5` argument used in the pipeline).

Usage:
    python check_tif_mpp.py /path/to/slide.tif [--expected 0.5]
"""

import argparse
import sys

import tifffile


def frac_to_float(tag_value):
    """tifffile may return a single (num, den) tuple or a tuple of them."""
    if isinstance(tag_value, tuple) and len(tag_value) == 2 and all(
        isinstance(v, int) for v in tag_value
    ):
        num, den = tag_value
        return num / den if den != 0 else float("nan")
    # Sometimes tifffile already resolves to a plain float
    return float(tag_value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tif_path", help="Path to a converted .tif file")
    parser.add_argument(
        "--expected",
        type=float,
        default=0.5,
        help="Expected approx MPP from the conversion target (default 0.5, "
        "matching the -s 0.5 argument used in save_image_at_spacing_py.py)",
    )
    args = parser.parse_args()

    print(f"Reading: {args.tif_path}")
    print("-" * 60)

    with tifffile.TiffFile(args.tif_path) as tf:
        page = tf.pages[0]
        tags = page.tags

        print(f"Number of pages/levels in file: {len(tf.pages)}")
        print(f"Page 0 shape: {page.shape}")
        print()

        if "XResolution" not in tags or "YResolution" not in tags:
            print("ERROR: XResolution/YResolution tags not found on page 0.")
            sys.exit(1)

        xres_raw = tags["XResolution"].value
        yres_raw = tags["YResolution"].value
        res_unit_tag = tags["ResolutionUnit"].value if "ResolutionUnit" in tags else None

        xres = frac_to_float(xres_raw)
        yres = frac_to_float(yres_raw)

        print(f"Raw XResolution tag value: {xres_raw}  -> {xres:.6f}")
        print(f"Raw YResolution tag value: {yres_raw}  -> {yres:.6f}")
        print(f"ResolutionUnit tag value: {res_unit_tag} "
              f"(1=none, 2=inch, 3=cm per TIFF spec)")
        print()

        # Interpretation A: trust the ResolutionUnit tag literally
        unit_to_um = {1: None, 2: 25400.0, 3: 10000.0}  # um per unit
        literal_um_per_unit = unit_to_um.get(res_unit_tag)
        if literal_um_per_unit is not None:
            mpp_x_literal = literal_um_per_unit / xres
            mpp_y_literal = literal_um_per_unit / yres
        else:
            mpp_x_literal = mpp_y_literal = float("nan")

        # Interpretation B: known libvips quirk -- always pixels/cm
        # regardless of what ResolutionUnit claims
        mpp_x_quirk = 10000.0 / xres
        mpp_y_quirk = 10000.0 / yres

        print("Interpretation A (trust ResolutionUnit tag literally):")
        print(f"  mpp_x = {mpp_x_literal:.6f} um/px")
        print(f"  mpp_y = {mpp_y_literal:.6f} um/px")
        print()
        print("Interpretation B (libvips quirk: always pixels/cm, ignore ResolutionUnit):")
        print(f"  mpp_x = {mpp_x_quirk:.6f} um/px")
        print(f"  mpp_y = {mpp_y_quirk:.6f} um/px")
        print()

        print(f"Expected MPP (~from -s {args.expected} conversion target): {args.expected}")
        print("-" * 60)

        tol = args.expected * 0.3  # generous tolerance given SPACING_MARGIN logic upstream

        a_match = abs(mpp_x_literal - args.expected) < tol if literal_um_per_unit else False
        b_match = abs(mpp_x_quirk - args.expected) < tol

        if b_match and not a_match:
            print("RESULT: Interpretation B (cm quirk) matches the expected MPP.")
            print("        => Use: mpp = 10000.0 / XResolution, regardless of ResolutionUnit tag.")
        elif a_match and not b_match:
            print("RESULT: Interpretation A (literal ResolutionUnit) matches the expected MPP.")
            print("        => The libvips cm-quirk does NOT apply here -- use the tag as stated.")
        elif a_match and b_match:
            print("RESULT: Both interpretations match (ResolutionUnit tag must be 'cm').")
            print("        => Either formula works; the quirk is moot in this case.")
        else:
            print("RESULT: NEITHER interpretation matches the expected MPP.")
            print("        => Don't trust either formula yet. Investigate further before")
            print("           using this for downstream area/perimeter calculations.")
            print(f"           (mpp_x_literal={mpp_x_literal}, mpp_x_quirk={mpp_x_quirk}, "
                  f"expected~{args.expected})")


if __name__ == "__main__":
    main()
