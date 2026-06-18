import json
import urllib.parse
import urllib.request

from PySide6.QtCore import QObject, QRunnable, Signal

LOSPEC_API = "https://lospec.com/palette-list/load"


class _Signals(QObject):
    results  = Signal(list, int)  # (palettes, total_count)
    error    = Signal(str)
    finished = Signal()


class LospecWorker(QRunnable):
    def __init__(self, query: str = "", sort: str = "downloads", page: int = 0):
        super().__init__()
        self.setAutoDelete(False)   # keep Python wrapper alive so signals survive run()
        self.signals = _Signals()
        self._query = query
        self._sort  = sort
        self._page  = page

    def run(self):
        try:
            params = urllib.parse.urlencode({
                "colorNumberFilterType": "any",
                "page": self._page,
                "tag": "",
                "sortingType": self._sort,
                "query": self._query,
            })
            req = urllib.request.Request(
                f"{LOSPEC_API}?{params}",
                headers={"User-Agent": "PixelForge/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            self.signals.results.emit(data.get("palettes", []), data.get("totalCount", 0))
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()
