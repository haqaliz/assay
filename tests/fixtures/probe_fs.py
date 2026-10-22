"""Attempt file operations and report what the kernel allowed.

Invoked as: probe_fs.py '<json spec>' where spec is a list of
{"name": str, "path": str, "mode": "read"|"write"}.
Prints one `assay-denial:` line per denied operation and a RESULT json line.
"""

import json
import os
import socket
import sys


def attempt(item, results):
    name, path, mode = item["name"], item["path"], item["mode"]
    try:
        if mode == "write":
            with open(path, "w") as fh:
                fh.write("x")
        elif mode == "list":
            os.listdir(path)
        else:
            with open(path, "rb") as fh:
                fh.read(16)
        results[name] = "ALLOWED"
    except PermissionError as exc:
        results[name] = "DENIED"
        kind = "file-write" if mode == "write" else "file-read"
        print(f"assay-denial: {kind} {path} {exc}", flush=True)
    except Exception as exc:  # noqa: BLE001 - the probe reports, it does not judge
        results[name] = type(exc).__name__


if __name__ == "__main__":
    results = {}
    for item in json.loads(sys.argv[1]):
        attempt(item, results)
    print("RESULT " + json.dumps(results))
