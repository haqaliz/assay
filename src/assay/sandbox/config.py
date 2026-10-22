"""Jail configuration: validated frozen data plus a deterministic hash."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping

OUTPUT_CAP_BYTES = 1024 * 1024


def _check_path(path: object, name: str) -> Path:
    if not isinstance(path, (str, Path)):
        raise ValueError(f"{name} must be a path, got {type(path).__name__}")
    p = Path(path)
    if '"' in str(p):
        raise ValueError(f'{name} must not contain a double quote: the Seatbelt profile quotes paths')
    if not p.is_absolute():
        raise ValueError(f"{name} must be absolute, got {p}")
    return p


@dataclass(frozen=True)
class NetRule:
    """Seatbelt accepts only '*' or 'localhost' as a host, plus a port. No IPs, no CIDRs."""

    host: Literal["*", "localhost"] = "*"
    port: int = 443

    def __post_init__(self) -> None:
        if self.host not in ("*", "localhost"):
            raise ValueError(
                f'NetRule.host must be "*" or "localhost" (Seatbelt cannot express IPs or CIDRs), '
                f"got {self.host!r}"
            )
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise ValueError(f"NetRule.port must be an int in 1..65535, got {self.port!r}")


@dataclass(frozen=True)
class Limits:
    wall_seconds: float = 30.0
    cpu_seconds: int = 30
    file_bytes: int = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        if self.wall_seconds <= 0:
            raise ValueError(f"wall_seconds must be positive, got {self.wall_seconds!r}")
        for name in ("cpu_seconds", "file_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive int, got {value!r}")


@dataclass(frozen=True)
class JailConfig:
    run_root: Path
    allow_network: tuple[NetRule, ...] = ()
    allow_read_extra: tuple[Path, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)
    limits: Limits = field(default_factory=Limits)
    keep: bool = False

    def __post_init__(self) -> None:
        root = _check_path(self.run_root, "run_root")
        if not root.exists():
            raise ValueError(f"run_root must exist, got {root}")
        if not root.is_dir():
            raise ValueError(f"run_root must be a directory, got {root}")
        if root.is_symlink():
            raise ValueError(f"run_root must not be a symlink, got {root}")
        # Canonicalise: macOS reports /var/... while the kernel enforces /private/var/..., and a
        # profile written with the short form would not match the vnode the child touches.
        object.__setattr__(self, "run_root", root.resolve())

        extra = tuple(
            _check_path(p, "allow_read_extra").resolve() for p in self.allow_read_extra
        )
        object.__setattr__(self, "allow_read_extra", extra)

        rules = tuple(self.allow_network)
        for rule in rules:
            if not isinstance(rule, NetRule):
                raise ValueError(f"allow_network entries must be NetRule, got {type(rule).__name__}")
        object.__setattr__(self, "allow_network", rules)

        env = dict(self.env)
        for key, value in env.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError(f"env must map str to str, got {key!r}={value!r}")
        object.__setattr__(self, "env", env)

    @property
    def config_hash(self) -> str:
        """Operational settings only: run_root and keep are per-machine/per-run, not identity."""
        payload = {
            "allow_network": sorted([r.host, r.port] for r in self.allow_network),
            "allow_read_extra": sorted(str(p) for p in self.allow_read_extra),
            "env": dict(sorted(self.env.items())),
            "limits": {
                "wall_seconds": self.limits.wall_seconds,
                "cpu_seconds": self.limits.cpu_seconds,
                "file_bytes": self.limits.file_bytes,
            },
            "output_cap_bytes": OUTPUT_CAP_BYTES,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(blob.encode()).hexdigest()
