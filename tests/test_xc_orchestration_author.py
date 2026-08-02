from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUTHOR_SKILL = REPOSITORY_ROOT / "skills" / "xc-orchestration-author"
AUTHOR = AUTHOR_SKILL / "scripts" / "template_builder.py"
RUNTIME = (
    REPOSITORY_ROOT
    / "skills"
    / "xc-orchestration-runtime"
    / "scripts"
    / "orchestration.py"
)
CONTROL_METADATA_FIXTURE = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "orchestration"
    / "control-metadata-conformance-v1.json"
)


class XcOrchestrationAuthorTests(unittest.TestCase):
    def run_json(
        self,
        command: list[str],
        *,
        cwd: Path = REPOSITORY_ROOT,
    ) -> tuple[int, dict[str, Any]]:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertTrue(result.stdout, result.stderr)
        return result.returncode, json.loads(result.stdout)

    def metadata_object(self, flattened: dict[str, str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for qualified, value in flattened.items():
            self.assertTrue(qualified.startswith("metadata."))
            current = result
            parts = qualified.split(".")[1:]
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = value
        return result

    def flow_for_case(self, case: dict[str, Any]) -> dict[str, Any]:
        node = {
            "template_id": "case-node",
            "title": str(case["id"]),
            "type": str(case["node_type"]),
            "role": "case-node",
            "executor": "main",
            "metadata": self.metadata_object(case["metadata"]),
        }
        if case["node_type"] == "composite":
            node["role"] = "dynamic-group"
            node["mode"] = "sequence"
        return {
            "name": str(case["id"]),
            "schema_version": 1,
            "blackboard": {},
            "root": {
                "template_id": "root",
                "title": "Conformance case",
                "type": "composite",
                "role": "root",
                "mode": "sequence",
                "executor": "main",
                "children": [node],
            },
        }

    def normalize_violations(
        self,
        payload: dict[str, Any],
    ) -> list[dict[str, str]]:
        return [
            {"key": item["key"], "code": item["code"]}
            for item in payload["error"]["details"]["violations"]
        ]

    def assert_fixture_expectation(
        self,
        case: dict[str, Any],
        violations: list[dict[str, str]],
    ) -> None:
        if "violations" in case:
            self.assertEqual(violations, case["violations"])
        else:
            self.assertEqual(
                sorted({item["code"] for item in violations}),
                sorted(case["violation_codes"]),
            )

    def initialize_dynamic_group(self, root: Path) -> tuple[Path, str]:
        config = root / "runtime.json"
        config.write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
        flow = {
            "name": "author-runtime-parity",
            "schema_version": 1,
            "blackboard": {},
            "root": {
                "template_id": "root",
                "title": "Author runtime parity",
                "type": "composite",
                "role": "root",
                "mode": "sequence",
                "executor": "main",
                "children": [
                    {
                        "template_id": "dynamic",
                        "title": "Dynamic",
                        "type": "composite",
                        "role": "dynamic-group",
                        "mode": "sequence",
                        "executor": "main",
                    }
                ],
            },
        }
        spec = root / "base-flow.json"
        spec.write_text(json.dumps(flow), encoding="utf-8")
        template = root / "base-template.xml"
        code, built = self.run_json(
            [
                sys.executable,
                str(AUTHOR),
                "build",
                "--spec",
                str(spec),
                "--out",
                str(template),
                "--config",
                str(config),
            ]
        )
        self.assertEqual(code, 0, built)
        runtime_path = root / ".xcoding" / "work-orders" / "parity" / "runtime"
        runtime_path.mkdir(parents=True)
        (root / ".xcoding" / "xc-orchestration-runtime.json").write_text(
            json.dumps({"git": {"auto_commit": False}}) + "\n",
            encoding="utf-8",
        )
        code, initialized = self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "init",
                "--template",
                str(template),
                "--runtime-path",
                str(runtime_path),
                "--work-order-id",
                "author-runtime-parity",
            ]
        )
        self.assertEqual(code, 0, initialized)
        tree = Path(initialized["tree_path"])
        code, found = self.run_json(
            [
                sys.executable,
                str(RUNTIME),
                "find",
                "--tree",
                str(tree),
                "--template-id",
                "dynamic",
            ]
        )
        self.assertEqual(code, 0, found)
        return tree, str(found["nodes"][0]["id"])

    def test_control_metadata_conformance_and_runtime_parity(self) -> None:
        fixture = json.loads(CONTROL_METADATA_FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(fixture["schema_version"], 1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tree, group_id = self.initialize_dynamic_group(root)
            for case in fixture["cases"]:
                with self.subTest(case=case["id"]):
                    spec = root / f"{case['id']}.json"
                    spec.write_text(
                        json.dumps(self.flow_for_case(case)),
                        encoding="utf-8",
                    )
                    author_code, author_payload = self.run_json(
                        [
                            sys.executable,
                            str(AUTHOR),
                            "validate-spec",
                            "--spec",
                            str(spec),
                        ]
                    )
                    if case["valid"]:
                        self.assertEqual(author_code, 0, author_payload)
                        self.assertTrue(author_payload["valid"])
                        output = root / f"{case['id']}.xml"
                        build_code, built = self.run_json(
                            [
                                sys.executable,
                                str(AUTHOR),
                                "build",
                                "--spec",
                                str(spec),
                                "--out",
                                str(output),
                                "--config",
                                str(root / "runtime.json"),
                            ]
                        )
                        self.assertEqual(build_code, 0, built)
                        runtime_code, runtime_payload = self.run_json(
                            [
                                sys.executable,
                                str(RUNTIME),
                                "validate",
                                "--tree",
                                str(output),
                            ]
                        )
                        self.assertEqual(runtime_code, 0, runtime_payload)
                        self.assertTrue(runtime_payload["valid"])
                        continue

                    self.assertEqual(author_code, 2, author_payload)
                    self.assertEqual(
                        author_payload["error"]["code"],
                        "invalid_control_metadata",
                    )
                    author_violations = self.normalize_violations(author_payload)
                    self.assert_fixture_expectation(case, author_violations)

                    output = root / f"rejected-{case['id']}.xml"
                    build_code, build_payload = self.run_json(
                        [
                            sys.executable,
                            str(AUTHOR),
                            "build",
                            "--spec",
                            str(spec),
                            "--out",
                            str(output),
                            "--config",
                            str(root / "runtime.json"),
                        ]
                    )
                    self.assertEqual(build_code, 2, build_payload)
                    self.assertEqual(
                        build_payload["error"]["code"],
                        "invalid_control_metadata",
                    )
                    self.assertFalse(output.exists())

                    runtime_command = [
                        sys.executable,
                        str(RUNTIME),
                        "add-node",
                        "--tree",
                        str(tree),
                        "--parent",
                        group_id,
                        "--logical-key",
                        f"case-{case['id']}",
                        "--title",
                        str(case["id"]),
                        "--type",
                        str(case["node_type"]),
                        "--role",
                        "dynamic-group"
                        if case["node_type"] == "composite"
                        else "case-node",
                        "--executor",
                        "main",
                    ]
                    if case["node_type"] == "composite":
                        runtime_command.extend(["--mode", "sequence"])
                    for key, value in case["metadata"].items():
                        runtime_command.extend(["--metadata", f"{key}={value}"])
                    runtime_code, runtime_payload = self.run_json(runtime_command)
                    self.assertEqual(runtime_code, 2, runtime_payload)
                    self.assertEqual(
                        runtime_payload["error"]["code"],
                        "invalid_control_metadata",
                    )
                    runtime_violations = self.normalize_violations(runtime_payload)
                    self.assertEqual(author_violations, runtime_violations)

    def test_unknown_ordinary_metadata_is_preserved(self) -> None:
        fixture = json.loads(CONTROL_METADATA_FIXTURE.read_text(encoding="utf-8"))
        case = next(
            item
            for item in fixture["cases"]
            if item["id"] == "valid-unknown-ordinary-metadata"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "runtime.json"
            config.write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
            spec = root / "ordinary.json"
            spec.write_text(json.dumps(self.flow_for_case(case)), encoding="utf-8")
            template = root / "ordinary.xml"
            code, built = self.run_json(
                [
                    sys.executable,
                    str(AUTHOR),
                    "build",
                    "--spec",
                    str(spec),
                    "--out",
                    str(template),
                    "--config",
                    str(config),
                ]
            )
            self.assertEqual(code, 0, built)
            workshop = root / ".xcoding"
            workshop.mkdir()
            (workshop / "xc-orchestration-runtime.json").write_text(
                json.dumps({"git": {"auto_commit": False}}) + "\n",
                encoding="utf-8",
            )
            code, initialized = self.run_json(
                [
                    sys.executable,
                    str(RUNTIME),
                    "init",
                    "--template",
                    str(template),
                    "--runtime-path",
                    str(workshop / "work-orders" / "ordinary" / "runtime"),
                    "--work-order-id",
                    "ordinary-metadata",
                ]
            )
            self.assertEqual(code, 0, initialized)
            code, found = self.run_json(
                [
                    sys.executable,
                    str(RUNTIME),
                    "find",
                    "--tree",
                    str(initialized["tree_path"]),
                    "--template-id",
                    "case-node",
                ]
            )
            self.assertEqual(code, 0, found)
            self.assertEqual(
                found["nodes"][0]["attributes"]["metadata.domain.arbitrary"],
                "preserved",
            )

    def test_new_spec_matches_public_template_and_builds_runtime_valid_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generated = root / "flow.json"
            code, created = self.run_json(
                [
                    sys.executable,
                    str(AUTHOR),
                    "new-spec",
                    "--out",
                    str(generated),
                ]
            )
            self.assertEqual(code, 0, created)
            expected = json.loads(
                (AUTHOR_SKILL / "assets" / "templates" / "flow-spec-template.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(json.loads(generated.read_text(encoding="utf-8")), expected)
            code, validated = self.run_json(
                [
                    sys.executable,
                    str(AUTHOR),
                    "validate-spec",
                    "--spec",
                    str(generated),
                ]
            )
            self.assertEqual(code, 0, validated)
            config = root / "runtime.json"
            config.write_text(json.dumps({"git": {"auto_commit": False}}) + "\n", encoding="utf-8")
            template = root / "template.xml"
            code, built = self.run_json(
                [
                    sys.executable,
                    str(AUTHOR),
                    "build",
                    "--spec",
                    str(generated),
                    "--out",
                    str(template),
                    "--config",
                    str(config),
                ]
            )
            self.assertEqual(code, 0, built)
            code, runtime_validation = self.run_json(
                [
                    sys.executable,
                    str(RUNTIME),
                    "validate",
                    "--tree",
                    str(template),
                ]
            )
            self.assertEqual(code, 0, runtime_validation)
            self.assertTrue(runtime_validation["valid"])

    def test_author_production_code_has_no_runtime_private_dependency(self) -> None:
        sources = [
            AUTHOR.read_text(encoding="utf-8"),
            (AUTHOR.parent / "author_core.py").read_text(encoding="utf-8"),
        ]
        combined = "\n".join(sources)
        self.assertNotIn("runtime_core", combined)
        self.assertNotIn('/ "xc-orchestration-runtime" /', combined)
        self.assertNotIn("\\xc-orchestration-runtime\\scripts", combined)


if __name__ == "__main__":
    unittest.main()
