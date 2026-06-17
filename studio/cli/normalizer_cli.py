"""CLI entry point for Palette Normalizer — mirrors the original pixelforge.py interface."""

import sys
import argparse

from backends.normalizer_backend import (
    make_manifest_context,
    cmd_scan,
    cmd_rebalance,
    cmd_build,
    cmd_verify,
    cmd_export,
    all_groups,
)


def main():
    ap = argparse.ArgumentParser(prog="pixelforge-studio normalize")
    ap.add_argument("--manifest", default="palettes.yaml")
    ap.add_argument("--input", default="sprites_src")
    ap.add_argument("--output", default="build")
    ap.add_argument("--palettes", default="palettes")

    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan")
    sub.add_parser("build")

    rb = sub.add_parser("rebalance")
    rb.add_argument("group", nargs="?")
    rb.add_argument("--all", action="store_true")
    rb.add_argument("--force", action="store_true")

    sub.add_parser("verify")

    ex = sub.add_parser("export")
    ex.add_argument("group", nargs="?")
    ex.add_argument("--all", action="store_true")

    args = ap.parse_args()

    try:
        m = make_manifest_context(args.manifest, args.input, args.output, args.palettes)

        if args.cmd == "scan":
            sys.exit(cmd_scan(m))

        elif args.cmd == "build":
            rc, _ = cmd_build(m)
            sys.exit(rc)

        elif args.cmd == "verify":
            sys.exit(cmd_verify(m))

        elif args.cmd == "rebalance":
            if not getattr(args, "group", None) and not args.all:
                ap.error("rebalance needs a group or --all")
            rc, _ = cmd_rebalance(
                m,
                group=args.group,
                all_groups_flag=args.all,
                force=args.force,
            )
            sys.exit(rc)

        elif args.cmd == "export":
            if not getattr(args, "group", None) and not args.all:
                ap.error("export needs a group or --all")
            sys.exit(cmd_export(m, group=args.group, all_groups_flag=args.all))

    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
