"""
Palette Normalizer backend — SNES-style palette pipeline for sprite libraries.

All functions are pure (no print, no sys.exit). Pass a log callback to capture output.
RuntimeError is raised instead of SystemExit for errors the caller should surface.
"""

import glob
import os
import struct
import subprocess
import tempfile
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import yaml
from PIL import Image
from scipy import ndimage
from sklearn.cluster import KMeans


# ── color space ──────────────────────────────────────────────────────────────

def srgb_to_linear(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_oklab(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = np.cbrt(l), np.cbrt(m), np.cbrt(s)
    return np.stack(
        [
            0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
        ],
        -1,
    )


def oklab_to_linear(lab):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return np.stack(
        [
            4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
        ],
        -1,
    )


def rgb_to_oklab(rgb_u8):
    return linear_to_oklab(srgb_to_linear(np.asarray(rgb_u8, float)))


def linear_to_srgb_u8(c):
    c = np.clip(c, 0, 1)
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)
    return np.round(s * 255).astype(np.uint8)


def snap_rgb555(u8):
    v5 = np.round(np.asarray(u8, float) / 255.0 * 31.0)
    return np.round(v5 * 255.0 / 31.0).astype(np.uint8)


# ── manifest ──────────────────────────────────────────────────────────────────

DEFAULTS = dict(
    palette_size=16,
    weighting="sqrt",
    bg_key="black",
    bg_luma_thresh=18,
    force_black=True,
    fit_warn=0.05,
)


def load_manifest(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return yaml.safe_load(f) or {}


def save_manifest(path: str, m: dict):
    with open(path, "w") as f:
        yaml.safe_dump(m, f, sort_keys=False, allow_unicode=True)


def cfg(m: dict, group: Optional[str], key: str):
    g = (m.get("groups") or {}).get(group) or {}
    if key in g:
        return g[key]
    d = m.get("defaults") or {}
    if key in d:
        return d[key]
    return DEFAULTS[key]


def make_manifest_context(manifest_path: str, input_dir: str, output_dir: str, palettes_dir: str) -> dict:
    """Load (or create) manifest and inject runtime path keys."""
    m = load_manifest(manifest_path) or {
        "defaults": dict(DEFAULTS),
        "groups": {},
        "entities": [],
    }
    m["_path"] = manifest_path
    m["_input"] = input_dir
    m["_output"] = output_dir
    m["_palettes"] = palettes_dir
    os.makedirs(palettes_dir, exist_ok=True)
    return m


# ── aseprite support ──────────────────────────────────────────────────────────

ASEPRITE_EXTS = {".ase", ".aseprite"}


def is_aseprite(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in ASEPRITE_EXTS


def _ase_frame_count(path: str) -> int:
    with open(path, "rb") as f:
        f.read(4)
        magic, n = struct.unpack("<HH", f.read(4))
    if magic != 0xA5E0:
        raise ValueError(f"not a valid Aseprite file: {os.path.basename(path)}")
    return n


def frames_from_aseprite(path: str) -> List[np.ndarray]:
    with tempfile.TemporaryDirectory() as tmp:
        pat = os.path.join(tmp, "frame{frame001}.png")
        try:
            subprocess.run(
                ["aseprite", "-b", path, "--save-as", pat],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "aseprite CLI not found; add it to PATH "
                "(macOS: /Applications/Aseprite.app/Contents/MacOS/aseprite)"
            )
        pngs = sorted(glob.glob(os.path.join(tmp, "frame*.png")))
        return [np.array(Image.open(p).convert("RGBA")) for p in pngs]


def save_build(frames_rgba: List[np.ndarray], file: str, out_dir: str):
    out_path = os.path.join(out_dir, file)
    if is_aseprite(file):
        with tempfile.TemporaryDirectory() as tmp:
            pngs = []
            for i, fr in enumerate(frames_rgba):
                p = os.path.join(tmp, f"frame{i:03d}.png")
                Image.fromarray(fr, "RGBA").save(p)
                pngs.append(p)
            try:
                subprocess.run(
                    ["aseprite", "-b"] + pngs + ["--save-as", out_path],
                    check=True,
                    capture_output=True,
                )
            except FileNotFoundError:
                raise RuntimeError(
                    "aseprite CLI not found; add it to PATH "
                    "(macOS: /Applications/Aseprite.app/Contents/MacOS/aseprite)"
                )
    else:
        sheet = np.concatenate(frames_rgba, axis=1) if len(frames_rgba) > 1 else frames_rgba[0]
        Image.fromarray(sheet, "RGBA").save(out_path)


# ── frames ────────────────────────────────────────────────────────────────────

class FrameError(Exception):
    pass


def frame_layout(W: int, H: int, tileable: bool = False):
    if tileable:
        return 1, (W, H)
    if W % H != 0:
        raise FrameError(
            f"width {W} is not a multiple of frame height {H} "
            f"(square-frame convention) -> fix this sprite"
        )
    return W // H, (H, H)


def split_frames(rgb: np.ndarray, n: int, side):
    s = side if isinstance(side, int) else side[0]
    return [rgb[:, i * s : (i + 1) * s] for i in range(n)]


# ── bg keying ─────────────────────────────────────────────────────────────────

def bg_mask(rgb: np.ndarray, luma_thresh: float) -> np.ndarray:
    luma = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    dark = luma < luma_thresh
    lbl, _ = ndimage.label(dark)
    border = set(
        np.unique(
            np.concatenate([lbl[0, :], lbl[-1, :], lbl[:, 0], lbl[:, -1]])
        )
    )
    border.discard(0)
    return np.isin(lbl, list(border))


def content_of(frame: np.ndarray, bg_key: str, luma_thresh: float) -> np.ndarray:
    if bg_key == "none":
        return np.ones(frame.shape[:2], bool)
    return ~bg_mask(frame, luma_thresh)


# ── entity I/O ────────────────────────────────────────────────────────────────

def entity_frames(m: dict, ent: dict):
    path = os.path.join(m["_input"], ent["file"])
    tileable = bool(ent.get("tileable", cfg(m, ent.get("group"), "bg_key") == "none"))
    bgk = "none" if tileable else cfg(m, ent.get("group"), "bg_key")
    lt = cfg(m, ent.get("group"), "bg_luma_thresh")
    if is_aseprite(path):
        for rgba in frames_from_aseprite(path):
            rgb = rgba[..., :3]
            content = np.ones(rgb.shape[:2], bool) if tileable else rgba[..., 3] > 0
            yield rgb, content
    else:
        rgb = np.array(Image.open(path).convert("RGB"))
        H, W, _ = rgb.shape
        n, side = frame_layout(W, H, tileable=tileable)
        for fr in split_frames(rgb, n, side):
            yield fr, content_of(fr, bgk, lt)


def built_frames(m: dict, ent: dict):
    path = os.path.join(m["_output"], "sprites", ent["file"])
    if is_aseprite(path):
        yield from frames_from_aseprite(path)
    else:
        rgba = np.array(Image.open(path).convert("RGBA"))
        H, W, _ = rgba.shape
        tileable = bool(ent.get("tileable", cfg(m, ent.get("group"), "bg_key") == "none"))
        n, side = frame_layout(W, H, tileable=tileable)
        s = side[0] if isinstance(side, tuple) else side
        for i in range(n):
            yield rgba[:, i * s : (i + 1) * s]


def entity_histogram(m: dict, ent: dict):
    cols = []
    cnts = []
    for fr, content in entity_frames(m, ent):
        px = fr[content].reshape(-1, 3)
        if len(px) == 0:
            continue
        u, c = np.unique(px, axis=0, return_counts=True)
        cols.append(u)
        cnts.append(c)
    if not cols:
        return np.zeros((0, 3), np.uint8), np.zeros((0,))
    cols = np.concatenate(cols)
    cnts = np.concatenate(cnts).astype(float)
    u, inv = np.unique(cols, axis=0, return_inverse=True)
    agg = np.zeros(len(u))
    np.add.at(agg, inv, cnts)
    w = np.sqrt(agg) if cfg(m, ent.get("group"), "weighting") == "sqrt" else agg
    w = w / w.sum() * float(ent.get("weight", 1.0))
    return u, w


# ── palette build ─────────────────────────────────────────────────────────────

def build_palette(m: dict, group: str, entities: list) -> np.ndarray:
    k = cfg(m, group, "palette_size")
    cols = []
    ws = []
    for ent in entities:
        u, w = entity_histogram(m, ent)
        if len(u):
            cols.append(u)
            ws.append(w)
    if not cols:
        raise RuntimeError(f"group '{group}': no content pixels")
    cols = np.concatenate(cols)
    ws = np.concatenate(ws)
    lab = rgb_to_oklab(cols)
    K = min(k, len(cols))
    km = KMeans(n_clusters=K, random_state=0, n_init=6, max_iter=300).fit(
        lab, sample_weight=ws
    )
    pal = np.zeros((K, 3))
    for c in range(K):
        sel = km.labels_ == c
        sw = ws[sel].sum()
        cen = (lab[sel] * ws[sel][:, None]).sum(0) / sw
        pal[c] = linear_to_srgb_u8(oklab_to_linear(cen))
    pal = snap_rgb555(pal.astype(np.uint8))
    if cfg(m, group, "force_black"):
        luma = 0.299 * cols[:, 0] + 0.587 * cols[:, 1] + 0.114 * cols[:, 2]
        if (luma < 24).any() and pal.max(1).min() > 24:
            pal[pal.sum(1).argmin()] = [0, 0, 0]
    return np.unique(pal, axis=0)


# ── remap ─────────────────────────────────────────────────────────────────────

def remap_frame(frame: np.ndarray, content: np.ndarray, pal: np.ndarray) -> np.ndarray:
    pal_lab = rgb_to_oklab(pal)
    h, w, _ = frame.shape
    out = np.zeros((h, w, 4), np.uint8)
    px = frame[content].reshape(-1, 3)
    if len(px):
        d2 = ((rgb_to_oklab(px)[:, None, :] - pal_lab[None, :, :]) ** 2).sum(-1)
        orgb = np.zeros((h, w, 3), np.uint8)
        orgb[content] = pal[d2.argmin(1)]
        out[..., :3] = orgb
    out[..., 3] = (content * 255).astype(np.uint8)
    return out


def fit_error(m: dict, ent: dict, pal: np.ndarray) -> float:
    pal_lab = rgb_to_oklab(pal)
    tot = 0.0
    npx = 0
    for fr, content in entity_frames(m, ent):
        px = fr[content].reshape(-1, 3)
        if not len(px):
            continue
        d2 = ((rgb_to_oklab(px)[:, None, :] - pal_lab[None, :, :]) ** 2).sum(-1)
        tot += np.sqrt(d2.min(1)).sum()
        npx += len(px)
    return tot / npx if npx else 0.0


# ── palette files ─────────────────────────────────────────────────────────────

def pal_path(m: dict, group: str) -> str:
    return os.path.join(m["_palettes"], f"{group}.hex")


def load_pal(m: dict, group: str) -> Optional[np.ndarray]:
    p = pal_path(m, group)
    if not os.path.exists(p):
        return None
    return np.array(
        [
            [int(l[0:2], 16), int(l[2:4], 16), int(l[4:6], 16)]
            for l in (x.strip() for x in open(p))
            if l
        ],
        np.uint8,
    )


def write_pal(m: dict, group: str, pal: np.ndarray):
    with open(pal_path(m, group), "w") as f:
        for c in pal:
            f.write("%02X%02X%02X\n" % (c[0], c[1], c[2]))


# ── helpers ───────────────────────────────────────────────────────────────────

def entities_in(m: dict, group: str) -> list:
    return [e for e in m.get("entities", []) if e.get("group") == group]


def all_groups(m: dict) -> list:
    return list((m.get("groups") or {}).keys())


def palette_diff(old: Optional[np.ndarray], new: np.ndarray) -> str:
    if old is None:
        return f"new palette: {len(new)} colors"
    so = {tuple(c) for c in old}
    sn = {tuple(c) for c in new}
    return (
        f"{len(old)} -> {len(new)} colors | "
        f"removed {len(so - sn)}, added {len(sn - so)}, kept {len(so & sn)}"
    )


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_scan(m: dict, log: Optional[Callable] = None) -> int:
    _log = log or print
    raw = []
    for pat in ["*.png", "*.ase", "*.aseprite"]:
        raw.extend(glob.glob(os.path.join(m["_input"], pat)))
    files = sorted(os.path.basename(f) for f in raw)
    known = {e["file"] for e in m.get("entities", [])}
    m.setdefault("entities", [])
    added = []
    errors = []
    for f in files:
        path = os.path.join(m["_input"], f)
        try:
            if is_aseprite(path):
                n = _ase_frame_count(path)
                info = f"{n} frame(s) [aseprite]"
            else:
                rgb = np.array(Image.open(path).convert("RGB"))
                H, W, _ = rgb.shape
                n, _ = frame_layout(W, H)
                info = f"{n} frame(s)"
        except (FrameError, ValueError, OSError, struct.error) as e:
            errors.append((f, str(e)))
            info = "MALFORMED"
        if f not in known:
            eid = os.path.splitext(f)[0]
            m["entities"].append({"id": eid, "file": f, "group": None})
            added.append((f, info))
    missing = [e["file"] for e in m["entities"] if e["file"] not in set(files)]
    _log(f"scanned {len(files)} file(s) in {m['_input']}")
    for f, info in added:
        _log(f"  + {f:34s} {info}")
    if not added:
        _log("  (no new files)")
    if missing:
        _log("MISSING (in manifest, no file):")
        for x in missing:
            _log(f"  - {x}")
    if errors:
        _log("\nERRORS (fix these sprites):")
        for f, e in errors:
            _log(f"  ! {f}: {e}")
    unassigned = [e["id"] for e in m["entities"] if not e.get("group")]
    if unassigned:
        _log("\nUNASSIGNED entities (set 'group:' in the manifest):")
        for x in unassigned:
            _log(f"  ? {x}")
    save_manifest(m["_path"], {k: v for k, v in m.items() if not k.startswith("_")})
    return 1 if errors else 0


def cmd_rebalance(
    m: dict,
    group: Optional[str] = None,
    all_groups_flag: bool = False,
    force: bool = False,
    log: Optional[Callable] = None,
) -> Tuple[int, Dict[str, float]]:
    """Returns (rc, fit_scores) where fit_scores maps entity_id -> fit_error."""
    _log = log or print
    groups = all_groups(m) if all_groups_flag else [group]
    rc = 0
    fit_scores: Dict[str, float] = {}
    for g in groups:
        if g not in all_groups(m):
            _log(f"unknown group '{g}'")
            rc = 1
            continue
        locked = bool((m.get("groups", {}).get(g) or {}).get("locked"))
        if locked and not force:
            _log(f"group '{g}' is locked; use --force to rebalance")
            rc = 1
            continue
        ents = entities_in(m, g)
        if not ents:
            _log(f"group '{g}': no entities, skip")
            continue
        new = build_palette(m, g, ents)
        old = load_pal(m, g)
        _log(f"[rebalance] {g}: {palette_diff(old, new)}")
        for e in ents:
            err = fit_error(m, e, new)
            fit_scores[e["id"]] = err
            flag = " <-- poor fit" if err > cfg(m, g, "fit_warn") else ""
            _log(f"    {e['id']:24s} fit={err:.4f}{flag}")
        write_pal(m, g, new)
    return rc, fit_scores


def cmd_build(m: dict, log: Optional[Callable] = None) -> Tuple[int, Dict[str, float]]:
    """Returns (rc, fit_scores) where fit_scores maps entity_id -> fit_error."""
    _log = log or print
    out_sprites = os.path.join(m["_output"], "sprites")
    os.makedirs(out_sprites, exist_ok=True)
    rc = 0
    fit_scores: Dict[str, float] = {}
    for e in m.get("entities", []):
        g = e.get("group")
        if not g:
            _log(f"skip {e['id']}: unassigned group")
            continue
        pal = load_pal(m, g)
        if pal is None:
            _log(f"skip {e['id']}: group '{g}' has no palette (run: rebalance {g})")
            rc = 1
            continue
        try:
            frames = list(entity_frames(m, e))
        except FrameError as ex:
            _log(f"ERROR {e['id']}: {ex}")
            rc = 1
            continue
        outs = [remap_frame(fr, content, pal) for fr, content in frames]
        save_build(outs, e["file"], out_sprites)
        err = fit_error(m, e, pal)
        fit_scores[e["id"]] = err
        flag = " <-- POOR FIT (rebalance or regroup?)" if err > cfg(m, g, "fit_warn") else ""
        _log(f"  {e['id']:24s} -> {g:10s} {len(outs)}fr fit={err:.4f}{flag}")
    return rc, fit_scores


def cmd_verify(m: dict, log: Optional[Callable] = None) -> int:
    _log = log or print
    rc = 0
    out_sprites = os.path.join(m["_output"], "sprites")
    for e in m.get("entities", []):
        g = e.get("group")
        if not g:
            _log(f"  {e['id']:24s} UNASSIGNED")
            rc = 1
            continue
        pal = load_pal(m, g)
        if pal is None:
            _log(f"  {e['id']:24s} no palette for '{g}'")
            rc = 1
            continue
        bp = os.path.join(out_sprites, e["file"])
        if not os.path.exists(bp):
            _log(f"  {e['id']:24s} not built (run build)")
            rc = 1
            continue
        if is_aseprite(bp):
            chunks = [
                rgba[..., :3][rgba[..., 3] > 0].reshape(-1, 3)
                for rgba in frames_from_aseprite(bp)
                if (rgba[..., 3] > 0).any()
            ]
            px = np.concatenate(chunks) if chunks else np.zeros((0, 3), np.uint8)
        else:
            img = np.array(Image.open(bp).convert("RGBA"))
            px = img[..., :3][img[..., 3] > 0].reshape(-1, 3)
        palset = {tuple(c) for c in pal}
        u, c = np.unique(px, axis=0, return_counts=True)
        off = sum(int(cc) for uu, cc in zip(u, c) if tuple(uu) not in palset)
        try:
            err = fit_error(m, e, pal)
        except FrameError:
            err = 0.0
        if off > 0:
            status = f"{off}/{len(px)} OFF-PALETTE px"
            rc = 1
        elif err > cfg(m, g, "fit_warn"):
            status = f"ok (source poor fit {err:.4f})"
        else:
            status = "ok"
        _log(f"  {e['id']:24s} {g:10s} {status}")
    return rc


def cmd_export(
    m: dict,
    group: Optional[str] = None,
    all_groups_flag: bool = False,
    log: Optional[Callable] = None,
) -> int:
    _log = log or print
    out_sprites = os.path.join(m["_output"], "sprites")
    export_dir = os.path.join(m["_output"], "export")
    os.makedirs(export_dir, exist_ok=True)
    if all_groups_flag:
        ents = m.get("entities", [])
    else:
        if group not in all_groups(m):
            _log(f"unknown group '{group}'")
            return 1
        ents = entities_in(m, group)
    rc = 0
    for e in ents:
        built = os.path.join(out_sprites, e["file"])
        if not os.path.exists(built):
            _log(f"  {e['id']:24s} not built (run build)")
            rc = 1
            continue
        try:
            frames = list(built_frames(m, e))
        except FrameError as ex:
            _log(f"  ERROR {e['id']}: {ex}")
            rc = 1
            continue
        sheet = np.concatenate(frames, axis=1) if len(frames) > 1 else frames[0]
        out = os.path.join(export_dir, f"{e['id']}.png")
        Image.fromarray(sheet, "RGBA").save(out)
        _log(f"  {e['id']:24s} -> {e['id']}.png  ({len(frames)} frame(s))")
    return rc
