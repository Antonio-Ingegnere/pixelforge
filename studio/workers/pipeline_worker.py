"""
Pipeline worker — runs up to three steps on a single sprite (non-destructive).

Step order:
  1. normalize      original → processed/{id}_normalized.png
  2. resize_sprite  (normalized or original) → processed/{id}_scaled_{W}x{H}.png
                    One axis may be 0 (auto) — aspect ratio is preserved.
  3. resize_canvas  (scaled/normalized/original) → processed/{id}_canvas_{W}x{H}.png
                    Paste source centered (or at anchor) on a blank canvas.

Each step is skipped if not enabled in the sprite's pipeline config.
"""

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, Signal

from backends.forge_backend import convert as forge_convert
from backends.project_backend import (
    get_normalized_path,
    get_scaled_path,
    get_canvas_path,
    get_original_path,
    get_scale_input,
    get_canvas_input,
)


class PipelineSignals(QObject):
    log = Signal(str)
    result = Signal(object)   # dict: {sprite_id, outputs: {step: Path}}
    error = Signal(str)
    finished = Signal()


class PipelineWorker(QRunnable):
    """
    Runs the enabled pipeline steps for one sprite.
    Pass steps=None to run all enabled steps, or a list like ['normalize']
    to run only specific steps.
    """

    def __init__(self, project: dict, sprite: dict, steps=None):
        super().__init__()
        self.signals = PipelineSignals()
        self._project = project
        self._sprite = sprite
        self._steps = steps
        self.setAutoDelete(True)

    def run(self):
        sprite = self._sprite
        project = self._project
        pipe = sprite.get("pipeline", {})
        d = project["_dir"]
        sid = sprite["id"]
        outputs = {}

        def should_run(step_name):
            if self._steps is not None:
                return step_name in self._steps
            return pipe.get(step_name, {}).get("enabled", False)

        try:
            # ── Step 1: normalize ─────────────────────────────────────────────
            if should_run("normalize"):
                norm_cfg = pipe.get("normalize", {})
                src = get_original_path(project, sprite)
                out_path = get_normalized_path(d, sid)
                out_path.parent.mkdir(parents=True, exist_ok=True)

                result_path, _, _ = forge_convert(
                    input_path=src,
                    target_w=None,
                    target_h=None,
                    auto=norm_cfg.get("auto", True),
                    colors=None,
                    output_path=out_path,
                    preview_scale=1,
                    log=self.signals.log.emit,
                )
                outputs["normalize"] = result_path
                self.signals.log.emit(f"  normalized → {result_path.name}")

            # ── Step 2: resize sprite (scale, ratio-aware) ────────────────────
            if should_run("resize_sprite"):
                scale_cfg = pipe.get("resize_sprite", {})
                w = scale_cfg.get("width", 0)
                h = scale_cfg.get("height", 0)

                if not w and not h:
                    self.signals.log.emit("  resize sprite skipped: W and H are both 0")
                else:
                    src = get_scale_input(project, sprite)
                    img = Image.open(src).convert("RGBA")

                    # Compute missing axis from aspect ratio
                    if not w:
                        w = max(1, round(img.width * h / img.height))
                    elif not h:
                        h = max(1, round(img.height * w / img.width))

                    out_path = get_scaled_path(d, sid, w, h)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    img = img.resize((w, h), Image.NEAREST)
                    img.save(out_path, "PNG")
                    outputs["resize_sprite"] = out_path
                    self.signals.log.emit(f"  scaled to {w}×{h} → {out_path.name}")

            # ── Step 3: resize canvas (pad / crop with anchor) ────────────────
            if should_run("resize_canvas"):
                canvas_cfg = pipe.get("resize_canvas", {})
                cw = canvas_cfg.get("width", 0)
                ch = canvas_cfg.get("height", 0)
                anchor = canvas_cfg.get("anchor", "center")

                if not cw or not ch:
                    self.signals.log.emit("  resize canvas skipped: W or H is 0")
                else:
                    src = get_canvas_input(project, sprite)
                    img = Image.open(src).convert("RGBA")
                    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
                    ox, oy = _anchor_offset(img.width, img.height, cw, ch, anchor)
                    canvas.paste(img, (ox, oy))
                    out_path = get_canvas_path(d, sid, cw, ch)
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    canvas.save(out_path, "PNG")
                    outputs["resize_canvas"] = out_path
                    self.signals.log.emit(
                        f"  canvas {cw}×{ch} anchor={anchor} → {out_path.name}"
                    )

            self.signals.result.emit({"sprite_id": sid, "outputs": outputs})

        except Exception as exc:
            self.signals.error.emit(f"{sid}: {exc}")
        finally:
            self.signals.finished.emit()


def _anchor_offset(src_w: int, src_h: int, dst_w: int, dst_h: int, anchor: str):
    """Return (x, y) paste offset to place src onto a dst-sized canvas."""
    ax, ay = {
        "top-left":      (0.0, 0.0),
        "top-center":    (0.5, 0.0),
        "top-right":     (1.0, 0.0),
        "middle-left":   (0.0, 0.5),
        "center":        (0.5, 0.5),
        "middle-right":  (1.0, 0.5),
        "bottom-left":   (0.0, 1.0),
        "bottom-center": (0.5, 1.0),
        "bottom-right":  (1.0, 1.0),
    }.get(anchor, (0.5, 0.5))
    return int((dst_w - src_w) * ax), int((dst_h - src_h) * ay)
