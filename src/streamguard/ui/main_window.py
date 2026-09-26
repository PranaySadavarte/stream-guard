import json
from pathlib import Path
import sys
import threading
import time
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QPlainTextEdit,
    QGroupBox, QFormLayout, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy)
from ..audio.devices import devices
from ..audio.censor import CensorSettings
from ..config import AudioSettings
from ..detection.profanity import DEFAULT_TERMS, ProfanityDictionary
from ..detection.vosk_backend import VoskDetector
from ..pipeline.controller import LiveController
from ..telemetry import event_logger, log_event, masked_event
from .settings import data_directory, load_settings, save_settings

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
QTableWidget { background:#142031; border:1px solid #304054; gridline-color:#26364b; }
QHeaderView::section { background:#233249; color:#cbd9eb; padding:8px; border:0; }
'''


class MainWindow(QMainWindow):
    def __init__(self, state_directory=None):
        super().__init__()
        self.setWindowTitle('StreamGuard • Sponsor Safe Mode')
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
        container=QWidget(); self.setCentralWidget(container)
        layout=QVBoxLayout(container); layout.setContentsMargins(24,20,24,20); layout.setSpacing(12)
        title=QLabel('StreamGuard'); title.setObjectName('title'); layout.addWidget(title)
        subtitle=QLabel('SPONSOR SAFE MODE  /  Local speech filtering'); subtitle.setObjectName('subtitle'); layout.addWidget(subtitle)
        self.status=QLabel('STOPPED'); self.status.setObjectName('status'); layout.addWidget(self.status)
        notice=QLabel('Only the audience path is delayed. Unfinished recognition is muted. Speech recognition can miss words.')
        notice.setWordWrap(True); layout.addWidget(notice)
        columns=QHBoxLayout(); layout.addLayout(columns)
        self.routing=QGroupBox('Audio and recognition'); form=QFormLayout(self.routing); columns.addWidget(self.routing,1)
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
        self.backend=QComboBox(); self.backend.addItem('Vosk · local English model'); form.addRow('Detector',self.backend)
        self.delay=QComboBox()
        for ms in (500,750,1000,1250,1500,2000,2500,3000): self.delay.addItem(f'{ms/1000:g} seconds',ms)
        self.delay.setCurrentIndex(4); form.addRow('Audience delay',self.delay)
        self.rate=QComboBox()
        for rate in (16000,32000,44100,48000):self.rate.addItem(f'{rate} Hz',rate)
        self.rate.setCurrentIndex(3); form.addRow('Sample rate',self.rate)
        self.channels=QComboBox();self.channels.addItem('Mono',1);self.channels.addItem('Stereo',2);self.channels.setCurrentIndex(1)
        form.addRow('Output channels',self.channels)
        note=QLabel('OBS uses CABLE Output. StreamGuard sends to CABLE Input.\nFor the current Vosk model, try 3 seconds if speech is muted.')
        note.setWordWrap(True);form.addRow(note)
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
        controls=QHBoxLayout(); layout.addLayout(controls)
        self.start_button=QPushButton('Start protection');self.start_button.setObjectName('start');self.start_button.clicked.connect(self.start)
        self.stop_button=QPushButton('Stop');self.stop_button.setEnabled(False);self.stop_button.clicked.connect(self.stop)
        self.save_button=QPushButton('Save settings');self.save_button.clicked.connect(self.save)
        controls.addWidget(self.start_button);controls.addWidget(self.stop_button);controls.addStretch();controls.addWidget(self.save_button)
        self.metrics=QLabel('Detected 0   •   Muted 0.0 s   •   Queue 0   •   Headroom —');self.metrics.setWordWrap(True);layout.addWidget(self.metrics)
        self.events=QTableWidget(0,4);self.events.setHorizontalHeaderLabels(['Time','Term','Confidence','Timing'])
        self.events.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.events.setEditTriggers(QTableWidget.NoEditTriggers);layout.addWidget(self.events,1)
        self.message=QLabel('Ready to configure. Choose devices explicitly; no audio is routed until you start.');self.message.setWordWrap(True);layout.addWidget(self.message)
        self.refresh_devices()
        try:self.restore(load_settings(self.root/'settings.json'))
        except Exception as exc:self.message.setText(f'Could not load saved settings: {exc}')
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(150)
        self.setStyleSheet(STYLE)

    def refresh_devices(self):
        self.input.clear();self.output.clear()
        for combo in (self.input,self.output):combo.addItem('Select a device…',None)
        try:
            for device in devices():
                label=f"{device['name']} · {device['host']}"
                if device['input_channels']:self.input.addItem(label,device['id'])
                if device['output_channels']:self.output.addItem(label,device['id'])
        except Exception as exc:self.status.setText(f'Device enumeration failed: {exc}')

    def browse_model(self):
        selected=QFileDialog.getExistingDirectory(self,'Choose local Vosk model')
        if selected:self.model.setText(selected)

    def update_count(self):
        self.count.setText(f'{len(set(self.words.toPlainText().split()))} blocked terms')

    def values(self):
        return {'input':self.input.currentText(),'output':self.output.currentText(),
                'model':self.model.text(),'delay':self.delay.currentData(),'rate':self.rate.currentData(),
                'channels':self.channels.currentData(),'mode':self.mode.currentText(),
                'frequency':self.frequency.value(),'volume':self.volume.value(),
                'before':self.before.value(),'after':self.after.value(),'words':self.words.toPlainText()}

    def restore(self,data):
        for name in ('input','output','mode'):
            combo=getattr(self,name);idx=combo.findText(str(data.get(name,'')))
            if idx>=0:combo.setCurrentIndex(idx)
        for name in ('delay','rate','channels'):
            combo=getattr(self,name);idx=combo.findData(data.get(name))
            if idx>=0:combo.setCurrentIndex(idx)
        for name in ('frequency','volume','before','after'):
            if name in data:getattr(self,name).setValue(int(data[name]))
        if 'model' in data:self.model.setText(str(data['model']))
        if 'words' in data:self.words.setPlainText(str(data['words']))

    def save(self):
        try:
            save_settings(self.root/'settings.json',self.values())
            self.message.setText(f'Settings saved. Event logs: {self.root}')
        except Exception as exc:self.message.setText(f'Could not save settings: {exc}')

    def lock(self,running):
        self.routing.setEnabled(not running);self.censor_group.setEnabled(not running)
        self.start_button.setEnabled(not running);self.save_button.setEnabled(not running)

    def start(self):
        if self.task or self.controller:return
        try:
            if self.input.currentData() is None or self.output.currentData() is None:
                raise ValueError('Choose both a microphone and output device.')
            model=self.model.text().strip()
            if not (Path(model)/'am'/'final.mdl').is_file():raise ValueError('Choose the extracted Vosk model folder (containing am/final.mdl).')
            audio=AudioSettings(self.input.currentData(),self.output.currentData(),sample_rate=self.rate.currentData(),
                                delay_ms=self.delay.currentData(),output_channels=self.channels.currentData())
            censor=CensorSettings(self.mode.currentText().lower(),self.frequency.value(),self.volume.value()/100,
                                   self.before.value(),self.after.value())
            dictionary=ProfanityDictionary(self.words.toPlainText().splitlines())
            controller=LiveController(audio,VoskDetector(model),dictionary,censor)
        except Exception as exc:
            self.status.setText('NOT STARTED');self.message.setText(str(exc));return
        self.lock(True);self.status.setText('LOADING LOCAL MODEL…');self.last_event=0;self.events.setRowCount(0)
        self.message.setText('Loading locally. Recognition errors can still miss words; test a local OBS recording before broadcasting.')
        def launch():
            try:
                controller.start();self.task_result=('started',controller)
            except Exception as exc:self.task_result=('error',str(exc))
        self.task=threading.Thread(target=launch,daemon=True);self.task.start()

    def stop(self):
        if self.task or not self.controller:return
        controller=self.controller;self.controller=None
        self.stop_button.setEnabled(False);self.status.setText('STOPPING…')
        def shutdown():
            try:controller.close();self.task_result=('stopped',None)
            except Exception as exc:self.task_result=('error',str(exc))
        self.task=threading.Thread(target=shutdown,daemon=True);self.task.start()

    def poll(self):
        if self.task_result is not None and self.task is not None and not self.task.is_alive():
            action,value=self.task_result;self.task_result=None;self.task=None
            if action=='started':self.controller=value;self.stop_button.setEnabled(True)
            else:
                self.lock(False);self.status.setText('STOPPED' if action=='stopped' else 'ERROR — OUTPUT STOPPED')
                if value:self.message.setText(str(value))
            if self.closing:
                if self.controller:self.stop()
                else:self.close()
        if not self.controller:return
        status=self.controller.snapshot();self.status.setText(status['state'])
        if time.monotonic()-self.last_log_time>=1:
            self.last_log_time=time.monotonic()
            self.logger.info(json.dumps({k:v for k,v in status.items() if k!='events'}))
        latency=status['detection_latency_ms'];p99=f"{latency['p99']:.0f} ms" if latency else '—'
        self.metrics.setText(f"Detected {status['detected']}  •  Muted {status['muted_ms']/1000:.1f} s  •  Queue {status['queue_depth']}  •  Headroom {status['headroom_ms']:.0f} ms  •  Detection p99 {p99}")
        for event in status['events']:
            if event['id']<=self.last_event:continue
            self.last_event=event['id'];masked=masked_event(event)
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
        if self.controller or self.task:
            self.closing=True;event.ignore()
            if self.controller and not self.task:self.stop()
            self.status.setText('STOPPING AUDIO BEFORE CLOSE…')
        else:event.accept()


def main():
    app=QApplication.instance() or QApplication(sys.argv)
    window=MainWindow();window.show()
    return app.exec()


if __name__=='__main__':raise SystemExit(main())
