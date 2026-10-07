"""One desktop instance per user; subsequent launches reveal its window."""
import hashlib
import sys
from PySide6.QtCore import QLockFile
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox
from .settings import data_directory


def run(state_directory=None):
    from .main_window import MainWindow
    app=QApplication.instance() or QApplication(sys.argv)
    identity=data_directory()
    name='StreamGuard-'+hashlib.sha256(str(identity).casefold().encode()).hexdigest()[:16]
    lock=QLockFile(str(identity/'application.lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        socket=QLocalSocket();socket.connectToServer(name)
        if socket.waitForConnected(1500):
            socket.write(b'show');socket.waitForBytesWritten(1000);socket.disconnectFromServer()
        else:
            QMessageBox.information(None,'StreamGuard is already running',
                'StreamGuard is already starting or running. Use its existing window; check the taskbar.')
        return 0
    server=QLocalServer()
    QLocalServer.removeServer(name)
    if not server.listen(name):
        lock.unlock()
        QMessageBox.critical(None,'Could not start StreamGuard',server.errorString())
        return 1
    window=MainWindow(state_directory)
    def reveal():
        while server.hasPendingConnections():
            socket=server.nextPendingConnection();socket.disconnectFromServer();socket.deleteLater()
        window.showNormal();window.raise_();window.activateWindow()
    server.newConnection.connect(reveal)
    window.show()
    try:return app.exec()
    finally:server.close();lock.unlock()
