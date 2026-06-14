# pixelforge — SNES-style palette pipeline

Repeatable, deterministic palette reduction for a growing sprite library.
RGB555 (true 15-bit SNES color), no dithering, geometry never changed,
black background keyed to transparency (per tile), per-sprite/per-group palettes.

## Install
    pip install numpy pillow scipy scikit-learn pyyaml
Single file: `pixelforge.py`.

For `.ase`/`.aseprite` source files the Aseprite CLI must be on `PATH`:

    # macOS — Aseprite ships as an app bundle
    export PATH="/Applications/Aseprite.app/Contents/MacOS:$PATH"

## Layout
    sprites_src/      source PNGs or Aseprite files (drop new ones here)
    palettes/         frozen palettes, one <group>.hex per group  (commit these)
    build/sprites/    recolored output in original format (hand-clean if needed)
    build/export/     individual PNG frames produced by `export`
    palettes.yaml     the manifest

## Spritesheet convention (PNG only)
A frame is **square, side = image height**, so `frames = width / height`.
`width % height != 0` is a hard error — the sprite is malformed and must be fixed.
Single sprite = 1 frame (width == height). Textures (`tileable: true`) skip this.
Aseprite files carry their own frame data and are not subject to this convention.

## Commands
    pixelforge scan                   # register new PNGs/Aseprite files, report malformed/unassigned
    pixelforge rebalance <group>      # (re)build & freeze that group's palette, show diff+fit
    pixelforge rebalance --all
    pixelforge build                  # map every sprite onto its FROZEN palette
    pixelforge verify                 # check built sprites use only their palette (catch hand-edits)
    pixelforge export <group>         # export built sprites as individual PNGs to build/export/
    pixelforge export --all
Paths override: `--input --output --palettes --manifest`.

## Workflow
1. Drop PNGs or Aseprite files in `sprites_src/`, run `scan`, set each entity's `group:` in the manifest.
2. `rebalance --all` to create the palettes (review the fit numbers).
3. `build`, then hand-clean output if you like.
4. `verify` before committing — flags stray off-palette pixels.
5. `export --all` to produce individual PNG frames for your engine.

Add more sprites later → `scan` → `build` (new sprites map onto the existing frozen
palettes; nothing already approved changes). Only `rebalance` ever rewrites a palette,
and it shows a diff first. Lock a palette with `locked: true` (then rebalance needs `--force`).

## Source formats
**PNG** sprites are stored as horizontal sprite sheets in `build/sprites/` and split back
into frames on export. **Aseprite** (`.ase`/`.aseprite`) files are processed frame-by-frame
using the Aseprite CLI, and the palette-reduced result is written back as an Aseprite file
in `build/sprites/`. Both formats are exported to individual per-frame PNGs by `export`.

For Aseprite files the alpha channel is used directly as the content mask. For PNGs, border-connected
near-black pixels are flood-filled to transparency (`bg_key: black`).

## Two guarantees
* **Stable palettes.** `build` never changes a frozen palette. Adding sprites can't
  silently recolor your existing, hand-cleaned art.
* **Frame-count neutral.** The unit of palette is the *entity* (a sprite or a whole
  sheet), not the frame. Each entity contributes EQUAL weight to its group's palette
  regardless of frame count — a 1-frame prop and a 30-frame animation have identical
  influence. All frames of one entity share one palette, so an animation never flickers color.

## The grouping knob
Grouping = how much sprites share. One entity per group = a dedicated 16-color palette
(max fidelity). Many entities per group = fewer palettes but color outliers may be squeezed.
`rebalance`/`build` print a `fit` number per entity and flag `poor fit` (default >0.05) so
you know when an outlier wants its own group. Per-entity `weight:` (default 1.0) lets a
hero outvote a background prop.

## Manifest keys
defaults / per-group: palette_size, weighting (sqrt|linear), bg_key (black|none),
bg_luma_thresh, force_black, fit_warn, locked, tileable.
entity: id, file, group, optional weight, optional tileable.
