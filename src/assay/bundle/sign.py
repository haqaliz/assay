"""Sign and verify bundle payloads with the host's `ssh-keygen`; Assay never opens a key."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .records import NAMESPACE, Signature

SIGN_TIMEOUT = 15

_BEGIN = "-----BEGIN SSH SIGNATURE-----"
_KEY_TYPES = (
    "ssh-ed25519",
    "ssh-rsa",
    "ecdsa-sha2-",
    "sk-ssh-ed25519@openssh.com",
    "sk-ecdsa-",
)
_TIMED_OUT = (
    "passphrase-protected keys are not supported; use a dedicated unencrypted key"
)


class SigningError(Exception):
    """A signing or verification operation failed. Messages are '<cause>: <detail>'."""


def _keygen() -> str:
    binary = shutil.which("ssh-keygen")
    if binary is None:
        raise SigningError(
            "ssh-keygen-not-found: install OpenSSH or use a signing backend"
        )
    return binary


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:200]
    return ""


def _run(
    argv: list[str], stdin: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    if stdin is None:
        return subprocess.run(
            argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=SIGN_TIMEOUT
        )
    return subprocess.run(argv, input=stdin, capture_output=True, timeout=SIGN_TIMEOUT)


def _stderr(proc: subprocess.CompletedProcess[bytes]) -> str:
    return proc.stderr.decode("utf-8", errors="replace")


def _detail(proc: subprocess.CompletedProcess[bytes], fallback: str) -> str:
    return _first_line(_stderr(proc)) or fallback


def _redact_path(detail: str, private_key: Path) -> str:
    # ssh-keygen names the key file in its errors; the bundle and its reports never do.
    return detail.replace(str(private_key), "<key>")


def _public_key_line(public_key: Path) -> str:
    try:
        text = Path(public_key).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SigningError(f"public-key-invalid: {exc}") from None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise SigningError(
            f"public-key-invalid: expected one public key line, got {len(lines)}"
        )
    line = lines[0]
    if not line.startswith(_KEY_TYPES):
        raise SigningError("public-key-invalid: not an SSH public key line")
    return line


def _fingerprint_output(proc: subprocess.CompletedProcess[bytes]) -> str:
    if proc.returncode != 0:
        raise SigningError(
            "public-key-invalid: "
            + _detail(proc, f"ssh-keygen exited {proc.returncode}")
        )
    text = proc.stdout.decode("utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    fields = lines[0].split() if len(lines) == 1 else []
    if len(fields) < 2 or not fields[1].startswith("SHA256:"):
        raise SigningError("public-key-invalid: unexpected fingerprint output")
    return fields[1]


def fingerprint(public_key: Path) -> str:
    line = _public_key_line(public_key)
    binary = _keygen()
    try:
        proc = _run([binary, "-lf", str(public_key)])
    except subprocess.TimeoutExpired:
        raise SigningError("public-key-invalid: ssh-keygen -lf timed out") from None
    return _fingerprint_output(proc)


def sign(payload: bytes, private_key: Path) -> Signature:
    binary = _keygen()
    try:
        public = _run([binary, "-y", "-f", str(private_key)])
    except subprocess.TimeoutExpired:
        raise SigningError(f"signing-timed-out: {_TIMED_OUT}") from None
    if public.returncode != 0:
        detail = _redact_path(
            _detail(public, f"ssh-keygen exited {public.returncode}"), private_key
        )
        raise SigningError(f"signing-key-unavailable: {detail}")
    line = _first_line(public.stdout.decode("utf-8", errors="replace"))
    try:
        finger = _run([binary, "-lf", "-"], line.encode("utf-8") + b"\n")
    except subprocess.TimeoutExpired:
        raise SigningError("public-key-invalid: ssh-keygen -lf timed out") from None
    signer = _fingerprint_output(finger)
    try:
        proc = _run(
            [binary, "-Y", "sign", "-f", str(private_key), "-n", NAMESPACE, "-"],
            payload,
        )
    except subprocess.TimeoutExpired:
        raise SigningError(f"signing-timed-out: {_TIMED_OUT}") from None
    if proc.returncode != 0:
        detail = _redact_path(
            _detail(proc, f"ssh-keygen exited {proc.returncode}"), private_key
        )
        raise SigningError(f"signing-failed: {detail}")
    value = proc.stdout.decode("utf-8", errors="replace")
    if not value.startswith(_BEGIN):
        raise SigningError("signing-failed: unexpected output")
    return Signature(signer=signer, value=value)


def verify(payload: bytes, signature: Signature, public_key: Path) -> None:
    signer = fingerprint(public_key)
    if signer != signature.signer:
        raise SigningError(
            f"signer-mismatch: expected {signature.signer}, got {signer}"
        )
    line = _public_key_line(public_key)
    binary = _keygen()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        allowed_signers = root / "allowed_signers"
        sig = root / "sig"
        allowed_signers.write_text(f"{NAMESPACE} {line}\n", encoding="utf-8")
        sig.write_text(signature.value, encoding="utf-8")
        try:
            proc = _run(
                [
                    binary,
                    "-Y",
                    "verify",
                    "-f",
                    str(allowed_signers),
                    "-I",
                    NAMESPACE,
                    "-n",
                    NAMESPACE,
                    "-s",
                    str(sig),
                    "-",
                ],
                payload,
            )
        except subprocess.TimeoutExpired:
            raise SigningError(
                "verification-timed-out: ssh-keygen did not finish"
            ) from None
    if proc.returncode != 0:
        raise SigningError(
            "signature-invalid: "
            + _detail(proc, f"ssh-keygen exited {proc.returncode}")
        )
