"""CLI entry point for Sprite Forge — mirrors the original convert.py interface."""

import sys
from pathlib import Path

import argparse

from backends.forge_backend import convert, parse_size


def main():
    parser = argparse.ArgumentParser(
        prog="pixelforge-studio forge",
        description="Convert AI-generated images to pixel art at exact resolutions.",
    )
    parser.add_argument("input", nargs="+", help="Input image path(s)")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-detect art pixel size via autocorrelation")

    size_group = parser.add_mutually_exclusive_group()
    size_group.add_argument("-s", "--size", type=parse_size, metavar="SIZE",
                            help="Target size: N or WxH")
    size_group.add_argument("--height", type=int, metavar="H")
    size_group.add_argument("--width", type=int, metavar="W")

    parser.add_argument("-c", "--colors", type=int, default=None, metavar="N")
    parser.add_argument("-p", "--preview", type=int, default=1, metavar="SCALE")
    parser.add_argument("-o", "--output", type=Path, default=None)

    args = parser.parse_args()

    if not args.auto and not args.size and not args.height and not args.width:
        parser.error("one of --auto, --size, --height, or --width is required")
    if args.output and len(args.input) > 1:
        print("Error: --output can only be used with a single input file.", file=sys.stderr)
        sys.exit(1)
    if args.colors is not None and not (2 <= args.colors <= 256):
        print("Error: --colors must be between 2 and 256.", file=sys.stderr)
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
            output, _src, _res = convert(
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
