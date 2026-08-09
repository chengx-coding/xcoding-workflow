from __future__ import annotations

import argparse
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
MINIMAL_TEMPLATE = (
    REPOSITORY_ROOT
    / "src"
    / "xcoding"
    / "runtime"
    / "assets"
    / "minimal-template.xml"
)

import sys

sys.path.insert(0, str(SOURCE_ROOT))

from xcoding.runtime import application, commands, core, query


class RuntimeQueryTests(unittest.TestCase):
    def environment(self) -> application.RuntimeEnvironment:
        return application.RuntimeEnvironment(MINIMAL_TEMPLATE)

    def initialize(self, root: Path) -> Path:
        runtime_root = root / "runtime"
        result = application.execute(
            [
                "init",
                "--runtime-path",
                str(runtime_root),
                "--work-order-id",
                "query-test",
                "--name",
                "Query Test",
            ],
            self.environment(),
        )
        self.assertEqual(result.exit_code, 0, result.payload)
        return runtime_root / "orchestration.xml"

    def test_read_only_command_set_is_exact(self) -> None:
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
            set(commands.COMMAND_NAMES) - set(query.READ_ONLY_COMMANDS),
            {
                "init",
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
                "repair-integrity",
            },
        )

    def test_typed_queries_match_direct_application_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            ready = application.execute(
                ["next", "--tree", str(tree)],
                self.environment(),
            )
            node = ready.payload["ready"][0]
            cases = (
                ("next", {"limit": 3}, ["next", "--tree", str(tree), "--limit", "3"]),
                (
                    "summary",
                    {"limit": 4},
                    ["summary", "--tree", str(tree), "--limit", "4"],
                ),
                (
                    "show",
                    {"node": node["id"]},
                    ["show", "--tree", str(tree), "--node", node["id"]],
                ),
                (
                    "control-packet",
                    {"node": node["id"]},
                    [
                        "control-packet",
                        "--tree",
                        str(tree),
                        "--node",
                        node["id"],
                    ],
                ),
                (
                    "find",
                    {
                        "template_id": node["template_id"],
                        "instance_id": node["origin_instance_id"],
                    },
                    [
                        "find",
                        "--tree",
                        str(tree),
                        "--template-id",
                        node["template_id"],
                        "--instance-id",
                        node["origin_instance_id"],
                    ],
                ),
                (
                    "artifacts",
                    {"audience": "internal"},
                    [
                        "artifacts",
                        "--tree",
                        str(tree),
                        "--audience",
                        "internal",
                    ],
                ),
                ("snapshot", {}, ["snapshot", "--tree", str(tree)]),
                (
                    "integrity-status",
                    {},
                    ["integrity-status", "--tree", str(tree)],
                ),
                ("validate", {}, ["validate", "--tree", str(tree)]),
            )
            for command, parameters, argv in cases:
                with self.subTest(command=command):
                    typed = query.execute_query(
                        command,
                        tree,
                        parameters,
                        self.environment(),
                    )
                    direct = application.execute(argv, self.environment())
                    self.assertEqual(typed, direct)

    def test_query_and_application_errors_have_the_same_shape(self) -> None:
        missing = REPOSITORY_ROOT / "missing-query-runtime.xml"
        typed = query.execute_query(
            "summary",
            missing,
            {},
            self.environment(),
        )
        direct = application.execute(
            ["summary", "--tree", str(missing)],
            self.environment(),
        )
        self.assertEqual(typed, direct)
        self.assertEqual(typed.exit_code, 2)
        self.assertFalse(typed.payload["ok"])

    def test_mutation_and_unknown_commands_reject_before_tree_access(self) -> None:
        forbidden = tuple(
            command
            for command in commands.COMMAND_NAMES
            if command not in query.READ_ONLY_COMMANDS
        )
        with (
            mock.patch.object(core, "parse_xml") as parse_xml,
            mock.patch.object(core, "read_tree_with_integrity") as read_tree,
            mock.patch.object(core, "tree_snapshot") as tree_snapshot,
        ):
            for command in (*forbidden, "not-a-command"):
                with self.subTest(command=command):
                    result = query.execute_query(
                        command,
                        Path("must-not-be-read.xml"),
                        {},
                        self.environment(),
                    )
                    self.assertEqual(result.exit_code, 2)
                    self.assertEqual(
                        result.payload["error"]["code"],
                        "invalid_query",
                    )
        parse_xml.assert_not_called()
        read_tree.assert_not_called()
        tree_snapshot.assert_not_called()

    def test_invalid_parameters_reject_before_tree_access(self) -> None:
        cases: tuple[tuple[str, object, str], ...] = (
            ("summary", {"limit": True}, "parameter_not_integer"),
            ("summary", {"limit": 0}, "parameter_out_of_range"),
            ("summary", {"limit": 65}, "parameter_out_of_range"),
            ("summary", {"extra": 1}, "unknown_parameters"),
            ("show", {}, "missing_parameters"),
            ("show", {"node": ""}, "parameter_empty"),
            ("show", {"node": "bad\nnode"}, "parameter_control_character"),
            (
                "show",
                {"node": "x" * (query.MAX_QUERY_SCALAR_BYTES + 1)},
                "parameter_too_large",
            ),
            ("find", {"template_id": 1}, "parameter_not_string"),
            ("artifacts", {"audience": "other"}, "parameter_invalid_choice"),
            ("snapshot", {"limit": 1}, "unknown_parameters"),
            ("summary", [], "parameters_not_object"),
            (
                "summary",
                {f"key-{index}": index for index in range(9)},
                "too_many_parameters",
            ),
            ("summary", {"": 1}, "parameter_name_invalid"),
            (
                "summary",
                {"bad\nname": 1},
                "parameter_name_control_character",
            ),
            (
                "summary",
                {"x" * (query.MAX_QUERY_SCALAR_BYTES + 1): 1},
                "parameter_name_too_large",
            ),
        )
        with (
            mock.patch.object(core, "parse_xml") as parse_xml,
            mock.patch.object(core, "read_tree_with_integrity") as read_tree,
            mock.patch.object(core, "tree_snapshot") as tree_snapshot,
        ):
            for command, parameters, reason in cases:
                with self.subTest(command=command, reason=reason):
                    result = query.execute_query(
                        command,
                        Path("must-not-be-read.xml"),
                        parameters,  # type: ignore[arg-type]
                        self.environment(),
                    )
                    self.assertEqual(result.exit_code, 2)
                    self.assertEqual(
                        result.payload["error"]["details"]["reason"],
                        reason,
                    )
        parse_xml.assert_not_called()
        read_tree.assert_not_called()
        tree_snapshot.assert_not_called()

    def test_invalid_command_identifiers_reject_before_tree_access(self) -> None:
        cases = (
            ("bad\ncommand", "command_control_character"),
            (
                "x" * (query.MAX_QUERY_SCALAR_BYTES + 1),
                "command_too_large",
            ),
        )
        with (
            mock.patch.object(core, "parse_xml") as parse_xml,
            mock.patch.object(core, "read_tree_with_integrity") as read_tree,
            mock.patch.object(core, "tree_snapshot") as tree_snapshot,
        ):
            for command, reason in cases:
                with self.subTest(reason=reason):
                    result = query.execute_query(
                        command,
                        Path("must-not-be-read.xml"),
                        {},
                        self.environment(),
                    )
                    self.assertEqual(result.exit_code, 2)
                    self.assertEqual(
                        result.payload["error"]["details"]["reason"],
                        reason,
                    )
        parse_xml.assert_not_called()
        read_tree.assert_not_called()
        tree_snapshot.assert_not_called()

    def test_query_service_is_non_printing(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = query.execute_query(
                "not-a-command",
                Path("must-not-be-read.xml"),
                {},
                self.environment(),
            )
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_execute_parsed_preserves_validation_exit_mapping(self) -> None:
        valid_false = argparse.Namespace(
            func=lambda _: {"valid": False},
        )
        result = application.execute_parsed(
            valid_false,
            self.environment(),
        )
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.payload, {"ok": True, "valid": False})


if __name__ == "__main__":
    unittest.main()
