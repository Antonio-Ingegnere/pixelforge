# sprite_forge

A CLI tool for converting AI-generated pixel art images to exact target resolutions without antialiasing artifacts.

## Problem it solves

AI image generators produce pixel art at arbitrary large sizes (e.g. 531×984) where each "art pixel" is rendered as a block of several source pixels (~8–19px per art pixel). Naive resizing (bilinear, bicubic) blurs the result. This tool detects the underlying pixel grid and samples cleanly from each block center, preserving hard edges and exact colors.

## Dependencies

- Python 3.9+
- Pillow 11+
- numpy

No install step needed — both are available in the environment.

## Entry point

```
python convert.py <input> [options]
```

## Core pipeline

1. **Auto-detect pixel grid** (when `--auto`): compute the average color-difference profile along each axis, then find the dominant period via normalized autocorrelation. The peak lag = art pixel size in source pixels.
2. **Center-sample downsample**: for each output pixel, sample from the center of its corresponding source block — `source_x = int((x + 0.5) * scale)`. Center pixels hold the true solid color; antialiasing only occurs at block edges.
3. **Optional color quantization** (`-c N`): median-cut palette reduction, alpha-channel preserved. Off by default because center sampling already gives clean discrete colors.
4. **Optional NEAREST upscale**: when `--auto` is combined with `--height`/`--width`/`--size`, the detected art is upscaled to the desired output size using nearest-neighbor (no blurring).

## CLI reference

```
python convert.py <input...> --auto                  # detect grid, output at natural art resolution
python convert.py <input...> --auto --height 128     # detect grid, then upscale to 128px tall
python convert.py <input...> --auto --size 69x128    # detect grid, then upscale to exact WxH
python convert.py <input...> -s 32                   # force square 32×32 output
python convert.py <input...> --height 128            # force 128px height, proportional width
python convert.py <input...> --width 64              # force 64px width, proportional height
python convert.py <input...> -s 69x128               # force explicit WxH
python convert.py <input...> --auto -c 32            # auto + reduce to 32-color palette
python convert.py <input...> --auto -p 4             # auto + 4× nearest-neighbor preview upscale
python convert.py <input...> --auto -o out.png       # explicit output path (single file only)
```

### Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--auto` | off | Auto-detect art pixel size via autocorrelation |
| `-s / --size N` or `WxH` | — | Force square or explicit output dimensions |
| `--height H` | — | Force output height; width computed proportionally |
| `--width W` | — | Force output width; height computed proportionally |
| `-c / --colors N` | off | Quantize palette to N colors (2–256) |
| `-p / --preview SCALE` | 1 | Upscale saved file by SCALE with NEAREST (for viewing only — increases file dimensions) |
| `-o / --output PATH` | auto | Output file path; auto-named `<stem>_WxH.png` next to input |

**Important:** `-p / --preview` increases the actual saved file dimensions. Never use it when you need the true art resolution on disk.

## Key design decisions

### Why center sampling, not NEAREST or mode
- PIL's NEAREST maps output x to `int(x * scale)` — samples from the block's top-left corner, which often lands on antialiased edge pixels.
- Mode sampling (most common color per block) fails for thin features like 1-pixel outlines: the outline is a minority inside the block and gets outvoted by the background.
- Center sampling (`int((x + 0.5) * scale)`) reliably hits the solid interior of each art pixel.

### Why autocorrelation for grid detection
- Run-length analysis fails when images have significant antialiasing (short runs dominate).
- Autocorrelation of the average color-difference profile finds the dominant repeating period even through noise. The search range is lag 3–64, skipping lags 1–2 which reflect local smoothness rather than the pixel grid.

### Why quantization is off by default
- Source pixel art already has a defined palette. Center sampling preserves those exact colors.
- Enabling quantization with too few colors (`-c 16` or `-c 32`) silently drops minority colors (e.g. a red needle in a predominantly dark-blue image). Use it only when you explicitly want palette reduction.

### Auto + target size workflow
When `--auto` is combined with `--height`/`--width`/`--size`, the pipeline is:
```
source → center-sample to detected grid → NEAREST upscale to target
```
This correctly separates "find the true art" from "scale to game resolution." Upscaling with NEAREST keeps pixels hard.

## Output naming

Without `-o`, output is saved next to the input:
- `sprite.png --auto` → `sprite_28x52.png`
- `sprite.png --auto --height 128` → `sprite_69x128.png`
- `sprite.png -s 32` → `sprite_32x32.png`
