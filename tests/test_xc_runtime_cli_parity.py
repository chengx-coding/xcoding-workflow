from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
RUNTIME_SCRIPTS = (
    REPOSITORY_ROOT
    / "skills"
    / "xc-orchestration-runtime"
    / "scripts"
)
MINIMAL_TEMPLATE = (
    REPOSITORY_ROOT
    / "skills"
    / "xc-orchestration-runtime"
    / "assets"
    / "minimal-template.xml"
)

sys.path.insert(0, str(SOURCE_ROOT))
sys.path.insert(0, str(RUNTIME_SCRIPTS))

from xcoding import cli as package_cli
from xcoding import dispatch as package_dispatch
from xcoding.runtime import application as canonical_application
from xcoding.runtime import commands as canonical_commands
from xcoding.runtime import core as canonical_core

import orchestration as legacy_application
from _runtime_compat import application as generated_application
from _runtime_compat import commands as generated_commands
from _runtime_compat import core as generated_core


def parser_signature(
    parser: argparse.ArgumentParser,
) -> dict[str, list[dict[str, object]]]:
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    result: dict[str, list[dict[str, object]]] = {}
    for command, child in subparsers.choices.items():
        actions: list[dict[str, object]] = []
        for action in child._actions:
            if isinstance(action, argparse._HelpAction):
                continue
            actions.append(
                {
                    "class": type(action).__name__,
                    "option_strings": list(action.option_strings),
                    "dest": action.dest,
                    "required": action.required,
                    "nargs": action.nargs,
                    "default": action.default,
                    "choices": (
                        sorted(action.choices)
                        if action.choices is not None
                        else None
                    ),
                    "type": (
                        getattr(action.type, "__name__", None)
                        if action.type is not None
                        else None
                    ),
                }
            )
        result[command] = actions
    return result


def invoke(
    function,
    arguments: list[str],
    environment,
) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = function(arguments, environment)
    return code, stdout.getvalue(), stderr.getvalue()


def normalize_paths(value, replacements: dict[str, str]):
    if isinstance(value, dict):
        return {
            key: normalize_paths(item, replacements)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [normalize_paths(item, replacements) for item in value]
    if isinstance(value, str):
        normalized = value
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)
        return normalized
    return value


class RuntimeCliParityTests(unittest.TestCase):
    def canonical_environment(self) -> canonical_application.RuntimeEnvironment:
        return canonical_application.RuntimeEnvironment(MINIMAL_TEMPLATE)

    def generated_environment(self) -> generated_application.RuntimeEnvironment:
        return generated_application.RuntimeEnvironment(MINIMAL_TEMPLATE)

    def test_shared_spec_declares_all_23_commands_with_exact_arguments(self) -> None:
        expected = (
            "init",
            "next",
            "start",
            "complete",
            "fail",
            "block",
            "unblock",
            "retry-failed",
            "set",
            "add-node",
            "embed-subtree",
            "close-group",
            "reopen-group",
            "reopen",
            "summary",
            "show",
            "control-packet",
            "find",
            "artifacts",
            "snapshot",
            "integrity-status",
            "repair-integrity",
            "validate",
        )
        self.assertEqual(canonical_commands.COMMAND_NAMES, expected)
        self.assertEqual(generated_commands.COMMAND_NAMES, expected)
        self.assertEqual(
            parser_signature(canonical_commands.build_parser()),
            parser_signature(generated_commands.build_parser()),
        )

    def test_canonical_and_generated_runtime_modules_are_byte_identical(self) -> None:
        canonical_root = REPOSITORY_ROOT / "src" / "xcoding" / "runtime"
        generated_root = RUNTIME_SCRIPTS / "_runtime_compat"
        for name in ("__init__.py", "application.py", "commands.py", "core.py"):
            self.assertEqual(
                (canonical_root / name).read_bytes(),
                (generated_root / name).read_bytes(),
                name,
            )

    def test_legacy_and_package_adapters_match_read_and_error_results(self) -> None:
        cases = (
            ["validate", "--tree", str(MINIMAL_TEMPLATE)],
            [
                "summary",
                "--tree",
                str(REPOSITORY_ROOT / "missing-runtime.xml"),
            ],
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                legacy = invoke(
                    legacy_application.main,
                    list(arguments),
                    self.generated_environment(),
                )
                package = invoke(
                    package_cli._runtime_main,
                    list(arguments),
                    self.canonical_environment(),
                )
                self.assertEqual(package, legacy)
                self.assertEqual(package[2], "")
                self.assertEqual(
                    json.loads(package[1]),
                    json.loads(legacy[1]),
                )

    def test_legacy_and_package_adapters_match_init_state(self) -> None:
        fixed_now = "2030-01-02T03:04:05+00:00"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy_root = root / "legacy"
            package_root = root / "package"
            arguments = [
                "init",
                "--work-order-id",
                "parity-work-order",
                "--name",
                "Parity",
            ]
            with (
                mock.patch.object(
                    generated_core,
                    "utc_now",
                    return_value=fixed_now,
                ),
                mock.patch.object(
                    generated_core,
                    "today",
                    return_value="2030-01-02",
                ),
                mock.patch.object(
                    canonical_core,
                    "utc_now",
                    return_value=fixed_now,
                ),
                mock.patch.object(
                    canonical_core,
                    "today",
                    return_value="2030-01-02",
                ),
            ):
                legacy = invoke(
                    legacy_application.main,
                    [
                        *arguments,
                        "--runtime-path",
                        str(legacy_root),
                    ],
                    self.generated_environment(),
                )
                package = invoke(
                    package_cli._runtime_main,
                    [
                        *arguments,
                        "--runtime-path",
                        str(package_root),
                    ],
                    self.canonical_environment(),
                )

            self.assertEqual(legacy[0], 0)
            self.assertEqual(package[0], 0)
            legacy_payload = normalize_paths(
                json.loads(legacy[1]),
                {str(legacy_root): "<RUNTIME>"},
            )
            package_payload = normalize_paths(
                json.loads(package[1]),
                {str(package_root): "<RUNTIME>"},
            )
            self.assertEqual(package_payload, legacy_payload)
            self.assertEqual(
                (
                    package_root / "orchestration.xml"
                ).read_bytes(),
                (
                    legacy_root / "orchestration.xml"
                ).read_bytes(),
            )

    def test_public_cli_routes_runtime_without_subprocess_dispatch(self) -> None:
        with mock.patch.object(
            package_dispatch.subprocess,
            "run",
        ) as run:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = package_cli.main(
                    [
                        "runtime",
                        "validate",
                        "--tree",
                        str(MINIMAL_TEMPLATE),
                    ]
                )
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout.getvalue())["ok"])
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
