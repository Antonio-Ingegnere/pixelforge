from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QMainWindow

from ui.catalogue_view import CatalogueView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PixelForge Studio")
        self.resize(1280, 860)

        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(2)

        self.setCentralWidget(CatalogueView(self._pool))
