#!/usr/bin/env python3
"""
PixelForge Studio — unified sprite conversion and palette normalization tool.

GUI mode (default):
    python app.py

CLI mode (sprite forge):
    python app.py forge <input.png> [options]
    python app.py forge --help

CLI mode (palette normalizer):
    python app.py normalize <command> [options]
    python app.py normalize --help
"""

import sys
import os

# Ensure the studio/ directory is on sys.path when invoked as a script
sys.path.insert(0, os.path.dirname(__file__))


def _run_gui():
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("PixelForge Studio")
    app.setStyle("Fusion")

    # Dark palette
    palette = QPalette()
    dark = QColor(30, 30, 30)
    mid = QColor(45, 45, 45)
    light = QColor(210, 210, 210)
    accent = QColor(100, 160, 240)

    palette.setColor(QPalette.Window, dark)
    palette.setColor(QPalette.WindowText, light)
    palette.setColor(QPalette.Base, QColor(22, 22, 22))
    palette.setColor(QPalette.AlternateBase, mid)
    palette.setColor(QPalette.ToolTipBase, mid)
    palette.setColor(QPalette.ToolTipText, light)
    palette.setColor(QPalette.Text, light)
    palette.setColor(QPalette.Button, mid)
    palette.setColor(QPalette.ButtonText, light)
    palette.setColor(QPalette.BrightText, QColor(255, 100, 100))
    palette.setColor(QPalette.Link, accent)
    palette.setColor(QPalette.Highlight, accent)
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


def _run_forge_cli():
    from cli.forge_cli import main
    main()


def _run_normalizer_cli():
    from cli.normalizer_cli import main
    main()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "forge":
        sys.argv = [sys.argv[0]] + args[1:]
        _run_forge_cli()
    elif args and args[0] == "normalize":
        sys.argv = [sys.argv[0]] + args[1:]
        _run_normalizer_cli()
    else:
        _run_gui()
