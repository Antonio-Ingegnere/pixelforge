"""
Project backend — manages the PixelForge catalogue (project) data model.

A project is a folder:
  MyGame/
  ├── project.yaml     ← manifest (name, groups, sprites, pipeline config)
  ├── sprites/         ← imported originals, never modified
  ├── processed/       ← pipeline intermediates (normalized, resized PNGs)
  ├── palettes/        ← one .hex file per group
  └── export/          ← final build output

Pipeline per sprite (non-destructive, sequential):
  sprites/{file}  →  [normalize]  →  processed/{id}_normalized.png
                  →  [resize]     →  processed/{id}_resized_{W}x{H}.png

Each step is optional. get_active_file() returns the most-processed file
that exists on disk for a given sprite.
"""

import shutil
from pathlib import Path
from typing import Dict, List, Optional

import yaml

SCHEMA_VERSION = 1
PROJECT_FILE = "project.yaml"

DEFAULTS = dict(
    palette_size=16,
    weighting="sqrt",
    bg_key="black",
    bg_luma_thresh=18,
    force_black=True,
    fit_warn=0.05,
)


# ── project lifecycle ─────────────────────────────────────────────────────────

def new_project(directory: str, name: str) -> dict:
    """Create the folder structure and return a fresh project dict."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    for sub in ("sprites", "processed", "palettes", "export"):
        (d / sub).mkdir(exist_ok=True)
    project = _make_runtime(
        {
            "version": SCHEMA_VERSION,
            "name": name,
            "defaults": dict(DEFAULTS),
            "groups": {},
            "sprites": [],
        },
        d,
    )
    save_project(project)
    return project


def load_project(directory: str) -> dict:
    """Load project.yaml; inject runtime keys; create missing subdirs."""
    d = Path(directory)
    path = d / PROJECT_FILE
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    for sub in ("sprites", "processed", "palettes", "export"):
        (d / sub).mkdir(exist_ok=True)
    data.setdefault("sprites", [])
    data.setdefault("groups", {})
    data.setdefault("defaults", dict(DEFAULTS))
    return _make_runtime(data, d)


def save_project(project: dict):
    """Persist project.yaml (strips runtime _ keys)."""
    data = {k: v for k, v in project.items() if not k.startswith("_")}
    with open(project["_path"], "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def _make_runtime(data: dict, directory: Path) -> dict:
    data["_dir"] = str(directory)
    data["_path"] = str(directory / PROJECT_FILE)
    return data


def is_project_dir(directory: str) -> bool:
    return (Path(directory) / PROJECT_FILE).exists()


# ── sprite management ─────────────────────────────────────────────────────────

def add_sprites(project: dict, source_paths: List[Path]) -> List[dict]:
    """
    Copy each source file into sprites/ and register it.
    Skips files that are already inside the project's sprites/ dir.
    Returns list of newly added sprite dicts.
    """
    sprites_dir = Path(project["_dir"]) / "sprites"
    existing_ids = {s["id"] for s in project["sprites"]}
    added = []
    for src in source_paths:
        src = Path(src)
        if not src.exists():
            continue
        dest_name = _unique_filename(sprites_dir, src.name)
        dest = sprites_dir / dest_name
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        sprite_id = _make_id(dest_name, existing_ids)
        existing_ids.add(sprite_id)
        sprite = {
            "id": sprite_id,
            "file": dest_name,
            "group": None,
            "weight": 1.0,
            "pipeline": {
                "normalize":     {"enabled": False, "auto": True},
                "resize_sprite": {"enabled": False, "width": 64, "height": 0},
                "resize_canvas": {"enabled": False, "width": 64, "height": 64, "anchor": "center"},
            },
        }
        project["sprites"].append(sprite)
        added.append(sprite)
    return added


def remove_sprite(project: dict, sprite_id: str):
    project["sprites"] = [s for s in project["sprites"] if s["id"] != sprite_id]


def get_sprite(project: dict, sprite_id: str) -> Optional[dict]:
    for s in project["sprites"]:
        if s["id"] == sprite_id:
            return s
    return None


def update_sprite_pipeline(project: dict, sprite_id: str, step: str, params: dict):
    """Merge params into a sprite's pipeline step config."""
    s = get_sprite(project, sprite_id)
    if s:
        s["pipeline"].setdefault(step, {}).update(params)


# ── pipeline paths ────────────────────────────────────────────────────────────

def get_normalized_path(project_dir: str, sprite_id: str) -> Path:
    return Path(project_dir) / "processed" / f"{sprite_id}_normalized.png"


def get_scaled_path(project_dir: str, sprite_id: str, width: int, height: int) -> Path:
    return Path(project_dir) / "processed" / f"{sprite_id}_scaled_{width}x{height}.png"


def get_canvas_path(project_dir: str, sprite_id: str, width: int, height: int) -> Path:
    return Path(project_dir) / "processed" / f"{sprite_id}_canvas_{width}x{height}.png"


def get_original_path(project: dict, sprite: dict) -> Path:
    return Path(project["_dir"]) / "sprites" / sprite["file"]


def get_active_file(project: dict, sprite: dict) -> Path:
    """
    Return the most-processed file that exists on disk.
    Priority: canvas > scaled > normalized > original.
    """
    d = project["_dir"]
    pipe = sprite.get("pipeline", {})

    canvas_cfg = pipe.get("resize_canvas", {})
    if canvas_cfg.get("enabled") and canvas_cfg.get("width") and canvas_cfg.get("height"):
        p = get_canvas_path(d, sprite["id"], canvas_cfg["width"], canvas_cfg["height"])
        if p.exists():
            return p

    scale_cfg = pipe.get("resize_sprite", {})
    if scale_cfg.get("enabled") and (scale_cfg.get("width") or scale_cfg.get("height")):
        w = scale_cfg.get("width", 0)
        h = scale_cfg.get("height", 0)
        if w and h:
            p = get_scaled_path(d, sprite["id"], w, h)
            if p.exists():
                return p

    norm_cfg = pipe.get("normalize", {})
    if norm_cfg.get("enabled"):
        p = get_normalized_path(d, sprite["id"])
        if p.exists():
            return p

    return get_original_path(project, sprite)


def get_scale_input(project: dict, sprite: dict) -> Path:
    """Input for the resize_sprite step: normalized file if it exists, else original."""
    d = project["_dir"]
    norm_cfg = sprite.get("pipeline", {}).get("normalize", {})
    if norm_cfg.get("enabled"):
        p = get_normalized_path(d, sprite["id"])
        if p.exists():
            return p
    return get_original_path(project, sprite)


def get_canvas_input(project: dict, sprite: dict) -> Path:
    """Input for the resize_canvas step: scaled > normalized > original."""
    d = project["_dir"]
    pipe = sprite.get("pipeline", {})

    scale_cfg = pipe.get("resize_sprite", {})
    w, h = scale_cfg.get("width", 0), scale_cfg.get("height", 0)
    if scale_cfg.get("enabled") and w and h:
        p = get_scaled_path(d, sprite["id"], w, h)
        if p.exists():
            return p

    norm_cfg = pipe.get("normalize", {})
    if norm_cfg.get("enabled"):
        p = get_normalized_path(d, sprite["id"])
        if p.exists():
            return p

    return get_original_path(project, sprite)


def pipeline_status(project: dict, sprite: dict) -> str:
    """
    Returns the highest pipeline step whose output exists on disk.
    One of: 'imported', 'normalized', 'scaled', 'canvas'.
    """
    d = project["_dir"]
    pipe = sprite.get("pipeline", {})

    canvas_cfg = pipe.get("resize_canvas", {})
    if canvas_cfg.get("enabled") and canvas_cfg.get("width") and canvas_cfg.get("height"):
        if get_canvas_path(d, sprite["id"], canvas_cfg["width"], canvas_cfg["height"]).exists():
            return "canvas"

    scale_cfg = pipe.get("resize_sprite", {})
    w, h = scale_cfg.get("width", 0), scale_cfg.get("height", 0)
    if scale_cfg.get("enabled") and w and h:
        if get_scaled_path(d, sprite["id"], w, h).exists():
            return "scaled"

    if pipe.get("normalize", {}).get("enabled"):
        if get_normalized_path(d, sprite["id"]).exists():
            return "normalized"

    return "imported"


# ── group management ──────────────────────────────────────────────────────────

def add_group(project: dict, name: str):
    project["groups"].setdefault(name, {})


def remove_group(project: dict, name: str):
    project["groups"].pop(name, None)
    for s in project["sprites"]:
        if s.get("group") == name:
            s["group"] = None


def rename_group(project: dict, old_name: str, new_name: str):
    if old_name not in project["groups"] or new_name == old_name:
        return
    project["groups"][new_name] = project["groups"].pop(old_name)
    for s in project["sprites"]:
        if s.get("group") == old_name:
            s["group"] = new_name


def all_groups(project: dict) -> List[str]:
    return list(project.get("groups", {}).keys())


def assign_group(project: dict, sprite_id: str, group_name: Optional[str]):
    s = get_sprite(project, sprite_id)
    if s:
        s["group"] = group_name


def sprites_in_group(project: dict, group_name: str) -> List[dict]:
    return [s for s in project["sprites"] if s.get("group") == group_name]


def inbox_sprites(project: dict) -> List[dict]:
    return [s for s in project["sprites"] if not s.get("group")]


# ── normalizer bridge ─────────────────────────────────────────────────────────

def make_normalizer_context(project: dict) -> dict:
    """
    Build a manifest dict compatible with normalizer_backend functions.
    Each sprite's active (most-processed) file is used as the source.
    _input is set to the project root so entity file paths (sprites/foo.png
    or processed/foo_normalized.png) resolve correctly via os.path.join.
    """
    d = Path(project["_dir"])
    entities = []
    for s in project["sprites"]:
        active = get_active_file(project, s)
        try:
            rel = str(active.relative_to(d))
        except ValueError:
            rel = str(active)
        entities.append(
            {
                "id": s["id"],
                "file": active.name,       # basename only → clean export/sprites/ output
                "_source_path": str(active),  # absolute path for entity_frames()
                "group": s.get("group"),
                "weight": s.get("weight", 1.0),
                "tileable": s.get("tileable", False),
            }
        )
    return {
        "_dir": str(d),
        "_path": str(d / PROJECT_FILE),
        "_input": str(d),
        "_output": str(d / "export"),
        "_palettes": str(d / "palettes"),
        "defaults": project.get("defaults", dict(DEFAULTS)),
        "groups": project.get("groups", {}),
        "entities": entities,
    }


# ── palette file helpers ──────────────────────────────────────────────────────

def load_palette(project: dict, group: str) -> Optional[List]:
    """Return list of (R, G, B) tuples from group's .hex file, or None."""
    p = Path(project["_dir"]) / "palettes" / f"{group}.hex"
    if not p.exists():
        return None
    colors = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if len(line) >= 6:
            colors.append((int(line[0:2], 16), int(line[2:4], 16), int(line[4:6], 16)))
    return colors or None


# ── private helpers ───────────────────────────────────────────────────────────

def _make_id(filename: str, existing: set) -> str:
    base = Path(filename).stem.lower().replace(" ", "-").replace("_", "-")
    if base not in existing:
        return base
    i = 2
    while f"{base}-{i}" in existing:
        i += 1
    return f"{base}-{i}"


def _unique_filename(directory: Path, name: str) -> str:
    if not (directory / name).exists():
        return name
    stem, ext = Path(name).stem, Path(name).suffix
    i = 2
    while (directory / f"{stem}_{i}{ext}").exists():
        i += 1
    return f"{stem}_{i}{ext}"
