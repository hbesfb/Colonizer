import os
import zmq
import numpy as np
from typing import Tuple
import threading

_context = zmq.Context.instance()
_thread_local = threading.local()

def _resolve_address():
    """
    Determine the correct ZMQ address based on environment variables.

    HARDWARE_TRANSPORT = "ipc" or "tcp"
    HARDWARE_ADDR      = full tcp://host:port (for tcp mode)
    """
    # Determine transport type from environment variable, default to "ipc"
    transport = os.environ.get("HARDWARE_TRANSPORT", "ipc")
    if transport == "ipc": # running app locally, Pi runs both app + daemon; use IPC transport
        return "ipc:///tmp/settleplate_hw"

    if transport == "tcp": # running app in k8s, use TCP transport - HARDWARE_ADDR contains full address
        addr = os.environ.get("HARDWARE_ADDR")
        return addr
    
    raise ValueError(f"Unknown HARDWARE_TRANSPORT={transport}")

def _get_socket():
    """Return a thread-local REQ socket, creating it if needed."""
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