import json
import os
from pathlib import Path
import sys


def smoke_test():
    os.environ['QT_QPA_PLATFORM']='offscreen'
    from PySide6.QtWidgets import QApplication
    from streamguard.ui.main_window import MainWindow
    from streamguard.detection.vosk_backend import VoskDetector
    import numpy as np
    destination=Path(sys.argv[2]).resolve()
    app=QApplication([])
    window=MainWindow(destination.parent/'packaged-test-state')
    detector=VoskDetector(sys.argv[3]);detector.start(16000)
    detector.process_audio(np.zeros(320,dtype=np.float32));detector.stop()
    destination.write_text(json.dumps({'qt':'loaded','vosk':'loaded and processed PCM','title':window.windowTitle()}))
    window.close()


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--smoke-test':
        try:smoke_test()
        except BaseException:
            import traceback
            Path(sys.argv[2]).write_text(json.dumps({'error':traceback.format_exc()}))
            raise SystemExit(1)
    else:
        from streamguard.ui.main_window import main
        raise SystemExit(main())
