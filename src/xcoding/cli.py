"""Stable command-line interface for the xcoding package."""

from __future__ import annotations

import argparse
import json
import os
import sys
from importlib import metadata, resources
from pathlib import Path
from typing import Any, Sequence

from .bundle.manifest import BundleValidationError
from .bundle.resources import inspect_installed_bundle, installed_bundle_root
from .doctor import DoctorReadinessError, doctor_report
from .runtime import application as runtime_application
from .setup_plan import SetupInputError, SetupReadinessError
from .setup_transaction import (
    SetupTransactionError,
    recover as recover_setup,
    rollback as rollback_setup,
    setup as run_setup,
)
from .version import version_report


SCHEMA_VERSION = 1
EXIT_SUCCESS = 0
EXIT_INPUT = 2
EXIT_BUNDLE = 3
EXIT_READINESS = 4
EXIT_INTERNAL = 5

_RUNTIME_TEMPLATE = (
    "assets",
    "minimal-template.xml",
)


class CliInputError(ValueError):
    """A stable command-line or input-structure error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliInputError(
            "invalid_arguments",
            message,
            details={},
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = _JsonArgumentParser(add_help=False)
    commands = parser.add_subparsers(dest="command", required=True)

    version = commands.add_parser("version", add_help=False)
    version.add_argument("--json", action="store_true", dest="json_output")

    bundle = commands.add_parser("bundle", add_help=False)
    bundle_commands = bundle.add_subparsers(
        dest="bundle_command",
        required=True,
    )
    inspect = bundle_commands.add_parser("inspect", add_help=False)
    inspect.add_argument("--json", action="store_true", dest="json_output")

    doctor = commands.add_parser("doctor", add_help=False)
    doctor.add_argument("--json", action="store_true", dest="json_output")
    doctor.add_argument("--target-root")

    setup = commands.add_parser("setup", add_help=False)
    setup.add_argument("--dry-run", action="store_true")
    setup.add_argument("--json", action="store_true", dest="json_output")
    setup.add_argument("--project-root")
    setup.add_argument("--host", action="append", default=[])
    setup.add_argument("--rollback", action="store_true")
    setup.add_argument("--recover", action="store_true")
    return parser


def _command_name(arguments: Sequence[str]) -> str:
    if arguments[:1] == ["version"]:
        return "version"
    if arguments[:1] == ["bundle"]:
        return "bundle inspect"
    if arguments[:1] == ["doctor"]:
        return "doctor"
    if arguments[:1] == ["setup"]:
        return "setup"
    return ""


def _success(command: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "command": command,
        "result": result,
    }


def _failure(
    command: str,
    code: str,
    message: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "command": command,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def _runtime_default_template() -> Path:
    resource = resources.files("xcoding.runtime").joinpath(*_RUNTIME_TEMPLATE)
    try:
        path = Path(os.fspath(resource))
    except TypeError as error:
        raise OSError(
            "packaged runtime template is not a physical resource"
        ) from error
    if (
        not path.is_file()
        or path.is_symlink()
        or (
            getattr(path, "is_junction", None) is not None
            and path.is_junction()
        )
    ):
        raise OSError(
            "packaged runtime template is not a regular physical file"
        )
    return path


def _runtime_main(
    arguments: Sequence[str],
    environment: runtime_application.RuntimeEnvironment | None = None,
) -> int:
    needs_default_template = (
        list(arguments[:1]) == ["init"]
        and "--template" not in arguments
    )
    resolved = environment or runtime_application.RuntimeEnvironment(
        default_template=(
            _runtime_default_template()
            if needs_default_template
            else Path()
        )
    )
    result = runtime_application.execute(list(arguments), resolved)
    runtime_application.json_print(result.payload)
    return result.exit_code


def _require_json(arguments: argparse.Namespace) -> None:
    if not getattr(arguments, "json_output", False):
        raise CliInputError(
            "json-required",
            "xcoding machine-readable commands require an explicit --json option",
        )


def _execute(arguments: argparse.Namespace, command: str) -> dict[str, Any]:
    _require_json(arguments)
    if command == "version":
        return version_report()
    if command == "bundle inspect":
        return inspect_installed_bundle().as_dict()
    if command == "doctor":
        target = Path(arguments.target_root) if arguments.target_root else None
        return doctor_report(target)
    if command == "setup":
        if arguments.project_root is None:
            raise CliInputError(
                "project_root_required",
                "setup requires an explicit --project-root",
            )
        if arguments.rollback and arguments.recover:
            raise CliInputError(
                "setup_mode_conflict",
                "setup accepts only one of --rollback or --recover",
            )
        if arguments.rollback or arguments.recover:
            if arguments.host or arguments.dry_run:
                raise CliInputError(
                    "setup_mode_conflict",
                    "rollback and recovery do not accept --host or --dry-run",
                )
            if arguments.rollback:
                return rollback_setup(arguments.project_root)
            return recover_setup(arguments.project_root)
        if not arguments.host:
            raise CliInputError(
                "host_required",
                "setup requires at least one explicit --host",
            )
        return run_setup(
            arguments.project_root,
            arguments.host,
            dry_run=arguments.dry_run,
        )
    raise CliInputError("invalid_arguments", "unknown command")


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one command, emit exactly one JSON envelope, and return its exit."""
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    if raw_arguments[:1] == ["viewer"]:
        from .viewer import cli as viewer_cli

        return viewer_cli.main(raw_arguments[1:])
    if raw_arguments[:1] == ["daemon"]:
        from .daemon import cli as daemon_cli

        return daemon_cli.main(raw_arguments[1:])
    if raw_arguments[:1] == ["runtime"]:
        return _runtime_main(raw_arguments[1:])
    command = _command_name(raw_arguments)
    try:
        arguments = _build_parser().parse_args(raw_arguments)
        result = _execute(arguments, command)
    except (CliInputError, SetupInputError) as error:
        _emit(_failure(command, error.code, str(error), error.details))
        return EXIT_INPUT
    except BundleValidationError as error:
        _emit(_failure(command, error.code, str(error), error.details))
        return EXIT_BUNDLE
    except metadata.PackageNotFoundError as error:
        _emit(
            _failure(
                command,
                "version_mismatch",
                "installed distribution metadata is unavailable",
                {"distribution": error.name},
            )
        )
        return EXIT_BUNDLE
    except (DoctorReadinessError, SetupReadinessError, SetupTransactionError) as error:
        _emit(_failure(command, error.code, str(error), error.details))
        return EXIT_READINESS
    except OSError as error:
        _emit(
            _failure(
                command,
                "environment_error",
                str(error),
                {"exception": type(error).__name__},
            )
        )
        return EXIT_READINESS
    except Exception as error:
        _emit(
            _failure(
                command,
                "internal_error",
                "unclassified internal command failure",
                {"exception": type(error).__name__},
            )
        )
        return EXIT_INTERNAL

    _emit(_success(command, result))
    return EXIT_SUCCESS


__all__ = [
    "EXIT_BUNDLE",
    "EXIT_INPUT",
    "EXIT_INTERNAL",
    "EXIT_READINESS",
    "EXIT_SUCCESS",
    "SCHEMA_VERSION",
    "main",
]
