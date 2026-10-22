"""Attempt loopback connections to two ports and report what the kernel allowed."""

import socket
import sys

for label, port in (("ALLOWED", sys.argv[1]), ("DENIED", sys.argv[2])):
    try:
        sock = socket.create_connection(("127.0.0.1", int(port)), timeout=2)
        sock.close()
        print(f"{label}_PORT: CONNECTED", flush=True)
    except PermissionError as exc:
        print(f"{label}_PORT: DENIED", flush=True)
        print(f"assay-denial: network 127.0.0.1:{port} {exc}", flush=True)
    except Exception as exc:  # noqa: BLE001 - the probe reports, it does not judge
        print(f"{label}_PORT: {type(exc).__name__} {exc}", flush=True)
