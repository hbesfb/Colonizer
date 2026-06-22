from threading import Timer
from webdaemon.database import db
from sqlalchemy import text
from settings import settings
from datetime import datetime, timedelta
import os
import hwlayer.client

# ------------------------------------------------------------
# Local (Pi) monitor — original Timer-based implementation
# ------------------------------------------------------------

class LocalServiceMonitor(Timer):
    sleeptimer = 600
    interval = 30

    def __init__(self,):
        self._app = None
        self._status = {
            'sql': False,
            'camera': False,
            'storage': False
        }
        self._lastaccess = datetime.now()
        super().__init__(self.interval, self.check_services)
        self.daemon = True

    @property
    def status(self):
        self._lastaccess = datetime.now()
        if ((self._lastaccess - self._lastupdate) > timedelta(seconds=self.interval)):
            self.check_services()
        return self._status.copy()

    def init(self, app):
        self._app = app
        self.check_services()
        self.start()

    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)

    def check_services(self):
        if (datetime.now() - self._lastaccess) > timedelta(seconds=self.sleeptimer):
            return
        # check sql status
        try:
            with self._app.app_context():
                db.session.execute(text('SELECT 1'))
            self._status['sql'] = True
        except:
            self._status['sql'] = False

        # check camera status
        self._status['camera'] = hwlayer.client.is_ready()

        # check storage status
        self._status['storage'] = os.path.ismount(settings['general']['mountpoint'])

        # timestamp update
        self._lastupdate = datetime.now()

# ------------------------------------------------------------
# K8s monitor — imported only when needed
# # ------------------------------------------------------------
from .monitor_k8s import K8sServiceMonitor

# ------------------------------------------------------------
# Factory: choose monitor based on environment
# ------------------------------------------------------------
def running_in_k8s():
    return (
        os.environ.get("SETTLEPLATE_CONFIG") == "kubernetes"
        or "KUBERNETES_SERVICE_HOST" in os.environ  # var exists in k8s pods by default
    )


servicemonitor = K8sServiceMonitor() if running_in_k8s() else LocalServiceMonitor()