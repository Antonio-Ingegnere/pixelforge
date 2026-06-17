#!/usr/bin/env python3
"""
sprite_forge/convert.py — Convert AI-generated images to pixel art at exact resolutions.

Usage:
    python convert.py sprite.png --auto              # detect pixel grid automatically
    python convert.py sprite.png -s 32              # square 32x32
    python convert.py sprite.png --height 128       # 128px tall, width proportional
    python convert.py sprite.png --width 64         # 64px wide, height proportional
    python convert.py sprite.png --size 69x128      # explicit WxH
    python convert.py *.png --auto -c 32            # batch auto-detect
    python convert.py sprite.png -s 32 --no-quantize -o out.png
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image

VALID_SQUARE_SIZES = [16, 32, 64, 128, 256]


def parse_size(value: str) -> Tuple[Optional[int], Optional[int]]:
    if "x" in value:
        parts = value.lower().split("x", 1)
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid size '{value}'. Use N or WxH.")
    try:
        n = int(value)
        return n, n
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid size '{value}'. Use N or WxH.")


def compute_target(
    src_w: int,
    src_h: int,
    target_w: Optional[int],
    target_h: Optional[int],
) -> Tuple[int, int]:
    if target_w and target_h:
        return target_w, target_h
    if target_h:
        return max(1, round(src_w * target_h / src_h)), target_h
    if target_w:
        return target_w, max(1, round(src_h * target_w / src_w))
    raise ValueError("At least one of width or height must be specified.")


def _autocorr_period(profile: np.ndarray, lo: int = 3, hi: int = 64) -> int:
    """
    Find the dominant repeat period in a 1D color-difference profile via
    normalized autocorrelation. Searches for the first strong peak in [lo, hi].
    Skips lags 1-2 which reflect local smoothness, not the art pixel grid.
    """
    sig = (profile - profile.mean()).astype(np.float64)
    n = len(sig)
    acorr = np.correlate(sig, sig, mode='full')[n - 1:]
    if acorr[0] == 0:
        return lo
    acorr /= acorr[0]
    hi = min(hi, len(acorr) - 1)
    return lo + int(np.argmax(acorr[lo : hi + 1]))


def detect_pixel_size(img: Image.Image) -> Tuple[int, int]:
    """
    Detect the art-pixel size (in source pixels) by autocorrelating the
    average color-change profiles along each axis.
    """
    arr = np.array(img.convert("RGB")).astype(np.float32)
    h_diff = np.abs(np.diff(arr, axis=1)).sum(axis=2).mean(axis=0)
    v_diff = np.abs(np.diff(arr, axis=0)).sum(axis=2).mean(axis=1)
    return _autocorr_period(h_diff), _autocorr_period(v_diff)


def quantize_rgba(img: Image.Image, colors: int) -> Image.Image:
    rgb = img.convert("RGB")
    quantized = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=0)
    result = quantized.convert("RGBA")
    _, _, _, alpha = img.split()
    result.putalpha(alpha)
    return result


def center_sample(img: Image.Image, tw: int, th: int) -> Image.Image:
    """
    Sample from the center of each source block. For pixel-art sources the
    center of each art-pixel block holds the true solid color; antialiasing
    only occurs near block edges.
    """
    arr = np.array(img)
    src_h, src_w = arr.shape[:2]
    xs = np.clip(((np.arange(tw) + 0.5) * src_w / tw).astype(int), 0, src_w - 1)
    ys = np.clip(((np.arange(th) + 0.5) * src_h / th).astype(int), 0, src_h - 1)
    return Image.fromarray(arr[np.ix_(ys, xs)])


def convert(
    input_path: Path,
    target_w: Optional[int],
    target_h: Optional[int],
    auto: bool,
    colors: Optional[int],
    output_path: Optional[Path],
    preview_scale: int,
) -> Path:
    img = Image.open(input_path).convert("RGBA")
    src_w, src_h = img.size

    if auto:
        px_w, px_h = detect_pixel_size(img)
        tw = max(1, round(src_w / px_w))
        th = max(1, round(src_h / px_h))
        print(f"  detected pixel size: {px_w}×{px_h}px  →  art resolution: {tw}×{th}")
    else:
        tw, th = compute_target(src_w, src_h, target_w, target_h)

    downsampled = center_sample(img, tw, th)
    result = quantize_rgba(downsampled, colors) if colors is not None else downsampled

    # When --auto is combined with a target size, upscale the detected art to
    # that size using NEAREST to preserve hard pixel edges.
    if auto and (target_w or target_h):
        uw, uh = compute_target(tw, th, target_w, target_h)
        result = result.resize((uw, uh), Image.NEAREST)
        tw, th = uw, uh
        print(f"  upscaled to: {tw}×{th}")

    if preview_scale > 1:
        w, h = result.size
        result = result.resize((w * preview_scale, h * preview_scale), Image.NEAREST)

    if output_path is None:
        scale_suffix = f"_x{preview_scale}" if preview_scale > 1 else ""
        output_path = (
            input_path.parent / f"{input_path.stem}_{tw}x{th}{scale_suffix}.png"
        )

    result.save(output_path, "PNG")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert AI-generated images to pixel art at exact resolutions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", nargs="+", help="Input image path(s)")

    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-detect the art pixel size via autocorrelation and downsample to the natural grid resolution. "
             "Combine with --height/--width/--size to upscale the result to a desired output size.",
    )

    size_group = parser.add_mutually_exclusive_group(required=False)
    size_group.add_argument(
        "-s", "--size",
        type=parse_size,
        metavar="SIZE",
        help="Target size: N for square (e.g. 32) or WxH for non-square (e.g. 69x128)",
    )
    size_group.add_argument(
        "--height",
        type=int,
        metavar="H",
        help="Target height in pixels; width is computed proportionally",
    )
    size_group.add_argument(
        "--width",
        type=int,
        metavar="W",
        help="Target width in pixels; height is computed proportionally",
    )

    parser.add_argument(
        "-c", "--colors",
        type=int,
        default=None,
        metavar="N",
        help="Reduce output to N colors (2–256). Off by default — center sampling from pixel art already gives clean colors.",
    )
    parser.add_argument(
        "-p", "--preview",
        type=int,
        default=1,
        metavar="SCALE",
        help="Upscale output with nearest-neighbor for easy viewing (e.g. -p 4)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output file path (single input only)",
    )

    args = parser.parse_args()

    if not args.auto and not args.size and not args.height and not args.width:
        parser.error("one of --auto, --size, --height, or --width is required")

    if args.output and len(args.input) > 1:
        print("Error: --output can only be used with a single input file.", file=sys.stderr)
        sys.exit(1)

    if args.colors is not None and not (2 <= args.colors <= 256):
        print("Error: --colors must be between 2 and 256.", file=sys.stderr)
        sys.exit(1)

    if args.preview < 1:
        print("Error: --preview must be at least 1.", file=sys.stderr)
        sys.exit(1)

    target_w = target_h = None
    if args.size:
        target_w, target_h = args.size
    elif args.height:
        target_h = args.height
    elif args.width:
        target_w = args.width

    errors = 0
    for path_str in args.input:
        input_path = Path(path_str)
        if not input_path.exists():
            print(f"Skipping (not found): {input_path}", file=sys.stderr)
            errors += 1
            continue
        try:
            output = convert(
                input_path=input_path,
                target_w=target_w,
                target_h=target_h,
                auto=args.auto,
                colors=args.colors,
                output_path=args.output,
                preview_scale=args.preview,
            )
            print(f"{input_path}  →  {output}")
        except Exception as exc:
            print(f"Error processing {input_path}: {exc}", file=sys.stderr)
            errors += 1

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
