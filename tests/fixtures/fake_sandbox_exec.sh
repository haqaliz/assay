#!/bin/sh
# Test-only stand-in for sandbox-exec: drop "-p <profile>" and exec the rest.
shift 2
exec "$@"
