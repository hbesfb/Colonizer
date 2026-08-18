# Colonizer
- Colonizer DB has only a single entity SETTLEPLATE 
- A location is a particular point that will be sampled (eg a desk, table or floor)
- Colonizer allows only for one settleplate registration for each each location within a batch
- Registrations and scan results are stored as separate SETTLEPLATE records and are linked by barcode. A registration record has Counts = -1, while scan records have Counts >= 0.
- Normally locations are not resampled, but if one feels inclined to do so, then they have the option to either use a plate from a another batch OR delete the previous sample/settleplate that exists for this location from the DB
- A registering user has a "grace period" within which they can edit or delete plates they have registered?? TODO Confirm this
- The first scanned plate of a new batch is auto registered to belong to location PositiveTest by specifying it in the config file. (The default is first plate of batch == positive plate). In the lab, this plate is then incubated in a heated chamber for 3 days, after which it can be scanned to record its colony counts
- A new batch of plates has only one postive-test plate
- Registering of the positive test is not blocking; other plates of the same batch can be registered even if the colonies of the exisitng positive test plate have not been counted. During normal lab rutines, the positive test plates are scanned way ahead in good time before plates of the batches in current use are depleted.

## Here is how the lab rutine is envision to work with Colonizer:
### Phase 1 - Registration via Colonizer UI: 
- Scan settleplate(s) to register them in the DB. Information captured is:
    - Settleplate batch , serial number, and expiry date.
    - Location - The point that will be sampled/monitored
    - Default Counts - This will be auto asigned to -1 to indicate "registered but not scanned."

### Phase 2 - Capture/sampling: Manual process 
- The registered plates are placed in their corresponding registered locations.

### Phase 3 - Incubation: Manual process - plates moved to incubator.
- The plates are incubated in an incubator

### Phase 4 - Scanning via Colonizer UI:
- This is done contineously during the incubation period at the scanning station. This uses a raspberry Pi and camera
- Plate barcode is scanned using a barcode scanner to retrieve its details from the DB
- User then places the plate into the automatic scanner and uses the colonixer UI to auto detect colony count on the plate
- User then confirms/adjusts counts and saves to the db. Details captured are:
    - operator id (ie person scanning)
    - colony count on the plate, image of plate and timestamp upon saving.
A new DB row is created with the above details and same barcode as existed previously
TODO test to see what happens if user adjusts counts to say -2 instead of a number greater than -1

## Deployment Modes

Colonizer service should supports two distinct deployment modes, the mode depends on where the main application runs.
Both modes share the same repository/codebase but differ in what components run locally on the Pi.
Here is a high‑level overview of each mode and what they install

### Deployment Mode 1: Pi Runs App + Hardware (Full Standalone Mode)
This is the original mode the service was written to support. In this mode, a Raspberry Pi runs the entire Colonizer stack, including:
- Colonizer web application (Gunicorn)
- Colonizer hardware daemon (hwlayer.server)
- Nginx (reverse proxy)
- Redis
- Supervisor (process manager)
- Watchdog (system health monitor)
- FreeTDS (SQL Server connectivity)
- Static assets (Bootstrap, jQuery, FontAwesome, TensorFlow.js, JSONEditor)
- A repair script

This mode is ideal when:
- You want a self‑contained device that runs everything locally
- You are not using Kubernetes
- The Pi must operate independently

### Installer for the Full Standalone Mode (This is a WIP for the script and documentation)
`Pi_running_both_app_and_hardware/install_both_app_and_hardware.sh`

**Key features**
- Clones the repo into /app/Colonizer
- Creates a Python virtual environment
- Installs all system dependencies
- Installs Supervisor configs for app + hardware
- Installs watchdog + repair.sh
- Sets SETTLEPLATE_CONFIG=production via Supervisor
- Starts all services automatically

**How services are managed**
- Supervisor manages:
    - colonizer-app (Gunicorn)
    - colonizer-hw (hardware daemon)
- Systemd manages:
    - nginx
    - redis
    - watchdog

This mode gives an all‑in‑one deployment.
For more details check the installer and readme at `./Pi_running_both_app_and_hardware`
---

### Deployment Mode 2: Pi Runs Hardware Only (App Runs in Kubernetes)
In this mode, the Raspberry Pi runs only the hardware daemon, while the main Colonizer application runs in Kubernetes.
The Pi is responsible for:
- Camera hardware control and Image capture
- Responding to ZeroMQ commands from the K8s app

This mode is ideal when:
- You want to deploy Colonizer app in Kubernetes
- The Pi should act only as a hardware endpoint
- You want minimal dependencies on the Pi

### Installer for the Hardware Only Mode
`Pi_running_only_hardware/install_hardware_only.sh`

**key features**
- Clones the repo into /app/Colonizer
- Creates a minimal Python virtual environment
- Installs only hardware‑specific dependencies
- Installs Supervisor config for the hardware daemon
- Enforces HARDWARE_TRANSPORT=tcp
- Starts the hardware daemon at boot via Supervisor

**How services are managed**
- On the Pi, supervisor manages colonizer-hw
- The web service is deployed and managed in k8s

For more details check the installer and readme at `Pi_files/Pi_running_only_hardware`