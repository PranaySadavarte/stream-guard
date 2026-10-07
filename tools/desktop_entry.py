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
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    player=QMediaPlayer();player.setAudioOutput(QAudioOutput(player))
    detector=VoskDetector(sys.argv[3]);detector.start(16000)
    detector.process_audio(np.zeros(320,dtype=np.float32));detector.stop()
    from streamguard.detection.bounded_vosk import BoundedVoskDetector
    from streamguard.detection.profanity import ProfanityDictionary
    from streamguard.ui import application
    bounded=BoundedVoskDetector(sys.argv[3],750,250,ProfanityDictionary(['banana','cat']).terms)
    bounded.start(16000)
    for _ in range(50):bounded.process_audio(np.zeros(320,dtype=np.float32))
    bounded.stop()
    whisper_status='not requested'
    if len(sys.argv)>4:
        from streamguard.detection.whisper_backend import WhisperFileDetector
        from streamguard.offline import write_wav
        sample=destination.parent/'packaged-whisper-sample.wav'
        write_wav(sample,np.zeros((16000,1),dtype=np.float32),16000)
        WhisperFileDetector(sys.argv[4]).transcribe_file(sample)
        whisper_status='loaded and transcribed local WAV'
        window.restore({'session_mode':1,'backend':2,'model':sys.argv[3],
                        'models':{'whisper':sys.argv[4]},'mode_backends':{'0':1,'1':2}})
        for mode,backend in ((0,1),(1,2),(0,1),(1,2)):
            window.session_mode.setCurrentIndex(mode)
            assert window.backend.currentIndex()==backend
    destination.write_text(json.dumps({'qt':'loaded','playback':'Qt multimedia loaded',
        'vosk':'loaded and processed PCM','bounded':'loaded, finalized windows and accepted edited word list',
        'single_instance':'Qt Network imported','mode_switching':'compatible detectors restored',
        'whisper':whisper_status,'title':window.windowTitle()}))
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
