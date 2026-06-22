from pathlib import Path

import pyvips
from skimage import color
from skimage.filters import threshold_otsu
from skimage.morphology import (
    remove_small_holes,
    remove_small_objects,
)

from wholeslidedata import WholeSlideImage

import argparse


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    wsi_tif = WholeSlideImage(args.input)

    processing_spacing = 8.0
    processing_spacing = wsi_tif.get_real_spacing(processing_spacing)

    print("Processing spacing:", processing_spacing)

    processing_slide = wsi_tif.get_slide(processing_spacing)

    grey_processing_slide = color.rgb2gray(processing_slide)

    processing_slide_mask = (
        grey_processing_slide
        < threshold_otsu(grey_processing_slide)
    )

    processing_slide_mask = remove_small_objects(
        processing_slide_mask,
        min_size=500,
    )

    processing_slide_mask = remove_small_holes(
        processing_slide_mask,
        area_threshold=500,
    )

    tif_mask_spacing = 2.0
    tif_mask_spacing = wsi_tif.get_real_spacing(
        tif_mask_spacing
    )

    print("Mask spacing:", tif_mask_spacing)

    upsample_ratio = (
        processing_spacing
        / tif_mask_spacing
    )

    print("Upsample ratio:", upsample_ratio)

    mask_img = pyvips.Image.new_from_array(
        processing_slide_mask.astype("uint8") * 255
    )

    mask_img_upscaled = mask_img.resize(
        upsample_ratio,
        kernel=pyvips.enums.Kernel.NEAREST,
    )

    output_path = args.output

    xres = tif_mask_spacing
    yres = tif_mask_spacing

    # Ensure binary mask (0/255 uint8)
    mask_img_upscaled = mask_img_upscaled > 0
    mask_img_upscaled = mask_img_upscaled.cast("uchar") * 255

    # Save pyramid TIFF
    mask_img_upscaled.tiffsave(
        output_path,
        compression="lzw",
        tile=True,
        tile_width=512,
        tile_height=512,
        pyramid=True,
        bigtiff=True,
        background=[0],
        resunit="cm",
        xres=1000 / tif_mask_spacing,
        yres=1000 / tif_mask_spacing
    )

    print("Saved:", output_path)


if __name__ == "__main__":
    main()