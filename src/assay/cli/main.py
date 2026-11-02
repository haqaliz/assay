"""The `assay` command line: check one skill, bundle a trace, verify a bundle."""

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
from assay.bundle import Bundle, BundleError, SigningError, build, verify
from assay.capture import CaptureError, TraceStore, capture
from assay.corpus import CaseError, evaluate, load_corpus
from assay.ingest import SkillParseError, parse_skill
from assay.sandbox import SandboxUnavailable
from assay.sandbox.base import Sandbox, select_sandbox
from assay.verdict import Strictness, StrictnessPolicy, Verdict, assess

from .output import (
    bundle_refusal,
    corpus_refusal,
    refusal,
    render_bundle,
    render_corpus,
    render_human,
    render_json,
    render_verify,
)


class UsageError(Exception):
    """A setting the command needs is missing or invalid; never a verdict."""


MAX_BUNDLE_BYTES = 64 * 1024 * 1024


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
    bundle = commands.add_parser("bundle", help="sign a saved trace into a bundle")
    bundle.add_argument("trace", type=str)
    bundle.add_argument("--skill", required=True, metavar="SKILL.md|DIR")
    bundle.add_argument("--key", required=True, metavar="PRIVATE_KEY")
    bundle.add_argument(
        "--strictness", choices=[level.value for level in Strictness], default="standard"
    )
    bundle.add_argument("--out", type=Path, metavar="DIR")
    bundle.add_argument("--json", action="store_true")
    verify_command = commands.add_parser(
        "verify", help="check a bundle's integrity and signature"
    )
    verify_command.add_argument("bundle", type=str)
    verify_command.add_argument("--public-key", required=True, metavar="PUBLIC_KEY")
    verify_command.add_argument("--json", action="store_true")
    corpus = commands.add_parser(
        "corpus", help="report verdicts against a labeled corpus"
    )
    corpus.add_argument("corpus", type=str)
    corpus.add_argument("--json", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    model: Model | None = None,
    sandbox: Sandbox | None = None,
) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == "check":
            _validate(args)
            return _check(args, model, sandbox)
        if args.command == "bundle":
            _validate_bundle(args)
            return _bundle(args)
        if args.command == "corpus":
            return _corpus(args)
        return _verify(args)
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


def _validate_bundle(args: argparse.Namespace) -> None:
    args.strictness = Strictness(args.strictness)


def _bundle(args: argparse.Namespace) -> int:
    trace_path = Path(args.trace)
    out = Path(args.out) if args.out is not None else trace_path.parent
    target = (out / f"{trace_path.stem}.bundle.json").resolve()
    if not trace_path.is_file():
        return _bundle_failure(
            "trace-unreadable", f"no trace file at {trace_path}", target, args.json
        )
    try:
        trace = TraceStore(trace_path.parent).load(trace_path)
    except CaptureError as exc:
        return _bundle_failure("trace-invalid", str(exc), target, args.json)
    skill_path = Path(args.skill)
    if skill_path.is_dir():
        skill_path = skill_path / "SKILL.md"
    try:
        skill = parse_skill(skill_path)
    except SkillParseError as exc:
        return _bundle_failure("skill-invalid", exc.detail, target, args.json)
    try:
        record = build(skill, trace, Strictness(args.strictness), Path(args.key))
    except (BundleError, SigningError) as exc:
        cause, detail = _cause_detail(exc)
        return _bundle_failure(cause, detail, target, args.json)
    try:
        out.mkdir(parents=True, exist_ok=True)
        _write_atomic(target, record.to_json())
    except OSError as exc:
        return _bundle_failure("bundle-write-failed", str(exc), target, args.json)
    _emit(render_bundle(record, target, args.json), sys.stdout)
    return 0


def _verify(args: argparse.Namespace) -> int:
    path = Path(args.bundle)
    try:
        size = path.stat().st_size
    except OSError as exc:
        return _bundle_failure("bundle-unreadable", str(exc), path, args.json)
    if size > MAX_BUNDLE_BYTES:
        return _bundle_failure(
            "bundle-too-large",
            f"bundle is {size} bytes; the limit is {MAX_BUNDLE_BYTES} bytes",
            path,
            args.json,
        )
    try:
        data = path.read_bytes()
    except OSError as exc:
        return _bundle_failure("bundle-unreadable", str(exc), path, args.json)
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        return _bundle_failure("bundle-invalid", str(exc), path, args.json)
    try:
        record = Bundle.from_json(text)
    except BundleError as exc:
        cause, detail = _cause_detail(exc)
        return _bundle_failure(cause, detail, path, args.json)
    try:
        verify(record, Path(args.public_key))
    except SigningError as exc:
        cause, detail = _cause_detail(exc)
        return _bundle_failure(cause, detail, path, args.json)
    _emit(render_verify(record, path, args.json), sys.stdout)
    return 0


def _corpus(args: argparse.Namespace) -> int:
    path = Path(args.corpus)
    try:
        cases = load_corpus(path)
    except CaseError as exc:
        cause, detail = _cause_detail(exc, default="corpus-invalid")
        _emit(corpus_refusal(cause, detail, path, args.json), sys.stdout)
        return 1
    _emit(render_corpus(evaluate(cases), path, args.json), sys.stdout)
    return 0


def _bundle_failure(cause: str, detail: str, path: Path, as_json: bool) -> int:
    _emit(bundle_refusal(cause, detail, path, as_json), sys.stdout)
    return 1


def _cause_detail(exc: Exception, default: str = "bundle-invalid") -> tuple[str, str]:
    cause, separator, detail = str(exc).partition(": ")
    if not separator or not cause or not detail:
        return default, str(exc)
    return cause, detail


def _write_atomic(path: Path, text: str) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".bundle-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(text.encode("utf-8"))
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _make_run_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="assay-run-"))


def _emit(text: str, stream: object) -> None:
    """Write UTF-8 even when the locale is ASCII, without mutating the process stream."""
    try:
        stream.write(text)  # type: ignore[attr-defined]
    except UnicodeEncodeError:
        stream.buffer.write(text.encode("utf-8"))  # type: ignore[attr-defined]
