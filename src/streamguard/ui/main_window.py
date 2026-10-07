import json
from pathlib import Path
import sys
import threading
import time
import uuid
from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QPlainTextEdit,
    QGroupBox, QFormLayout, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy, QCheckBox)
from ..audio.devices import devices
from ..audio.censor import CensorSettings
from ..config import AudioSettings
from ..detection.profanity import DEFAULT_TERMS, ProfanityDictionary
from ..detection.vosk_backend import VoskDetector
from ..detection.bounded_vosk import BoundedVoskDetector
from ..detection.whisper_backend import WhisperFileDetector
from ..detection.vocabulary import UnsupportedWordsError, check_live_words
from ..pipeline.controller import LiveController
from ..pipeline.session import RecordedSession
from ..telemetry import event_logger, log_event, masked_event
from .settings import data_directory, load_settings, save_settings, migrate_live_test_settings

STYLE = '''
QMainWindow,QWidget { background:#101723; color:#e7edf7; font-family:Segoe UI; font-size:13px; }
QGroupBox { border:1px solid #304054; border-radius:10px; margin-top:16px; padding:16px 12px 10px; }
QGroupBox::title { subcontrol-origin:margin; left:14px; color:#a8b8cb; }
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QPlainTextEdit { background:#1a2738; border:1px solid #3b4d65; border-radius:5px; padding:6px; }
QPushButton { background:#25364b; padding:10px 16px; border-radius:6px; border:1px solid #4b607a; }
QPushButton:hover { background:#314963; } QPushButton:disabled { color:#65758b; border-color:#26354a; }
QPushButton#start { background:#39d7b2; color:#071b17; font-weight:700; }
QLabel#title { font-size:30px; font-weight:700; } QLabel#subtitle { color:#9eb0c8; }
QLabel#status { background:#1b293b; padding:14px; border-radius:8px; font-size:18px; font-weight:600; }
QLabel#violation { background:#613c15; color:#fff0c9; padding:12px; border:1px solid #e6a84b; border-radius:8px; font-size:16px; font-weight:600; }
QTableWidget { background:#142031; border:1px solid #304054; gridline-color:#26364b; }
QHeaderView::section { background:#233249; color:#cbd9eb; padding:8px; border:0; }
'''


class MainWindow(QMainWindow):
    def __init__(self, state_directory=None):
        super().__init__()
        self.setWindowTitle('StreamGuard 0.3 RC1 • Sponsor Safe Mode')
        self.resize(1080, 850)
        self.root = Path(state_directory) if state_directory else data_directory()
        self.root.mkdir(parents=True, exist_ok=True)
        self.logger = event_logger(self.root/'events.log')
        self.controller = None
        self.task = None
        self.task_result = None
        self.last_event = 0
        self.last_log_time = 0
        self.closing = False
        self.last_recording = None
        self.original_recording = None
        self.player = None
        self.cancel_start = False
        self.task_kind = None
        self.unsupported_words = ()
        self._restoring = False
        self._mode_index = 0
        self._backend_index = 0
        self._recordings = {0:(None,None),1:(None,None)}
        repo=Path(sys.executable).resolve().parents[2] if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[3]
        self._models = {'vosk':str(repo/'models/vosk-model-small-en-us-0.15'),
                        'whisper':str(repo/'models/faster-whisper-small.en')}
        self._backends = {0:1 if (Path(self._models['whisper'])/'model.bin').is_file() else 0,1:2}
        container=QWidget(); self.setCentralWidget(container)
        layout=QVBoxLayout(container); layout.setContentsMargins(24,20,24,20); layout.setSpacing(12)
        title=QLabel('StreamGuard'); title.setObjectName('title'); layout.addWidget(title)
        subtitle=QLabel('SPONSOR SAFE MODE  /  Local speech filtering'); subtitle.setObjectName('subtitle'); layout.addWidget(subtitle)
        self.status=QLabel('STOPPED'); self.status.setObjectName('status'); layout.addWidget(self.status)
        self.violation=QLabel();self.violation.setObjectName('violation');self.violation.setWordWrap(True)
        self.violation.hide();layout.addWidget(self.violation)
        self.notice_timer=QTimer(self);self.notice_timer.setSingleShot(True)
        self.notice_timer.timeout.connect(self.violation.hide)
        self.notice=QLabel();self.notice.setWordWrap(True);layout.addWidget(self.notice)
        columns=QHBoxLayout(); layout.addLayout(columns)
        self.routing=QGroupBox('Audio and recognition'); form=QFormLayout(self.routing); columns.addWidget(self.routing,1)
        self.session_mode=QComboBox();self.session_mode.addItems(['Record full session, filter after Stop','Live protection (experimental)'])
        form.addRow('Test mode',self.session_mode)
        self.input=QComboBox(); self.output=QComboBox()
        for combo in (self.input,self.output):
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(20)
            combo.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        form.addRow('Microphone',self.input); form.addRow('Output to OBS',self.output)
        self.refresh=QPushButton('Refresh devices'); self.refresh.clicked.connect(self.refresh_devices); form.addRow(self.refresh)
        self.model=QLineEdit(); self.model.setPlaceholderText('Choose extracted Vosk model folder')
        model_row=QHBoxLayout(); model_row.addWidget(self.model)
        browse=QPushButton('Browse'); browse.clicked.connect(self.browse_model); model_row.addWidget(browse)
        form.addRow('Local model',model_row)
        self.backend=QComboBox();self.backend.addItems(['Vosk - local English model','Whisper - local English, offline','Vosk - fast live (experimental)'])
        form.addRow('Detector',self.backend)
        self.delay=QComboBox()
        for ms in (500,750,1000,1250,1500,2000,2500,3000): self.delay.addItem(f'{ms/1000:g} seconds',ms)
        self.delay.setCurrentIndex(4); form.addRow('Audience delay',self.delay)
        self.rate=QComboBox()
        for rate in (16000,32000,44100,48000):self.rate.addItem(f'{rate} Hz',rate)
        self.rate.setCurrentIndex(3); form.addRow('Sample rate',self.rate)
        self.channels=QComboBox();self.channels.addItem('Mono',1);self.channels.addItem('Stereo',2);self.channels.setCurrentIndex(1)
        form.addRow('Output channels',self.channels)
        self.route_note=QLabel();self.route_note.setWordWrap(True);form.addRow(self.route_note)
        self.censor_group=QGroupBox('Censorship'); censor_form=QFormLayout(self.censor_group);columns.addWidget(self.censor_group,1)
        self.mode=QComboBox();self.mode.addItems(['Beep','Silence']);censor_form.addRow('Replacement',self.mode)
        self.frequency=QSpinBox();self.frequency.setRange(100,4000);self.frequency.setValue(1000);self.frequency.setSuffix(' Hz');censor_form.addRow('Beep frequency',self.frequency)
        self.volume=QSpinBox();self.volume.setRange(0,100);self.volume.setValue(20);self.volume.setSuffix(' %');censor_form.addRow('Beep volume',self.volume)
        self.before=QSpinBox();self.after=QSpinBox()
        for control in (self.before,self.after):control.setRange(0,500);control.setValue(150);control.setSuffix(' ms')
        censor_form.addRow('Padding before',self.before);censor_form.addRow('Padding after',self.after)
        self.words=QPlainTextEdit('\n'.join(DEFAULT_TERMS));self.words.setMaximumHeight(150)
        censor_form.addRow('Blocked words\n(one per line)',self.words)
        self.count=QLabel();self.words.textChanged.connect(self.update_count);censor_form.addRow(self.count);self.update_count()
        self.word_issue=QLabel();self.word_issue.setWordWrap(True);self.word_issue.hide();censor_form.addRow(self.word_issue)
        self.remove_words=QPushButton('Remove unsupported words');self.remove_words.hide()
        self.remove_words.clicked.connect(self.remove_unsupported_words);censor_form.addRow(self.remove_words)
        controls=QHBoxLayout(); layout.addLayout(controls)
        self.start_button=QPushButton('Start protection');self.start_button.setObjectName('start');self.start_button.clicked.connect(self.start)
        self.stop_button=QPushButton('Stop');self.stop_button.setEnabled(False);self.stop_button.clicked.connect(self.stop)
        self.save_button=QPushButton('Save settings');self.save_button.clicked.connect(self.save)
        controls.addWidget(self.start_button);controls.addWidget(self.stop_button);controls.addStretch();controls.addWidget(self.save_button)
        recording_controls=QHBoxLayout();layout.addLayout(recording_controls)
        self.record_output=QCheckBox('Record protected output from Start to Stop');self.record_output.setChecked(True)
        recording_controls.addWidget(self.record_output)
        self.replay_button=QPushButton('Play recording');self.replay_button.setEnabled(False)
        self.replay_button.clicked.connect(self.replay);recording_controls.addWidget(self.replay_button)
        self.original_button=QPushButton('Play original');self.original_button.setEnabled(False)
        self.original_button.clicked.connect(lambda checked=False:self.replay(True));recording_controls.addWidget(self.original_button)
        self.folder_button=QPushButton('Open recordings');self.folder_button.clicked.connect(self.open_recordings)
        recording_controls.addWidget(self.folder_button)
        self.recording_status=QLabel('Recording is saved locally. Playback is available after Stop.');self.recording_status.setWordWrap(True)
        layout.addWidget(self.recording_status)
        self.metrics=QLabel('Detected 0   •   Muted 0.0 s   •   Queue 0   •   Headroom —');self.metrics.setWordWrap(True);layout.addWidget(self.metrics)
        self.events=QTableWidget(0,4);self.events.setHorizontalHeaderLabels(['Time','Term','Confidence','Timing'])
        self.events.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.events.setEditTriggers(QTableWidget.NoEditTriggers);layout.addWidget(self.events,1)
        self.message=QLabel('Ready to configure. Choose devices explicitly; no audio is routed until you start.');self.message.setWordWrap(True);layout.addWidget(self.message)
        self.refresh_devices()
        try:
            if state_directory is None:migrate_live_test_settings(self.root,repo/'recordings/live-test-state/settings.json')
            self.restore(load_settings(self.root/'settings.json'))
        except Exception as exc:
            self.restore({});self.message.setText(f'Could not load saved settings; defaults restored: {exc}')
        self.session_mode.currentIndexChanged.connect(self.update_session_mode)
        self.backend.currentIndexChanged.connect(self.choose_backend_model)
        self.update_session_mode()
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(150)
        self.setStyleSheet(STYLE)

    def refresh_devices(self):
        selected=(self.input.currentText(),self.output.currentText())
        self.input.clear();self.output.clear()
        for combo in (self.input,self.output):combo.addItem('Select a device…',None)
        try:
            for device in devices():
                label=f"{device['name']} · {device['host']}"
                if device['input_channels']:self.input.addItem(label,device['id'])
                if device['output_channels']:self.output.addItem(label,device['id'])
            for combo,label in zip((self.input,self.output),selected):
                index=combo.findText(label)
                if index>=0:combo.setCurrentIndex(index)
        except Exception as exc:self.status.setText(f'Device enumeration failed: {exc}')

    def browse_model(self):
        selected=QFileDialog.getExistingDirectory(self,'Choose local recognition model')
        if selected:self.model.setText(selected)

    def update_count(self):
        self.count.setText(f'{len(set(self.words.toPlainText().split()))} blocked terms')

    def values(self):
        self.remember_model()
        values={'input':self.input.currentText(),'output':self.output.currentText(),
                'model':self.model.text(),'delay':self.delay.currentData(),'rate':self.rate.currentData(),
                'channels':self.channels.currentData(),'mode':self.mode.currentText(),
                'frequency':self.frequency.value(),'volume':self.volume.value(),
                'before':self.before.value(),'after':self.after.value(),'words':self.words.toPlainText(),
                'record_output':self.record_output.isChecked()}
        values['session_mode']=self.session_mode.currentIndex();values['backend']=self.backend.currentIndex()
        values['models']=dict(self._models)
        values['settings_version']=2
        values['mode_backends']={str(k):v for k,v in self._backends.items()}
        return values

    def restore(self,data):
        self._restoring=True
        mode=data.get('session_mode',0)
        mode=mode if mode in (0,1) else 0
        backend=data.get('backend',self._backends[mode])
        for key,value in (data.get('models') or {}).items():
            if key in self._models and isinstance(value,str) and value:self._models[key]=value
        for key,value in (data.get('mode_backends') or {}).items():
            if key in ('0','1') and value in ((0,1) if key=='0' else (0,2)):self._backends[int(key)]=value
        if isinstance(data.get('model'),str) and data['model']:
            self._models['whisper' if backend==1 else 'vosk']=data['model']
        if backend in ((0,1) if mode==0 else (0,2)):self._backends[mode]=backend
        self._mode_index=mode;self._backend_index=self._backends[mode]
        self.session_mode.setCurrentIndex(mode)
        self.backend.setCurrentIndex(self._backend_index)
        self.model.setText(self._models['whisper' if self._backend_index==1 else 'vosk'])
        for name in ('input','output','mode'):
            combo=getattr(self,name);idx=combo.findText(str(data.get(name,'')))
            if idx>=0:combo.setCurrentIndex(idx)
        for name in ('delay','rate','channels'):
            combo=getattr(self,name);idx=combo.findData(data.get(name))
            if idx>=0:combo.setCurrentIndex(idx)
        for name in ('frequency','volume','before','after'):
            if name in data:getattr(self,name).setValue(int(data[name]))
        if 'words' in data:self.words.setPlainText(str(data['words']))
        if 'record_output' in data:self.record_output.setChecked(bool(data['record_output']))
        self._restoring=False
        self.update_session_mode()

    def choose_backend_model(self):
        if self._restoring:return
        new=self.backend.currentIndex()
        allowed=(0,1) if self._mode_index==0 else (0,2)
        if new not in allowed or self.task or self.controller:
            self.backend.blockSignals(True);self.backend.setCurrentIndex(self._backend_index);self.backend.blockSignals(False)
            return
        self.remember_model()
        self._backend_index=new;self._backends[self._mode_index]=new
        self.model.setText(self._models['whisper' if new==1 else 'vosk'])
        self.update_session_mode()

    def remember_model(self):
        if self.model.text().strip():
            self._models['whisper' if self._backend_index==1 else 'vosk']=self.model.text().strip()

    def remove_unsupported_words(self):
        from ..detection.profanity import normalize
        self.words.setPlainText('\n'.join(line for line in self.words.toPlainText().splitlines()
                                         if normalize(line) not in self.unsupported_words))
        self.unsupported_words=();self.word_issue.hide();self.remove_words.hide()
        self.message.setText('Unsupported words removed from the draft. Save settings to validate and apply the list.')

    def show_error(self,error):
        self.message.setText(str(error))
        if isinstance(error,UnsupportedWordsError):
            self.unsupported_words=error.words
            self.word_issue.setText(str(error));self.word_issue.show();self.remove_words.show()

    def update_session_mode(self):
        if self._restoring:return
        new=self.session_mode.currentIndex()
        if new!=self._mode_index:
            if self.task or self.controller:
                self.session_mode.blockSignals(True);self.session_mode.setCurrentIndex(self._mode_index);self.session_mode.blockSignals(False)
                return
            self.remember_model();self._backends[self._mode_index]=self._backend_index
            self._recordings[self._mode_index]=(self.last_recording,self.original_recording)
            self._mode_index=new;self._backend_index=self._backends[new]
            self.last_recording,self.original_recording=self._recordings[new]
            self.backend.blockSignals(True);self.backend.setCurrentIndex(self._backend_index);self.backend.blockSignals(False)
            self.model.setText(self._models['whisper' if self._backend_index==1 else 'vosk'])
            if self.player:self.player.stop()
        for index in range(self.backend.count()):
            self.backend.model().item(index).setEnabled(index in ((0,1) if new==0 else (0,2)))
        if self._backend_index==2 and self.delay.currentData()<1250:
            self.delay.setCurrentIndex(self.delay.findData(1250))
        batch=self.session_mode.currentIndex()==0
        self.output.setEnabled(not batch);self.delay.setEnabled(not batch);self.channels.setEnabled(not batch)
        self.record_output.setEnabled(not batch)
        self.record_output.setVisible(not batch)
        self.record_output.setText('Full session saved locally' if batch else 'Save live output')
        self.start_button.setText('Start recording' if batch else 'Start protection')
        self.route_note.setText('Full-session mode uses only the microphone. Output and audience delay are unused.' if batch else
                               'For OBS, select CABLE Input here and capture CABLE Output in OBS. Fast live needs at least 1.25 seconds of audience delay.')
        self.replay_button.setText('Play filtered' if batch else 'Play recording')
        if not self.task and not self.controller:
            self.replay_button.setEnabled(self.last_recording is not None)
            self.original_button.setEnabled(self.original_recording is not None)
        if not self.controller and not self.task and not self.last_recording:
            self.metrics.setText('Ready to record the entire session; filtering begins after Stop.' if batch else
                                 'Detected 0 • Muted 0.0 s • Queue 0 • Headroom —')
        self.notice.setText('Record first, filter after Stop. Original and filtered audio are saved locally; no audio is sent to OBS.'
                            if batch else 'Experimental live mode: unfinished recognition is muted. Recognition can miss words.')


    def open_recordings(self):
        folder=self.root/'recordings';folder.mkdir(parents=True,exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))

    def replay(self,original=False):
        path=self.original_recording if original else self.last_recording
        if self.controller or self.task or not path:return
        if self.player is None:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            self.player=QMediaPlayer(self);self.playback_output=QAudioOutput(self)
            self.playback_output.setVolume(.5);self.player.setAudioOutput(self.playback_output)
            self.player.playbackStateChanged.connect(self.replay_state)
            self.player.errorOccurred.connect(lambda error,text:self.recording_status.setText(f'Playback failed: {text}'))
        if self.player.isPlaying() and self.player.source()==QUrl.fromLocalFile(str(path.resolve())):
            self.player.stop();return
        self.player.stop();self.playback_button=self.original_button if original else self.replay_button
        self.player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.player.play()
        self.recording_status.setText(f"Playing {'ORIGINAL — UNCENSORED' if original else 'filtered'} audio through Windows default output: {path}")

    def replay_state(self,state):
        self.replay_button.setText('Play filtered' if self.session_mode.currentIndex()==0 else 'Play recording')
        self.original_button.setText('Play original')
        if state==self.player.PlayingState:self.playback_button.setText('Stop replay')

    def save(self):
        if self.task or self.controller:return
        try:
            dictionary=ProfanityDictionary(self.words.toPlainText().splitlines())
            values=self.values()
            if values['backend']==2 and not (Path(values['model'])/'am/final.mdl').is_file():
                raise ValueError('Choose the extracted Vosk model folder before saving live settings.')
        except Exception as exc:self.show_error(exc);return
        def validate_and_save():
            try:
                if values['backend']==2:check_live_words(values['model'],dictionary.terms)
                save_settings(self.root/'settings.json',values)
                self.task_result=('saved',None)
            except Exception as exc:self.task_result=('error',exc)
        self.lock(True);self.status.setText('VALIDATING SETTINGS...');self.task_kind='save'
        self.task=threading.Thread(target=validate_and_save,daemon=True);self.task.start()

    def lock(self,running):
        self.routing.setEnabled(not running);self.censor_group.setEnabled(not running)
        self.start_button.setEnabled(not running);self.save_button.setEnabled(not running)
        self.record_output.setEnabled(not running)
        self.replay_button.setEnabled(not running and self.last_recording is not None)
        self.original_button.setEnabled(not running and self.original_recording is not None)
        if not running:self.update_session_mode()

    def start(self):
        if self.task or self.controller:return
        self.cancel_start=False
        try:
            batch=self.session_mode.currentIndex()==0
            if self.input.currentData() is None:raise ValueError('Choose a microphone device.')
            if not batch and self.output.currentData() is None:raise ValueError('Choose both a microphone and output device.')
            model=self.model.text().strip()
            whisper=self.backend.currentIndex()==1
            bounded=self.backend.currentIndex()==2
            if bounded and batch:raise ValueError('Fast live detection requires Live protection mode. Use Whisper for full-session recording.')
            if bounded and self.delay.currentData()<1250:raise ValueError('Fast live detection currently needs at least 1.25 seconds of audience delay.')
            if whisper and not batch:raise ValueError('Whisper is supported in full-session recording mode. Use Vosk for experimental live mode.')
            if not (Path(model)/('model.bin' if whisper else 'am/final.mdl')).is_file():
                raise ValueError('Choose the downloaded Whisper model folder.' if whisper else 'Choose the extracted Vosk model folder (containing am/final.mdl).')
            detector=WhisperFileDetector(model) if whisper else VoskDetector(model)
            audio=AudioSettings(self.input.currentData(),self.output.currentData() or 0,sample_rate=self.rate.currentData(),
                                delay_ms=self.delay.currentData(),output_channels=self.channels.currentData())
            censor=CensorSettings(self.mode.currentText().lower(),self.frequency.value(),self.volume.value()/100,
                                   self.before.value(),self.after.value())
            dictionary=ProfanityDictionary(self.words.toPlainText().splitlines())
            if bounded:detector=BoundedVoskDetector(model,750,250,dictionary.terms)
            recording_path=(self.root/'recordings'/f"session-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.wav"
                            if batch or self.record_output.isChecked() else None)
            controller=(RecordedSession(audio,detector,dictionary,censor,recording_path) if batch else
                        LiveController(audio,detector,dictionary,censor,recording_path=recording_path))
        except Exception as exc:
            self.status.setText('NOT STARTED');self.show_error(exc);return
        self.lock(True);self.status.setText('STARTING MICROPHONE…' if batch else 'LOADING LOCAL MODEL…');self.last_event=0;self.events.setRowCount(0)
        self.notice_timer.stop();self.violation.hide()
        if self.player:self.player.stop()
        self.stop_button.setEnabled(True);self.task_kind='start'
        self.recording_status.setText('Saving full original audio locally; filtering starts after Stop.' if batch else
                                     ('Recording protected output locally…' if recording_path else 'Recording disabled for this session.'))
        self.message.setText('Speak normally for the full test; no special pauses are needed. This mode does not broadcast.' if batch else
                             'Recognition errors can still miss words; test locally before broadcasting.')
        def launch():
            try:
                controller.start()
                if self.cancel_start:
                    controller.close();self.task_result=('cancelled',None)
                else:self.task_result=('started',controller)
            except Exception as exc:
                try:controller.close()
                except Exception as cleanup:self.logger.error('Startup cleanup failed: %s',cleanup)
                self.task_result=('error',exc)
        self.task=threading.Thread(target=launch,daemon=True);self.task.start()

    def stop(self):
        if self.task and self.task_kind=='start':
            self.cancel_start=True;self.stop_button.setEnabled(False);self.status.setText('CANCELLING START...');return
        if self.task or not self.controller:return
        controller=self.controller;self.controller=None
        self.stop_button.setEnabled(False);self.status.setText('STOPPING…')
        def shutdown():
            try:
                controller.close()
                if isinstance(controller,RecordedSession):
                    self.task_result=('recorded',controller);return
                recorder=getattr(controller,'recorder',None)
                self.task_result=('stopped',{'path':recorder.path if recorder and recorder.complete else None,
                    'error':recorder.error if recorder else None})
            except Exception as exc:self.task_result=('error',exc)
        self.task_kind='stop'
        self.task=threading.Thread(target=shutdown,daemon=True);self.task.start()

    def poll(self):
        if self.task_result is not None and self.task is not None and not self.task.is_alive():
            action,value=self.task_result;self.task_result=None;self.task=None
            self.task_kind=None
            if action=='recorded':
                self.original_recording=value.raw_path if value.raw_path.exists() else None
                self.status.setText('PROCESSING FULL RECORDING…')
                def process_session():
                    try:self.task_result=('stopped',value.filter())
                    except Exception as exc:self.task_result=('error',f'Filtering failed; original retained at {value.raw_path}: {exc}')
                self.task=threading.Thread(target=process_session,daemon=True);self.task.start();return
            if action=='started':
                self.controller=value;self.last_recording=self.original_recording=None
                self.unsupported_words=();self.word_issue.hide();self.remove_words.hide()
                self.stop_button.setEnabled(True)
                if self.cancel_start:self.stop();return
            else:
                self.stop_button.setEnabled(False)
                if action=='saved':
                    self.unsupported_words=();self.word_issue.hide();self.remove_words.hide()
                    self.message.setText('Settings validated and saved. The next session will use this word list.')
                if action=='stopped':
                    self.last_recording=value['path']
                    self.original_recording=value.get('original',self.original_recording)
                    if 'detections' in value:self.metrics.setText(f"Full recording processed • {value['detections']} blocked word intervals replaced • No deadline muting")
                    self.recording_status.setText(value['error'] or (
                        f'Saved protected output: {self.last_recording}' if self.last_recording else 'No recording saved for this session.'))
                self.lock(False);self.status.setText('ERROR — OUTPUT STOPPED' if action=='error' else 'STOPPED')
                if value and action=='error':
                    self.show_error(value)
                    self.recording_status.setText('Operation failed. Correct the issue and try again; previous recordings are retained.')
            if self.closing:
                if self.controller:self.stop()
                else:self.close()
        if not self.controller:return
        status=self.controller.snapshot();self.status.setText(status['state'])
        if isinstance(self.controller,RecordedSession):
            self.metrics.setText(f"Recorded {status['recorded_seconds']:.1f} seconds • Recognition runs after Stop • No live playback")
            if status['error']:self.message.setText(status['error']);self.stop()
            return
        recorder=getattr(self.controller,'recorder',None)
        if recorder and recorder.error:self.recording_status.setText(recorder.error)
        if time.monotonic()-self.last_log_time>=1:
            self.last_log_time=time.monotonic()
            self.logger.info(json.dumps({k:v for k,v in status.items() if k!='events'}))
        latency=status['detection_latency_ms'];p99=f"{latency['p99']:.0f} ms" if latency else '—'
        self.metrics.setText(f"Detected {status['detected']}  •  Muted {status['muted_ms']/1000:.1f} s  •  Queue {status['queue_depth']}  •  Headroom {status['headroom_ms']:.0f} ms  •  Detection p99 {p99}")
        for event in status['events']:
            if event['id']<=self.last_event:continue
            self.last_event=event['id'];masked=masked_event(event)
            timing='Recognition arrived late; output uses protective muting.' if event['late'] else 'Censorship scheduled for the delayed audio.'
            self.violation.setText(f"Blocked word detected: {masked['term']} — {timing} Avoid repeating it.")
            self.violation.show();self.notice_timer.start(10000)
            row=self.events.rowCount();self.events.insertRow(row)
            values=[time.strftime('%H:%M:%S',time.localtime(event['timestamp'])),masked['term'],
                    f"{event['confidence']:.0%}",'Late / muted' if event['late'] else f"{event['latency_ms']:.0f} ms"]
            for col,value in enumerate(values):self.events.setItem(row,col,QTableWidgetItem(value))
            if self.events.rowCount()>100:self.events.removeRow(0)
            try:log_event(self.logger,event)
            except OSError as exc:self.message.setText(f'Event log unavailable: {exc}')
        if status['error']:
            self.message.setText(status['error']);self.stop()

    def closeEvent(self,event):
        if self.player:self.player.stop()
        if self.controller or self.task:
            self.closing=True;event.ignore()
            if self.task_kind=='start':self.cancel_start=True
            if self.controller and not self.task:self.stop()
            self.status.setText('STOPPING AUDIO BEFORE CLOSE…')
        else:event.accept()


def main(state_directory=None):
    from .application import run
    return run(state_directory)


if __name__=='__main__':raise SystemExit(main())
