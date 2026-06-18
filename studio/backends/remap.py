"""
Palette remapping — nearest-neighbour in OKLab perceptual colour space.

Public API
  compute_mapping(img, palette, overrides) -> Dict[RGBTuple, RGBTuple]
  remap_image(img, palette, overrides)     -> PIL Image
"""

import numpy as np
from PIL import Image
from typing import Dict, List, Optional, Tuple

RGBTuple = Tuple[int, int, int]

_M1 = np.array([
    [0.4122214708, 0.5363325363, 0.0514459929],
    [0.2119034982, 0.6806995451, 0.1073969566],
    [0.0883024619, 0.2817188376, 0.6299787005],
], dtype=np.float64)

_M2 = np.array([
    [ 0.2104542553,  0.7936177850, -0.0040720468],
    [ 1.9779984951, -2.4285922050,  0.4505937099],
    [ 0.0259040371,  0.7827717662, -0.8086757660],
], dtype=np.float64)


def _to_oklab(rgb_f: np.ndarray) -> np.ndarray:
    """(N, 3) sRGB [0–1] float → (N, 3) OKLab"""
    lin = np.where(rgb_f <= 0.04045,
                   rgb_f / 12.92,
                   ((rgb_f + 0.055) / 1.055) ** 2.4)
    return np.cbrt(lin @ _M1.T) @ _M2.T


def compute_mapping(
    img: Image.Image,
    palette: List[RGBTuple],
    overrides: Optional[Dict[str, str]] = None,
) -> Dict[RGBTuple, RGBTuple]:
    """
    Return {src_rgb: tgt_rgb} for every unique non-transparent pixel.
    overrides: {"rrggbb": "rrggbb"} hex-string forced assignments.
    """
    arr   = np.asarray(img.convert("RGBA"), dtype=np.uint8)
    alpha = arr[:, :, 3]
    rgb   = arr[:, :, :3]

    mask = alpha > 0
    if not mask.any():
        return {}

    unique = np.unique(rgb[mask].reshape(-1, 3), axis=0)    # (U, 3) uint8
    pal    = np.array(palette, dtype=np.uint8)               # (P, 3) uint8

    u_lab  = _to_oklab(unique.astype(np.float64) / 255.0)   # (U, 3)
    p_lab  = _to_oklab(pal.astype(np.float64)    / 255.0)   # (P, 3)

    # nearest palette colour per unique source colour
    dists = np.sum((u_lab[:, None] - p_lab[None]) ** 2, axis=2)  # (U, P)
    idx   = np.argmin(dists, axis=1)                              # (U,)

    mapping: Dict[RGBTuple, RGBTuple] = {
        tuple(int(v) for v in src): tuple(int(v) for v in pal[i])
        for src, i in zip(unique, idx)
    }

    if overrides:
        pal_by_hex = {f"{r:02x}{g:02x}{b:02x}": (r, g, b) for r, g, b in palette}
        for src_hex, tgt_hex in overrides.items():
            src_t = (int(src_hex[0:2], 16), int(src_hex[2:4], 16), int(src_hex[4:6], 16))
            if src_t in mapping and tgt_hex in pal_by_hex:
                mapping[src_t] = pal_by_hex[tgt_hex]

    return mapping


def remap_image(
    img: Image.Image,
    palette: List[RGBTuple],
    overrides: Optional[Dict[str, str]] = None,
) -> Image.Image:
    """Remap every non-transparent pixel to its nearest palette colour."""
    mapping = compute_mapping(img, palette, overrides)
    if not mapping:
        return img.copy()

    arr = np.asarray(img.convert("RGBA"), dtype=np.uint8).copy()
    rgb = arr[:, :, :3]

    for src_t, tgt_t in mapping.items():
        mask = np.all(rgb == np.array(src_t, dtype=np.uint8), axis=2)
        arr[mask, 0] = tgt_t[0]
        arr[mask, 1] = tgt_t[1]
        arr[mask, 2] = tgt_t[2]

    return Image.fromarray(arr, "RGBA")
