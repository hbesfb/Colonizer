# webdaemon/monitor_k8s.py

import threading
import os
from datetime import datetime
from webdaemon.database import db
from sqlalchemy import text
from settings import settings
import hwlayer.client
import logging

log = logging.getLogger("ServiceMonitor")

class K8sServiceMonitor(threading.Thread):
    """
    Periodic service monitor used when running inside Kubernetes.
    This monitor:
    - checks SQL, camera (via ZMQ to the Pi), and storage (PVC)
    - avoids unnecessary checks when the UI is idle
    - runs as a dedicated background thread with a fixed interval
    - logs transitions (eg SQL OK to FAIL, camera online to offline, storage OK to FAIL)
    - handles offline Pi gracefully (sets camera=False and sends a log when state changes)
    """
    def __init__(self, interval=30, sleeptimer=600):
        super().__init__(daemon=True)
        self.interval = interval
        self.sleeptimer = sleeptimer
        self._app = None
        self._status = {"sql": False, "camera": False, "storage": False}
        self._lastaccess = datetime.now()
        self._lastupdate = datetime.now()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    @property
    def status(self):
        """Return cached status and update last-access timestamp."""
        self._lastaccess = datetime.now()
        with self._lock:
            return self._status.copy()

    def init(self, app):
        """Initialize and start the timer."""
        self._app = app
        log.info("K8sServiceMonitor: initializing and performing first check")
        self.check_services()
        self.start()

    def run(self):
        """Timer loop."""
        while not self._stop_event.wait(self.interval):
            try:
                self.check_services()
            except Exception as e:
                log.error(f"K8sServiceMonitor error: {e}")

    def check_services(self):
        now = datetime.now()
        # Skip service checks when the UI has been inactive for a while.
        # This avoids unnecessary SQL/ZMQ/storage polling when no one is using the system.
        if (now - self._lastaccess).total_seconds() > self.sleeptimer:
            return

        # Check SQL status
        try:
            with self._app.app_context():
                db.session.execute(text("SELECT 1"))
            sql_status = True
        except Exception as e:
            log.debug(f"K8sServiceMonitor: SQL check failed: {e}")
            sql_status = False

        # Check camera (ZeroMQ round‑trip from the Kubernetes pod → to the Raspberry Pi → and back)
        # ie in k8s client.py sends JSON to the Pi (socket.send_json({"CMD": "ready"})) and expects a JSON response {"msg": True/False} from the Pi
        try:
            camera_status = hwlayer.client.is_ready()
        except Exception as e:
            log.debug(f"K8sServiceMonitor: Camera/Pi check failed: {e}")
            camera_status = False

        # Check storage status (PVC)
        storage_status = False
        try:
            mountpoint = settings["general"].get("mountpoint", "/mnt/data")
            savepath = settings["general"].get("savepath", "/mnt/data/Data/Colonizer/")
            if os.path.ismount(mountpoint):
                storage_status = True
            # Check if savepath exists and is writable
            elif os.path.exists(savepath) and os.access(savepath, os.W_OK):
                storage_status = True
        except Exception as e:
            log.warning(f"K8sServiceMonitor: Storage check failed: {e}")

        # --- Update status with transition logging ---
        new_status = {
            "sql": sql_status,
            "camera": camera_status,
            "storage": storage_status
        }
        with self._lock:
            old_status = self._status.copy()
            if new_status != old_status:
                log.info(
                    f"K8sServiceMonitor: status changed | "
                    f"SQL: {old_status['sql']} to {new_status['sql']}, "
                    f"Camera: {old_status['camera']} to {new_status['camera']}, "
                    f"Storage: {old_status['storage']} to {new_status['storage']}"
                )

            self._status = new_status
            self._lastupdate = now