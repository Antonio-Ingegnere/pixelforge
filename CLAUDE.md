# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**pixelforge** — an SNES-style palette pipeline for deterministic, repeatable sprite palette reduction. Converts high-color PNGs to limited palettes (16 colors, RGB555) for use in a retro-style game.

## Setup

```bash
pip install numpy pillow scipy scikit-learn pyyaml
```

Aseprite files (`.ase`/`.aseprite`) also require the Aseprite CLI in `PATH`. On macOS it ships inside the app bundle:

```bash
export PATH="/Applications/Aseprite.app/Contents/MacOS:$PATH"
```

## Commands

```bash
python pixelforge.py scan                  # Register new PNGs/Aseprite files; report unassigned/malformed
python pixelforge.py rebalance <group>     # Rebuild & freeze a group's palette
python pixelforge.py rebalance --all       # Rebalance all groups
python pixelforge.py build                 # Remap every sprite onto its frozen palette
python pixelforge.py verify                # Check built sprites use only their palette colors
```

Path overrides: `--input`, `--output`, `--palettes`, `--manifest`.

## Workflow

1. Drop new PNGs or Aseprite files in `sprites_src/`
2. `scan` → register them in `palettes.yaml`
3. Edit `palettes.yaml` to assign the entity to a group
4. `rebalance <group>` → freezes the palette to `palettes/<group>.hex`
5. `build` → writes recolored output to `build/sprites/`
6. Optional hand-clean of PNGs in `build/sprites/`
7. `verify` → confirms no off-palette pixels exist

## Architecture

All logic lives in `pixelforge.py` (single file, ~333 lines). The pipeline:

1. **Manifest** (`palettes.yaml`) — source of truth for all config and entity registry. Entities belong to groups; groups share a frozen `.hex` palette.
2. **Background keying** — dark pixels (luma < `bg_luma_thresh`) on the border are flood-filled to transparency, so content pixels only are used for palette generation.
3. **Color space** — sRGB → linear RGB → OKLab (perceptually uniform). k-means clustering runs in OKLab space, then centers are snapped back to RGB555 (SNES 15-bit grid).
4. **Entity weighting** — each entity contributes equally to palette generation regardless of animation frame count (`weight` field, default `1.0`). This prevents multi-frame spritesheets from dominating single-frame sprites.
5. **Frozen palettes** — `rebalance` is the only command that writes `.hex` files. `build` is read-only with respect to palettes.
6. **Fit scoring** — every entity gets a fit error (mean OKLab distance to nearest palette color). High fit error indicates the entity may be poorly grouped.

## Key Design Invariants

- `build` is fully deterministic and never modifies palettes.
- Palette files (`palettes/*.hex`) are frozen between rebalances — treat them like build artifacts, not source.
- `tileable: true` on a group/entity disables bg-keying (keeps the full frame, e.g., ground textures).
- `force_black: true` always inserts black as the first palette entry when dark content pixels exist.
