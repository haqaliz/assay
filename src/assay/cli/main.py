"""`assay check`: parse, validate and (later) run one skill end to end."""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path
from typing import Sequence

from assay.agent import Model
from assay.sandbox.base import Sandbox
from assay.verdict import Strictness


class UsageError(Exception):
    """A setting the command needs is missing or invalid; never a verdict."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assay", description="Run one skill through Assay.")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="run a skill and print its verdict")
    check.add_argument("skill", type=str)
    check.add_argument(
        "--strictness", choices=[level.value for level in Strictness], default="standard"
    )
    check.add_argument("--max-cost", metavar="USD")
    check.add_argument("--model", metavar="NAME")
    check.add_argument("--input-price", metavar="USD_PER_MTOK")
    check.add_argument("--output-price", metavar="USD_PER_MTOK")
    check.add_argument("--max-steps", default=20)
    check.add_argument("--max-actions", default=40)
    check.add_argument("--max-wall-seconds", default=300)
    check.add_argument("--out", type=Path, default=Path("./.assay/traces"), metavar="DIR")
    check.add_argument("--json", action="store_true")
    check.add_argument("--keep-run-root", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    model: Model | None = None,
    sandbox: Sandbox | None = None,
) -> int:
    try:
        args = build_parser().parse_args(argv)
        _validate(args)
        return _check(args, model, sandbox)
    except KeyboardInterrupt:
        return 130
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # no traceback ever reaches the user
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def _validate(args: argparse.Namespace) -> None:
    args.strictness = Strictness(args.strictness)
    args.max_cost = _number(args, "max_cost", "--max-cost", "ASSAY_MAX_COST", positive=True)
    args.input_price = _number(
        args, "input_price", "--input-price", "ASSAY_INPUT_PRICE", positive=False
    )
    args.output_price = _number(
        args, "output_price", "--output-price", "ASSAY_OUTPUT_PRICE", positive=False
    )
    if not args.model:
        args.model = os.environ.get("ASSAY_MODEL")
    if not isinstance(args.model, str) or not args.model.strip():
        raise UsageError("--model is required (or set ASSAY_MODEL)")
    args.max_steps = _integer(args.max_steps, "--max-steps")
    args.max_actions = _integer(args.max_actions, "--max-actions")
    args.max_wall_seconds = _number(
        args, "max_wall_seconds", "--max-wall-seconds", "ASSAY_MAX_WALL_SECONDS", positive=True
    )


def _number(
    args: argparse.Namespace, attr: str, flag: str, env: str, *, positive: bool
) -> float:
    raw = getattr(args, attr)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raw = os.environ.get(env)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise UsageError(f"{flag} is required (or set {env})")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise UsageError(f"{flag} must be a number, got {raw!r}") from None
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        kind = "positive" if positive else "non-negative"
        raise UsageError(f"{flag} must be a finite {kind} number, got {raw!r}")
    return value


def _integer(raw: object, flag: str) -> int:
    try:
        value = int(str(raw), 10)
    except ValueError:
        raise UsageError(f"{flag} must be an integer, got {raw!r}") from None
    if value < 1:
        raise UsageError(f"{flag} must be an integer >= 1, got {raw!r}")
    return value


def _check(
    args: argparse.Namespace, model: Model | None, sandbox: Sandbox | None
) -> int:
    raise NotImplementedError("the check pipeline is not wired yet")
