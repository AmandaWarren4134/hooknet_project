"""
TLS/GC Feature Extraction
"""

import argparse
import json
import math
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import tifffile
from shapely.geometry import shape
from shapely.validation import make_valid
from scipy.spatial import cKDTree


# ---------------------------------------------------------------------------
# MPP helpers
# ---------------------------------------------------------------------------

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
        mpp_x = 10000.0 / xres
        mpp_y = 10000.0 / yres
        return mpp_x, mpp_y


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def repair_geometry(geom, label=""):
    if geom is None:
        return None
    if not geom.is_valid:
        warnings.warn(
            f"Invalid geometry{' for ' + label if label else ''}; "
            "repairing with make_valid()."
        )
        geom = make_valid(geom)
    return geom


def px_area_to_um2(area_px2, mpp_x, mpp_y):
    return area_px2 * mpp_x * mpp_y


def px_length_to_um(length_px, mpp_x, mpp_y):
    mpp_mean = (mpp_x + mpp_y) / 2.0
    return length_px * mpp_mean


def circularity(area_px2, perimeter_px):
    if perimeter_px <= 0:
        return float("nan")
    c = (4.0 * math.pi * area_px2) / (perimeter_px ** 2)
    return min(c, 1.0)


def solidity(geom):
    hull_area = geom.convex_hull.area
    if hull_area <= 0:
        return float("nan")
    return geom.area / hull_area


def aspect_ratio(geom):
    try:
        mrr = geom.minimum_rotated_rectangle
        coords = list(mrr.exterior.coords)
        if len(coords) < 4:
            return float("nan")
        dx0 = coords[1][0] - coords[0][0]
        dy0 = coords[1][1] - coords[0][1]
        dx1 = coords[2][0] - coords[1][0]
        dy1 = coords[2][1] - coords[1][1]
        e0 = math.hypot(dx0, dy0)
        e1 = math.hypot(dx1, dy1)
        major = max(e0, e1)
        minor = min(e0, e1)
        return major / minor if minor > 0 else float("nan")
    except Exception:
        return float("nan")


def geometry_features(geom, mpp_x, mpp_y, prefix=""):
    area_px = geom.area
    perim_px = geom.length
    hull_area_px = geom.convex_hull.area
    centroid = geom.centroid
    area_um2      = px_area_to_um2(area_px, mpp_x, mpp_y)
    perim_um      = px_length_to_um(perim_px, mpp_x, mpp_y)
    hull_area_um2 = px_area_to_um2(hull_area_px, mpp_x, mpp_y)
    return {
        f"{prefix}area_um2":             area_um2,
        f"{prefix}perimeter_um":         perim_um,
        f"{prefix}circularity":          circularity(area_px, perim_px),
        f"{prefix}solidity":             solidity(geom),
        f"{prefix}aspect_ratio":         aspect_ratio(geom),
        f"{prefix}centroid_x_px":        centroid.x,
        f"{prefix}centroid_y_px":        centroid.y,
        f"{prefix}convex_hull_area_um2": hull_area_um2,
    }


# ---------------------------------------------------------------------------
# Load and split GeoJSON
# ---------------------------------------------------------------------------

def load_geojson(geojson_path: str):
    gdf = gpd.read_file(geojson_path)

    if len(gdf) == 0 or "classification" not in gdf.columns:
        print("  No annotations found in GeoJSON (empty slide).")
        empty = gpd.GeoDataFrame(columns=["geometry", "class_name"])
        return empty, empty

    def extract_class_name(val):
        if isinstance(val, dict):
            return val.get("name", "")
        if isinstance(val, str):
            try:
                d = json.loads(val.replace("'", '"'))
                return d.get("name", "")
            except Exception:
                return val
        return str(val) if val is not None else ""

    gdf["class_name"] = gdf["classification"].apply(extract_class_name)
    gdf["geometry"] = [
        repair_geometry(g, label=f"feature {i}")
        for i, g in enumerate(gdf.geometry)
    ]
    gdf = gdf[gdf.geometry.notna()].copy()

    tls_gdf = gdf[gdf["class_name"] == "tls"].copy().reset_index(drop=True)
    gc_gdf  = gdf[gdf["class_name"] == "gc"].copy().reset_index(drop=True)

    print(f"  Loaded {len(tls_gdf)} TLS, {len(gc_gdf)} GC annotations")
    return tls_gdf, gc_gdf


# ---------------------------------------------------------------------------
# Nearest-neighbour distances
# ---------------------------------------------------------------------------

def nearest_neighbour_distances(tls_gdf, mpp_x, mpp_y):
    if len(tls_gdf) < 2:
        return pd.Series([float("nan")] * len(tls_gdf), index=tls_gdf.index)
    mpp_mean = (mpp_x + mpp_y) / 2.0
    centroids = np.array([[g.centroid.x, g.centroid.y] for g in tls_gdf.geometry])
    tree = cKDTree(centroids)
    dists, _ = tree.query(centroids, k=2)
    nn_dists_px = dists[:, 1]
    nn_dists_um = nn_dists_px * mpp_mean
    return pd.Series(nn_dists_um, index=tls_gdf.index)


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_features(slide: str, geojson_path: str, mpp_x: float, mpp_y: float, output_dir: Path):
    print(f"\nProcessing slide: {slide}")

    print(f"  MPP: x={mpp_x:.4f}, y={mpp_y:.4f} um/px")

    tls_gdf, gc_gdf = load_geojson(geojson_path)

    if len(tls_gdf) == 0:
        print("  WARNING: No TLS annotations found.")

        cols = [
            "slide", "tls_id", "mpp_x", "mpp_y",
            "tls_area_um2", "tls_perimeter_um", "tls_circularity",
            "tls_solidity", "tls_aspect_ratio", "tls_convex_hull_area_um2",
            "tls_centroid_x_px", "tls_centroid_y_px",
            "gc_count", "gc_present",
            "gc_total_area_um2", "gc_mean_area_um2", "gc_area_ratio",
            "gc_mean_circularity", "gc_mean_solidity",
            "nn_dist_um",
        ]

        tls_df = pd.DataFrame(columns=cols)

        output_dir.mkdir(parents=True, exist_ok=True)
        tls_out = output_dir / f"{slide}_tls.csv"
        tls_df.to_csv(tls_out, index=False)

        print(f"  Wrote empty TLS table -> {tls_out}")

        return tls_df, None

    # Per-TLS geometry features
    tls_rows = []
    for tls_idx, row in tls_gdf.iterrows():
        geom = row.geometry
        feats = geometry_features(geom, mpp_x, mpp_y, prefix="tls_")
        feats["tls_id"] = tls_idx
        feats["slide"]  = slide
        feats["mpp_x"]  = mpp_x
        feats["mpp_y"]  = mpp_y
        tls_rows.append(feats)

    tls_df = pd.DataFrame(tls_rows)
    tls_df["nn_dist_um"] = nearest_neighbour_distances(tls_gdf, mpp_x, mpp_y).values

    # GC -> TLS spatial join
    gc_agg = pd.DataFrame(columns=[
        "tls_id", "gc_count", "gc_total_area_um2",
        "gc_mean_area_um2", "gc_mean_circularity", "gc_mean_solidity"
    ])
    orphan_gc_rows = []

    if len(gc_gdf) > 0:
        tls_join = tls_gdf[["geometry"]].copy()
        tls_join["tls_id"] = tls_gdf.index

        joined = gpd.sjoin(gc_gdf, tls_join, how="left", predicate="within")
        orphan_mask = joined["index_right"].isna()

        if orphan_mask.sum() > 0:
            orphan_gc = gc_gdf.loc[joined[orphan_mask].index].copy()
            fallback = gpd.sjoin(orphan_gc, tls_join, how="left", predicate="intersects")
            fallback = fallback.sort_values("index_right").drop_duplicates(subset=["geometry"], keep="first")
            joined.loc[orphan_mask, "index_right"] = fallback["index_right"].values

        true_orphan_mask = joined["index_right"].isna()
        if true_orphan_mask.sum() > 0:
            print(f"  WARNING: {true_orphan_mask.sum()} GC(s) not within any TLS.")
            orphan_gc_rows = gc_gdf.loc[joined[true_orphan_mask].index].copy()
            orphan_gc_rows["slide"] = slide

        assigned_gc = joined[~joined["index_right"].isna()].copy()
        assigned_gc["tls_id"] = assigned_gc["index_right"].astype(int)

        gc_feat_rows = []
        for _, gc_row in assigned_gc.iterrows():
            f = geometry_features(gc_row.geometry, mpp_x, mpp_y, prefix="gc_")
            f["tls_id"] = gc_row["tls_id"]
            gc_feat_rows.append(f)

        if gc_feat_rows:
            gc_feat_df = pd.DataFrame(gc_feat_rows)
            gc_agg = gc_feat_df.groupby("tls_id").agg(
                gc_count           =("gc_area_um2",    "count"),
                gc_total_area_um2  =("gc_area_um2",    "sum"),
                gc_mean_area_um2   =("gc_area_um2",    "mean"),
                gc_mean_circularity=("gc_circularity", "mean"),
                gc_mean_solidity   =("gc_solidity",    "mean"),
            ).reset_index()
    else:
        print("  No GC annotations found on this slide.")

    # Merge and derive final columns
    tls_df = tls_df.merge(gc_agg, on="tls_id", how="left")
    tls_df["gc_count"]          = tls_df["gc_count"].fillna(0).astype(int)
    tls_df["gc_total_area_um2"] = tls_df["gc_total_area_um2"].fillna(0.0)
    tls_df["gc_present"]        = (tls_df["gc_count"] > 0).astype(int)
    tls_df["gc_area_ratio"]     = tls_df["gc_total_area_um2"] / tls_df["tls_area_um2"]
    tls_df["gc_area_ratio"]     = tls_df["gc_area_ratio"].where(tls_df["gc_present"] == 1)

    col_order = [
        "slide", "tls_id", "mpp_x", "mpp_y",
        "tls_area_um2", "tls_perimeter_um", "tls_circularity",
        "tls_solidity", "tls_aspect_ratio", "tls_convex_hull_area_um2",
        "tls_centroid_x_px", "tls_centroid_y_px",
        "gc_count", "gc_present",
        "gc_total_area_um2", "gc_mean_area_um2", "gc_area_ratio",
        "gc_mean_circularity", "gc_mean_solidity",
        "nn_dist_um",
    ]
    tls_df = tls_df[[c for c in col_order if c in tls_df.columns]]

    output_dir.mkdir(parents=True, exist_ok=True)
    tls_out = output_dir / f"{slide}_tls.csv"
    tls_df.to_csv(tls_out, index=False)
    print(f"  Wrote {len(tls_df)} TLS rows -> {tls_out}")

    if len(orphan_gc_rows) > 0:
        orphan_out = output_dir / f"{slide}_orphan_gc.csv"
        orphan_gc_rows.to_csv(orphan_out, index=False)
        print(f"  Wrote orphan GC rows -> {orphan_out}")

    return tls_df, orphan_gc_rows


# ---------------------------------------------------------------------------
# Slide-level summary
# ---------------------------------------------------------------------------

def slide_summary(tls_df: pd.DataFrame, slide: str):
    if tls_df is None or len(tls_df) == 0:
        return None
    d = {"slide": slide}
    d["tls_count"]         = len(tls_df)
    d["gc_plus_tls_count"] = tls_df["gc_present"].sum()
    d["gc_plus_fraction"]  = tls_df["gc_present"].mean()
    d["total_gc_count"]    = tls_df["gc_count"].sum()
    d["mean_gc_per_tls"]   = tls_df["gc_count"].mean()
    for col in ["tls_area_um2", "tls_circularity", "tls_solidity",
                "tls_aspect_ratio", "gc_area_ratio", "nn_dist_um"]:
        if col in tls_df:
            d[f"mean_{col}"]   = tls_df[col].mean()
            d[f"median_{col}"] = tls_df[col].median()
    d["total_tls_area_um2"] = tls_df["tls_area_um2"].sum()
    d["total_gc_area_um2"]  = tls_df["gc_total_area_um2"].sum()
    return d


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--geojson", required=True)
    p.add_argument("--mpp",     required=True, help="Path to .json sidecar with mpp_x/mpp_y")
    p.add_argument("--slide",   required=True)
    p.add_argument("--output",  required=True)
    return p.parse_args()


def main():
    args = parse_args()
    output_dir = Path(args.output)

    with open(args.mpp) as f:
        mpp_data = json.load(f)
    mpp_x = mpp_data["mpp_x"]
    mpp_y = mpp_data["mpp_y"]

    tls_df, _ = extract_features(
        slide=args.slide,
        geojson_path=args.geojson,
        mpp_x=mpp_x,
        mpp_y=mpp_y,
        output_dir=output_dir,
    )

    summary_row = slide_summary(tls_df, args.slide)

    print(f"\nDone. Per-slide: {output_dir / (args.slide + '_tls.csv')}")


if __name__ == "__main__":
    main()
