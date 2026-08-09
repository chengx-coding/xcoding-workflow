from __future__ import annotations

import argparse
import builtins
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "model_robust_workflow"
SCENARIOS = FIXTURE_ROOT / "scenarios-v1.json"
HISTORICAL_MANIFEST = FIXTURE_ROOT / "baseline-v1.json"
CURRENT_MANIFEST = FIXTURE_ROOT / "post-change-v1.json"
RUNTIME = REPOSITORY_ROOT / "tests" / "runtime_cli.py"
OPEN_WORK_ORDER = REPOSITORY_ROOT / "skills" / "xc-open-work-order" / "scripts" / "open_work_order.py"
RENDER = REPOSITORY_ROOT / "skills" / "xc-document" / "scripts" / "render_document.py"
VALIDATE = REPOSITORY_ROOT / "skills" / "xc-document" / "scripts" / "validate_document.py"
WORK_ORDER_TEMPLATE = REPOSITORY_ROOT / "skills" / "xc-work" / "assets" / "work-order-template.xml"
DOCUMENT_EVOLUTION_TEMPLATE = (
    REPOSITORY_ROOT / "skills" / "xc-document-evolution" / "assets" / "document-evolution-template.xml"
)
DOCUMENT_TEMPLATES = REPOSITORY_ROOT / "skills" / "xc-document" / "assets" / "templates"
NORMALIZATION_VERSION = 1
HISTORICAL_MANIFEST_ROLE = "historical-pre-change"
CURRENT_MANIFEST_ROLE = "current-post-change"
HISTORICAL_MANIFEST_ID = "model-robust-workflow-baseline-v1"
CURRENT_MANIFEST_ID = "model-robust-workflow-post-change-v1"
HISTORICAL_MANIFEST_SHA256 = "4bc5af9d9d11914c236761adf1015979af52a15210978271b8407360ad6e881d"
COUNTED_RUNTIME_COMMANDS = {
    "init",
    "set",
    "find",
    "embed-subtree",
    "add-node",
    "control-packet",
    "next",
    "start",
    "complete",
    "summary",
}
TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)
SHA256_PATTERN = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")
INPUT_PATHS = (
    "tests/fixtures/model_robust_workflow/scenarios-v1.json",
    "tests/workflow_scenario_harness.py",
    "tests/test_xc_workflow_governance.py",
    "skills/xc-work/scripts/classify.py",
    "skills/xc-work/scripts/classify_governance.py",
    "skills/xc-open-work-order/scripts/open_work_order.py",
    "skills/xc-orchestration-runtime/scripts/orchestration.py",
    "tests/runtime_cli.py",
    "src/xcoding/runtime/application.py",
    "src/xcoding/runtime/commands.py",
    "src/xcoding/runtime/__init__.py",
    "src/xcoding/runtime/core.py",
    "src/xcoding/runtime/query.py",
    "src/xcoding/runtime/assets/minimal-template.xml",
    "src/xcoding/cli.py",
    "skills/xc-work/assets/work-order-template.xml",
    "skills/xc-document-evolution/assets/document-evolution-template.xml",
    "skills/xc-document/scripts/render_document.py",
    "skills/xc-document/scripts/validate_document.py",
    "skills/xc-document/assets/templates/work-order-goal.md",
    "skills/xc-document/assets/templates/work-order-analysis.md",
    "skills/xc-document/assets/templates/work-order-solution.md",
    "skills/xc-document/assets/templates/work-order-result.md",
    "skills/xc-document/assets/templates/node-artifact.md",
)
PROFILE_DOCUMENTS = {
    "T1-M": ("work-order-goal", "work-order-result"),
    "T2": ("work-order-goal", "work-order-analysis", "work-order-result"),
    "T3": (
        "work-order-goal",
        "work-order-analysis",
        "work-order-solution",
        "work-order-result",
    ),
    "T4": (
        "work-order-goal",
        "work-order-analysis",
        "work-order-solution",
        "work-order-result",
    ),
}
PROFILE_WORKERS = {
    "T1-M": (0, 0),
    "T2": (0, 0),
    "T3": (1, 1),
    "T4": (3, 2),
}
DOCUMENT_GROUPS = {
    "work-order-goal": "goal-document",
    "work-order-analysis": "analysis-group",
    "work-order-solution": "work-order-solution-document",
    "work-order-result": "result-document",
}
DOCUMENT_PATHS = {
    "work-order-goal": "goal.md",
    "work-order-analysis": "analysis.md",
    "work-order-solution": "solution.md",
    "work-order-result": "result.md",
}
DOCUMENT_HEADINGS = {
    "work-order-goal": {
        "document_title": "Work Order Goal",
        "requested_outcome_heading": "Requested Outcome",
        "scope_and_constraints_heading": "Scope and Constraints",
        "acceptance_conditions_heading": "Acceptance Conditions",
    },
    "work-order-analysis": {
        "document_title": "Work Order Analysis",
        "evidence_and_current_state_heading": "Evidence and Current State",
        "reconciliation_heading": "Reconciliation",
        "impact_and_risks_heading": "Impact and Risks",
        "alternatives_heading": "Alternatives",
    },
    "work-order-solution": {
        "document_title": "Work Order Solution",
        "selected_change_heading": "Selected Change",
        "feature_baseline_impact_heading": "Feature Baseline Impact",
        "implementation_and_migration_strategy_heading": "Implementation and Migration Strategy",
        "verification_strategy_heading": "Verification Strategy",
    },
    "work-order-result": {
        "document_title": "Work Order Result",
        "actual_changes_heading": "Actual Changes",
        "validation_evidence_heading": "Validation Evidence",
        "baseline_synchronization_heading": "Baseline Synchronization",
        "deviations_and_residual_risks_heading": "Deviations and Residual Risks",
    },
}


class HarnessError(RuntimeError):
    pass


class HarnessBoundaryViolation(HarnessError):
    """A measured attempt to bypass the harness runtime-access policy."""

    def __init__(self, operation: str, transcript: "RuntimeTranscript") -> None:
        self.operation = operation
        self.snapshot_calls = transcript.snapshot_calls
        self.direct_runtime_xml_reads = transcript.direct_runtime_xml_reads
        super().__init__(
            f"forbidden harness operation rejected: {operation} "
            f"(snapshot_calls={self.snapshot_calls}, "
            f"direct_runtime_xml_reads={self.direct_runtime_xml_reads})"
        )


class HarnessInstrumentation:
    """Process-local guards for managed runtime XML and snapshot access."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tree_owners: dict[Path, RuntimeTranscript] = {}
        self._active = False
        self.snapshot_calls = 0
        self.direct_runtime_xml_reads = 0

    def register_tree(self, tree: Path, transcript: "RuntimeTranscript") -> None:
        with self._lock:
            self._tree_owners[tree.resolve()] = transcript

    def reject_snapshot(self, transcript: "RuntimeTranscript") -> None:
        with self._lock:
            self.snapshot_calls += 1
            transcript.snapshot_calls += 1
        raise HarnessBoundaryViolation("snapshot", transcript)

    def _guard_read(self, target: object, mode: object) -> None:
        if isinstance(target, int):
            return
        try:
            path = Path(os.fspath(target)).resolve()
        except (TypeError, ValueError, OSError):
            return
        if isinstance(mode, int):
            access_mode = mode & (os.O_WRONLY | os.O_RDWR)
            reads = access_mode != os.O_WRONLY
        else:
            text_mode = str(mode or "r")
            reads = "r" in text_mode or not any(flag in text_mode for flag in "wax")
        if not reads:
            return
        with self._lock:
            transcript = self._tree_owners.get(path)
            if transcript is None:
                return
            self.direct_runtime_xml_reads += 1
            transcript.direct_runtime_xml_reads += 1
        raise HarnessBoundaryViolation("direct-runtime-xml-read", transcript)

    @contextmanager
    def enforce(self) -> Iterable[None]:
        with self._lock:
            if self._active:
                raise HarnessError("harness instrumentation is already active")
            self._active = True
        original_builtin_open = builtins.open
        original_io_open = io.open
        original_os_open = os.open

        def guarded_builtin_open(file: object, *args: object, **kwargs: object) -> Any:
            mode = args[0] if args else kwargs.get("mode", "r")
            self._guard_read(file, mode)
            return original_builtin_open(file, *args, **kwargs)

        def guarded_io_open(file: object, *args: object, **kwargs: object) -> Any:
            mode = args[0] if args else kwargs.get("mode", "r")
            self._guard_read(file, mode)
            return original_io_open(file, *args, **kwargs)

        def guarded_os_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
            self._guard_read(path, flags)
            return original_os_open(path, flags, *args, **kwargs)

        builtins.open = guarded_builtin_open
        io.open = guarded_io_open
        os.open = guarded_os_open
        try:
            yield
        finally:
            builtins.open = original_builtin_open
            io.open = original_io_open
            os.open = original_os_open
            with self._lock:
                self._active = False


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_json(value: object) -> str:
    return sha256_bytes(compact_json(value).encode("utf-8"))


def normalize_string(value: str, temporary_root: Path | None = None) -> str:
    replacements: list[tuple[str, str]] = []
    if temporary_root is not None:
        resolved = str(temporary_root.resolve())
        replacements.extend(
            [
                (resolved, "<TEMP_ROOT>"),
                (resolved.replace("\\", "/"), "<TEMP_ROOT>"),
            ]
        )
    repository = str(REPOSITORY_ROOT.resolve())
    replacements.extend(
        [
            (repository, "<REPOSITORY_ROOT>"),
            (repository.replace("\\", "/"), "<REPOSITORY_ROOT>"),
        ]
    )
    normalized = value
    for source, target in replacements:
        normalized = normalized.replace(source, target)
    normalized = TIMESTAMP_PATTERN.sub("<TIMESTAMP>", normalized)
    normalized = SHA256_PATTERN.sub("<SHA256>", normalized)
    return normalized


def normalize_payload(value: object, temporary_root: Path | None = None) -> object:
    if isinstance(value, dict):
        return {
            key: normalize_payload(item, temporary_root)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [normalize_payload(item, temporary_root) for item in value]
    if isinstance(value, str):
        return normalize_string(value, temporary_root)
    return value


def input_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in INPUT_PATHS:
        path = REPOSITORY_ROOT / relative
        if not path.is_file():
            raise HarnessError(f"baseline input is missing: {relative}")
        hashes[relative] = sha256_bytes(path.read_bytes())
    return hashes


def run_process(
    command: list[str],
    *,
    cwd: Path,
    expect_json: bool = True,
    runtime_transcript: "RuntimeTranscript | None" = None,
) -> dict[str, object] | str:
    if len(command) >= 3:
        try:
            invokes_runtime = Path(command[1]).resolve() == RUNTIME.resolve()
        except (OSError, ValueError):
            invokes_runtime = False
        if invokes_runtime:
            if runtime_transcript is None:
                raise HarnessError("runtime CLI must be invoked through RuntimeTranscript")
            if command[2] == "snapshot":
                runtime_transcript.instrumentation.reject_snapshot(runtime_transcript)
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        raise HarnessError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"{result.stderr or result.stdout}"
        )
    if not expect_json:
        return result.stdout.strip()
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise HarnessError(f"command did not emit JSON: {' '.join(command)}") from exc
    if not isinstance(payload, dict):
        raise HarnessError(f"command emitted a non-object JSON result: {' '.join(command)}")
    return payload


def run_git(repository: Path, *args: str) -> str:
    return str(
        run_process(
            ["git", *args],
            cwd=repository,
            expect_json=False,
        )
    )


def repository_head() -> str:
    return run_git(REPOSITORY_ROOT, "rev-parse", "HEAD")


def load_scenarios() -> dict[str, dict[str, object]]:
    payload = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    return {str(item["id"]): item for item in payload["scenarios"]}


class RuntimeTranscript:
    def __init__(
        self,
        project: Path,
        temporary_root: Path,
        instrumentation: HarnessInstrumentation,
    ) -> None:
        self.project = project
        self.temporary_root = temporary_root
        self.instrumentation = instrumentation
        self.context_bytes = 0
        self.runtime_calls = 0
        self.explicit_transitions = 0
        self.delegations = 0
        self.subagent_delegations = 0
        self.tool_delegations = 0
        self.terminal_operations = 0
        self.gates = 0
        self.artifacts = 0
        self.documents = 0
        self.snapshot_calls = 0
        self.direct_runtime_xml_reads = 0

    def invoke(
        self,
        command: str,
        *args: str,
        include_context: bool = True,
        count_call: bool = True,
    ) -> dict[str, object]:
        payload = run_process(
            [sys.executable, str(RUNTIME), command, *args],
            cwd=self.project,
            runtime_transcript=self,
        )
        assert isinstance(payload, dict)
        if command == "init":
            tree_path = payload.get("tree_path")
            if isinstance(tree_path, str) and tree_path:
                self.instrumentation.register_tree(Path(tree_path), self)
        if include_context:
            normalized = normalize_payload(payload, self.temporary_root)
            self.context_bytes += len(compact_json(normalized).encode("utf-8"))
        if count_call and command in COUNTED_RUNTIME_COMMANDS:
            self.runtime_calls += 1
        if command in {"start", "complete", "fail", "block", "unblock", "reopen"}:
            self.explicit_transitions += 1
        if command == "start":
            node = payload.get("node")
            if isinstance(node, dict):
                executor = str(node.get("executor", ""))
                node_type = str(node.get("type", ""))
                if executor != "main":
                    self.delegations += 1
                if executor == "subagent":
                    self.subagent_delegations += 1
                if executor == "tool":
                    self.tool_delegations += 1
                if node_type == "gate":
                    self.gates += 1
        if command in {"complete", "fail", "block"}:
            self.terminal_operations += 1
            node = payload.get("node")
            if isinstance(node, dict):
                result = node.get("result")
                if isinstance(result, dict):
                    artifacts = result.get("artifacts", [])
                    if isinstance(artifacts, list):
                        self.artifacts += len(artifacts)
        return payload


def create_environment(root: Path, auto_commit: bool) -> tuple[Path, Path]:
    project = root / "project"
    project.mkdir(parents=True)
    run_git(project, "init", "--quiet")
    run_git(project, "config", "user.name", "XC Baseline")
    run_git(project, "config", "user.email", "xc-baseline@example.invalid")

    workshop_repository = root / "workshop"
    workshop = workshop_repository / ".xcoding"
    workshop.mkdir(parents=True)
    run_git(workshop_repository, "init", "--quiet")
    run_git(workshop_repository, "config", "user.name", "XC Baseline")
    run_git(workshop_repository, "config", "user.email", "xc-baseline@example.invalid")
    config = workshop / "xc-orchestration-runtime.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "git": {
                    "auto_commit": auto_commit,
                    "commit_message": (
                        "test(orchestration): {operation} {work_order_id} "
                        "[{checksum_short}]"
                    ),
                    "on_commit_failure": "warn",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    run_git(workshop_repository, "add", ".xcoding/xc-orchestration-runtime.json")
    run_git(workshop_repository, "commit", "--quiet", "-m", "Initialize baseline workshop")
    return project, workshop


def open_work_order(project: Path, workshop: Path, work_order_id: str) -> dict[str, object]:
    payload = run_process(
        [
            sys.executable,
            str(OPEN_WORK_ORDER),
            "--workshop",
            str(workshop),
            "--project-root",
            str(project),
            "--topic",
            work_order_id,
            "--work-order-id",
            work_order_id,
        ],
        cwd=project,
    )
    assert isinstance(payload, dict)
    return payload


def find_one(
    transcript: RuntimeTranscript,
    tree: Path,
    template_id: str,
    instance_id: str = "",
) -> dict[str, object]:
    args = ["--tree", str(tree), "--template-id", template_id]
    if instance_id:
        args.extend(["--instance-id", instance_id])
    payload = transcript.invoke("find", *args)
    nodes = payload.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != 1 or not isinstance(nodes[0], dict):
        raise HarnessError(f"expected one {template_id} node, received: {payload}")
    return nodes[0]


def set_values(
    transcript: RuntimeTranscript,
    tree: Path,
    values: dict[str, str],
) -> None:
    args = ["--tree", str(tree)]
    for key, value in values.items():
        args.extend(["--set", f"{key}={value}"])
    transcript.invoke("set", *args)


def complete_ready(
    transcript: RuntimeTranscript,
    tree: Path,
    expected_template_id: str,
    *,
    summary: str | None = None,
    artifact: Path | None = None,
    read_packet: bool = False,
    gate_outcome: str = "",
    decision: str = "",
) -> dict[str, object]:
    ready = transcript.invoke("next", "--tree", str(tree)).get("ready")
    if not isinstance(ready, list) or not ready or not isinstance(ready[0], dict):
        raise HarnessError(f"no ready node for {expected_template_id}")
    node = ready[0]
    if node.get("template_id") != expected_template_id:
        raise HarnessError(f"expected {expected_template_id}, received {node.get('template_id')}")
    node_id = str(node["id"])
    if read_packet:
        packet = transcript.invoke("control-packet", "--tree", str(tree), "--node", node_id)
        target = packet.get("packet", {}).get("target")
        if not isinstance(target, dict) or target.get("id") != node_id:
            raise HarnessError(f"control packet did not target {node_id}: {packet}")
    transcript.invoke(
        "start",
        "--tree",
        str(tree),
        "--node",
        node_id,
        "--agent",
        "baseline-harness",
    )
    args = [
        "--tree",
        str(tree),
        "--node",
        node_id,
        "--summary",
        summary or f"Completed {expected_template_id}.",
        "--validation",
        "baseline fixture validation passed",
    ]
    if artifact is not None:
        args.extend(["--artifact", str(artifact)])
    if gate_outcome:
        args.extend(["--gate-outcome", gate_outcome])
    if decision:
        args.extend(["--decision", decision])
    return transcript.invoke("complete", *args)


def render_work_order_document(
    project: Path,
    tree: Path,
    work_order: dict[str, object],
    document_kind: str,
    document_path: Path,
) -> None:
    args = [
        "--template",
        str(DOCUMENT_TEMPLATES / f"{document_kind}.md"),
        "--out",
        str(document_path),
        "--set",
        f"work_order_id={work_order['work_order_id']}",
        "--set",
        f"tree_ref={tree}",
        "--set",
        "content_language=en",
        "--set-json",
        "feature_ids=[]",
    ]
    for key, value in DOCUMENT_HEADINGS[document_kind].items():
        args.extend(["--set", f"{key}={value}"])
    run_process([sys.executable, str(RENDER), *args], cwd=project)
    run_process(
        [
            sys.executable,
            str(VALIDATE),
            "--document",
            str(document_path),
            "--expected-kind",
            document_kind,
        ],
        cwd=project,
    )


def complete_document(
    transcript: RuntimeTranscript,
    tree: Path,
    work_order: dict[str, object],
    document_kind: str,
) -> str:
    project = transcript.project
    group_template_id = DOCUMENT_GROUPS[document_kind]
    instance_id = f"baseline-{group_template_id}"
    parent = find_one(transcript, tree, group_template_id)
    transcript.invoke(
        "embed-subtree",
        "--tree",
        str(tree),
        "--parent",
        str(parent["id"]),
        "--template",
        str(DOCUMENT_EVOLUTION_TEMPLATE),
        "--instance-id",
        instance_id,
    )
    document_path = Path(str(work_order["workbench_path"])) / DOCUMENT_PATHS[document_kind]
    set_values(
        transcript,
        tree,
        {
            "document.path": str(document_path),
            "document.kind": document_kind,
            "document.template": str(DOCUMENT_TEMPLATES / f"{document_kind}.md"),
            "document.inputs": "baseline fixture",
            "document.contract": "managed document contract",
            "document.content_language": "en",
            "document.receipt.content_language": "en",
            "document.receipt.audience": "",
            "document.review_required": "false",
            "document.gate_required": "false",
            "document.gate_outcome": "accepted",
            "document.review.open_issues": "false",
        },
    )
    writer = find_one(transcript, tree, "write-document", instance_id)
    transcript.invoke(
        "start",
        "--tree",
        str(tree),
        "--node",
        str(writer["id"]),
        "--agent",
        "xc-document",
    )
    render_work_order_document(project, tree, work_order, document_kind, document_path)
    transcript.invoke(
        "complete",
        "--tree",
        str(tree),
        "--node",
        str(writer["id"]),
        "--summary",
        f"Wrote {document_kind}.",
        "--validation",
        "xc-document validation passed",
        "--artifact",
        str(document_path),
    )
    transcript.documents += 1

    for template_id in ("validate-draft", "validate-final"):
        validator = find_one(transcript, tree, template_id, instance_id)
        transcript.invoke(
            "start",
            "--tree",
            str(tree),
            "--node",
            str(validator["id"]),
            "--agent",
            "xc-document",
        )
        validated = run_process(
            [
                sys.executable,
                str(VALIDATE),
                "--document",
                str(document_path),
                "--expected-kind",
                document_kind,
            ],
            cwd=project,
        )
        if not isinstance(validated, dict) or validated.get("ok") is not True:
            raise HarnessError(f"xc-document rejected {document_kind}: {validated}")
        receipt = validated.get("receipt")
        if not isinstance(receipt, dict):
            raise HarnessError(f"xc-document returned no receipt for {document_kind}")
        transcript.invoke(
            "complete",
            "--tree",
            str(tree),
            "--node",
            str(validator["id"]),
            "--summary",
            f"Validated {document_kind}.",
            "--validation",
            "xc-document validation passed",
            "--check-result-json",
            compact_json(receipt),
        )
    return str(writer["id"])


def render_node_artifact(
    project: Path,
    tree: Path,
    work_order_id: str,
    node_id: str,
    artifact_path: Path,
    title: str,
) -> None:
    args = [
        "--template",
        str(DOCUMENT_TEMPLATES / "node-artifact.md"),
        "--out",
        str(artifact_path),
        "--set",
        f"work_order_id={work_order_id}",
        "--set",
        f"tree_ref={tree}",
        "--set",
        f"node_id={node_id}",
        "--set",
        "content_language=en",
        "--set",
        "audience=internal",
        "--set-json",
        "feature_ids=[]",
        "--set",
        f"artifact_title={title}",
        "--set",
        "scope_heading=Scope",
        "--set",
        "evidence_heading=Evidence",
        "--set",
        "findings_heading=Findings",
        "--set",
        "conclusion_heading=Conclusion",
    ]
    run_process([sys.executable, str(RENDER), *args], cwd=project)
    run_process(
        [
            sys.executable,
            str(VALIDATE),
            "--document",
            str(artifact_path),
            "--expected-kind",
            "node-artifact",
        ],
        cwd=project,
    )


def execute_dynamic_group(
    transcript: RuntimeTranscript,
    tree: Path,
    work_order: dict[str, object],
    *,
    group_template_id: str,
    worker_kind: str,
    count: int,
) -> None:
    if count == 0:
        return
    parent = find_one(transcript, tree, group_template_id)
    nodes: list[dict[str, object]] = []
    for index in range(1, count + 1):
        logical_key = f"{worker_kind}-{index}"
        payload = transcript.invoke(
            "add-node",
            "--tree",
            str(tree),
            "--parent",
            str(parent["id"]),
            "--logical-key",
            logical_key,
            "--title",
            f"{worker_kind.title()} worker {index}",
            "--type",
            "task",
            "--role",
            worker_kind,
            "--executor",
            "subagent",
            "--instructions",
            f"Execute fixed {worker_kind} fixture work {index}.",
            "--inputs",
            "Approved phase-0 baseline fixture.",
            "--deliverables",
            f"A deterministic {worker_kind} node artifact.",
            "--acceptance",
            f"The {worker_kind} artifact validates as a node artifact.",
        )
        node = payload.get("node")
        if not isinstance(node, dict):
            raise HarnessError(f"add-node returned no node: {payload}")
        nodes.append(node)
    transcript.invoke(
        "close-group",
        "--tree",
        str(tree),
        "--group",
        str(parent["id"]),
        count_call=False,
    )

    for index, node in enumerate(nodes, start=1):
        ready = transcript.invoke("next", "--tree", str(tree)).get("ready")
        if not isinstance(ready, list) or not ready or ready[0].get("id") != node["id"]:
            raise HarnessError(f"{worker_kind} worker {index} is not ready")
        transcript.invoke(
            "start",
            "--tree",
            str(tree),
            "--node",
            str(node["id"]),
            "--agent",
            f"baseline-{worker_kind}-{index}",
        )
        artifact = (
            Path(str(work_order["artifacts_path"]))
            / worker_kind
            / f"{worker_kind}-{index}.md"
        )
        render_node_artifact(
            transcript.project,
            tree,
            str(work_order["work_order_id"]),
            str(node["id"]),
            artifact,
            f"{worker_kind.title()} Evidence {index}",
        )
        transcript.invoke(
            "complete",
            "--tree",
            str(tree),
            "--node",
            str(node["id"]),
            "--summary",
            f"Completed {worker_kind} worker {index}.",
            "--validation",
            "node artifact validation passed",
            "--artifact",
            str(artifact),
        )
        if worker_kind == "implementation" and count > 1:
            transcript.invoke("summary", "--tree", str(tree))


def template_node_counts(path: Path) -> tuple[int, int]:
    """Count static template nodes without touching a managed runtime tree."""
    nodes = [element for element in ET.parse(path).getroot().iter() if element.tag == "node"]
    executable = sum(
        1
        for node in nodes
        if node.get("type") in {"task", "gate"}
        and not any(child.tag == "node" for child in node)
    )
    return len(nodes), executable


def expected_profile_node_counts(scenario_id: str) -> tuple[int, int]:
    work_order_nodes, work_order_executable = template_node_counts(WORK_ORDER_TEMPLATE)
    document_nodes, document_executable = template_node_counts(
        DOCUMENT_EVOLUTION_TEMPLATE
    )
    document_count = len(PROFILE_DOCUMENTS[scenario_id])
    dynamic_count = sum(PROFILE_WORKERS[scenario_id])
    return (
        work_order_nodes + document_nodes * document_count + dynamic_count,
        work_order_executable + document_executable * document_count + dynamic_count,
    )


def status_paths(repository: Path) -> list[str]:
    output = run_git(repository, "status", "--short", "--untracked-files=all")
    return [line[3:].replace("\\", "/") for line in output.splitlines() if line]


def cleanup_result(
    project: Path,
    workshop: Path,
    work_order_id: str,
    auto_commit: bool,
) -> dict[str, object]:
    project_paths = status_paths(project)
    workshop_repository = workshop.parent
    workshop_paths = status_paths(workshop_repository)
    declared_prefix = f".xcoding/work-orders/{work_order_id}"
    undeclared = [
        path
        for path in workshop_paths
        if path != declared_prefix and not path.startswith(f"{declared_prefix}/")
    ]
    if auto_commit and workshop_paths:
        undeclared.extend(workshop_paths)
    return {
        "project_undeclared_paths": project_paths,
        "workshop_undeclared_paths": sorted(set(undeclared)),
        "workshop_declared_dirty_paths": [] if auto_commit else workshop_paths,
    }


def profile_blackboard(scenario_id: str) -> dict[str, str]:
    analysis = scenario_id in {"T2", "T3", "T4"}
    solution = scenario_id in {"T3", "T4"}
    implementation = scenario_id in {"T3", "T4"}
    return {
        "work_order.document_language": "en",
        "work_order.has_features": "false",
        "work_order.requires_analysis": str(analysis).lower(),
        "work_order.requires_clarification": "false",
        "work_order.requires_solution": str(solution).lower(),
        "work_order.solution_gate_required": str(solution).lower(),
        "work_order.requires_implementation": str(implementation).lower(),
        "work_order.requires_verification": str(implementation).lower(),
    }


def collect_profile(
    scenario_id: str,
    auto_commit: bool,
    maintenance_families: int,
    instrumentation: HarnessInstrumentation,
) -> dict[str, object]:
    temporary = tempfile.TemporaryDirectory(
        prefix=f"xc-model-robust-{scenario_id.lower()}-{'commit' if auto_commit else 'no-commit'}-"
    )
    root = Path(temporary.name)
    try:
        project, workshop = create_environment(root, auto_commit)
        work_order_id = f"baseline-{scenario_id.lower().replace('-', '')}"
        work_order = open_work_order(project, workshop, work_order_id)
        transcript = RuntimeTranscript(project, root, instrumentation)
        initialized = transcript.invoke(
            "init",
            "--template",
            str(WORK_ORDER_TEMPLATE),
            "--runtime-path",
            str(work_order["runtime_path"]),
            "--work-order-id",
            work_order_id,
            "--name",
            f"Baseline {scenario_id}",
        )
        tree = Path(str(initialized["tree_path"]))
        set_values(transcript, tree, profile_blackboard(scenario_id))
        complete_ready(transcript, tree, "prepare-work-order")

        document_sources: dict[str, str] = {}
        for document_kind in PROFILE_DOCUMENTS[scenario_id]:
            if document_kind == "work-order-result":
                if scenario_id in {"T3", "T4"}:
                    set_values(
                        transcript,
                        tree,
                        {
                            "work_order.solution_source_ids": compact_json(
                                [document_sources["work-order-solution"]]
                            )
                        },
                    )
                    complete_ready(
                        transcript,
                        tree,
                        "approve-work-order-solution",
                        summary="The fixed baseline solution is approved.",
                        read_packet=True,
                        gate_outcome="approved",
                        decision="Approve the fixed post-change baseline solution.",
                    )
                    implementation_count, verification_count = PROFILE_WORKERS[scenario_id]
                    execute_dynamic_group(
                        transcript,
                        tree,
                        work_order,
                        group_template_id="implementation-group",
                        worker_kind="implementation",
                        count=implementation_count,
                    )
                    execute_dynamic_group(
                        transcript,
                        tree,
                        work_order,
                        group_template_id="verification-group",
                        worker_kind="verification",
                        count=verification_count,
                    )
                document_sources[document_kind] = complete_document(
                    transcript,
                    tree,
                    work_order,
                    document_kind,
                )
            else:
                document_sources[document_kind] = complete_document(
                    transcript,
                    tree,
                    work_order,
                    document_kind,
                )

        set_values(
            transcript,
            tree,
            {
                "work_order.objective_source_ids": compact_json(
                    [document_sources["work-order-goal"]]
                ),
                "work_order.result_source_ids": compact_json(
                    [document_sources["work-order-result"]]
                ),
            },
        )
        complete_ready(
            transcript,
            tree,
            "finalize-work-order",
            read_packet=True,
        )
        summary = transcript.invoke("summary", "--tree", str(tree))
        if summary.get("status") != "complete":
            raise HarnessError(f"{scenario_id} did not complete: {summary}")
        nodes, executable_nodes = expected_profile_node_counts(scenario_id)
        counts = summary.get("counts")
        if not isinstance(counts, dict) or sum(counts.values()) != nodes:
            raise HarnessError(
                f"{scenario_id} public summary count disagrees with tracked templates"
            )
        setup_commits = 1
        commits = int(run_git(workshop.parent, "rev-list", "--count", "HEAD")) - setup_commits
        cleanup = cleanup_result(project, workshop, work_order_id, auto_commit)
        metrics = {
            "context_bytes": transcript.context_bytes,
            "runtime_calls": transcript.runtime_calls,
            "explicit_transitions": transcript.explicit_transitions,
            "delegations": transcript.delegations,
            "subagent_delegations": transcript.subagent_delegations,
            "tool_delegations": transcript.tool_delegations,
            "nodes": nodes,
            "executable_nodes": executable_nodes,
            "artifacts": transcript.artifacts,
            "documents": transcript.documents,
            "gates": transcript.gates,
            "terminal_operations": transcript.terminal_operations,
            "checkpoint_commits": commits,
            "maintenance_families": maintenance_families,
            "snapshot_calls": transcript.snapshot_calls,
            "direct_runtime_xml_reads": transcript.direct_runtime_xml_reads,
        }
        if cleanup["project_undeclared_paths"] or cleanup["workshop_undeclared_paths"]:
            raise HarnessError(f"{scenario_id} left undeclared files: {cleanup}")
        return {
            "metrics": metrics,
            "cleanup": cleanup,
        }
    finally:
        temporary.cleanup()
        removed = not root.exists()
        if not removed:
            shutil.rmtree(root, ignore_errors=True)
            raise HarnessError(f"temporary profile root was not removed: {root}")


def zero_metrics(
    maintenance_families: int,
    instrumentation: HarnessInstrumentation,
) -> dict[str, int]:
    return {
        "context_bytes": 0,
        "runtime_calls": 0,
        "explicit_transitions": 0,
        "delegations": 0,
        "subagent_delegations": 0,
        "tool_delegations": 0,
        "nodes": 0,
        "executable_nodes": 0,
        "artifacts": 0,
        "documents": 0,
        "gates": 0,
        "terminal_operations": 0,
        "checkpoint_commits": 0,
        "maintenance_families": maintenance_families,
        "snapshot_calls": instrumentation.snapshot_calls,
        "direct_runtime_xml_reads": instrumentation.direct_runtime_xml_reads,
    }


def collect_semantic_negative_baseline(
    instrumentation: HarnessInstrumentation,
) -> dict[str, object]:
    temporary = tempfile.TemporaryDirectory(prefix="xc-model-robust-semantic-")
    root = Path(temporary.name)
    try:
        project, workshop = create_environment(root, auto_commit=False)
        work_order_id = "baseline-semantic-negative"
        work_order = open_work_order(project, workshop, work_order_id)
        transcript = RuntimeTranscript(project, root, instrumentation)
        initialized = transcript.invoke(
            "init",
            "--template",
            str(WORK_ORDER_TEMPLATE),
            "--runtime-path",
            str(work_order["runtime_path"]),
            "--work-order-id",
            work_order_id,
            "--name",
            "Semantic negative baseline",
            include_context=False,
        )
        tree = Path(str(initialized["tree_path"]))
        parent = find_one(transcript, tree, "implementation-group")
        special = {
            0: ("target-work", "task", "subagent", "target"),
            1: ("decision-gate", "gate", "main", "confirmed-decision"),
            2: ("supporting-evidence-a", "task", "subagent", "supporting-record"),
            3: ("supporting-evidence-b", "task", "subagent", "supporting-record"),
            4: ("blocked-work", "task", "subagent", "blocker"),
            5: ("approved-recovery", "task", "subagent", "recovery"),
        }
        siblings: list[dict[str, object]] = []
        by_key: dict[str, dict[str, object]] = {}
        for index in range(128):
            logical_key, node_type, executor, role = special.get(
                index,
                (f"unrelated-sibling-{index:03d}", "task", "subagent", "unrelated"),
            )
            payload = transcript.invoke(
                "add-node",
                "--tree",
                str(tree),
                "--parent",
                str(parent["id"]),
                "--logical-key",
                logical_key,
                "--title",
                logical_key.replace("-", " ").title(),
                "--type",
                node_type,
                "--role",
                role,
                "--executor",
                executor,
                "--instructions",
                f"Fixed semantic fixture node {logical_key}.",
                "--inputs",
                "Only explicitly supplied node inputs.",
                "--deliverables",
                "A fixed semantic fixture result.",
                "--acceptance",
                "No sibling context is required.",
                include_context=False,
            )
            node = payload.get("node")
            if not isinstance(node, dict):
                raise HarnessError(f"semantic add-node returned no node: {payload}")
            siblings.append(node)
            by_key[logical_key] = node

        set_values(
            transcript,
            tree,
            {
                "unrelated.secret": "must-not-enter-a-scoped-packet",
                "semantic.fixture": "negative-baseline",
            },
        )
        transcript.invoke("next", "--tree", str(tree), "--limit", "1", include_context=False)
        target = by_key["target-work"]
        target_payload = transcript.invoke(
            "show",
            "--tree",
            str(tree),
            "--node",
            str(target["id"]),
            include_context=False,
            count_call=False,
        )
        source_keys = (
            "decision-gate",
            "supporting-evidence-a",
            "supporting-evidence-b",
            "blocked-work",
            "approved-recovery",
        )
        for key in source_keys:
            transcript.invoke(
                "show",
                "--tree",
                str(tree),
                "--node",
                str(by_key[key]["id"]),
                include_context=False,
                count_call=False,
            )
        transcript.invoke(
            "artifacts",
            "--tree",
            str(tree),
            include_context=False,
            count_call=False,
        )
        summary = transcript.invoke(
            "summary",
            "--tree",
            str(tree),
            include_context=False,
        )
        target_text = compact_json(target_payload)
        sibling_ids = [str(item["id"]) for item in siblings if item["id"] != target["id"]]
        sibling_occurrences = sum(target_text.count(node_id) for node_id in sibling_ids)
        blackboard = summary.get("blackboard")
        full_blackboard_exposes_unselected = (
            isinstance(blackboard, dict)
            and blackboard.get("unrelated.secret") == "must-not-enter-a-scoped-packet"
        )
        cleanup = cleanup_result(project, workshop, work_order_id, auto_commit=False)
        if cleanup["project_undeclared_paths"] or cleanup["workshop_undeclared_paths"]:
            raise HarnessError(f"semantic fixture left undeclared files: {cleanup}")
        return {
            "sibling_count": 128,
            "target_projection_count": 1,
            "target_forbidden_sibling_id_occurrences": sibling_occurrences,
            "manual_source_ids_required": len(source_keys),
            "target_to_source_bindings": 0,
            "scoped_decision_bindings": 0,
            "scoped_evidence_bindings": 0,
            "scoped_blocker_recovery_bindings": 0,
            "full_blackboard_exposes_unselected_value": full_blackboard_exposes_unselected,
            "snapshot_calls": transcript.snapshot_calls,
            "direct_runtime_xml_reads": transcript.direct_runtime_xml_reads,
            "category_access": {
                "target": "show-by-manual-node-id",
                "confirmed_decisions": "show-by-manual-node-id-or-full-blackboard",
                "supporting_records": "show-by-two-manual-node-ids",
                "blocker_recovery": "show-by-two-manual-node-ids",
            },
            "cleanup": cleanup,
        }
    finally:
        temporary.cleanup()
        removed = not root.exists()
        if not removed:
            shutil.rmtree(root, ignore_errors=True)
            raise HarnessError(f"temporary semantic root was not removed: {root}")


def exercise_boundary_mutation(action: str) -> None:
    """Run one deliberately forbidden operation under collection guards."""
    instrumentation = HarnessInstrumentation()
    with instrumentation.enforce():
        with tempfile.TemporaryDirectory(prefix="xc-model-robust-boundary-") as temporary:
            root = Path(temporary)
            project, workshop = create_environment(root, auto_commit=False)
            work_order = open_work_order(project, workshop, "baseline-boundary-mutation")
            transcript = RuntimeTranscript(project, root, instrumentation)
            initialized = transcript.invoke(
                "init",
                "--template",
                str(WORK_ORDER_TEMPLATE),
                "--runtime-path",
                str(work_order["runtime_path"]),
                "--work-order-id",
                "baseline-boundary-mutation",
                "--name",
                "Boundary mutation",
                include_context=False,
            )
            tree = Path(str(initialized["tree_path"]))
            if action == "direct-runtime-xml-read":
                tree.read_text(encoding="utf-8")
            elif action == "snapshot":
                transcript.invoke(
                    "snapshot",
                    "--tree",
                    str(tree),
                    include_context=False,
                    count_call=False,
                )
            else:
                raise ValueError(f"unknown boundary mutation: {action}")
    raise HarnessError(f"boundary mutation was not rejected: {action}")


def collect_measurements() -> dict[str, object]:
    scenarios = load_scenarios()
    instrumentation = HarnessInstrumentation()
    profiles: dict[str, dict[str, object]] = {
        "T0": {
            "auto_commit_false": {
                "metrics": zero_metrics(
                    len(scenarios["T0"]["maintenance_families"]),
                    instrumentation,
                ),
                "cleanup": {
                    "project_undeclared_paths": [],
                    "workshop_undeclared_paths": [],
                    "workshop_declared_dirty_paths": [],
                },
            },
            "auto_commit_true": {
                "metrics": zero_metrics(
                    len(scenarios["T0"]["maintenance_families"]),
                    instrumentation,
                ),
                "cleanup": {
                    "project_undeclared_paths": [],
                    "workshop_undeclared_paths": [],
                    "workshop_declared_dirty_paths": [],
                },
            },
        },
        "T1": {
            "auto_commit_false": {
                "metrics": zero_metrics(
                    len(scenarios["T1"]["maintenance_families"]),
                    instrumentation,
                ),
                "cleanup": {
                    "project_undeclared_paths": [],
                    "workshop_undeclared_paths": [],
                    "workshop_declared_dirty_paths": [],
                },
            },
            "auto_commit_true": {
                "metrics": zero_metrics(
                    len(scenarios["T1"]["maintenance_families"]),
                    instrumentation,
                ),
                "cleanup": {
                    "project_undeclared_paths": [],
                    "workshop_undeclared_paths": [],
                    "workshop_declared_dirty_paths": [],
                },
            },
        },
    }
    with instrumentation.enforce():
        jobs: dict[object, tuple[str, bool]] = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            for scenario_id in PROFILE_DOCUMENTS:
                maintenance = len(scenarios[scenario_id]["maintenance_families"])
                for auto_commit in (False, True):
                    future = executor.submit(
                        collect_profile,
                        scenario_id,
                        auto_commit,
                        maintenance,
                        instrumentation,
                    )
                    jobs[future] = (scenario_id, auto_commit)
            for future in as_completed(jobs):
                scenario_id, auto_commit = jobs[future]
                profiles.setdefault(scenario_id, {})[
                    "auto_commit_true" if auto_commit else "auto_commit_false"
                ] = future.result()

        semantic_negative_baseline = collect_semantic_negative_baseline(
            instrumentation
        )

    ordered_profiles = {
        scenario_id: profiles[scenario_id]
        for scenario_id in ("T0", "T1", "T1-M", "T2", "T3", "T4")
    }
    checkpoint_commits = {
        auto_commit: {
            scenario_id: int(
                ordered_profiles[scenario_id][auto_commit]["metrics"]["checkpoint_commits"]
            )
            for scenario_id in ordered_profiles
        }
        for auto_commit in ("auto_commit_false", "auto_commit_true")
    }
    return {
        "profiles": ordered_profiles,
        "checkpoint_commits": checkpoint_commits,
        "semantic_negative_baseline": semantic_negative_baseline,
        "classification_only_scenarios": ["T-U"],
    }


def current_identity() -> dict[str, object]:
    return {
        "normalization_version": NORMALIZATION_VERSION,
        "python_version": platform.python_version(),
        "input_hashes": input_hashes(),
    }


def compare_values(expected: object, actual: object, prefix: str = "") -> list[dict[str, object]]:
    drift: list[dict[str, object]] = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in expected:
                drift.append({"field": path, "expected": None, "actual": actual[key]})
            elif key not in actual:
                drift.append({"field": path, "expected": expected[key], "actual": None})
            else:
                drift.extend(compare_values(expected[key], actual[key], path))
        return drift
    if isinstance(expected, list) and isinstance(actual, list):
        if expected != actual:
            drift.append({"field": prefix, "expected": expected, "actual": actual})
        return drift
    if expected != actual:
        drift.append({"field": prefix, "expected": expected, "actual": actual})
    return drift


def load_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HarnessError(f"manifest is not a JSON object: {path}")
    return payload


def historical_descriptor() -> dict[str, object]:
    return {
        "manifest_role": HISTORICAL_MANIFEST_ROLE,
        "manifest_id": HISTORICAL_MANIFEST_ID,
        "path": "tests/fixtures/model_robust_workflow/baseline-v1.json",
        "sha256": HISTORICAL_MANIFEST_SHA256,
    }


def validate_historical_manifest(path: Path) -> tuple[int, dict[str, object]]:
    if not path.is_file():
        return 2, {
            "ok": False,
            "manifest_role": HISTORICAL_MANIFEST_ROLE,
            "error": {"code": "historical_manifest_missing", "path": str(path)},
        }
    actual_sha256 = sha256_bytes(path.read_bytes())
    if actual_sha256 != HISTORICAL_MANIFEST_SHA256:
        return 1, {
            "ok": False,
            "manifest_role": HISTORICAL_MANIFEST_ROLE,
            "error": {"code": "historical_manifest_bytes_changed"},
            "expected_sha256": HISTORICAL_MANIFEST_SHA256,
            "actual_sha256": actual_sha256,
        }
    manifest = load_manifest(path)
    identity = {
        "schema_version": manifest.get("schema_version"),
        "manifest_id": manifest.get("manifest_id"),
        "normalization_version": manifest.get("normalization_version"),
        "scenario_fixture": manifest.get("scenario_fixture"),
    }
    expected_identity = {
        "schema_version": 1,
        "manifest_id": HISTORICAL_MANIFEST_ID,
        "normalization_version": NORMALIZATION_VERSION,
        "scenario_fixture": "tests/fixtures/model_robust_workflow/scenarios-v1.json",
    }
    drift = compare_values(expected_identity, identity)
    if drift or not isinstance(manifest.get("measurements"), dict):
        return 2, {
            "ok": False,
            "manifest_role": HISTORICAL_MANIFEST_ROLE,
            "error": {"code": "historical_manifest_invalid"},
            "drift": drift,
        }
    return 0, {
        "ok": True,
        "manifest_role": HISTORICAL_MANIFEST_ROLE,
        "manifest_id": HISTORICAL_MANIFEST_ID,
        "sha256": actual_sha256,
    }


def build_measurement_deltas(
    historical: object,
    current: object,
    reason: str,
) -> list[dict[str, object]]:
    deltas: list[dict[str, object]] = []
    for item in compare_values(historical, current, "measurements"):
        old_value = item["expected"]
        new_value = item["actual"]
        delta: dict[str, object] = {
            "field": item["field"],
            "historical_value": old_value,
            "current_value": new_value,
            "explanation": reason,
        }
        if (
            isinstance(old_value, (int, float))
            and not isinstance(old_value, bool)
            and isinstance(new_value, (int, float))
            and not isinstance(new_value, bool)
        ):
            delta["numeric_delta"] = new_value - old_value
        deltas.append(delta)
    return deltas


def build_manifest(
    measurements: dict[str, object],
    reason: str,
    historical: dict[str, object],
) -> dict[str, object]:
    identity = current_identity()
    historical_measurements = historical.get("measurements")
    measurement_deltas = build_measurement_deltas(
        historical_measurements,
        measurements,
        reason,
    )
    return {
        "schema_version": 2,
        "manifest_id": CURRENT_MANIFEST_ID,
        "manifest_role": CURRENT_MANIFEST_ROLE,
        **identity,
        "recording_base_commit": repository_head(),
        "scenario_fixture": "tests/fixtures/model_robust_workflow/scenarios-v1.json",
        "measurements": measurements,
        "comparison": {
            "historical_manifest": historical_descriptor(),
            "measurement_deltas": measurement_deltas,
        },
        "change_note": {
            "reason": reason,
            "old_value": historical_measurements,
            "new_value": measurements,
            "input_hashes": identity["input_hashes"],
        },
    }


def write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def verify_manifest(path: Path) -> tuple[int, dict[str, object]]:
    if not path.is_file():
        return 2, {
            "ok": False,
            "command": "verify",
            "error": {"code": "manifest_missing", "path": str(path)},
        }
    manifest = load_manifest(path)
    expected_contract = {
        "schema_version": 2,
        "manifest_id": CURRENT_MANIFEST_ID,
        "manifest_role": CURRENT_MANIFEST_ROLE,
        "normalization_version": NORMALIZATION_VERSION,
        "scenario_fixture": "tests/fixtures/model_robust_workflow/scenarios-v1.json",
    }
    actual_contract = {key: manifest.get(key) for key in expected_contract}
    contract_drift = compare_values(expected_contract, actual_contract)
    recording_base_commit = manifest.get("recording_base_commit")
    if not isinstance(recording_base_commit, str) or re.fullmatch(
        r"[0-9a-f]{40}",
        recording_base_commit,
    ) is None:
        contract_drift.append(
            {
                "field": "recording_base_commit",
                "expected": "informational 40-character lowercase Git object ID",
                "actual": recording_base_commit,
            }
        )
    if contract_drift:
        return 2, {
            "ok": False,
            "command": "verify",
            "error": {"code": "current_manifest_invalid"},
            "drift": contract_drift,
        }
    historical_code, historical_result = validate_historical_manifest(HISTORICAL_MANIFEST)
    if historical_code != 0:
        return historical_code, {
            "ok": False,
            "command": "verify",
            "error": {"code": "historical_comparison_unavailable"},
            "historical_validation": historical_result,
        }
    historical = load_manifest(HISTORICAL_MANIFEST)
    change_note = manifest.get("change_note")
    comparison = manifest.get("comparison")
    if not isinstance(change_note, dict) or not isinstance(comparison, dict):
        return 2, {
            "ok": False,
            "command": "verify",
            "error": {"code": "current_manifest_invalid"},
        }
    reason = change_note.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return 2, {
            "ok": False,
            "command": "verify",
            "error": {"code": "record_reason_required"},
        }
    expected_comparison = {
        "historical_manifest": historical_descriptor(),
        "measurement_deltas": build_measurement_deltas(
            historical.get("measurements"),
            manifest.get("measurements"),
            reason,
        ),
    }
    comparison_drift = compare_values(expected_comparison, comparison, "comparison")
    expected_change_note = {
        "reason": reason,
        "old_value": historical.get("measurements"),
        "new_value": manifest.get("measurements"),
        "input_hashes": manifest.get("input_hashes"),
    }
    comparison_drift.extend(
        compare_values(expected_change_note, change_note, "change_note")
    )
    if comparison_drift or not expected_comparison["measurement_deltas"]:
        return 2, {
            "ok": False,
            "command": "verify",
            "error": {"code": "historical_comparison_invalid"},
            "drift": comparison_drift,
        }
    expected_identity = {
        key: manifest.get(key)
        for key in (
            "normalization_version",
            "python_version",
            "input_hashes",
        )
    }
    identity_drift = compare_values(expected_identity, current_identity())
    if identity_drift:
        return 1, {
            "ok": False,
            "command": "verify",
            "error": {"code": "current_input_drift"},
            "drift": identity_drift,
        }
    measurements = collect_measurements()
    drift = compare_values(manifest.get("measurements"), measurements, "measurements")
    if drift:
        return 1, {
            "ok": False,
            "command": "verify",
            "error": {"code": "current_measurement_drift"},
            "drift": drift,
        }
    return 0, {
        "ok": True,
        "command": "verify",
        "manifest_id": CURRENT_MANIFEST_ID,
        "manifest_role": CURRENT_MANIFEST_ROLE,
        "normalization_version": NORMALIZATION_VERSION,
        "measurements_sha256": sha256_json(measurements),
        "historical_manifest_sha256": historical_result["sha256"],
        "drift": [],
    }


def record_manifest(
    path: Path,
    reason: str,
    historical_path: Path = HISTORICAL_MANIFEST,
) -> tuple[int, dict[str, object]]:
    if not reason.strip():
        return 2, {
            "ok": False,
            "command": "record",
            "error": {"code": "record_reason_required"},
        }
    if path.resolve() == HISTORICAL_MANIFEST.resolve():
        return 2, {
            "ok": False,
            "command": "record",
            "error": {"code": "historical_manifest_immutable"},
        }
    historical_code, historical_result = validate_historical_manifest(
        historical_path.resolve()
    )
    if historical_code != 0:
        return historical_code, {
            "ok": False,
            "command": "record",
            "error": {"code": "historical_comparison_unavailable"},
            "historical_validation": historical_result,
        }
    historical = load_manifest(historical_path.resolve())
    measurements = collect_measurements()
    payload = build_manifest(measurements, reason.strip(), historical)
    write_manifest(path, payload)
    return 0, {
        "ok": True,
        "command": "record",
        "manifest_id": CURRENT_MANIFEST_ID,
        "manifest_role": CURRENT_MANIFEST_ROLE,
        "measurements_sha256": sha256_json(measurements),
        "historical_manifest_sha256": historical_result["sha256"],
        "measurement_delta_count": len(
            payload["comparison"]["measurement_deltas"]
        ),
        "reason": reason.strip(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect and verify model-robust workflow scenario baselines."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser(
        "verify",
        help="Verify the checked-in current post-change manifest without writing it.",
    )
    verify.add_argument("--manifest", required=True, type=Path)
    record = subparsers.add_parser(
        "record",
        help="Explicitly record the current manifest against the immutable historical manifest.",
    )
    record.add_argument("--manifest", required=True, type=Path)
    record.add_argument("--reason", required=True)
    record.add_argument(
        "--historical-manifest",
        type=Path,
        default=HISTORICAL_MANIFEST,
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "verify":
            code, payload = verify_manifest(args.manifest.resolve())
        else:
            code, payload = record_manifest(
                args.manifest.resolve(),
                args.reason,
                args.historical_manifest,
            )
    except (HarnessError, OSError, ValueError, json.JSONDecodeError) as exc:
        code = 1
        payload = {
            "ok": False,
            "command": args.command,
            "error": {
                "code": "baseline_collection_failed",
                "message": str(exc),
            },
        }
    print(compact_json(payload))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
