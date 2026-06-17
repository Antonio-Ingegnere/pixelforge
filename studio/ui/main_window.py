from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QMainWindow, QTabWidget

from ui.forge_tab import ForgeTab
from ui.normalizer_tab import NormalizerTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PixelForge Studio")
        self.resize(1200, 820)

        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(2)

        tabs = QTabWidget()
        tabs.addTab(ForgeTab(self._pool), "Sprite Forge")
        tabs.addTab(NormalizerTab(self._pool), "Palette Normalizer")
        self.setCentralWidget(tabs)
