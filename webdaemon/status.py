import threading
import os
from datetime import datetime
from webdaemon.database import db
from sqlalchemy import text
from settings import settings
import hwlayer.client
import logging

log = logging.getLogger("ServiceMonitor")


class ServiceMonitor(threading.Thread):
    """
    Background thread that periodically checks:
    - SQL
    - Camera (Pi via ZMQ)
    - Storage (local mount or PVC)
    Handles offline Pi gracefully.
    """

    def __init__(self, interval: int = 30, sleeptimer: int = 600):
        super().__init__(daemon=True)
        self.interval = interval
        self.sleeptimer = sleeptimer
        self._app = None
        self._status = {
            "sql": False,
            "camera": False,
            "storage": False,
        }
        self._lastaccess = datetime.now()
        self._lastupdate = datetime.now()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    @property
    def status(self):
        """Return last cached status without blocking."""
        self._lastaccess = datetime.now()
        with self._lock:
            return self._status.copy()

    def init(self, app):
        """Start monitoring thread."""
        self._app = app
        log.info("ServiceMonitor: initializing and performing first check")
        self.check_services()
        self.start()

    def run(self):
        """Background loop to check services."""
        while not self._stop_event.wait(self.interval):
            try:
                self.check_services()
            except Exception as e:
                log.error(f"ServiceMonitor: check_services error: {e}")

    def check_services(self):
        now = datetime.now()

        # Skip if inactive eg. the UI  is not being accessed, no API calls to /status, the system is idle.
        if (now - self._lastaccess).total_seconds() > self.sleeptimer:
            log.debug("ServiceMonitor: skipping checks (inactive)")
            return

        # --- SQL ---
        sql_status = False
        try:
            with self._app.app_context():
                db.session.execute(text("SELECT 1"))
            sql_status = True
        except Exception as e:
            log.warning(f"ServiceMonitor: SQL check failed: {e}")

        # --- Camera (Pi via ZMQ) ---
        camera_status = False
        try:
            camera_status = hwlayer.client.is_ready()
        except Exception as e:
            log.debug(f"ServiceMonitor: Camera/Pi check failed (may be offline): {e}")

        # --- Storage check (PVC or local mount) ---
        storage_status = False
        try:
            mountpoint = settings['general'].get('mountpoint', '/mnt/data')
            savepath = settings['general'].get('savepath', '/mnt/data/Data/Colonizer/')

            if os.path.ismount(mountpoint) or os.path.ismount(os.path.dirname(savepath)):
                storage_status = True
            elif os.path.exists(savepath) and os.access(savepath, os.W_OK):
                storage_status = True
        except Exception as e:
            log.warning(f"ServiceMonitor: Image storage check failed: {e}")

        # --- Update status safely, only one thread at a time can read or write _status ---
        with self._lock:
            old = self._status.copy()
            new = {
                "sql": sql_status,
                "camera": camera_status,
                "storage": storage_status,
            }

            if new != old: # log showing “old value → new value”
                log.info(
                    f"ServiceMonitor: status changed | "
                    f"SQL: {old['sql']}→{new['sql']}, "
                    f"Camera: {old['camera']}→{new['camera']}, "
                    f"Storage: {old['storage']}→{new['storage']}"
                )

            self._status = new
            self._lastupdate = now

# Create one servicemonitor instance that is shared in entire application
servicemonitor = ServiceMonitor()