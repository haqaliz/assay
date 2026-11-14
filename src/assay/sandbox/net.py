"""Landlock + seccomp launcher for the Linux network allowlist.

The launcher is a self-contained Python program passed to ``python3 -c`` inside the jail. It
applies a Landlock TCP connect/bind allowlist and a seccomp rule that denies UDP/raw sockets, then
execs the real command. DNS is resolved by the parent (``Toolbox._http_argv`` passes ``--resolve``),
so the jail never needs UDP/53.

Requires Linux 6.7+ (Landlock ABI 4) and libseccomp. If either is missing, the launcher exits 126
with ``assay-launcher:`` on stderr; the backend turns that into ``SandboxFailed``, never a pass.
"""

from __future__ import annotations

from typing import Sequence

_TEMPLATE = r'''
import ctypes
import os
import sys

PORTS = __PORTS__

libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long

SYS_LANDLOCK_CREATE_RULESET = 444
SYS_LANDLOCK_ADD_RULE = 445
SYS_LANDLOCK_RESTRICT_SELF = 446
LANDLOCK_CREATE_RULESET_VERSION = 1
LANDLOCK_RULE_NET_PORT = 2
LANDLOCK_ACCESS_NET_BIND_TCP = 1 << 0
LANDLOCK_ACCESS_NET_CONNECT_TCP = 1 << 1

SCMP_ACT_ALLOW = 0x7FFF0000
SCMP_CMP_EQ = 4
SCMP_CMP_MASKED_EQ = 7
AF_INET = 2
AF_INET6 = 10
SOCK_DGRAM = 2
SOCK_RAW = 3
SOCK_TYPE_MASK = 0xF


class RulesetAttr(ctypes.Structure):
    _fields_ = [
        ("handled_access_fs", ctypes.c_uint64),
        ("handled_access_net", ctypes.c_uint64),
    ]


class NetPortAttr(ctypes.Structure):
    _fields_ = [("allowed_access", ctypes.c_uint64), ("port", ctypes.c_uint64)]


class ScmpArgCmp(ctypes.Structure):
    _fields_ = [
        ("arg", ctypes.c_uint),
        ("op", ctypes.c_int),
        ("datum_a", ctypes.c_uint64),
        ("datum_b", ctypes.c_uint64),
    ]


def die(message):
    sys.stderr.write("assay-launcher: " + message + "\n")
    sys.stderr.flush()
    os._exit(126)


def landlock():
    abi = libc.syscall(
        SYS_LANDLOCK_CREATE_RULESET, None, 0, LANDLOCK_CREATE_RULESET_VERSION
    )
    if abi < 4:
        die("landlock version %s < 4" % abi)
    attr = RulesetAttr(
        0, LANDLOCK_ACCESS_NET_BIND_TCP | LANDLOCK_ACCESS_NET_CONNECT_TCP
    )
    fd = libc.syscall(
        SYS_LANDLOCK_CREATE_RULESET, ctypes.byref(attr), ctypes.sizeof(attr), 0
    )
    if fd < 0:
        die("landlock_create_ruleset: errno %s" % ctypes.get_errno())
    for port in PORTS:
        rule = NetPortAttr(LANDLOCK_ACCESS_NET_CONNECT_TCP, port)
        rc = libc.syscall(
            SYS_LANDLOCK_ADD_RULE, fd, LANDLOCK_RULE_NET_PORT, ctypes.byref(rule), 0
        )
        if rc < 0:
            die("landlock_add_rule(%s): errno %s" % (port, ctypes.get_errno()))
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        die("prctl: errno %s" % ctypes.get_errno())
    rc = libc.syscall(SYS_LANDLOCK_RESTRICT_SELF, fd, 0)
    if rc < 0:
        die("landlock_restrict_self: errno %s" % ctypes.get_errno())
    os.close(fd)


def seccomp():
    path = next(
        (
            candidate
            for candidate in (
                "/lib/x86_64-linux-gnu/libseccomp.so.2",
                "/usr/lib/x86_64-linux-gnu/libseccomp.so.2",
                "/lib/aarch64-linux-gnu/libseccomp.so.2",
                "/usr/lib/aarch64-linux-gnu/libseccomp.so.2",
                "/lib64/libseccomp.so.2",
                "/usr/lib64/libseccomp.so.2",
            )
            if os.path.exists(candidate)
        ),
        None,
    )
    if path is None:
        die("libseccomp not found")
    lib = ctypes.CDLL(path)
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_rule_add_array.restype = ctypes.c_int
    lib.seccomp_rule_add_array.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.c_void_p,
    ]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]

    ctx = lib.seccomp_init(SCMP_ACT_ALLOW)
    if not ctx:
        die("seccomp_init")
    sysno = lib.seccomp_syscall_resolve_name(b"socket")
    if sysno < 0:
        die("socket syscall not found")
    action = 0x00050000 | 1  # SCMP_ACT_ERRNO(EPERM)
    for domain in (AF_INET, AF_INET6):
        for typ in (SOCK_DGRAM, SOCK_RAW):
            args = (ScmpArgCmp * 2)(
                ScmpArgCmp(0, SCMP_CMP_EQ, domain, 0),
                ScmpArgCmp(1, SCMP_CMP_MASKED_EQ, SOCK_TYPE_MASK, typ),
            )
            rc = lib.seccomp_rule_add_array(
                ctx, action, sysno, 2, ctypes.cast(args, ctypes.c_void_p)
            )
            if rc != 0:
                die("seccomp_rule_add_array: %s" % rc)
    rc = lib.seccomp_load(ctx)
    if rc != 0:
        die("seccomp_load: %s" % rc)
    lib.seccomp_release(ctx)


if len(sys.argv) < 2:
    die("usage: launcher <command> [args...]")
landlock()
seccomp()
os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
'''


def launcher_code(ports: Sequence[int]) -> str:
    """Return the launcher program with an immutable port allowlist."""
    values = tuple(sorted({int(port) for port in ports}))
    return _TEMPLATE.replace("__PORTS__", repr(values))
