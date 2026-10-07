"""Exercise the real Qt lock/socket protocol in two offscreen processes."""
import json,os,subprocess,sys,tempfile,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='streamguard-instance-') as folder:
    folder=Path(folder)
    helper=folder/'helper.py'
    helper.write_text("""import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMainWindow
from PySide6.QtCore import QTimer
import streamguard.ui.main_window as ui
from streamguard.ui.application import run
root=Path(sys.argv[1])
class Window(QMainWindow):
    def __init__(self,*args):
        super().__init__()
        with (root/'windows.txt').open('a') as out:out.write('created\\n')
    def showNormal(self):
        (root/'revealed.txt').write_text('yes')
        super().showNormal()
ui.MainWindow=Window
app=QApplication([])
QTimer.singleShot(7000,app.quit)
raise SystemExit(run(root/'state'))
""",encoding='utf-8')
    env=dict(os.environ,QT_QPA_PLATFORM='offscreen',LOCALAPPDATA=str(folder))
    first=subprocess.Popen([sys.executable,str(helper),str(folder)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+5
        while not (folder/'windows.txt').exists() and time.monotonic()<deadline:time.sleep(.05)
        assert (folder/'windows.txt').exists(),'First app did not become ready'
        second=subprocess.run([sys.executable,str(helper),str(folder)],env=env,capture_output=True,timeout=5)
        assert second.returncode==0,second.stderr.decode(errors='replace')
        deadline=time.monotonic()+2
        while not (folder/'revealed.txt').exists() and time.monotonic()<deadline:time.sleep(.05)
        assert (folder/'windows.txt').read_text().splitlines()==['created']
        assert (folder/'revealed.txt').exists(),'Second launch did not reveal the first window'
        out,err=first.communicate(timeout=10)
        assert first.returncode==0,err.decode(errors='replace')
    finally:
        if first.poll() is None:first.terminate();first.wait(timeout=5)
print(json.dumps({'instances_created':1,'second_launch':'revealed existing window','hardware_access':False}))
