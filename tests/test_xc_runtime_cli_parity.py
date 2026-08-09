from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
MINIMAL_TEMPLATE = (
    SOURCE_ROOT / "xcoding" / "runtime" / "assets" / "minimal-template.xml"
)
LEGACY_ADAPTER = (
    REPOSITORY_ROOT
    / "skills"
    / "xc-orchestration-runtime"
    / "scripts"
    / "orchestration.py"
)
sys.path.insert(0, str(SOURCE_ROOT))

from xcoding import cli as package_cli
from xcoding.runtime import application
from xcoding.runtime import commands
from xcoding.runtime import query


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
    environment: application.RuntimeEnvironment,
) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = function(arguments, environment)
    return code, stdout.getvalue(), stderr.getvalue()


def load_legacy_adapter():
    spec = importlib.util.spec_from_file_location(
        "xc_runtime_legacy_adapter",
        LEGACY_ADAPTER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load legacy runtime adapter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeCliParityTests(unittest.TestCase):
    def environment(self) -> application.RuntimeEnvironment:
        return application.RuntimeEnvironment(MINIMAL_TEMPLATE)

    def test_shared_spec_declares_all_23_commands_with_exact_arguments(
        self,
    ) -> None:
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
        self.assertEqual(commands.COMMAND_NAMES, expected)
        self.assertEqual(
            query.READ_ONLY_COMMANDS,
            (
                "next",
                "summary",
                "show",
                "control-packet",
                "find",
                "artifacts",
                "snapshot",
                "integrity-status",
                "validate",
            ),
        )
        self.assertEqual(
            parser_signature(commands.build_parser()),
            parser_signature(commands.build_parser()),
        )

    def test_package_adapter_matches_application_results(self) -> None:
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
                expected = invoke(
                    application.main,
                    list(arguments),
                    self.environment(),
                )
                actual = invoke(
                    package_cli._runtime_main,
                    list(arguments),
                    self.environment(),
                )
                self.assertEqual(actual, expected)
                self.assertEqual(actual[2], "")
                self.assertEqual(json.loads(actual[1]), json.loads(expected[1]))

    def test_python_module_runtime_matches_direct_application(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SOURCE_ROOT)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "xcoding",
                "runtime",
                "validate",
                "--tree",
                str(MINIMAL_TEMPLATE),
            ],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        direct = application.execute(
            ["validate", "--tree", str(MINIMAL_TEMPLATE)],
            self.environment(),
        )
        self.assertEqual(result.returncode, direct.exit_code)
        self.assertEqual(json.loads(result.stdout), direct.payload)
        self.assertEqual(result.stderr, "")

    def test_legacy_adapter_has_bounded_missing_package_error(self) -> None:
        environment = os.environ.copy()
        environment["PATH"] = ""
        result = subprocess.run(
            [sys.executable, "-B", str(LEGACY_ADAPTER), "summary"],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "xcoding_unavailable")
        self.assertEqual(
            payload["error"]["details"],
            {"executable": "xcoding"},
        )
        self.assertNotIn("Traceback", result.stdout)

    def test_legacy_adapter_execs_xcoding_runtime_without_shell(self) -> None:
        adapter = load_legacy_adapter()
        with (
            mock.patch.object(
                adapter.shutil,
                "which",
                return_value="/tools/xcoding",
            ),
            mock.patch.object(
                adapter.sys,
                "argv",
                ["orchestration.py", "next", "--tree", "tree.xml"],
            ),
            mock.patch.object(
                adapter.os,
                "execv",
                side_effect=OSError("test stop"),
            ) as execute,
            mock.patch.object(adapter, "emit_unavailable", return_value=2),
        ):
            self.assertEqual(adapter.main(), 2)
        execute.assert_called_once_with(
            "/tools/xcoding",
            [
                "/tools/xcoding",
                "runtime",
                "next",
                "--tree",
                "tree.xml",
            ],
        )

    def test_runtime_init_uses_package_template(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "runtime"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = package_cli.main(
                    [
                        "runtime",
                        "init",
                        "--runtime-path",
                        str(runtime),
                        "--work-order-id",
                        "package-cutover",
                    ]
                )
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(Path(payload["template"]), MINIMAL_TEMPLATE)


if __name__ == "__main__":
    unittest.main()
