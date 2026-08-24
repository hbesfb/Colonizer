# Colonizer Hardware Node
This document describes how to set up a Raspberry Pi (ie Colony Counter computer with a Camera)
as a hardware‑only node for the Colonizer application when the main application (Colonizer) runs in Kubernetes.

In this mode, the Pi is responsible only for:
- controlling the camera
- controlling illumination hardware
- capturing images
- responding to ZMQ commands from the K8s app

The Pi does not run the full Colonizer web application, Nginx, Gunicorn, Redis, or PostgreSQL.
This mode is intentionally lightweight and uses Supervisor to run the hardware daemon.
---

## Overview
This setup will install the following:

- A Python hardware daemon (hwlayer.server, located at `./hwlayer/server.py` in the repo)
- A Supervisor program that starts and restarts the daemon automatically
- A minimal set of system packages (Python, libcamera, git, etc.)
- A virtual environment containing only hardware‑specific Python dependencies
- Weekly logrotate configs for the hardware daemon and Supervisor's own log
The hardware daemon communicates with the Kubernetes application using ZeroMQ over `TCP`
---
### Prerequisites
- Raspberry Pi running Debian GNU/Linux 13 (Trixie). This is where Colonizer hardware node will be setup
- A Raspberry Pi camera module supported by `picamera2`. This will be connected to the Pi CSI ribbon cable
- Internet access on the Pi (to clone the repo and install packages)
- SSH access to the Pi

---
### What the Installer Does
Running `./Pi_running_only_hardware/install_all.sh` will:
- Create a dedicated user (colonizer) and add the user to the `gpio` and `video groups`
- Install required system packages
- Create a Python virtual environment and install hardware specific dependencies
- The installer always deletes and recreates the virtual environment to ensure deterministic behavior and avoid stale or corrupted packages.
- Install the Supervisor program config (HARDWARE_TRANSPORT and SETTLEPLATE_CONFIG are set within it)
- Enable and start Supervisor
- Install logrotate configs (colonizer-hw, colonizer-supervisor)

After installation, the Pi will:
- start the hardware daemon at boot
- restart the hardware daemon automatically if it crashes (managed by Supervisor)
- rotate logs weekly (via logrotate, triggered by the systemd logrotate.timer)

---

### Initial preparations before installation:
Before running the installer script ensure the following files and directories exist on the Pi.
#### On the dev machine
We will be copying over the needed files from the repository parent dir to a writable location on the Pi 
- On hp06 run: 
	```
	scp -r Pi_files/ admin@plateleser.medtek.hbe.med.nvsl.no:/home/admin
	scp settings.py admin@plateleser.medtek.hbe.med.nvsl.no:/home/admin/Pi_files

	# copy files while excluding unneeded
	rsync -avz --exclude='config/default.json' config admin@plateleser.medtek.hbe.med.nvsl.no:/home/admin/Pi_files
	rsync -avz --exclude='hwlayer/client.py' hwlayer admin@plateleser.medtek.hbe.med.nvsl.no:/home/admin/Pi_files

#### On the Pi
- SSh to the Pi: `admin@plateleser.medtek.hbe.med.nvsl.no`
- The application root directory `/app/Colonizer` should already exist on the Pi. If not create it
- Move the copied files to `app/Colonizer`: `sudo cp -r Pi_files/. /app/Colonizer`

To know more about the use/content of these files checkout the section #About the files needed for Pi installation

## Installation Instructions
Run the installer: `sudo bash /app/Colonizer/Pi_running_only_hardware/install_all.sh`
After installation, the status of the hardware daemon will be printed automatically, but you can manually check if the hardware daemon is running at any time: `supervisorctl status colonizer-hw`
---

## Managing the Colonizer Hardware Service
Supervisor manages the hardware daemon
```bash
sudo supervisorctl start colonizer-hw      # start the hardware daemon
sudo supervisorctl stop colonizer-hw       # stop
sudo supervisorctl restart colonizer-hw    # restart
```
View logs:
```bash
	tail -f /var/log/colonizer-hw.out.log
	tail -f /var/log/colonizer-hw.err.log
	sudo tail -n 200 /var/log/colonizer-hw.err.log
```
---

### Managing log file accumulation on Pi
Log rotation config files exist in order to prevent the  SD-card from filling up.
To check on them we can run:
```
sudo logrotate -d /etc/logrotate.d/colonizer-hw   # dry-run, shows what it *would* do
sudo logrotate -d /etc/logrotate.d/colonizer-supervisor # dry-run, shows what it *would* do
sudo logrotate -f /etc/logrotate.d/colonizer-hw   # force a rotation right now to test
systemctl status logrotate.timer                   # confirm the timer is enabled/active
```

### Directory Layout
After installation we should have:

```
/app/Colonizer/
	venv/                                   # Python virtual environment
	hwlayer/                                # Hardware daemon code
/etc/supervisor/conf.d/colonizer_hw.conf    # Supervisor config
/etc/logrotate.d/colonizer-hw               # Logrotate config (app logs)
/etc/logrotate.d/colonizer-supervisor       # Logrotate config (Supervisor log)
```

---

### What This Setup Does NOT Include
This Pi mode does not run:
- Nginx
- Gunicorn
- Redis
- PostgreSQL
- The Colonizer web UI
Components needed for Colonizer app to be accessible online are all installed in Kubernetes.

---

## Environment Variables
These are hardcoded in `Pi_files/install/etc/supervisor/conf.d/colonizer_hw.conf` and the installer copies this file to `/etc/supervisor/conf.d/`
- `HARDWARE_TRANSPORT=tcp`. This makes the daemon bind to `tcp://*:3117` and `tcp://*:3118`. It waits for incoming ZMQ commands on these ports.
- `SETTLEPLATE_CONFIG="kubernetes"`.  Selects `kubernetes` as the settle-plate configuration used by the hardware daemon.

## Troubleshooting
### During installation.
#### Installation completes with error
```
Supervisor status:
colonizer-hw                     FATAL     Exited too quickly (process log may have details)
```
- Check out hints in the error and log files eg:
```
admin@colonizer:~ $ tail /var/log/colonizer-hw.err.log 
    from settings import settings
ModuleNotFoundError: No module named 'settings'
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/app/Colonizer/hwlayer/server.py", line 10, in <module>
    from hwlayer.illumination import illumination
  File "/app/Colonizer/hwlayer/illumination.py", line 4, in <module>
    from settings import settings
ModuleNotFoundError: No module named 'settings'
```
Hint: Ensure that settings.py was copied over to the Pi at `/app/Colonizer`

#### errors downloading stuff on Pi
ensure you have the  file `cat /etc/apt/apt.conf.d/05proxy` with the following info:
```
Acquire::https::proxy "http://proxy.yourOrgProxy:port";
Acquire::http::proxy "http://proxy.yourOrgProxy:port";
Acquire::ftp::proxy "http://proxy.yourOrgProxy:port";
```

ensure the proxy is also specified in this file as shown below.
```
cat /etc/pip.config
[global]
extra-index-url=https://www.piwheels.org/simple
proxy = http://your-proxy-host:port
```
If its missing append it (-a) using: `echo "proxy = http://yourOrgProxy:port" | sudo tee -a /etc/pip.conf`

Troubleshooting tip: In case of wierd errors even after copying over new files to the Pi, remove old Python bytecode cache: `sudo find /app/Colonizer -name "*.pyc" -delete`

### During operation
#### Camera not detected in the UI
Some physical checks on the Pi
- Check that the ribbon cable is properly seated
- The Pi is powered (Currently it uses PoE, ensure all cables are attached)

####  Daemon not responding
Signs: the K8s app cannot connect to the Pi — errors in UI that camera is offline, ZMQ connection refused in K8s logs etc.
SSh to the Pi and do the following checks
```bash
# Check Supervisor status
supervisorctl status colonizer-hw

# View error log
tail -f /var/log/colonizer-hw.err.log

# Check if the ZMQ sockets are bound (3117=commands, 3118=status)
ss -ltnp | grep -E '3117|3118'

# Check if the process is running
ps aux | grep hwlayer.server # if you see nothing the daemon is not active
```
#### Failing to copy images from Pi to remote dev (eg hp06)
Ssh to Pi and change permissions so all can read on the Pi: `sudo chmod a+rx /mnt/data/Data/Colonizer`
then try copying again. On hp06: `scp admin@10.85.66.116:/mnt/data/Data/Colonizer/admin-20260820_091411-598f3524.jpg .`
---

#### UI icons red (Pi and Pi storage show offline)
Usually means the status port isn't bound or isn't reachable.
```bash
# Check the status port specifically
ss -ltnp | grep 3118

# Confirm colonizer-hw is actually running
supervisorctl status colonizer-hw
```
## Uninstalling
To remove the hardware daemon:
```
sudo supervisorctl stop colonizer-hw
sudo rm /etc/supervisor/conf.d/colonizer_hw.conf
sudo systemctl restart supervisor
```
```bash
sudo supervisorctl stop colonizer-hw
sudo rm /etc/supervisor/conf.d/colonizer_hw.conf
sudo systemctl restart supervisor

# Remove application files
sudo rm -rf /app/Colonizer

# Remove log rotation configs
sudo rm -f /etc/logrotate.d/colonizer-hw
sudo rm -f /etc/logrotate.d/colonizer-supervisor

# Remove service user
sudo userdel -r colonizer
```

## About the files needed for Pi installation
- `Pi_files/install/etc/supervisor/conf.d/colonizer_hw.conf: The supervisor config file used by the hardware daemon. During installation this file is coppied over to `/app/Colonizer/install/etc/supervisor/conf.d/colonizer_hw.conf`on the Pi.
- Logrotation files. these are expected to exist and are used to ensure log files donnot consume all the space on the Pi:
	- `/app/Colonizer/install/maintenance/colonizer-hw` — logrotate config for the hardware daemon
	- `/app/Colonizer/install/maintenance/colonizer-supervisor` — logrotate config for Supervisor's own log
- The file `settings.py` must also exist in at `/app/Colonizer`as its needed by the hardware daemon
- Python files in `/app/Colonizer/hwlayer/`. The hardware daemon is not a single file. It is a Python package containing multiple modules that must all exist for the daemon to run correctly under Supervisor.

The following files must exist inside /app/Colonizer/hwlayer/:
	```
	/app/Colonizer/hwlayer/
	__init__.py
    server.py          # main hardware daemon (ZeroMQ REP server)
    illumination.py    # LED ring / top-light control
    logging.py         # hwlayer-specific logging wrapper
    picamera.py        # picamera2 wrapper (exposure, WB, crop, capture)
    base.py            # shared utilities used by multiple modules
	ueyecamera.py
	```