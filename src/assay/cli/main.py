"""`assay check`: parse, validate and (later) run one skill end to end."""

from __future__ import annotations

import argparse
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from assay.agent import (
    AnthropicModel,
    Budget,
    Model,
    ModelPrice,
    OpenAICompatibleModel,
    Toolbox,
    drive,
    task_for,
)
from assay.capture import TraceStore, capture
from assay.ingest import SkillParseError, parse_skill
from assay.sandbox import SandboxUnavailable
from assay.sandbox.base import Sandbox, select_sandbox
from assay.verdict import Strictness, StrictnessPolicy, Verdict, assess

from .output import refusal, render_human, render_json


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
    check.add_argument(
        "--provider", choices=["anthropic", "openai-compatible"], default="anthropic"
    )
    check.add_argument("--base-url", metavar="URL")
    check.add_argument("--api-key", metavar="KEY")
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
        _emit(f"error: {exc}\n", sys.stderr)
        return 2
    except Exception as exc:  # no traceback ever reaches the user
        _emit(f"error: {type(exc).__name__}: {exc}\n", sys.stderr)
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
    if args.provider == "anthropic" and args.base_url:
        raise UsageError("--base-url is only valid with --provider openai-compatible")
    if args.provider == "anthropic" and args.api_key:
        raise UsageError("--api-key is only valid with --provider openai-compatible")
    if args.provider == "openai-compatible":
        if not args.base_url:
            raise UsageError("--base-url is required with --provider openai-compatible")
        if args.api_key is None:
            args.api_key = os.environ.get("ASSAY_API_KEY")
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
    path = Path(args.skill)
    if path.is_dir():
        path = path / "SKILL.md"
    try:
        skill = parse_skill(path)
    except SkillParseError as exc:
        _emit(refusal("wont-parse", exc.detail, exc.path, args.json), sys.stdout)
        return 1
    if model is None:
        price = ModelPrice(args.input_price, args.output_price)
        if args.provider == "anthropic":
            model = AnthropicModel.from_env(args.model, price)
        else:
            model = OpenAICompatibleModel(
                args.model, price, args.base_url, api_key=args.api_key
            )
    if sandbox is None:
        try:
            sandbox = select_sandbox()
        except SandboxUnavailable as exc:
            _emit(refusal("sandbox-unavailable", str(exc), path, args.json), sys.stdout)
            return 1

    budget = Budget(
        max_usd=args.max_cost,
        max_steps=args.max_steps,
        max_actions=args.max_actions,
        max_wall_seconds=args.max_wall_seconds,
    )
    # Validate the destination before spending a single token.
    store = TraceStore(args.out)
    provider = args.provider
    if args.base_url:
        provider = f"{provider} @ {args.base_url}"
    _emit(f"model: {args.model} ({provider}) | max-cost: ${args.max_cost:.2f}\n", sys.stderr)
    run_root = _make_run_root()
    if args.keep_run_root:
        _emit(f"run root: {run_root}\n", sys.stderr)
    try:
        task = task_for(skill)
        with Toolbox(sandbox, run_root) as toolbox:
            outcome = drive(skill, task, model, toolbox, budget)
        trace = capture(skill, task, outcome)
        trace_path = store.save(trace).resolve()
        assessment = assess(skill, trace, policy=StrictnessPolicy(level=args.strictness))
        exit_code = 0 if assessment.verdict is Verdict.CLEAN else 1
        if args.json:
            _emit(render_json(skill, assessment, trace_path, trace), sys.stdout)
        else:
            _emit(
                render_human(skill, assessment, trace_path, trace, exit_code), sys.stdout
            )
        return exit_code
    finally:
        if not args.keep_run_root:
            shutil.rmtree(run_root, ignore_errors=True)


def _make_run_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="assay-run-"))


def _emit(text: str, stream: object) -> None:
    """Write UTF-8 even when the locale is ASCII, without mutating the process stream."""
    try:
        stream.write(text)  # type: ignore[attr-defined]
    except UnicodeEncodeError:
        stream.buffer.write(text.encode("utf-8"))  # type: ignore[attr-defined]
