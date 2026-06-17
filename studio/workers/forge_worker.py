from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QRunnable, Signal

from backends.forge_backend import convert


class ForgeSignals(QObject):
    log = Signal(str)
    result = Signal(object)   # (output_path, source_img, result_img)
    error = Signal(str)
    finished = Signal()


class ForgeWorker(QRunnable):
    def __init__(
        self,
        input_path: Path,
        target_w: Optional[int],
        target_h: Optional[int],
        auto: bool,
        colors: Optional[int],
        output_path: Optional[Path],
        preview_scale: int,
    ):
        super().__init__()
        self.signals = ForgeSignals()
        self._input_path = input_path
        self._params = dict(
            target_w=target_w,
            target_h=target_h,
            auto=auto,
            colors=colors,
            output_path=output_path,
            preview_scale=preview_scale,
        )
        self.setAutoDelete(True)

    def run(self):
        try:
            result = convert(
                input_path=self._input_path,
                log=self.signals.log.emit,
                **self._params,
            )
            self.signals.result.emit(result)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()
