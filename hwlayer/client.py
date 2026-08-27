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
import logging

log = logging.getLogger("hwlayer.client")

# Use one shared ZMQ context for the whole process. 
# Context.instance() returns a shared singleton context and 
# prevents accidental creation of multiple independent contexts.
_context = zmq.Context.instance()

# ZMQ sockets are not thread-safe; give each thread its own ZMQ socket.
# Thread-local storage ensures each thread has a separate
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

# resolve the separate status-socket address, mirroring
# _resolve_address(). Falls back to IPC when not specified.
def _resolve_status_address():
    addr = os.environ.get("HARDWARE_STATUS_ADDR", "ipc:///tmp/settleplate_hw_status")
    log.debug(f"STATUS ADDRESS = {addr}")
    if re.match(r"^(ipc|tcp)://.+", addr):
        return addr
    else:
        raise ValueError(f"Invalid HARDWARE_STATUS_ADDR={addr}, transport unknown")

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
        s.RCVTIMEO = 35000 # ms -- must exceed real capture time (measured 11-26s)
        s.SNDTIMEO = 5000   # ms -- send should be instant; if this timeout here means a broken socket
        s.connect(_resolve_address())
        _thread_local.socket = s
    return _thread_local.socket

# separate socket for ready/storage, now backed by its own
# thread+port on the Pi (see server.py) that's never blocked behind a
# capture. Short timeout is appropriate again since there's no more
# structural reason for these calls to be slow — a timeout here now
# means the Pi really is unreachable/dead, not just busy.
def _get_status_socket():
    if not hasattr(_thread_local, "status_socket") or _thread_local.status_socket is None:
        s = _context.socket(zmq.REQ)
        s.setsockopt(zmq.LINGER, 0)
        s.RCVTIMEO = 5000  # ms
        s.SNDTIMEO = 5000  # ms
        s.connect(_resolve_status_address())
        _thread_local.status_socket = s
    return _thread_local.status_socket


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

    If anything goes wrong, throw away this thread's REQ socket. 
    The next request (call to capture_image) will automatically create a clean replacement socket
    at socket = _get_socket()
    """
    try:
        socket = _get_socket()

        # request image
        request = capture_settings.copy()
        request['CMD'] = 'capture'

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
        try:
            _thread_local.socket.close(linger=0)
        except Exception:
            pass

        # close() shuts down the socket, but the thread-local variable still points
        # to the closed socket. Setting it to None forces _get_socket() to create a
        # fresh socket on the next request.
        _thread_local.socket = None
        return False, f"ZMQ error: {e}"

def send(payload):
    """
    Send a JSON RPC command to the Pi hardware daemon and return (success, response_dict).
    Supports multi-part messages when jpeg_bytes is included.
    """
    try:
        socket = _get_socket()
        payload = dict(payload)

        #extract jpeg_bytes if present
        jpeg_bytes = payload.pop('jpeg_bytes', None)

        # If there is no image data to send eg if payload = { "CMD": "ready"}
        if jpeg_bytes is None:
            socket.send_json(payload) # normal JSON-only RPC
        else:
            # First frame of a multipart message. SNDMORE tells ZMQ that additional 
            # frames belonging to the same message will be sent next.
            socket.send_json(payload, flags=zmq.SNDMORE)

            # Second and final frame containing the raw JPEG bytes.
            socket.send(jpeg_bytes, copy=True) # send the raw JPEG bytes.

        # wait for reply from server.
        # This blocks until server sends a reply ("ok", or "error")
        # or times out if the server does not reply (within s.RCVTIMEO or s.RCVTIMEO, depending on the socket)
        reply = socket.recv_json()

        return True, reply

    except Exception as e:
        # reset only this thread’s socket
        try:
            _thread_local.socket.close(linger=0)
        except Exception:
            pass
        _thread_local.socket = None
        return False, {'msg': 'error', 'error': str(e)}

def is_ready():
    """
    Returns a bolean that indicates if hardware server is ready.
    Uses the dedicated status socket, so it's answered immediately 
    instead of queueing behind captures.

    Returns True if response = {"msg": True},
    else it returns False if:
        response = {"msg": False}
        response = {"error": "camera unavailable"}
        Comminicatin fails eg ZMQ error (exception part)
    
    Returning False simply means the Pi is not currently usable, 
    either because it isn't ready or because we couldn't successfully verify that it is ready
    """
    try:
        socket = _get_status_socket()
        request = {'CMD': 'ready'}
        socket.send_json(request)
        response = socket.recv_json()
        return response.get("msg", False)
    except Exception as e:
        try:
            _thread_local.status_socket.close(linger=0)
        except Exception:
            pass
        _thread_local.status_socket = None
        return False

def pi_mounted_storage_ok():
    """
    Check whether the server's configured storage location available and writable
    by sendind a 'storage' request to the hardware daemon's dedicated status socket and returns
    the daemon's response

    Uses the dedicated status socket so the request is not delayed by
    long-running image capture operations
    """

    # obtain the thread's dedicated REQ socket connected to the server's status endpoint.
    socket = _get_status_socket()
    try:
        socket.send_json({'CMD': 'storage'}) # send a storage request to server
        response = socket.recv_json() # wait for servers response or timeouts
        return response.get("msg", False)
    except Exception as e:
        # in all other failures (eg ZMQ error, lost network connection)
        try:
            _thread_local.status_socket.close(linger=0)
        except Exception:
            pass
        _thread_local.status_socket = None
        return False