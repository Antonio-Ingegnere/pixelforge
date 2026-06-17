"""
Sprite Forge backend — convert AI-generated images to clean pixel art.

All functions are pure (no print, no sys.exit). Pass a log callback to capture output.
"""

from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np
from PIL import Image


def parse_size(value: str) -> Tuple[Optional[int], Optional[int]]:
    if "x" in value.lower():
        parts = value.lower().split("x", 1)
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            raise ValueError(f"Invalid size '{value}'. Use N or WxH.")
    try:
        n = int(value)
        return n, n
    except ValueError:
        raise ValueError(f"Invalid size '{value}'. Use N or WxH.")


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
    sig = (profile - profile.mean()).astype(np.float64)
    n = len(sig)
    acorr = np.correlate(sig, sig, mode="full")[n - 1:]
    if acorr[0] == 0:
        return lo
    acorr /= acorr[0]
    hi = min(hi, len(acorr) - 1)
    return lo + int(np.argmax(acorr[lo : hi + 1]))


def detect_pixel_size(img: Image.Image) -> Tuple[int, int]:
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
    log: Optional[Callable[[str], None]] = None,
) -> Tuple[Path, Image.Image, Image.Image]:
    """
    Convert a single image to pixel art.

    Returns (output_path, source_image, result_image).
    source_image and result_image are at the true art resolution (before preview_scale).
    """
    _log = log or print
    img = Image.open(input_path).convert("RGBA")
    src_w, src_h = img.size
    source_img = img.copy()

    if auto:
        px_w, px_h = detect_pixel_size(img)
        tw = max(1, round(src_w / px_w))
        th = max(1, round(src_h / px_h))
        _log(f"  detected pixel size: {px_w}×{px_h}px  →  art resolution: {tw}×{th}")
    else:
        tw, th = compute_target(src_w, src_h, target_w, target_h)

    downsampled = center_sample(img, tw, th)
    result = quantize_rgba(downsampled, colors) if colors is not None else downsampled

    if auto and (target_w or target_h):
        uw, uh = compute_target(tw, th, target_w, target_h)
        result = result.resize((uw, uh), Image.NEAREST)
        tw, th = uw, uh
        _log(f"  upscaled to: {tw}×{th}")

    result_img = result.copy()

    if preview_scale > 1:
        w, h = result.size
        result = result.resize((w * preview_scale, h * preview_scale), Image.NEAREST)

    if output_path is None:
        scale_suffix = f"_x{preview_scale}" if preview_scale > 1 else ""
        output_path = (
            input_path.parent / f"{input_path.stem}_{tw}x{th}{scale_suffix}.png"
        )

    result.save(output_path, "PNG")
    return output_path, source_img, result_img
