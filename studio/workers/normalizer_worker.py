import copy
from typing import Optional

from PySide6.QtCore import QObject, QRunnable, Signal

from backends.normalizer_backend import (
    cmd_scan,
    cmd_rebalance,
    cmd_build,
    cmd_verify,
    cmd_export,
    load_manifest,
    save_manifest,
)


class NormalizerSignals(QObject):
    log = Signal(str)
    result = Signal(object)   # dict with keys: rc, command, fit_scores, manifest
    error = Signal(str)
    finished = Signal()


class NormalizerWorker(QRunnable):
    """
    Runs a single normalizer command in a background thread.
    Receives a deep-copied manifest so the UI manifest stays safe.
    Emits the (possibly mutated) manifest back in result for the UI to adopt.
    """

    def __init__(self, command: str, manifest: dict, **kwargs):
        super().__init__()
        self.signals = NormalizerSignals()
        self._command = command
        self._manifest = copy.deepcopy(manifest)
        self._kwargs = kwargs
        self.setAutoDelete(True)

    def run(self):
        m = self._manifest
        log = self.signals.log.emit
        try:
            fit_scores = {}
            if self._command == "scan":
                rc = cmd_scan(m, log=log)
            elif self._command == "rebalance":
                rc, fit_scores = cmd_rebalance(
                    m,
                    group=self._kwargs.get("group"),
                    all_groups_flag=self._kwargs.get("all_groups", False),
                    force=self._kwargs.get("force", False),
                    log=log,
                )
            elif self._command == "build":
                rc, fit_scores = cmd_build(m, log=log)
            elif self._command == "verify":
                rc = cmd_verify(m, log=log)
            elif self._command == "export":
                rc = cmd_export(
                    m,
                    group=self._kwargs.get("group"),
                    all_groups_flag=self._kwargs.get("all_groups", False),
                    log=log,
                )
            else:
                raise ValueError(f"Unknown command: {self._command}")

            self.signals.result.emit(
                {
                    "rc": rc,
                    "command": self._command,
                    "fit_scores": fit_scores,
                    "manifest": m,
                }
            )
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()
