# PixelForge — SNES-style palette pipeline

Repeatable, deterministic palette reduction for a growing sprite library.
RGB555 (true 15-bit SNES color), no dithering, geometry never changed,
black background keyed to transparency per tile, per-sprite/per-group palettes.

Two ways to use it: the **Studio GUI** for interactive work, or the **CLI** for scripted pipelines.

---

## Studio

A PySide6 desktop app with a Lightroom-style three-panel layout.

### Install

```bash
pip install -r studio/requirements.txt
```

Requires Python 3.10+. For `.ase`/`.aseprite` source files the Aseprite CLI must be on `PATH`:

```bash
# macOS
export PATH="/Applications/Aseprite.app/Contents/MacOS:$PATH"
```

### Run

```bash
cd studio
python3 app.py
```

### Layout

```
┌─ Library ──────┬─ Grid ──────────────────┬─ Develop ──────────┐
│  Groups        │  Sprite thumbnails      │  Original vs.      │
│  + Inbox       │  with status badges     │  Processed preview │
│                │                         │                     │
│                │                         │  Pipeline:          │
│                │                         │  1. Normalize       │
│                │                         │  2. Resize sprite   │
│                │                         │  3. Resize canvas   │
│                │                         │                     │
│                │                         │  Group / Weight     │
└────────────────┴─────────────────────────┴─────────────────────┘
└─ Bottom bar: group palette swatch · Rebalance · Build · Verify · Export ─┘
```

### Sprite pipeline (per-sprite, non-destructive)

Each sprite has three optional processing steps applied in order:

| Step | What it does |
|------|-------------|
| **Normalize** | Floods near-black border pixels to transparency, converts to RGBA |
| **Resize sprite** | Scales the image to W×H; set either dimension to 0 to auto-preserve ratio |
| **Resize canvas** | Pads or crops to an exact W×H canvas with a configurable anchor point |

Processed files are stored in `processed/` inside the project folder. The original is never modified. Click **Apply Pipeline** to run the selected steps.

### Palette commands (bottom bar)

Select a group in the Library panel, then:

| Button | Action |
|--------|--------|
| **Rebalance** | Rebuild and freeze the group's palette from current processed sprites |
| **Build** | Remap every sprite onto its frozen palette |
| **Verify** | Check that built sprites use only their palette colors |
| **Export** | Export built sprites as individual per-frame PNGs |

---

## CLI

Single file: `pixelforge.py` at the repo root.

### Install

```bash
pip install numpy pillow scipy scikit-learn pyyaml
```

### Commands

```bash
python pixelforge.py scan                  # Register new PNGs/Aseprite files; report unassigned/malformed
python pixelforge.py rebalance <group>     # Rebuild & freeze a group's palette
python pixelforge.py rebalance --all
python pixelforge.py build                 # Remap every sprite onto its frozen palette
python pixelforge.py verify                # Check built sprites use only their palette colors
python pixelforge.py export <group>        # Export built sprites as individual PNGs
python pixelforge.py export --all
```

Path overrides: `--input --output --palettes --manifest`.

### Workflow

1. Drop PNGs or Aseprite files in `sprites_src/`, run `scan`, set each entity's `group:` in the manifest.
2. `rebalance --all` to create palettes (review the fit numbers).
3. `build`, then hand-clean output if needed.
4. `verify` before committing — flags stray off-palette pixels.
5. `export --all` to produce individual PNG frames for your engine.

Add more sprites later → `scan` → `build`. New sprites map onto existing frozen palettes; nothing already approved changes. Only `rebalance` ever rewrites a palette.

### Layout

```
sprites_src/      source PNGs or Aseprite files (drop new ones here)
palettes/         frozen palettes, one <group>.hex per group  (commit these)
build/sprites/    recolored output  (hand-clean if needed)
build/export/     individual PNG frames produced by `export`
palettes.yaml     the manifest
```

---

## Design invariants

**Stable palettes.** `build` never changes a frozen palette. Adding sprites can't silently recolor existing, hand-cleaned art.

**Frame-count neutral.** The palette unit is the *entity* (a sprite or whole sheet), not the frame. A 1-frame prop and a 30-frame animation have identical influence on the group palette. Per-entity `weight:` (default 1.0) lets a hero outvote a background prop.

**Deterministic.** Given the same inputs and frozen palettes, `build` always produces the same output.

## Grouping

Grouping controls how much sprites share. One entity per group = dedicated 16-color palette (max fidelity). Many entities per group = fewer palettes but outliers may be color-squeezed. The `fit` number per entity flags poor fits (default threshold 0.05) so you know when an outlier needs its own group.

## Spritesheet convention (PNG)

A frame is square with side = image height, so `frames = width / height`. `width % height != 0` is a hard error. Single sprite = 1 frame (width == height). Textures (`tileable: true`) skip this check. Aseprite files carry their own frame data.

## Manifest keys

Defaults / per-group: `palette_size`, `weighting` (sqrt|linear), `bg_key` (black|none), `bg_luma_thresh`, `force_black`, `fit_warn`, `locked`, `tileable`.

Per-entity: `id`, `file`, `group`, `weight`, `tileable`.
