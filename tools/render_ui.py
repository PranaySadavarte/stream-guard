"""Render a stopped UI preview; no microphone is opened."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from streamguard.ui.main_window import MainWindow

root=Path(__file__).resolve().parents[1]
app=QApplication([])
for font in ('segoeui.ttf','segoeuib.ttf'):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+font)
window=MainWindow(root/'recordings/ui-state')
window.model.setText(str(root/'models/vosk-model-small-en-us-0.15'))
window.show();app.processEvents()
window.grab().save(str(root/'recordings/ui-preview.png'))
window.close()
