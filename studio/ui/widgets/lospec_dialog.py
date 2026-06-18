"""
LospecDialog — browse lospec.com palettes and import one into a group.

Palettes are fetched from the Lospec JSON API, sorted by downloads by
default. Offline caching writes to ~/.pixelforge/lospec_cache.json and is
used automatically when the network is unavailable.

Colors are snapped to RGB555 on apply to keep them valid for Build/Verify.
"""

import json
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import QSize, Qt, QThreadPool
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from workers.lospec_worker import LospecWorker

CACHE_FILE = Path.home() / ".pixelforge" / "lospec_cache.json"
ROW_H = 44


# ── helpers ───────────────────────────────────────────────────────────────────

def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _snap_rgb555(r: int, g: int, b: int) -> Tuple[int, int, int]:
    return (r >> 3) << 3, (g >> 3) << 3, (b >> 3) << 3


def _parse_downloads(raw) -> int:
    """Lospec returns downloads as a comma-formatted string e.g. '333,019'."""
    try:
        return int(str(raw).replace(",", ""))
    except (ValueError, TypeError):
        return 0


def _swatch_px(colors: List[str], w: int, h: int) -> QPixmap:
    px = QPixmap(max(1, w), max(1, h))
    px.fill(QColor("#1a1a1a"))
    if colors:
        p = QPainter(px)
        cw = max(1, w // len(colors))
        for i, c in enumerate(colors):
            r, g, b = _hex_to_rgb(c)
            p.fillRect(i * cw, 0, cw, h, QColor(r, g, b))
        p.end()
    return px


# ── list row widget ───────────────────────────────────────────────────────────

class _Row(QWidget):
    def __init__(self, palette: dict, parent=None):
        super().__init__(parent)
        self._colors = palette.get("colors", [])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(2)

        self._swatch = QLabel()
        self._swatch.setFixedHeight(14)
        layout.addWidget(self._swatch)

        row = QHBoxLayout()
        row.setSpacing(0)
        name = QLabel(palette.get("title") or palette.get("slug", ""))
        name.setObjectName("FormLabel")
        row.addWidget(name)
        row.addStretch()
        n   = palette.get("numberOfColors") or len(self._colors)
        dl  = _parse_downloads(palette.get("downloads", 0))
        dls = f"{dl // 1000}k" if dl >= 1000 else str(dl)
        info = QLabel(f"{n}c · {dls}")
        info.setObjectName("HintLabel")
        row.addWidget(info)
        layout.addLayout(row)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._swatch.setPixmap(_swatch_px(self._colors, self._swatch.width(), 14))


# ── dialog ────────────────────────────────────────────────────────────────────

class LospecDialog(QDialog):
    def __init__(self, group_name: str, pool: QThreadPool, parent=None):
        super().__init__(parent)
        self._group   = group_name
        self._pool    = pool
        self._items:  List[dict] = []
        self._total   = 0
        self._page    = 0
        self._sel:    Optional[dict] = None
        self._gen     = 0          # incremented on each new search to drop stale results
        self._workers: set = set()
        self._result:  Optional[List[Tuple[int, int, int]]] = None

        self.setWindowTitle("Lospec Palette Browser")
        self.setMinimumSize(580, 640)
        self._build_ui()
        self._fetch(reset=True)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(8)

        hdr = QLabel(f"Applying to group: {self._group or '—'}")
        hdr.setObjectName("GroupLabel")
        root.addWidget(hdr)

        # Search bar
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self._q = QLineEdit()
        self._q.setPlaceholderText("Search palettes…")
        self._q.returnPressed.connect(self._on_search)
        bar.addWidget(self._q, stretch=1)
        self._sort = QComboBox()
        self._sort.addItem("Downloads", "downloads")
        self._sort.addItem("Newest",    "newest")
        self._sort.addItem("A–Z",       "alphabetical")
        self._sort.setFixedWidth(110)
        self._sort.currentIndexChanged.connect(self._on_search)
        bar.addWidget(self._sort)
        go = QPushButton("Search")
        go.setFixedWidth(72)
        go.clicked.connect(self._on_search)
        bar.addWidget(go)
        root.addLayout(bar)

        # Palette list
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SingleSelection)
        self._list.currentItemChanged.connect(self._on_select)
        root.addWidget(self._list, stretch=1)

        # Status / load-more row
        foot = QHBoxLayout()
        self._status = QLabel("")
        self._status.setObjectName("HintLabel")
        foot.addWidget(self._status)
        foot.addStretch()
        self._more_btn = QPushButton("Load More")
        self._more_btn.setEnabled(False)
        self._more_btn.clicked.connect(self._on_more)
        foot.addWidget(self._more_btn)
        root.addLayout(foot)

        # Selected preview
        self._preview = QLabel("No palette selected")
        self._preview.setObjectName("ViewerPlaceholder")
        self._preview.setFixedHeight(32)
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setScaledContents(True)
        root.addWidget(self._preview)

        self._meta = QLabel()
        self._meta.setObjectName("HintLabel")
        self._meta.setAlignment(Qt.AlignCenter)
        root.addWidget(self._meta)

        # Action buttons
        btns = QHBoxLayout()
        btns.setSpacing(6)
        self._save_btn = QPushButton("Save Offline")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        btns.addWidget(self._save_btn)
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        self._apply_btn = QPushButton("Apply to Group")
        self._apply_btn.setObjectName("PrimaryBtn")
        self._apply_btn.setEnabled(False)
        self._apply_btn.clicked.connect(self._on_apply)
        btns.addWidget(self._apply_btn)
        root.addLayout(btns)

    # ── fetching ──────────────────────────────────────────────────────────────

    def _fetch(self, reset: bool):
        if reset:
            self._gen += 1
            self._page = 0
            self._items.clear()
            self._list.clear()
        self._status.setText("Loading…")
        self._more_btn.setEnabled(False)
        gen = self._gen
        w = LospecWorker(
            query=self._q.text().strip(),
            sort=self._sort.currentData(),
            page=self._page,
        )
        self._workers.add(w)
        w.signals.results.connect(lambda p, t: self._on_results(p, t, gen))
        w.signals.error.connect(lambda e: self._on_error(e, gen))
        w.signals.finished.connect(lambda: self._workers.discard(w))
        self._pool.start(w)

    def _on_results(self, palettes: list, total: int, gen: int):
        if gen != self._gen:
            return
        self._total = total
        self._items.extend(palettes)
        for p in palettes:
            self._add_row(p)
        n = len(self._items)
        self._status.setText(f"Showing {n} of {total}")
        self._more_btn.setEnabled(n < total)

    def _on_error(self, msg: str, gen: int):
        if gen != self._gen:
            return
        cached = list(self._read_cache().values())
        if cached and self._page == 0:
            self._items = cached
            self._list.clear()
            for p in cached:
                self._add_row(p)
            self._status.setText(f"Offline — {len(cached)} saved palettes")
        else:
            self._status.setText(f"Error: {msg}")

    def _on_search(self):
        self._fetch(reset=True)

    def _on_more(self):
        self._page += 1
        self._fetch(reset=False)

    def _add_row(self, palette: dict):
        row = _Row(palette)
        item = QListWidgetItem()
        item.setData(Qt.UserRole, palette)
        item.setSizeHint(QSize(0, ROW_H))
        self._list.addItem(item)
        self._list.setItemWidget(item, row)

    # ── selection ─────────────────────────────────────────────────────────────

    def _on_select(self, item: Optional[QListWidgetItem], _prev):
        if item is None:
            self._sel = None
            self._preview.setText("No palette selected")
            self._meta.clear()
            self._apply_btn.setEnabled(False)
            self._save_btn.setEnabled(False)
            return

        p = item.data(Qt.UserRole)
        self._sel = p
        colors = p.get("colors", [])
        self._preview.setPixmap(_swatch_px(colors, max(self._preview.width(), 400), 32))

        slug   = p.get("slug", "")
        cached = self._is_cached(slug)
        dl     = _parse_downloads(p.get("downloads", 0))
        parts  = [p.get("title", slug), f"{len(colors)} colors", f"{dl:,} downloads"]
        if cached:
            parts.append("saved offline")
        self._meta.setText("  ·  ".join(parts))

        self._apply_btn.setEnabled(True)
        self._save_btn.setEnabled(not cached)

    # ── actions ───────────────────────────────────────────────────────────────

    def _on_apply(self):
        if not self._sel:
            return
        self._result = [
            _snap_rgb555(*_hex_to_rgb(h))
            for h in self._sel.get("colors", [])
        ]
        self.accept()

    def _on_save(self):
        if not self._sel:
            return
        cache = self._read_cache()
        cache[self._sel.get("slug", "")] = self._sel
        self._write_cache(cache)
        self._save_btn.setEnabled(False)
        txt = self._meta.text()
        if "saved offline" not in txt:
            self._meta.setText(txt + "  ·  saved offline")

    def get_colors(self) -> Optional[List[Tuple[int, int, int]]]:
        return self._result

    # ── offline cache ─────────────────────────────────────────────────────────

    def _is_cached(self, slug: str) -> bool:
        return slug in self._read_cache()

    def _read_cache(self) -> dict:
        try:
            if CACHE_FILE.exists():
                return json.loads(CACHE_FILE.read_text())
        except Exception:
            pass
        return {}

    def _write_cache(self, data: dict):
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(data, indent=2))

    # ── resize ────────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._sel:
            self._preview.setPixmap(
                _swatch_px(self._sel.get("colors", []), max(self._preview.width(), 400), 32)
            )
