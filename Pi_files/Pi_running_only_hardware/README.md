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
Before running the installer script needed files and the application root directory must exist on the Pi. How to ensure this:
#### On the dev machine
We will be copying over the needed files from the repository parent dir to a writable location on the Pi 
- On hp06 run: 
	```
	scp -r Pi_files/ admin@plateleser.medtek.hbe.med.nvsl.no:/home/admin
	scp settings.py admin@plateleser.medtek.hbe.med.nvsl.no:/home/admin/Pi_files

	# copy files while excluding unneeded
	rsync -avz --exclude='config/default.json' config admin@plateleser.medtek.hbe.med.nvsl.no:/home/admin/Pi_files
	rsync -avz --exclude='hwlayer/client.py' hwlayer admin@plateleser.medtek.hbe.med.nvsl.no:/home/admin/Pi_files
	```

#### On the Pi
- SSh to the Pi: `admin@plateleser.medtek.hbe.med.nvsl.no`, provide the password when prompted
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

currently installed versions as of 09.November.2026 (together with indirect dependences that are not specied in reqts file or the .sh scripts):

```
admin@colonizer:~ $ /app/Colonizer/venv/bin/pip freeze
Adafruit-Blinka==10.1.0
adafruit-circuitpython-busdevice==5.2.17
adafruit-circuitpython-connectionmanager==3.1.8
adafruit-circuitpython-neopixel-spi==1.0.16
adafruit-circuitpython-pixelbuf==2.1.0
adafruit-circuitpython-requests==4.1.18
adafruit-circuitpython-typing==1.13.0
Adafruit-PlatformDetect==3.90.0
Adafruit_PureIO==1.1.12
apt-listchanges==4.8
arrow==1.3.0
attrs==25.3.0
autocommand==2.2.2
av==19.0.2
babel==2.17.0
bcrypt==4.2.0
binho-host-adapter==0.1.6
blinker==1.9.0
certifi==2025.1.31
chardet==5.2.0
charset-normalizer==3.4.2
cloud-init==25.2
colorzero==2.0
configobj==5.0.9
cryptography==43.0.0
distlib==0.3.9
distro==1.9.0
filelock==3.18.0
fqdn==1.5.1
gpiod==2.2.0
gpiozero==2.0.1
idna==3.10
inflect==7.3.1
isoduration==20.11.0
jaraco.context==6.0.1
jaraco.functools==4.1.0
Jinja2==3.1.6
jsonpatch==1.32
jsonpointer==2.4
jsonschema==4.19.2
jsonschema-specifications==2023.12.1
lgpio==0.2.2.0
libarchive-c==5.3
linkify-it-py==2.0.3
mariadb==1.1.12
markdown-it-py==3.0.0
MarkupSafe==2.1.5
mdurl==0.1.2
more-itertools==10.7.0
numpy==2.5.1
oauthlib==3.2.2
opencv==4.10.0
OpenEXR==3.5.3
packaging==25.0
picamera2==0.3.36
pidng==4.0.9
piexif==1.1.3
pillow==13.0.0
platformdirs==4.3.7
pycryptodomex==3.20.0
pyftdi==0.57.2
Pygments==2.18.0
PyJWT==2.10.1
pyodbc==5.2.0
pyserial==3.5
python-apt==3.0.0
python-dateutil==2.9.0
python-prctl==1.8.1
pyusb==1.3.1
PyYAML==6.0.2
pyzmq==27.1.0
referencing==0.36.2
requests==2.32.3
rfc3339-validator==0.1.4
rfc3986-validator==0.1.1
rfc3987==1.3.8
rich==13.9.4
rpds-py==0.21.0
rpi-keyboard-config==1.0
rpi-lgpio==0.6
simplejpeg==1.9.0
smbus2==0.4.3
spidev==3.6
ssh-import-id==5.10
supervisor==4.2.5
sysv_ipc==1.2.0
tqdm==4.70.1
typeguard==4.4.2
types-aiofiles==24.1
types-antlr4-python3-runtime==4.13
types-assertpy==1.1
types-atheris==2.3
types-aws-xray-sdk==2.14
types-beautifulsoup4==4.12
types-bleach==6.2
types-boltons==24.1
types-braintree==4.31
types-cachetools==5.5
types-caldav==1.3
types-capturer==3.0
types-cffi==1.16
types-chevron==0.14
types-click-default-group==1.2
types-click-spinner==0.1
types-colorama==0.4
types-commonmark==0.9
types-console-menu==0.8
types-corus==0.10
types-croniter==5.0.1
types-dateparser==1.2
types-decorator==5.1
types-defusedxml==0.7
types-Deprecated==1.2.15
types-docker==7.1
types-dockerfile-parse==2.0
types-docutils==0.21
types-editdistance==0.8
types-entrypoints==0.4
types-ExifRead==3.0
types-fanstatic==1.4
types-first==2.0
types-flake8==7.1
types-flake8-bugbear==24.12.12
types-flake8-builtins==2.5
types-flake8-docstrings==1.7
types-flake8-rst-docstrings==0.3
types-flake8-simplify==0.21
types-flake8-typing-imports==1.16
types-Flask-Cors==5.0
types-Flask-Migrate==4.0
types-Flask-SocketIO==5.4
types-fpdf2==2.8.2
types-gdb==15.0
types-gevent==24.11
types-google-cloud-ndb==2.3
types-greenlet==3.1
types-hdbcli==2.23
types-html5lib==1.1
types-httplib2==0.22
types-humanfriendly==10.0
types-hvac==2.3
types-ibm-db==3.2.4
types-icalendar==6.1
types-influxdb-client==1.45
types-inifile==0.4
types-JACK-Client==0.5
types-Jetson.GPIO==2.1
types-jmespath==1.0
types-jsonschema==4.23
types-jwcrypto==1.5
types-keyboard==0.13
types-ldap3==2.9
types-libsass==0.23
types-lupa==2.2
types-lzstring==1.0
types-m3u8==6.0
types-Markdown==3.7
types-mock==5.1
types-mypy-extensions==1.0
types-mysqlclient==2.2
types-nanoid==2.0.0
types-netaddr==1.3
types-netifaces==0.11
types-networkx==3.4.2
types-oauthlib==3.2
types-objgraph==3.6
types-olefile==0.47
types-openpyxl==3.1.5
types-opentracing==2.4
types-paramiko==3.5
types-parsimonious==0.10
types-passlib==1.7
types-passpy==1.0
types-peewee==3.17.8
types-pep8-naming==0.14
types-pexpect==4.9
types-pika-ts==1.3
types-polib==1.2
types-portpicker==1.6
types-protobuf==5.29.1
types-psutil==6.1
types-psycopg2==2.9.10
types-pyasn1==0.6
types-pyaudio==0.2
types-PyAutoGUI==0.9
types-pycocotools==2.0
types-pycurl==7.45.4
types-pyfarmhash==0.4
types-pyflakes==3.2
types-pygit2==1.15
types-Pygments==2.18
types-pyinstaller==6.11
types-pyjks==20.0
types-PyMySQL==1.1
types-pynput==1.7.7
types-pyOpenSSL==24.1
types-pyRFC3339==2.0.1
types-PyScreeze==1.0.1
types-pyserial==3.5
types-pysftp==0.2
types-pytest-lazy-fixture==0.6
types-python-crontab==3.2
types-python-datemath==3.0.1
types-python-dateutil==2.9
types-python-http-client==3.3.7
types-python-jenkins==1.8
types-python-jose==3.3
types-python-nmap==0.7
types-python-xlib==0.33
types-pytz==2024.2
types-pywin32==308
types-pyxdg==0.28
types-PyYAML==6.0
types-qrbill==1.1
types-qrcode==8.0
types-regex==2024.11.6
types-reportlab==4.2.5
types-requests==2.32
types-requests-oauthlib==2.0
types-retry==0.9
types-RPi.GPIO==0.7
types-s2clientprotocol==5
types-seaborn==0.13.2
types-Send2Trash==1.8
types-setuptools==75.6
types-shapely==2.0
types-simplejson==3.19
types-singledispatch==4.1
types-six==1.17
types-slumber==0.7
types-str2bool==1.1
types-tabulate==0.9
types-tensorflow==2.18.0
types-TgCrypto==1.2
types-toml==0.10
types-toposort==1.10
types-tqdm==4.67
types-translationstring==1.4
types-tree-sitter-languages==1.10
types-ttkthemes==3.2
types-ujson==5.10
types-unidiff==0.7
types-untangle==1.2
types-usersettings==1.1
types-uWSGI==2.0
types-vobject==0.9.9
types-waitress==3.0.1
types-WebOb==1.8
types-whatthepatch==1.0
types-workalendar==17.0
types-WTForms==3.2.1
types-wurlitzer==3.1
types-xdgenvpy==3.0
types-xmltodict==0.14
types-zstd==1.5
types-zxcvbn==4.4
typing_extensions==4.13.2
uc-micro-py==1.0.3
uritemplate==4.1.1
urllib3==2.3.0
videodev2==0.0.4
virtualenv==20.31.2
watchdog==6.0.0
webcolors==1.13
wheel==0.46.1
```