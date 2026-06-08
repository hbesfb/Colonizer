# in K8s deployment client.py is the kubernetes‑side REQ client ie
    # Connects to the Pi using HARDWARE_ADDR=tcp://XXX.XXX.X.XXX:3117 where `XXX.XXX.X.XXX` 
        # is the ip that will have been assigned to the raspberry Pi
    # sends requests to the Pi server.py REQ-REP server to capture images
    # receive captured images from the Pi server.py

# In local development, it defaults to using HARDWARE_ADDR=ipc:///tmp/settleplate_hw 
# to connect to the local Pi server.
import os
import re
import zmq
import numpy as np
from typing import Tuple
import threading

# Use one shared ZMQ context for the whole process. Even if the app currently
# runs with one thread, Flask/Gunicorn or libraries may create additional
# threads. Context.instance() is safe in all cases and avoids creating
# multiple separate ZMQ contexts by accident.
_context = zmq.Context.instance()


# Each thread gets its own ZMQ socket. ZMQ sockets cannot be shared between
# threads, so using thread-local storage ensures each thread has a separate
# REQ socket and avoids message ordering problems.
_thread_local = threading.local()

def _resolve_address():
    """
    Determine the correct ZMQ address based on environment variables.
    HARDWARE_ADDR in k8s is the full tcp://host:port
    """
    # Determine transport type from environment variable, default to legacy "ipc" address
    addr = os.environ.get("HARDWARE_ADDR", "ipc:///tmp/settleplate_hw")

    # Accept only valid ZMQ transport prefixes ("ipc://" or "tcp://") at the start of the address
    if re.match(r"^(ipc|tcp)://.+", addr):
        return addr
    else:
        raise ValueError(f"Invalid HARDWARE_ADDR={addr}, transport unknown")

def _get_socket():
    """
    Return the ZMQ REQ socket for the current thread.

    ZMQ sockets cannot be shared between threads, so we store the socket in
    thread-local storage. This means:

    - If the thread has no socket yet, create one.
    - If the thread already has a socket, reuse it.
    - If the socket fails, set it to None so it will be recreated on the next call.

    This ensures each thread always uses its own safe REQ socket.
    """
    if not hasattr(_thread_local, "socket") or _thread_local.socket is None:
        s = _context.socket(zmq.REQ)
        s.setsockopt(zmq.LINGER, 0)
        s.RCVTIMEO = 5000 # ms
        s.connect(_resolve_address())
        _thread_local.socket = s
    return _thread_local.socket

def start_socket() -> bool:
   """Initialize the ZMQ REQ socket for the current thread."""
   try:
       _get_socket()
       return True
   except Exception:
       return False

def capture_image(capture_settings={}) -> Tuple[bool, np.ndarray]:
    """
    Request an image from the hardware server.
    Returns (success, image_or_error_message)
    """

    socket = _get_socket()

    # request image
    request = capture_settings.copy()
    request['CMD'] = 'capture'

    try:
        # send
        socket.send_json(request)
        # wait for data
        response = socket.recv_json()
        if 'error' in response:
            return False, response['error']
        else:
            buffer = socket.recv(copy=True)
            image = np.frombuffer(buffer, dtype=response['dtype'])
            image = image.reshape(response['shape'])
            return True, image
    except Exception as e:
        _thread_local.socket = None # reset only this thread’s socket, not global 
        return False, f"ZMQ error: {e}"

def is_ready():
    """ Check if hardware server is ready."""
    socket = _get_socket()
    request = {'CMD': 'ready'}
    try:
        socket.send_json(request)
        response = socket.recv_json()
        return response.get("msg", False)
    except Exception as e:
        _thread_local.socket = None # reset only this thread’s socket, not global
        return False