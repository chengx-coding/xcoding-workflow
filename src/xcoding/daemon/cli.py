"""Foreground and detached lifecycle adapter for the local daemon."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

from . import protocol, server


TOKEN_ENV = "XC_DAEMON_TOKEN"
BACKGROUND_START_TIMEOUT_SECONDS = 5
BACKGROUND_START_POLL_SECONDS = 0.05


class DaemonCliError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise DaemonCliError("invalid_arguments", message)


def _emit(payload: object) -> None:
    sys.stdout.write(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    sys.stdout.flush()


def _launch_payload(
    *,
    mode: str,
    pid: int,
    url: str,
    token: str,
    runtimes: object,
) -> dict[str, object]:
    return {
        "schema_version": protocol.SCHEMA_VERSION,
        "ok": True,
        "command": "daemon serve",
        "mode": mode,
        "pid": pid,
        "url": url,
        "token": token,
        "runtimes": runtimes,
    }


def _error_payload(
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": protocol.SCHEMA_VERSION,
        "ok": False,
        "command": "daemon serve",
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def publish_readiness(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
        newline="",
    )
    os.replace(temporary, path)


def read_readiness(path: Path) -> dict[str, object] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise DaemonCliError(
            "invalid_readiness",
            "daemon child published invalid readiness JSON",
        ) from error
    if not isinstance(payload, dict):
        raise DaemonCliError(
            "invalid_readiness",
            "daemon child readiness must be an object",
        )
    if "token" in payload:
        raise DaemonCliError(
            "readiness_secret_exposure",
            "daemon child readiness must not contain a token",
        )
    return payload


def child_command(
    arguments: argparse.Namespace,
    readiness_path: Path,
) -> list[str]:
    command = [
        sys.executable,
        "-B",
        "-m",
        "xcoding",
        "daemon",
        "serve",
        "--_child",
        "--ready-file",
        str(readiness_path),
        "--host",
        arguments.host,
        "--port",
        str(arguments.port),
    ]
    for tree in arguments.tree:
        command.extend(["--tree", tree])
    return command


def stop_background_process(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _foreground_event(
    event: str,
    details: dict[str, object],
) -> None:
    _emit(
        {
            "schema_version": protocol.SCHEMA_VERSION,
            "event": event,
            **details,
        }
    )


def run_foreground(arguments: argparse.Namespace) -> int:
    token = server.generate_token()

    def ready(payload: dict[str, object]) -> None:
        _emit(
            _launch_payload(
                mode="foreground",
                pid=os.getpid(),
                url=str(payload["url"]),
                token=token,
                runtimes=payload["runtimes"],
            )
        )

    return server.serve_foreground(
        [Path(value) for value in arguments.tree],
        token,
        host=arguments.host,
        port=arguments.port,
        ready=ready,
        event_sink=_foreground_event,
    )


def run_background_child(arguments: argparse.Namespace) -> int:
    token = os.environ.pop(TOKEN_ENV, "")
    readiness_path = Path(arguments.ready_file)
    if not token:
        publish_readiness(
            readiness_path,
            _error_payload(
                "token_unavailable",
                "daemon child did not receive its process token",
            ),
        )
        return 2

    def ready(payload: dict[str, object]) -> None:
        publish_readiness(
            readiness_path,
            {
                "ok": True,
                "url": payload["url"],
                "runtimes": payload["runtimes"],
            },
        )

    try:
        return server.serve_foreground(
            [Path(value) for value in arguments.tree],
            token,
            host=arguments.host,
            port=arguments.port,
            ready=ready,
            event_sink=None,
        )
    except (
        OSError,
        ValueError,
        protocol.ProtocolError,
    ) as error:
        publish_readiness(
            readiness_path,
            _error_payload(
                getattr(error, "code", "startup_failed"),
                str(error),
            ),
        )
        return 2


def launch_background(arguments: argparse.Namespace) -> int:
    token = server.generate_token()
    readiness_root = Path(
        tempfile.mkdtemp(prefix="xc-daemon-ready-")
    )
    readiness_path = readiness_root / "ready.json"
    environment = os.environ.copy()
    environment[TOKEN_ENV] = token
    process_options: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
        "env": environment,
    }
    if os.name == "nt":
        process_options["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        process_options["start_new_session"] = True
    try:
        process = subprocess.Popen(
            child_command(arguments, readiness_path),
            **process_options,
        )
    except OSError as error:
        shutil.rmtree(readiness_root, ignore_errors=True)
        _emit(
            _error_payload(
                "startup_failed",
                "daemon child could not be started",
                {"exception": type(error).__name__},
            )
        )
        return 2

    deadline = time.monotonic() + BACKGROUND_START_TIMEOUT_SECONDS
    try:
        while time.monotonic() < deadline:
            payload = read_readiness(readiness_path)
            if payload is not None:
                if payload.get("ok") is True:
                    _emit(
                        _launch_payload(
                            mode="background",
                            pid=process.pid,
                            url=str(payload["url"]),
                            token=token,
                            runtimes=payload["runtimes"],
                        )
                    )
                    return 0
                error = payload.get("error", {})
                message = (
                    str(error.get("message", "daemon startup failed"))
                    if isinstance(error, dict)
                    else "daemon startup failed"
                )
                raise DaemonCliError("startup_failed", message)
            if process.poll() is not None:
                raise DaemonCliError(
                    "startup_failed",
                    "daemon child exited before readiness",
                    {"returncode": process.returncode},
                )
            time.sleep(BACKGROUND_START_POLL_SECONDS)
        raise DaemonCliError(
            "startup_timeout",
            "daemon child did not become ready before timeout",
        )
    except DaemonCliError as error:
        stop_background_process(process)
        _emit(_error_payload(error.code, str(error), error.details))
        return 2
    finally:
        shutil.rmtree(readiness_root, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="xc daemon",
        description="Run the local authenticated read-only runtime daemon.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument(
        "--tree",
        action="append",
        required=True,
        help="Absolute managed runtime XML path. May be repeated.",
    )
    serve.add_argument("--host", default=server.DEFAULT_HOST)
    serve.add_argument("--port", type=int, default=server.DEFAULT_PORT)
    serve.add_argument("--foreground", action="store_true")
    serve.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    serve.add_argument("--ready-file", default="", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = build_parser().parse_args(
            list(sys.argv[1:] if argv is None else argv)
        )
        if arguments.command != "serve":
            raise DaemonCliError(
                "invalid_arguments",
                "unknown daemon command",
            )
        if arguments._child:
            if not arguments.ready_file:
                raise DaemonCliError(
                    "invalid_arguments",
                    "private daemon child requires a readiness file",
                )
            return run_background_child(arguments)
        if arguments.ready_file:
            raise DaemonCliError(
                "invalid_arguments",
                "readiness file is private to daemon child mode",
            )
        if arguments.foreground:
            return run_foreground(arguments)
        return launch_background(arguments)
    except DaemonCliError as error:
        _emit(_error_payload(error.code, str(error), error.details))
        return 2
    except protocol.ProtocolError as error:
        _emit(_error_payload(error.code, error.message, error.details))
        return 2
    except (OSError, ValueError) as error:
        _emit(
            _error_payload(
                "environment_error",
                str(error),
                {"exception": type(error).__name__},
            )
        )
        return 2


__all__ = [
    "BACKGROUND_START_POLL_SECONDS",
    "BACKGROUND_START_TIMEOUT_SECONDS",
    "DaemonCliError",
    "TOKEN_ENV",
    "build_parser",
    "child_command",
    "launch_background",
    "main",
    "publish_readiness",
    "read_readiness",
    "run_background_child",
    "run_foreground",
    "stop_background_process",
]
