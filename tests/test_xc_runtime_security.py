from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
AUTHOR_CORE_PATH = (
    REPOSITORY_ROOT
    / "skills"
    / "xc-orchestration-author"
    / "scripts"
    / "author_core.py"
)
sys.path.insert(0, str(SOURCE_ROOT))

from xcoding.delegation import DelegationError, validate_node_packet
from xcoding.runtime import application, assignment, core, query, terminal


AUTHOR_SPEC = importlib.util.spec_from_file_location("xc_author_security", AUTHOR_CORE_PATH)
assert AUTHOR_SPEC is not None and AUTHOR_SPEC.loader is not None
AUTHOR_CORE = importlib.util.module_from_spec(AUTHOR_SPEC)
AUTHOR_SPEC.loader.exec_module(AUTHOR_CORE)


class RuntimeSecurityTests(unittest.TestCase):
    WORK_ORDER_ID = "20260914-1200-runtime-security"

    def environment(self) -> application.RuntimeEnvironment:
        return application.RuntimeEnvironment(
            REPOSITORY_ROOT / "src" / "xcoding" / "runtime" / "assets" / "minimal-template.xml"
        )

    def execute(self, *argv: str) -> dict[str, object]:
        result = application.execute(list(argv), self.environment())
        self.assertEqual(result.exit_code, 0, result.payload)
        return result.payload

    def initialize(self, root: Path, *, worker_count: int = 1) -> tuple[Path, list[str]]:
        project = root / "project"
        context = project / ".xcoding"
        context.mkdir(parents=True)
        subprocess.run(["git", "init"], cwd=context, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "XC Test"], cwd=context, check=True)
        subprocess.run(
            ["git", "config", "user.email", "xc-test@example.invalid"],
            cwd=context,
            check=True,
        )
        (context / "xc-orchestration-runtime.json").write_text(
            json.dumps({"git": {"auto_commit": False}}) + "\n",
            encoding="utf-8",
        )
        config = core.load_config(context)
        template_path = project / "worker-template.xml"
        template_root = ET.Element(
            "orchestration",
            {"schema_version": "1", "name": "runtime-security"},
        )
        ET.SubElement(template_root, "blackboard")
        root_node = ET.SubElement(
            template_root,
            "node",
            {
                "template_id": "root",
                "title": "Runtime security",
                "type": "composite",
                "role": "root",
                "mode": "sequence",
                "executor": "main",
            },
        )
        children = ET.SubElement(root_node, "children")
        ET.SubElement(
            children,
            "node",
            {
                "template_id": "source",
                "title": "Source",
                "type": "task",
                "role": "source",
                "executor": "main",
            },
        )
        worker_group = ET.SubElement(
            children,
            "node",
            {
                "template_id": "workers",
                "title": "Workers",
                "type": "composite",
                "role": "worker-group",
                "mode": "parallel" if worker_count > 1 else "sequence",
                "executor": "main",
            },
        )
        worker_children = ET.SubElement(worker_group, "children")
        authorization = json.dumps(
            {
                "capabilities": [
                    {
                        "id": "runtime.terminal.assigned-node",
                        "values": ["block", "complete", "fail"],
                    },
                    {
                        "id": "workbench.write.artifact",
                        "values": ["artifacts/report.md"],
                    },
                ]
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        bindings = json.dumps(
            {
                "decision": {"source": "blackboard", "key": "decision.value"},
                "evidence": {"source": "control-packet", "category": "evidence"},
                "target": {"source": "target-contract"},
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        for index in range(worker_count):
            node = ET.SubElement(
                worker_children,
                "node",
                {
                    "template_id": f"worker-{index + 1}",
                    "title": f"Worker {index + 1}",
                    "type": "task",
                    "role": "runtime-security",
                    "executor": "subagent",
                    "metadata.control_packet.category.evidence.selectors": "[\"bb:source.ids\"]",
                    "metadata.control_packet.category.evidence.min_sources": "0",
                    "metadata.control_packet.category.evidence.artifact_min": "0",
                    "metadata.control_packet.blackboard_keys": "[\"decision.value\"]",
                    "metadata.worker_profile.schema_version": "1",
                    "metadata.worker_profile.owner_skill": "xc-analysis",
                    "metadata.worker_profile.profile_id": "runtime-security",
                    "metadata.worker_profile.security_mode": "enforced",
                    "metadata.worker_profile.context_bindings": bindings,
                    core.DELEGATION_AUTHORIZATION_KEY: authorization,
                },
            )
            for tag, text in (
                ("instructions", "Inspect only the assigned runtime node."),
                ("inputs", "Use the scoped assignment."),
                ("deliverables", "Write the declared report."),
                ("acceptance", "Submit through terminal authority."),
            ):
                ET.SubElement(node, tag).text = text
        core.ensure_managed_metadata(template_root, "template", config)
        core.apply_integrity(template_root, "template", config)
        core.atomic_write_text(
            template_path,
            core.serialize_xml(template_root, "template"),
        )
        initialized = self.execute(
            "init",
            "--template",
            str(template_path),
            "--runtime-path",
            str(context / "work-orders" / self.WORK_ORDER_ID / "runtime"),
            "--work-order-id",
            self.WORK_ORDER_ID,
            "--var",
            "source.ids=[]",
            "--var",
            "decision.value=go",
        )
        tree_path = Path(str(initialized["tree_path"]))
        source = self.execute("next", "--tree", str(tree_path))["ready"][0]
        source_id = str(source["id"])
        self.start(tree_path, source_id)
        self.execute(
            "complete",
            "--tree",
            str(tree_path),
            "--node",
            source_id,
            "--summary",
            "Source evidence ready.",
        )
        self.execute(
            "set",
            "--tree",
            str(tree_path),
            "--set",
            "source.ids=" + json.dumps([source_id], separators=(",", ":")),
        )
        ready = self.execute("next", "--tree", str(tree_path))["ready"]
        assert isinstance(ready, list)
        return tree_path, [str(item["id"]) for item in ready]

    def start(self, tree_path: Path, node_id: str) -> dict[str, object]:
        return self.execute("start", "--tree", str(tree_path), "--node", node_id)

    def assignment(self, tree_path: Path, node_id: str) -> dict[str, object]:
        return self.execute(
            "assignment-packet",
            "--tree",
            str(tree_path),
            "--node",
            node_id,
            "--attempt",
            "1",
        )

    def broker_inputs(self, tree_path: Path) -> tuple[terminal.TerminalBroker, dict[str, object], Path]:
        node_id = str(self.execute("next", "--tree", str(tree_path))["ready"][0]["id"])
        self.start(tree_path, node_id)
        artifact = tree_path.parent.parent / "artifacts" / "report.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        broker = terminal.TerminalBroker()
        capability = broker.issue(
            tree_path=tree_path,
            node_id=node_id,
            attempt=1,
            allowed_operations=["block", "complete", "fail"],
            artifact_bindings={"artifacts/report.md": artifact},
            envelope_sha256="a" * 64,
            prepare_receipt_id="receipt-1",
            prepare_receipt_sha256="b" * 64,
        )
        return broker, {"node_id": node_id, "capability": capability}, artifact

    def test_worker_profile_metadata_runtime_and_author_parity(self) -> None:
        valid = ET.Element(
            "node",
            {
                "type": "task",
                "executor": "subagent",
                "metadata.control_packet.category.evidence.selectors": "[\"bb:sources\"]",
                "metadata.control_packet.category.evidence.min_sources": "0",
                "metadata.control_packet.category.evidence.artifact_min": "0",
                "metadata.control_packet.blackboard_keys": "[\"selected.key\"]",
                "metadata.worker_profile.schema_version": "1",
                "metadata.worker_profile.owner_skill": "xc-analysis",
                "metadata.worker_profile.profile_id": "evidence-worker",
                "metadata.worker_profile.security_mode": "validated-only",
                "metadata.worker_profile.context_bindings": (
                    "{\"decision\":{\"key\":\"selected.key\",\"source\":\"blackboard\"},"
                    "\"evidence\":{\"category\":\"evidence\",\"source\":\"control-packet\"},"
                    "\"target\":{\"source\":\"target-contract\"}}"
                ),
            },
        )
        self.assertEqual(core.validate_control_metadata_for_node(valid), [])
        self.assertEqual(AUTHOR_CORE.validate_control_metadata_for_node(valid), [])

        cases = []
        partial = ET.Element("node", dict(valid.attrib))
        del partial.attrib["metadata.worker_profile.profile_id"]
        cases.append(partial)
        unknown = ET.Element("node", dict(valid.attrib))
        unknown.set("metadata.worker_profile.extra", "x")
        cases.append(unknown)
        wrong_owner = ET.Element("node", dict(valid.attrib))
        wrong_owner.set("executor", "main")
        cases.append(wrong_owner)
        noncanonical = ET.Element("node", dict(valid.attrib))
        noncanonical.set("metadata.worker_profile.context_bindings", "{ \"target\": {\"source\":\"target-contract\"}}")
        cases.append(noncanonical)
        undeclared = ET.Element("node", dict(valid.attrib))
        undeclared.set(
            "metadata.worker_profile.context_bindings",
            "{\"missing\":{\"category\":\"missing\",\"source\":\"control-packet\"}}",
        )
        cases.append(undeclared)
        for node in cases:
            with self.subTest(metadata=dict(node.attrib)):
                runtime_violations = core.validate_control_metadata_for_node(node)
                author_violations = AUTHOR_CORE.validate_control_metadata_for_node(node)
                self.assertTrue(runtime_violations)
                self.assertEqual(runtime_violations, author_violations)

    def test_real_runtime_assignment_matches_delegation_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, nodes = self.initialize(Path(temporary))
            node_id = nodes[0]
            self.assertTrue(node_id.startswith("rt_"), node_id)
            rejected = application.execute(
                [
                    "assignment-packet",
                    "--tree",
                    str(tree_path),
                    "--node",
                    node_id,
                    "--attempt",
                    "1",
                ],
                self.environment(),
            )
            self.assertEqual(rejected.exit_code, 2)
            self.start(tree_path, node_id)
            packet = self.assignment(tree_path, node_id)
            self.assertEqual(
                set(packet),
                {
                    "ok",
                    "schema_version",
                    "kind",
                    "revision",
                    "node_packet",
                    "node_profile_ref",
                    "target_contract",
                    "control_packet",
                    "digests",
                },
            )
            validated = validate_node_packet(packet["node_packet"])
            self.assertEqual(validated["node_id"], node_id)
            with self.assertRaises(DelegationError):
                validate_node_packet({**validated, "node_id": node_id.replace("rt_", "rt-", 1)})
            self.assertEqual(
                packet["digests"]["node_packet_sha256"],
                assignment.canonical_digest(packet["node_packet"]),
            )
            self.assertEqual(
                packet["node_packet"]["authorization"]["capabilities"][0]["id"],
                "runtime.terminal.assigned-node",
            )
            serialized = json.dumps(packet, sort_keys=True)
            self.assertNotIn(str(tree_path), serialized)
            self.assertNotIn("expected_revision", serialized)
            self.assertNotIn("source.ids", json.dumps(packet["node_packet"]["context"]))

            typed = query.execute_query(
                "assignment-packet",
                tree_path,
                {"node": node_id, "attempt": 1},
                self.environment(),
            )
            self.assertEqual(typed.exit_code, 0)
            self.assertEqual(typed.payload, packet)

    def test_terminal_complete_records_nonsecret_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, _ = self.initialize(Path(temporary))
            broker, values, artifact = self.broker_inputs(tree_path)
            capability = values["capability"]
            assert isinstance(capability, terminal.TerminalCapability)
            artifact.write_text("evidence\n", encoding="utf-8")
            result = broker.consume(
                capability,
                {
                    "schema_version": 1,
                    "operation": "complete",
                    "summary": "Implemented runtime security.",
                    "validation": "Focused tests passed.",
                    "artifacts": ["artifacts/report.md"],
                    "check_results": [],
                },
            )
            self.assertEqual(result["terminal_status"], "succeeded")
            self.assertEqual(broker.state(capability), "consumed")
            shown = self.execute(
                "show",
                "--tree",
                str(tree_path),
                "--node",
                str(values["node_id"]),
            )
            record = shown["node"]["result"]["terminal_authorities"][0]
            self.assertEqual(
                record["artifacts"],
                [
                    {
                        "path": "artifacts/report.md",
                        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    }
                ],
            )
            self.assertNotIn("secret", json.dumps(record))
            self.assertIn("<redacted>", repr(capability))
            self.assertNotIn(str(tree_path), json.dumps(result))

    def test_authenticated_invalid_request_consumes_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, _ = self.initialize(Path(temporary))
            broker, values, _ = self.broker_inputs(tree_path)
            capability = values["capability"]
            assert isinstance(capability, terminal.TerminalCapability)
            with self.assertRaises(terminal.TerminalAuthorityError):
                broker.consume(capability, {"schema_version": 1, "operation": "complete"})
            self.assertEqual(broker.state(capability), "consumed")
            shown = self.execute("show", "--tree", str(tree_path), "--node", str(values["node_id"]))
            self.assertEqual(shown["node"]["status"], "running")

    def test_same_capability_race_runs_one_terminal_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, _ = self.initialize(Path(temporary))
            broker, values, _ = self.broker_inputs(tree_path)
            capability = values["capability"]
            assert isinstance(capability, terminal.TerminalCapability)
            barrier = threading.Barrier(3)
            outcomes: list[str] = []

            def consume() -> None:
                barrier.wait()
                try:
                    broker.consume(
                        capability,
                        {
                            "schema_version": 1,
                            "operation": "fail",
                            "reason": "one terminal result",
                            "artifacts": [],
                        },
                    )
                    outcomes.append("success")
                except terminal.TerminalAuthorityError:
                    outcomes.append("rejected")

            threads = [threading.Thread(target=consume) for _ in range(2)]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join()
            self.assertCountEqual(outcomes, ["success", "rejected"])
            shown = self.execute("show", "--tree", str(tree_path), "--node", str(values["node_id"]))
            self.assertEqual(shown["node"]["status"], "failed")
            self.assertEqual(len(shown["node"]["result"]["terminal_authorities"]), 1)

    def test_different_nodes_use_independent_authorities_and_tree_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, nodes = self.initialize(Path(temporary), worker_count=2)
            broker = terminal.TerminalBroker()
            capabilities: list[terminal.TerminalCapability] = []
            for index, node_id in enumerate(nodes):
                self.start(tree_path, node_id)
                capabilities.append(
                    broker.issue(
                        tree_path=tree_path,
                        node_id=node_id,
                        attempt=1,
                        allowed_operations=["fail"],
                        artifact_bindings={},
                        envelope_sha256=f"{index + 1}" * 64,
                        prepare_receipt_id=f"receipt-{index + 1}",
                        prepare_receipt_sha256=f"{index + 3}" * 64,
                    )
                )
            outcomes: list[str] = []

            def consume(index: int) -> None:
                result = broker.consume(
                    capabilities[index],
                    {
                        "schema_version": 1,
                        "operation": "fail",
                        "reason": f"node {index}",
                        "artifacts": [],
                    },
                )
                outcomes.append(str(result["node_id"]))

            threads = [threading.Thread(target=consume, args=(index,)) for index in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertCountEqual(outcomes, nodes)
            for node_id in nodes:
                shown = self.execute("show", "--tree", str(tree_path), "--node", node_id)
                self.assertEqual(shown["node"]["status"], "failed")

    def test_checkpoint_failure_restores_runtime_and_consumes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, _ = self.initialize(Path(temporary))
            broker, values, _ = self.broker_inputs(tree_path)
            capability = values["capability"]
            assert isinstance(capability, terminal.TerminalCapability)
            before = tree_path.read_bytes()
            with mock.patch.object(
                application,
                "write_terminal_runtime",
                side_effect=core.RuntimeErrorBase("checkpoint failed"),
            ):
                with self.assertRaises(core.RuntimeErrorBase):
                    broker.consume(
                        capability,
                        {
                            "schema_version": 1,
                            "operation": "fail",
                            "reason": "checkpoint failure",
                            "artifacts": [],
                        },
                    )
            self.assertEqual(tree_path.read_bytes(), before)
            self.assertEqual(broker.state(capability), "consumed")

    def test_reissue_is_rejected_while_checkpoint_failure_is_in_flight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, _ = self.initialize(Path(temporary))
            broker, values, _ = self.broker_inputs(tree_path)
            capability = values["capability"]
            assert isinstance(capability, terminal.TerminalCapability)
            entered = threading.Event()
            release = threading.Event()
            consume_errors: list[str] = []
            issue_errors: list[str] = []

            def failed_checkpoint(*args, **kwargs):
                entered.set()
                self.assertTrue(release.wait(5))
                raise core.RuntimeErrorBase("checkpoint failed")

            def consume() -> None:
                try:
                    broker.consume(
                        capability,
                        {
                            "schema_version": 1,
                            "operation": "fail",
                            "reason": "checkpoint failure",
                            "artifacts": [],
                        },
                    )
                except core.RuntimeErrorBase as exc:
                    consume_errors.append(exc.code)

            def issue() -> None:
                try:
                    broker.issue(
                        tree_path=tree_path,
                        node_id=str(values["node_id"]),
                        attempt=1,
                        allowed_operations=["fail"],
                        artifact_bindings={},
                        envelope_sha256="c" * 64,
                        prepare_receipt_id="receipt-2",
                        prepare_receipt_sha256="d" * 64,
                    )
                except terminal.TerminalAuthorityError as exc:
                    issue_errors.append(str(exc.details["reason"]))

            before = tree_path.read_bytes()
            with mock.patch.object(
                application,
                "write_terminal_runtime",
                side_effect=failed_checkpoint,
            ):
                consumer = threading.Thread(target=consume)
                consumer.start()
                self.assertTrue(entered.wait(5))
                issuer = threading.Thread(target=issue)
                issuer.start()
                issuer.join(5)
                release.set()
                consumer.join(5)
                self.assertFalse(issuer.is_alive())
                self.assertFalse(consumer.is_alive())
            self.assertEqual(issue_errors, ["authority_already_active"])
            self.assertTrue(consume_errors)
            self.assertEqual(broker.state(capability), "consumed")
            self.assertEqual(tree_path.read_bytes(), before)

    def test_issue_rejects_invalid_ttl_and_missing_artifact_consumes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, nodes = self.initialize(Path(temporary))
            node_id = nodes[0]
            self.start(tree_path, node_id)
            artifact = tree_path.parent.parent / "artifacts" / "report.md"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            broker = terminal.TerminalBroker()
            common = {
                "tree_path": tree_path,
                "node_id": node_id,
                "attempt": 1,
                "allowed_operations": ["complete"],
                "artifact_bindings": {"artifacts/report.md": artifact},
                "envelope_sha256": "a" * 64,
                "prepare_receipt_id": "receipt-1",
                "prepare_receipt_sha256": "b" * 64,
            }
            with self.assertRaises(terminal.TerminalAuthorityError):
                broker.issue(**common, ttl_seconds=601)
            capability = broker.issue(**common)
            with self.assertRaises(terminal.TerminalAuthorityError):
                broker.consume(
                    capability,
                    {
                        "schema_version": 1,
                        "operation": "complete",
                        "summary": "Done.",
                        "validation": "Checked.",
                        "artifacts": ["artifacts/report.md"],
                        "check_results": [],
                    },
                )
            self.assertEqual(broker.state(capability), "consumed")
            shown = self.execute("show", "--tree", str(tree_path), "--node", node_id)
            self.assertEqual(shown["node"]["status"], "running")

    def test_issue_requires_exact_workbench_artifact_binding_and_portable_logical_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, nodes = self.initialize(Path(temporary))
            node_id = nodes[0]
            self.start(tree_path, node_id)
            expected = tree_path.parent.parent / "artifacts" / "report.md"
            wrong_bindings = (
                tree_path.parent.parent / "goal.md",
                tree_path.parents[2] / "another-work-order" / "artifacts" / "report.md",
                tree_path,
                tree_path.parents[3] / "other-work-order-evidence.md",
            )
            broker = terminal.TerminalBroker()
            common = {
                "tree_path": tree_path,
                "node_id": node_id,
                "attempt": 1,
                "envelope_sha256": "a" * 64,
                "prepare_receipt_id": "receipt-1",
                "prepare_receipt_sha256": "b" * 64,
            }
            for operation in ("block", "complete", "fail"):
                for unrelated in wrong_bindings:
                    with self.subTest(operation=operation, unrelated=unrelated):
                        with self.assertRaises(terminal.TerminalAuthorityError) as raised:
                            broker.issue(
                                **common,
                                allowed_operations=[operation],
                                artifact_bindings={"artifacts/report.md": unrelated},
                            )
                        self.assertEqual(
                            raised.exception.details["reason"],
                            "artifact_binding_mismatch",
                        )
            for logical in (
                "artifacts/carrier.txt:stream",
                "artifacts/NUL.txt",
                "artifacts/trailing.",
                "artifacts/trailing ",
            ):
                with self.subTest(logical=logical):
                    with self.assertRaises(terminal.TerminalAuthorityError) as raised:
                        broker.issue(
                            **common,
                            allowed_operations=["fail"],
                            artifact_bindings={logical: expected},
                        )
                    self.assertEqual(raised.exception.details["reason"], "invalid_artifact_path")

            expected.parent.mkdir(parents=True, exist_ok=True)
            expected.write_text("report\n", encoding="utf-8")
            original_reparse = terminal._is_reparse

            def marked_reparse(path: Path) -> bool:
                return path == expected or original_reparse(path)

            with mock.patch.object(terminal, "_is_reparse", side_effect=marked_reparse):
                with self.assertRaises(terminal.TerminalAuthorityError) as raised:
                    broker.issue(
                        **common,
                        allowed_operations=["fail"],
                        artifact_bindings={"artifacts/report.md": expected},
                    )
            self.assertEqual(raised.exception.details["reason"], "artifact_reparse_forbidden")

    def test_consuming_authority_blocks_reissue_until_request_returns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, _ = self.initialize(Path(temporary))
            broker, values, artifact = self.broker_inputs(tree_path)
            capability = values["capability"]
            assert isinstance(capability, terminal.TerminalCapability)
            entered = threading.Event()
            release = threading.Event()
            outcomes: list[str] = []
            original_request = terminal._request

            def paused_request(value: object) -> dict[str, object]:
                entered.set()
                self.assertTrue(release.wait(5))
                return original_request(value)

            def consume() -> None:
                try:
                    broker.consume(capability, {"schema_version": 1, "operation": "complete"})
                except terminal.TerminalAuthorityError as exc:
                    outcomes.append(str(exc.details["reason"]))

            with mock.patch.object(terminal, "_request", side_effect=paused_request):
                worker = threading.Thread(target=consume)
                worker.start()
                self.assertTrue(entered.wait(5))
                with self.assertRaises(terminal.TerminalAuthorityError) as raised:
                    broker.issue(
                        tree_path=tree_path,
                        node_id=str(values["node_id"]),
                        attempt=1,
                        allowed_operations=["block", "complete", "fail"],
                        artifact_bindings={"artifacts/report.md": artifact},
                        envelope_sha256="c" * 64,
                        prepare_receipt_id="receipt-2",
                        prepare_receipt_sha256="d" * 64,
                    )
                self.assertEqual(raised.exception.details["reason"], "authority_already_active")
                release.set()
                worker.join(5)
                self.assertFalse(worker.is_alive())
            self.assertEqual(outcomes, ["invalid_request_shape"])
            self.assertEqual(broker.state(capability), "consumed")
            replacement = broker.issue(
                tree_path=tree_path,
                node_id=str(values["node_id"]),
                attempt=1,
                allowed_operations=["fail"],
                artifact_bindings={},
                envelope_sha256="e" * 64,
                prepare_receipt_id="receipt-3",
                prepare_receipt_sha256="f" * 64,
            )
            broker.revoke(replacement)

    def test_reissue_is_rejected_during_unauthorized_and_policy_rejected_requests(self) -> None:
        cases = (
            (
                ["fail"],
                {
                    "schema_version": 1,
                    "operation": "complete",
                    "summary": "Done.",
                    "validation": "Checked.",
                    "artifacts": [],
                    "check_results": [],
                },
            ),
            (
                ["complete"],
                {
                    "schema_version": 1,
                    "operation": "complete",
                    "summary": "Done.",
                    "validation": "Checked.",
                    "artifacts": [],
                    "check_results": [
                        {
                            "schema_version": 1,
                            "check": "undeclared-check",
                            "ok": True,
                            "subject": "local",
                            "facts": {},
                        }
                    ],
                },
            ),
        )
        for allowed_operations, request in cases:
            with self.subTest(allowed_operations=allowed_operations):
                with tempfile.TemporaryDirectory() as temporary:
                    tree_path, nodes = self.initialize(Path(temporary))
                    node_id = nodes[0]
                    self.start(tree_path, node_id)
                    broker = terminal.TerminalBroker()
                    capability = broker.issue(
                        tree_path=tree_path,
                        node_id=node_id,
                        attempt=1,
                        allowed_operations=allowed_operations,
                        artifact_bindings={},
                        envelope_sha256="a" * 64,
                        prepare_receipt_id="receipt-1",
                        prepare_receipt_sha256="b" * 64,
                    )
                    entered = threading.Event()
                    release = threading.Event()
                    outcomes: list[str] = []
                    original_request = terminal._request

                    def paused_request(value: object) -> dict[str, object]:
                        entered.set()
                        self.assertTrue(release.wait(5))
                        return original_request(value)

                    def consume() -> None:
                        try:
                            broker.consume(capability, request)
                        except core.RuntimeErrorBase as exc:
                            outcomes.append(exc.code)

                    before = tree_path.read_bytes()
                    with mock.patch.object(terminal, "_request", side_effect=paused_request):
                        worker = threading.Thread(target=consume)
                        worker.start()
                        self.assertTrue(entered.wait(5))
                        with self.assertRaises(terminal.TerminalAuthorityError) as raised:
                            broker.issue(
                                tree_path=tree_path,
                                node_id=node_id,
                                attempt=1,
                                allowed_operations=allowed_operations,
                                artifact_bindings={},
                                envelope_sha256="c" * 64,
                                prepare_receipt_id="receipt-2",
                                prepare_receipt_sha256="d" * 64,
                            )
                        self.assertEqual(
                            raised.exception.details["reason"],
                            "authority_already_active",
                        )
                        release.set()
                        worker.join(5)
                        self.assertFalse(worker.is_alive())
                    self.assertTrue(outcomes)
                    self.assertEqual(broker.state(capability), "consumed")
                    self.assertEqual(tree_path.read_bytes(), before)
                    shown = self.execute("show", "--tree", str(tree_path), "--node", node_id)
                    self.assertEqual(shown["node"]["status"], "running")

    def test_check_results_are_strictly_bounded_and_invalid_input_consumes(self) -> None:
        exact_overhead = len(assignment.canonical_json_bytes({"value": ""}))
        exact = {"value": "x" * (terminal.MAX_CHECK_RESULT_BYTES - exact_overhead)}
        self.assertEqual(
            len(assignment.canonical_json_bytes(exact)),
            terminal.MAX_CHECK_RESULT_BYTES,
        )
        normalized = terminal._request(
            {
                "schema_version": 1,
                "operation": "complete",
                "summary": "Done.",
                "validation": "Checked.",
                "artifacts": [],
                "check_results": [exact],
            }
        )
        self.assertEqual(normalized["check_results"], [exact])

        too_large = {"value": exact["value"] + "x"}
        deep: dict[str, object] = {}
        nested: dict[str, object] = deep
        for _ in range(40):
            child: dict[str, object] = {}
            nested["child"] = child
            nested = child
        cyclic: dict[str, object] = {}
        cyclic["self"] = cyclic
        invalid_items = [
            too_large,
            deep,
            cyclic,
            {1: "non-string-key"},
            {"value": object()},
            {"value": float("nan")},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, nodes = self.initialize(Path(temporary), worker_count=len(invalid_items))
            broker = terminal.TerminalBroker()
            for node_id, item in zip(nodes, invalid_items, strict=True):
                with self.subTest(item_type=type(next(iter(item.values()))).__name__):
                    self.start(tree_path, node_id)
                    capability = broker.issue(
                        tree_path=tree_path,
                        node_id=node_id,
                        attempt=1,
                        allowed_operations=["complete"],
                        artifact_bindings={},
                        envelope_sha256="a" * 64,
                        prepare_receipt_id="receipt-1",
                        prepare_receipt_sha256="b" * 64,
                    )
                    before = tree_path.read_bytes()
                    with self.assertRaises(terminal.TerminalAuthorityError) as raised:
                        broker.consume(
                            capability,
                            {
                                "schema_version": 1,
                                "operation": "complete",
                                "summary": "Done.",
                                "validation": "Checked.",
                                "artifacts": [],
                                "check_results": [item],
                            },
                        )
                    self.assertEqual(raised.exception.details["reason"], "invalid_request_field")
                    self.assertEqual(broker.state(capability), "consumed")
                    self.assertEqual(tree_path.read_bytes(), before)
                    shown = self.execute("show", "--tree", str(tree_path), "--node", node_id)
                    self.assertEqual(shown["node"]["status"], "running")

        with self.assertRaises(terminal.TerminalAuthorityError) as raised:
            terminal._request(
                {
                    "schema_version": 1,
                    "operation": "complete",
                    "summary": "Done.",
                    "validation": "Checked.",
                    "artifacts": [],
                    "check_results": [exact, exact, exact, exact],
                }
            )
        self.assertEqual(raised.exception.details["reason"], "invalid_request_field")

        too_many_nodes = [
            {f"k{index}": False for index in range(128)}
            for _ in range(17)
        ]
        with self.assertRaises(terminal.TerminalAuthorityError) as raised:
            terminal._request(
                {
                    "schema_version": 1,
                    "operation": "complete",
                    "summary": "Done.",
                    "validation": "Checked.",
                    "artifacts": [],
                    "check_results": too_many_nodes,
                }
            )
        self.assertEqual(raised.exception.details["reason"], "invalid_request_field")

    def test_replaced_artifact_is_rejected_and_consumes_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, nodes = self.initialize(Path(temporary))
            node_id = nodes[0]
            self.start(tree_path, node_id)
            artifact = tree_path.parent.parent / "artifacts" / "report.md"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text("issued\n", encoding="utf-8")
            broker = terminal.TerminalBroker()
            capability = broker.issue(
                tree_path=tree_path,
                node_id=node_id,
                attempt=1,
                allowed_operations=["complete"],
                artifact_bindings={"artifacts/report.md": artifact},
                envelope_sha256="a" * 64,
                prepare_receipt_id="receipt-1",
                prepare_receipt_sha256="b" * 64,
            )
            replacement = artifact.with_name("replacement.md")
            replacement.write_text("replacement\n", encoding="utf-8")
            replacement.replace(artifact)
            with self.assertRaises(terminal.TerminalAuthorityError) as raised:
                broker.consume(
                    capability,
                    {
                        "schema_version": 1,
                        "operation": "complete",
                        "summary": "Done.",
                        "validation": "Checked.",
                        "artifacts": ["artifacts/report.md"],
                        "check_results": [],
                    },
                )
            self.assertEqual(raised.exception.details["reason"], "artifact_replaced")
            self.assertEqual(broker.state(capability), "consumed")

    def test_revoke_expiry_and_unrelated_revision_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, nodes = self.initialize(Path(temporary))
            node_id = nodes[0]
            self.start(tree_path, node_id)
            artifact = tree_path.parent.parent / "artifacts" / "report.md"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            clock = [10.0]
            broker = terminal.TerminalBroker(monotonic=lambda: clock[0])

            def issue(ttl: int = 300) -> terminal.TerminalCapability:
                return broker.issue(
                    tree_path=tree_path,
                    node_id=node_id,
                    attempt=1,
                    allowed_operations=["fail"],
                    artifact_bindings={},
                    envelope_sha256="a" * 64,
                    prepare_receipt_id="receipt-1",
                    prepare_receipt_sha256="b" * 64,
                    ttl_seconds=ttl,
                )

            revoked = issue()
            broker.revoke(revoked)
            self.assertEqual(broker.state(revoked), "revoked")
            with self.assertRaises(terminal.TerminalAuthorityError):
                broker.consume(
                    revoked,
                    {"schema_version": 1, "operation": "fail", "reason": "x", "artifacts": []},
                )

            expired = issue(ttl=1)
            clock[0] += 2
            self.assertEqual(broker.state(expired), "expired")
            with self.assertRaises(terminal.TerminalAuthorityError):
                broker.consume(
                    expired,
                    {"schema_version": 1, "operation": "fail", "reason": "x", "artifacts": []},
                )

            active = issue()
            self.execute(
                "set",
                "--tree",
                str(tree_path),
                "--set",
                "unrelated.revision=changed",
            )
            consumed = broker.consume(
                active,
                {
                    "schema_version": 1,
                    "operation": "fail",
                    "reason": "unrelated revision is allowed",
                    "artifacts": [],
                },
            )
            self.assertEqual(consumed["terminal_status"], "failed")

    def test_block_record_survives_unblock_and_second_terminal_use(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, nodes = self.initialize(Path(temporary))
            node_id = nodes[0]
            self.start(tree_path, node_id)
            artifact = tree_path.parent.parent / "artifacts" / "report.md"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text("stable\n", encoding="utf-8")
            broker = terminal.TerminalBroker()

            def issue() -> terminal.TerminalCapability:
                return broker.issue(
                    tree_path=tree_path,
                    node_id=node_id,
                    attempt=1,
                    allowed_operations=["block", "complete"],
                    artifact_bindings={"artifacts/report.md": artifact},
                    envelope_sha256="a" * 64,
                    prepare_receipt_id="receipt-1",
                    prepare_receipt_sha256="b" * 64,
                )

            broker.consume(
                issue(),
                {
                    "schema_version": 1,
                    "operation": "block",
                    "reason": "wait",
                    "artifacts": ["artifacts/report.md"],
                },
            )
            self.execute("unblock", "--tree", str(tree_path), "--node", node_id)
            self.start(tree_path, node_id)
            broker.consume(
                issue(),
                {
                    "schema_version": 1,
                    "operation": "complete",
                    "summary": "Done.",
                    "validation": "Checked.",
                    "artifacts": ["artifacts/report.md"],
                    "check_results": [],
                },
            )
            shown = self.execute("show", "--tree", str(tree_path), "--node", node_id)
            result = shown["node"]["result"]
            self.assertEqual(result["artifacts"], [str(artifact.resolve())])
            self.assertEqual(
                [item["operation"] for item in result["terminal_authorities"]],
                ["block", "complete"],
            )

    def test_failed_terminal_record_moves_with_retry_attempt_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, _ = self.initialize(Path(temporary))
            broker, values, _ = self.broker_inputs(tree_path)
            capability = values["capability"]
            assert isinstance(capability, terminal.TerminalCapability)
            broker.consume(
                capability,
                {
                    "schema_version": 1,
                    "operation": "fail",
                    "reason": "retryable failure",
                    "artifacts": [],
                },
            )
            node_id = str(values["node_id"])
            self.execute(
                "retry-failed",
                "--tree",
                str(tree_path),
                "--node",
                node_id,
                "--reason",
                "retry approved",
            )
            shown = self.execute("show", "--tree", str(tree_path), "--node", node_id)
            self.assertEqual(shown["node"]["attempt"], 2)
            record = shown["node"]["attempts"][0]["result"]["terminal_authorities"][0]
            self.assertEqual(record["attempt"], 1)
            self.assertEqual(record["operation"], "fail")
            validated = self.execute("validate", "--tree", str(tree_path))
            self.assertTrue(validated["valid"])

    def test_unblock_then_complete_does_not_duplicate_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree_path, nodes = self.initialize(Path(temporary))
            node_id = nodes[0]
            artifact = str(tree_path.parent.parent / "artifacts" / "same.md")
            self.start(tree_path, node_id)
            self.execute(
                "block",
                "--tree",
                str(tree_path),
                "--node",
                node_id,
                "--reason",
                "wait",
                "--artifact",
                artifact,
            )
            self.execute("unblock", "--tree", str(tree_path), "--node", node_id)
            self.start(tree_path, node_id)
            self.execute(
                "complete",
                "--tree",
                str(tree_path),
                "--node",
                node_id,
                "--artifact",
                artifact,
            )
            shown = self.execute("show", "--tree", str(tree_path), "--node", node_id)
            self.assertEqual(shown["node"]["result"]["artifacts"], [artifact])


if __name__ == "__main__":
    unittest.main()
