"""Tests for the `xc-change-report` Skill package.

The suite covers the positive end-to-end path (fixture change set -> manifest ->
single-file HTML -> validator receipt) plus every negative case listed in the design
specification's verification strategy, including case 26, which is deliberately a
reverse case: it proves the boundary of the mechanism rather than its strength.

Standard library only.
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "xc-change-report"
SCRIPTS = SKILL_ROOT / "scripts"
FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "change_report"
GOLDEN_DIR = FIXTURES / "diagrams"
SOURCE_ROOT = REPOSITORY_ROOT / "src"

for entry in (str(SCRIPTS), str(SOURCE_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import build_manifest as bm  # noqa: E402
import build_skeleton as bs  # noqa: E402
import capture_baseline as cb  # noqa: E402
import highlight_code as hc  # noqa: E402
import render_diagram as rd  # noqa: E402
import validate_report as vr  # noqa: E402
from xcoding.runtime import core as runtime_core  # noqa: E402


WORK_ORDER_ID = "20260915-1745-change-report-implementation"


# --------------------------------------------------------------------------------------
# Fixture materialisation
# --------------------------------------------------------------------------------------


def _content_bytes(spec: Any, fixture_dir: Path) -> bytes | None:
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise AssertionError(f"invalid fixture content spec: {spec!r}")
    if "base64" in spec:
        return base64.b64decode(spec["base64"])
    if "file" in spec:
        # Fixture files are checked in with their exact bytes (including non-UTF-8 ones).
        return (fixture_dir / spec["file"]).read_bytes()
    if "text" in spec:
        return spec["text"].encode(spec.get("encoding", "utf-8"))
    raise AssertionError(f"fixture content spec has no payload: {spec!r}")


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True)
    if proc.returncode not in (0, 1):
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace')}")
    return proc.stdout.decode("utf-8", "replace")


def materialise(fixture: str, root: Path, line_endings: str = "\n") -> dict[str, Any]:
    """Create a real git working tree plus the two baseline snapshots of a fixture scenario.

    The returned harness carries the baseline's own C4 digest, computed from the materialised
    worktree snapshot with the package's capture construction, so a manifest built from the
    harness proves the same baseline identity a real capture publishes instead of a literal.

    `line_endings` writes every text payload with `\\r\\n` instead of `\\n`, which is how a
    repository with `core.autocrlf=false` on a Windows checkout stores CRLF content. Binary
    fixture files (`base64`/`file` specs) are never rewritten.
    """
    fixture_dir = FIXTURES / fixture
    scenario = json.loads((fixture_dir / "scenario.json").read_text(encoding="utf-8"))

    def endings(spec: Any) -> Any:
        if line_endings == "\n" or not isinstance(spec, dict) or "text" not in spec:
            return spec
        if spec.get("encoding", "utf-8") != "utf-8":
            return spec
        converted = dict(spec)
        converted["text"] = re.sub(r"(?<!\r)\n", line_endings, spec["text"])
        return converted

    commit_state = {path: endings(spec) for path, spec in scenario.get("commit", {}).items()}
    baseline_state = _merge(commit_state, scenario.get("worktree_at_baseline", {}))
    baseline_state = {path: endings(spec) for path, spec in baseline_state.items()}
    head_state = _merge(baseline_state, scenario.get("head", {}))
    head_state = {path: endings(spec) for path, spec in head_state.items()}

    repo = root / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "user.name", "fixture")
    _git(repo, "config", "core.autocrlf", "false")

    def write_state(state: dict[str, Any]) -> None:
        for existing in sorted(repo.rglob("*"), reverse=True):
            if existing.is_file() and ".git" not in existing.parts:
                relative = existing.relative_to(repo).as_posix()
                if relative not in state:
                    existing.unlink()
        for relative, spec in state.items():
            payload = _content_bytes(spec, fixture_dir)
            if payload is None:
                continue
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)

    write_state(commit_state)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")
    commit = _git(repo, "rev-parse", "HEAD").strip()

    write_state(baseline_state)
    baseline_worktree = root / "tmp" / "baseline-worktree"
    baseline_untracked = root / "tmp" / "baseline-untracked"
    baseline_worktree.mkdir(parents=True)
    baseline_untracked.mkdir(parents=True)
    # C4a/C4b: the worktree snapshot mirrors the path set the baseline commit tracks and
    # nothing else. A path that was untracked when the work order opened belongs to the
    # untracked snapshot; leaving it in the worktree snapshot makes the whole snapshot read
    # `incomplete` and degrades every path's provenance.
    tracked_at_baseline = [
        path for path, spec in commit_state.items() if _content_bytes(spec, fixture_dir) is not None
    ]
    tracked_set = set(tracked_at_baseline)
    for item in sorted(repo.rglob("*")):
        if item.is_file() and ".git" not in item.parts:
            relative = item.relative_to(repo)
            target = baseline_worktree if relative.as_posix() in tracked_set else baseline_untracked
            (target / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target / relative)

    write_state(head_state)
    return {
        "repo": repo,
        "commit": commit,
        "baseline_worktree": baseline_worktree,
        "baseline_untracked": baseline_untracked,
        "baseline_digest": cb.digest_from_snapshot(
            baseline_worktree, sorted(tracked_at_baseline, key=bm.sort_key)
        ),
        "scenario": scenario,
        "root": root,
    }


def build_manifest_for(harness: dict[str, Any], strength: str = "standard", tmp_dir: Path | None = None) -> dict[str, Any]:
    return bm.build_manifest(
        repo_path=harness["repo"],
        work_order_id=WORK_ORDER_ID,
        baseline_commit=harness["commit"],
        baseline_digest=harness["baseline_digest"],
        baseline_algorithm=bm.DIGEST_ALGORITHM,
        baseline_worktree_dir=harness["baseline_worktree"],
        baseline_untracked_dir=harness["baseline_untracked"],
        tmp_dir=tmp_dir,
        captured_at="2026-09-15T17:45:00Z",
        generated_at="2026-09-15T18:00:00Z",
        strength=strength,
    )


def write_manifest(manifest: dict[str, Any], path: Path) -> Path:
    """Write with LF bytes so the manifest hash is platform-stable."""
    path.write_bytes((json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return path


def unit_pairs(manifest: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs = [
        (entry, hunk)
        for entry in manifest["files"]
        for hunk in entry["hunks"]
        if not hunk["excluded"]
    ]
    pairs.sort(key=lambda pair: pair[1]["unit_index"])
    return pairs


def make_analysis(
    manifest: dict[str, Any],
    repo: Path,
    unit_overrides: dict[str, Any] | None = None,
    glossary: bool = False,
    diagrams: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Author plausible analysis text that satisfies A13 and V11 by construction."""
    units: dict[str, Any] = {}
    for entry, hunk in unit_pairs(manifest):
        index = str(hunk["unit_index"])
        if unit_overrides and index in unit_overrides:
            units[index] = unit_overrides[index]
            continue
        lines = bm.unit_canonical_lines(
            bm.unit_lines(repo, manifest["baseline"]["commit"], bm.snapshot_dir(manifest), entry, hunk),
            hunk,
        )
        changed = (
            hunk["changed_old_lines"] if hunk["content_side"] == "old" else hunk["changed_new_lines"]
        )
        tokens = sorted(vr.unit_tokens(entry, hunk, lines, changed))
        token = next((item for item in tokens if item.isidentifier()), tokens[0] if tokens else entry["path"])
        summary = f"{entry['path']} ({entry['change_kind']})"
        fields = {}
        for field in bm.FIELD_NAMES:
            fields[field] = (
                f"{field}: {summary} introduces {token}. The unit keeps behaving as before for "
                f"every other input, because {token} only changes the value that this unit handles "
                "and no caller depends on the previous constant."
            )
        units[index] = {"fields": fields, "covers": [hunk["anchor"]]}

    analysis: dict[str, Any] = {
        "language": "en",
        "title": "Change report: fixture work order",
        "subtitle": "Fixture report for the xc-change-report test suite.",
        "units": units,
        "overview": {
            "what_changed": "The fixture change set modifies tracked files and adds new ones.",
            "why": "The test suite needs a deterministic change set with exclusions and renames.",
            "impact": "Only the fixture repository is affected.",
            "reading_guide": "Read the change map first, then the unit analysis.",
        },
        "process_position": {
            "narrative": "The change sits in the middle of the sample flow.",
            "before": "no coverage manifest",
            "after": "a manifest and a single-file report",
        },
        "verification": {
            "commands": [{"command": "python -m unittest", "result": "fixture evidence"}],
            "residual_risks": "The fixture proves the mechanism, not production behaviour.",
        },
        "rounds": [
            {
                "round": 1,
                "refresh_reason": "initial",
                "scope": "initial generation",
                "manifest_sha256": "",
                "at": "2026-09-15T18:00:00Z",
                "sections": "all",
            }
        ],
    }
    if glossary:
        analysis["glossary"] = [
            {"term": "unit", "explanation": "One analysable change unit with its own anchor."},
            {"term": "manifest", "explanation": "The machine-generated coverage manifest."},
        ]
    if diagrams is not None:
        analysis["diagrams"] = diagrams
    return analysis


def render_report(
    manifest: dict[str, Any],
    manifest_path: Path,
    repo: Path,
    analysis: dict[str, Any],
    out: Path,
) -> str:
    page = bs.build_report(
        repo=repo,
        manifest=manifest,
        analysis=analysis,
        template_text=(SKILL_ROOT / "assets" / "change-report-template.html").read_text(encoding="utf-8"),
        css_text=(SKILL_ROOT / "assets" / "change-report.css").read_text(encoding="utf-8"),
        generated_at="2026-09-15T18:00:00Z",
        manifest_bytes=manifest_path.read_bytes(),
    )
    out.write_bytes(page.encode("utf-8"))
    return page


def flow_spec(
    declared: list[str] | None = None,
    routes: dict[str, str] | None = None,
    rework_when: str = "report.gate_rework_required == true",
    publishers: list[dict[str, str]] | None = None,
    outer_max: str = "3",
    outer_continue: str = "report.gate_rework_required == true",
    inner_max: str = "3",
    inner_continue: str = "report.accuracy_open_issues == true",
    # G-33: a bounded quality loop that cannot converge escalates. Both loops carry the
    # escalation terminal state, so the fixture defaults to it and a caller can flip exactly
    # one loop to prove V12 checks each declaration rather than one of them.
    outer_on_limit: str = "blocked",
    inner_on_limit: str = "blocked",
) -> dict[str, Any]:
    declared = declared if declared is not None else list(bm.REPORT_GATE_OUTCOMES)
    routes = routes if routes is not None else {
        "accepted": "validate-final",
        "revision-required": "report-gate-recovery-group",
        "rejected": "report-gate-recovery-group",
        "accepted-with-followup": "validate-final",
    }
    # The O4 table in the shape one writer per round can actually take: validate-final writes
    # the value that ends the pass, report-gate adds the single `true` that a reworking decision
    # carries back to the next pass, and no node writes the key twice in one round.
    publishers = publishers if publishers is not None else [
        {"node": "report-gate", "publishes": "true", "terminates_round": "gate-rework"},
        {"node": "validate-final", "publishes": "true", "terminates_round": "review-loop-exit"},
        {"node": "validate-final", "publishes": "false", "terminates_round": "review-loop-exit"},
        {"node": "validate-final", "publishes": "true", "terminates_round": "validate-final-stale"},
        {"node": "validate-final", "publishes": "false", "terminates_round": "validate-final-stale"},
    ]
    return {
        "name": "change-report",
        "schema_version": 1,
        "blackboard": {"report.gate_rework_required": "false", "report.accuracy_open_issues": "false"},
        "root": {
            "template_id": "change-report",
            "title": "Produce change report",
            "type": "composite",
            "role": "root",
            "mode": "sequence",
            "executor": "main",
            "children": [
                {
                    "template_id": "report-pass-loop",
                    "title": "Report passes",
                    "type": "loop",
                    "role": "report-pass",
                    "mode": "sequence",
                    "executor": "main",
                    "loop.max_iterations": outer_max,
                    "loop.continue_when": outer_continue,
                    "loop.on_limit": outer_on_limit,
                    "metadata": {"rework_publishers": json.dumps(publishers)},
                    "children": [
                        {"template_id": "prepare-manifest", "type": "task", "role": "report-manifest", "executor": "tool", "instructions": "run build_manifest.py", "deliverables": "change-report-manifest.json", "acceptance": "manifest written"},
                        {"template_id": "author-report", "type": "task", "role": "report-author", "executor": "subagent", "instructions": "author the analysis", "deliverables": "change-report.html", "acceptance": "every unit analysed"},
                        {"template_id": "validate-coverage", "type": "task", "role": "report-validate", "executor": "tool", "instructions": "run validate_report.py", "deliverables": "receipt", "acceptance": "V1-V13 pass"},
                        {
                            "template_id": "report-review-loop",
                            "type": "loop",
                            "role": "report-review",
                            "mode": "sequence",
                            "executor": "main",
                            "loop.max_iterations": inner_max,
                            "loop.continue_when": inner_continue,
                            "loop.on_limit": inner_on_limit,
                            "children": [
                                {"template_id": "review-report", "type": "task", "role": "report-accuracy", "executor": "subagent", "instructions": "compare prose with code", "deliverables": "change-report-verdicts.json", "acceptance": "every unit judged"},
                                {"template_id": "revise-report", "type": "task", "role": "report-revise", "executor": "subagent", "when": "report.accuracy_open_issues == true", "when.policy": "latched", "instructions": "revise the analysis text", "deliverables": "change-report.html", "acceptance": "issues closed"},
                            ],
                        },
                        {
                            "template_id": "report-gate",
                            "type": "gate",
                            "role": "report-approval",
                            "executor": "main",
                            "when": "report.gate_required == true",
                            "when.policy": "latched",
                            "instructions": (
                                "ask the four focused questions; a reworking outcome publishes "
                                "report.gate_rework_required=true and report.gate_recovery_required="
                                "true, and an accepting outcome leaves report.gate_rework_required "
                                "to validate-final"
                            ),
                            "deliverables": (
                                "report.gate_outcome, report.gate_rework_required, "
                                "report.gate_recovery_required"
                            ),
                            "acceptance": "the owner has read the report",
                            "metadata": {
                                "gate": {
                                    "outcomes": json.dumps(declared),
                                    "routes": json.dumps(routes),
                                    "decision_required": "true",
                                    "outcome_key": "report.gate_outcome",
                                }
                            },
                        },
                        {
                            "template_id": "report-gate-recovery-group",
                            "type": "composite",
                            "role": "dynamic-group",
                            "mode": "sequence",
                            "executor": "main",
                            "when": rework_when,
                            "when.policy": "latched",
                            "instructions": (
                                "append the recovery; when it is complete publish "
                                "report.gate_recovery_required=false and leave "
                                "report.gate_rework_required alone so the loop re-enters"
                            ),
                            "deliverables": "recovery work",
                            "acceptance": "the recorded outcome is resolved",
                            "children": [],
                        },
                        {
                            "template_id": "validate-final",
                            "type": "task",
                            "role": "report-validate-final",
                            "executor": "tool",
                            "when": "report.gate_recovery_required == false",
                            "when.policy": "latched",
                            "instructions": (
                                "publish the refresh latch; a stale report publishes "
                                "report.gate_rework_required=true and a fresh one publishes "
                                "report.gate_rework_required=false"
                            ),
                            "deliverables": "receipt",
                            "acceptance": "V14 passes",
                        },
                    ],
                }
            ],
        },
    }


def write_flow_spec(spec: dict[str, Any], path: Path) -> Path:
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def error_ids(payload: dict[str, Any]) -> set[str]:
    return {item["id"] for item in payload.get("errors", [])}


def verdicts_payload(manifest: dict[str, Any], overrides: dict[int, str] | None = None) -> dict[str, Any]:
    entries = []
    for _, hunk in unit_pairs(manifest):
        verdict = (overrides or {}).get(hunk["unit_index"], "accurate")
        entry = {"unit_index": hunk["unit_index"], "verdict": verdict, "reason": ""}
        if verdict != "accurate":
            entry["reason"] = "the analysis text does not match the code at this anchor"
        entries.append(entry)
    return {"schema_version": 1, "work_order_id": WORK_ORDER_ID, "verdicts": entries}


class ReportCase(unittest.TestCase):
    """Shared harness: materialise a fixture, build the report and validate it."""

    fixture = "sample-diff"

    @classmethod
    def setUpClass(cls) -> None:
        cls._root = Path(tempfile.mkdtemp(prefix=f"xc-report-{cls.fixture}-"))
        cls.harness = materialise(cls.fixture, cls._root / "fixture")
        cls.manifest = build_manifest_for(cls.harness)
        cls.manifest_path = write_manifest(cls.manifest, cls._root / "change-report-manifest.json")
        cls.diagrams = [
            json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))
            for name in ("flow-spec.json", "state-spec.json", "sequence-spec.json")
        ]
        cls.analysis = make_analysis(cls.manifest, cls.harness["repo"], diagrams=cls.diagrams)
        cls.report_path = cls._root / "change-report.html"
        cls.page = render_report(
            cls.manifest, cls.manifest_path, cls.harness["repo"], cls.analysis, cls.report_path
        )
        cls.flow_path = write_flow_spec(flow_spec(), cls._root / "change-report-flow.json")
        cls.verdicts_path = cls._root / "change-report-verdicts.json"
        cls.verdicts_path.write_text(
            json.dumps(verdicts_payload(cls.manifest), ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._root, ignore_errors=True)

    # -- helpers -----------------------------------------------------------------
    def validate(
        self,
        report: Path | None = None,
        manifest: Path | None = None,
        stage: str = "coverage",
        verdicts: Path | None = None,
        accuracy: str | None = None,
        flow: Path | None = None,
        golden: Path | None = None,
        repo: Path | None = None,
    ) -> dict[str, Any]:
        payload, _ = vr.validate(
            report_path=report or self.report_path,
            manifest_path=manifest or self.manifest_path,
            # V15 recomputes the baseline digest from the snapshot and V16 re-enumerates the
            # baseline commit, so the repository a manifest is validated against must be the
            # repository it was built from.
            repo=repo or self.harness["repo"],
            work_order_id=WORK_ORDER_ID,
            stage=stage,
            verdicts_path=verdicts if verdicts is not None else self.verdicts_path,
            accuracy_open_issues=accuracy,
            flow_spec_path=flow if flow is not None else self.flow_path,
            golden_dir=golden,
        )
        return payload

    def case_dir(self, name: str) -> Path:
        target = self._root / f"case-{name}"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def mutated(
        self,
        name: str,
        page: str | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> tuple[Path, Path]:
        directory = self.case_dir(name)
        manifest_path = directory / "change-report-manifest.json"
        write_manifest(manifest if manifest is not None else self.manifest, manifest_path)
        report_path = directory / "change-report.html"
        report_path.write_bytes((page if page is not None else self.page).encode("utf-8"))
        return report_path, manifest_path

    def build_purpose_page(self, name: str) -> tuple[Path, int]:
        """Render a report that carries the full purpose layer (H42/A16/A17/D19)."""
        analysis = json.loads(json.dumps(self.analysis))
        indices = [hunk["unit_index"] for entry, hunk in unit_pairs(self.manifest)]
        first = indices[0]
        analysis["purposes"] = [
            {
                "id": "p1",
                "title": "Extend the reader navigation path",
                "theme": "platform",
                "narrative": "The change makes the reader path show the purpose of each unit.",
                "unit_refs": indices,
            }
        ]
        for index in indices:
            analysis["units"][str(index)]["purpose"] = {
                "id": "p1",
                "title": "Extend the reader navigation path",
            }
        analysis["units"][str(first)]["related_code_refs"] = [
            {
                "path": "src/app.py",
                "lines": "1-5",
                "note": "caller",
                "relation_type": "caller",
                "code": "def caller(): pass",
            }
        ]
        analysis["diagrams"].append(
            {
                "id": "diagram-purpose-map",
                "type": "flow",
                "render_mode": "svg",
                "title": "Purpose traceability",
                "summary": "Purpose to units.",
                "nodes": [
                    {"id": "p1", "label": "Extend reader path", "layer": 0, "kind": "purpose"},
                    {"id": "u1", "label": f"unit {first}", "layer": 2, "kind": "unit"},
                ],
                "edges": [{"from": "p1", "to": "u1", "label": "covers"}],
            }
        )
        out = self.case_dir(name) / "change-report.html"
        render_report(self.manifest, self.manifest_path, self.harness["repo"], analysis, out)
        return out, first


# --------------------------------------------------------------------------------------
# Positive cases
# --------------------------------------------------------------------------------------


class PositiveReportTests(ReportCase):
    def test_full_pipeline_passes_and_receipt_is_normalised(self) -> None:
        payload = self.validate()
        self.assertTrue(payload["ok"], payload["errors"])
        facts = payload["facts"]
        self.assertEqual(facts["coverage"], "complete")
        self.assertEqual(facts["units_total"], facts["units_covered"])
        self.assertEqual(facts["units_total"], facts["hash_bound"])
        self.assertEqual(facts["units_total"], facts["token_bound"])
        self.assertTrue(facts["self_contained"])
        self.assertTrue(facts["head_current"])
        self.assertEqual(payload["next_action"], "none")
        receipt = payload["receipt"]
        self.assertEqual(
            set(receipt), {"schema_version", "check", "ok", "subject", "facts"}
        )
        self.assertEqual(receipt["check"], "xc-change-report")
        # The runtime compares a declared completion-check fact against the blackboard as an
        # exact string, so every receipt fact must be text: "7", not 7; "true", not True.
        for key, value in receipt["facts"].items():
            self.assertIsInstance(value, str, key)
        self.assertEqual(receipt["facts"]["units_total"], str(facts["units_total"]))
        self.assertEqual(receipt["facts"]["self_contained"], "true")
        runtime_core.parse_check_results([json.dumps(receipt)])

    def test_final_stage_passes_with_accuracy_verdicts(self) -> None:
        payload = self.validate(stage="final", accuracy="false")
        self.assertTrue(payload["ok"], payload["errors"])
        self.assertEqual(payload["details"]["accuracy"]["status"], "checked")
        self.assertEqual(payload["details"]["accuracy"]["wrong"], 0)

    def test_report_is_a_single_self_contained_file(self) -> None:
        self.assertIn("<!DOCTYPE html>", self.page)
        self.assertNotIn("http://", self.page)
        self.assertNotIn("xmlns", self.page)
        self.assertFalse(
            [item for item in self._root.iterdir() if item.is_file() and item.suffix in {".css", ".js"}]
        )
        self.assertIn("<style>", self.page)

    def test_positive_golden_svg_fixtures_are_matched(self) -> None:
        payload = self.validate(golden=GOLDEN_DIR)
        self.assertTrue(payload["ok"], payload["errors"])
        self.assertEqual(payload["details"]["diagrams"]["svg"], 2)
        self.assertEqual(payload["details"]["diagrams"]["table"], 1)

    def test_url_text_inside_a_code_block_is_exempt(self) -> None:
        self.assertIn("https://api.example.invalid/v1", self.page)
        payload = self.validate()
        self.assertNotIn("V7", error_ids(payload))

    def test_purpose_layer_renders_and_validates(self) -> None:
        analysis = json.loads(json.dumps(self.analysis))
        indices = [hunk["unit_index"] for entry, hunk in unit_pairs(self.manifest)]
        first = indices[0]
        analysis["purposes"] = [
            {
                "id": "p1",
                "title": "Extend the reader navigation path",
                "theme": "platform",
                "narrative": "The change makes the reader path show the purpose of each unit.",
                "unit_refs": indices,
            }
        ]
        for index in indices:
            analysis["units"][str(index)]["purpose"] = {
                "id": "p1",
                "title": "Extend the reader navigation path",
            }
        analysis["units"][str(first)]["related_code_refs"] = [
            {
                "path": "src/app.py",
                "lines": "1-5",
                "note": "caller",
                "relation_type": "caller",
                "code": "def caller(): pass",
            }
        ]
        analysis["diagrams"].append(
            {
                "id": "diagram-purpose-map",
                "type": "flow",
                "render_mode": "svg",
                "title": "Purpose traceability",
                "summary": "Purpose to units.",
                "nodes": [
                    {"id": "p1", "label": "Extend reader path", "layer": 0, "kind": "purpose"},
                    {"id": "u1", "label": f"unit {first}", "layer": 2, "kind": "unit"},
                ],
                "edges": [{"from": "p1", "to": "u1", "label": "covers"}],
            }
        )
        out = self.case_dir("purpose-layer") / "change-report.html"
        page = render_report(self.manifest, self.manifest_path, self.harness["repo"], analysis, out)
        self.assertIn('id="section-purposes"', page)
        self.assertIn("report-purpose-card", page)
        self.assertIn('data-purpose="p1"', page)
        self.assertIn("diagram-node-purpose", page)
        payload = self.validate(report=out)
        self.assertTrue(payload["ok"], payload["errors"])

    def test_full_strength_requires_a_glossary(self) -> None:
        manifest = json.loads(json.dumps(self.manifest))
        manifest["strength"] = {
            "selected": "full",
            "requested": "full",
            "upgraded": False,
            "upgrade_reason": "",
        }
        directory = self.case_dir("full-strength")
        manifest_path = write_manifest(manifest, directory / "change-report-manifest.json")
        analysis = make_analysis(manifest, self.harness["repo"])
        with self.assertRaises(bs.SkeletonError):
            bs.build_report(
                repo=self.harness["repo"],
                manifest=manifest,
                analysis=analysis,
                template_text=(SKILL_ROOT / "assets" / "change-report-template.html").read_text(encoding="utf-8"),
                css_text=(SKILL_ROOT / "assets" / "change-report.css").read_text(encoding="utf-8"),
                generated_at="2026-09-15T18:00:00Z",
                manifest_bytes=manifest_path.read_bytes(),
            )
        analysis["glossary"] = [{"term": "unit", "explanation": "one analysable change unit"}]
        page = bs.build_report(
            repo=self.harness["repo"],
            manifest=manifest,
            analysis=analysis,
            template_text=(SKILL_ROOT / "assets" / "change-report-template.html").read_text(encoding="utf-8"),
            css_text=(SKILL_ROOT / "assets" / "change-report.css").read_text(encoding="utf-8"),
            generated_at="2026-09-15T18:00:00Z",
            manifest_bytes=manifest_path.read_bytes(),
        )
        self.assertIn("glossary-table", page)

    def test_file_slug_rule_and_file_level_anchors(self) -> None:
        self.assertEqual(bm.file_slug("src/App.Config.json"), "src-app-config-json")
        self.assertEqual(bm.file_slug("a\\b..c"), "a-b-c")
        for entry in self.manifest["files"]:
            for hunk in entry["hunks"]:
                if hunk["excluded"]:
                    continue
                self.assertIn(f'id="file-{bm.file_slug(entry["path"])}"', self.page)
                break

    def test_unit_index_is_global_and_monotonic(self) -> None:
        indexes = [hunk["unit_index"] for _, hunk in unit_pairs(self.manifest)]
        self.assertEqual(indexes, list(range(1, len(indexes) + 1)))
        self.assertEqual(self.manifest["units_total"], len(indexes))

    def test_strength_upgrades_one_way_from_minimal(self) -> None:
        manifest = build_manifest_for(self.harness, strength="minimal")
        self.assertGreater(manifest["units_total"], bm.MAX_UNITS_MINIMAL)
        self.assertEqual(manifest["strength"]["selected"], "standard")
        self.assertTrue(manifest["strength"]["upgraded"])
        self.assertEqual(manifest["strength"]["upgrade_reason"], "units_total_exceeds_max_units_minimal")

    def test_large_added_file_is_windowed_into_several_units(self) -> None:
        entry = next(item for item in self.manifest["files"] if item["path"] == "src/big_new.py")
        self.assertEqual(len(entry["hunks"]), 9)
        for hunk in entry["hunks"]:
            self.assertLessEqual(bm.range_length(hunk["new_range"]), bm.ADDED_UNIT_BLOCK_LINES)

    def test_deterministic_rerender_is_byte_identical(self) -> None:
        second = self.case_dir("rerender") / "change-report.html"
        page = render_report(
            self.manifest, self.manifest_path, self.harness["repo"], self.analysis, second
        )
        self.assertEqual(page, self.page)
        manifest_again = build_manifest_for(self.harness)
        self.assertEqual(
            json.dumps(manifest_again, sort_keys=True), json.dumps(self.manifest, sort_keys=True)
        )


class DiagramTests(unittest.TestCase):
    def test_svg_rendering_is_byte_stable_and_matches_golden(self) -> None:
        for name, kind in (("flow", "flow"), ("state", "state")):
            spec = json.loads((GOLDEN_DIR / f"{name}-spec.json").read_text(encoding="utf-8"))
            first = rd.render_diagram(spec)
            second = rd.render_diagram(spec)
            self.assertEqual(first, second, name)
            golden = (GOLDEN_DIR / f"{kind}-golden.svg").read_text(encoding="utf-8").strip()
            svg = re.search(r"<svg class=\"report-diagram-svg\".*?</svg>", first, re.S)
            self.assertIsNotNone(svg)
            self.assertEqual(svg.group(0).strip(), golden, name)

    def test_table_render_modes_emit_tables_and_never_geometry(self) -> None:
        spec = json.loads((GOLDEN_DIR / "sequence-spec.json").read_text(encoding="utf-8"))
        html = rd.render_diagram(spec)
        self.assertIn('class="report-diagram-table"', html)
        self.assertNotIn("<svg class=\"report-diagram-svg\"", html)
        self.assertIn("<title>", html)
        self.assertIn("<desc>", html)

    def test_unknown_type_and_mismatched_render_mode_are_errors(self) -> None:
        with self.assertRaises(rd.DiagramError):
            rd.render_diagram({"id": "d", "type": "timeline", "render_mode": "svg"})
        with self.assertRaises(rd.DiagramError):
            rd.render_diagram({"id": "d", "type": "flow", "render_mode": "table"})
        # sequence is a dual carrier (D22): an unknown render_mode is still an error.
        with self.assertRaises(rd.DiagramError):
            rd.render_diagram({"id": "d", "type": "sequence", "render_mode": "diagram"})

    def test_geometry_constants_are_respected(self) -> None:
        spec = {
            "id": "diagram-wide",
            "type": "flow",
            "render_mode": "svg",
            "title": "wide",
            "summary": "wide diagram",
            "nodes": [
                {"id": f"n{index}", "label": "x" * 80, "layer": 0} for index in range(9)
            ],
            "edges": [],
        }
        html = rd.render_diagram(spec)
        widths = [int(value) for value in re.findall(r"width=\"(\d+)\"", html)]
        self.assertTrue(widths)
        for width in widths:
            self.assertLessEqual(width, bm.MAX_SVG_CANVAS_WIDTH)
        self.assertIn("-page-", html)
        for label in re.findall(r"<text[^>]*>(?:<title>.*?</title>)?([^<]*)</text>", html):
            self.assertLessEqual(len(label), bm.MAX_TEXT_NODE_CHARS)


class HighlightTests(unittest.TestCase):
    def test_highlighting_is_a_pure_function(self) -> None:
        source = 'def f(x):\n    # comment\n    return "text" + str(42)\n'
        first = hc.highlight(source, "python")
        second = hc.highlight(source, "python")
        self.assertEqual(first, second)
        self.assertIn('class="tok-keyword"', first)
        self.assertIn('class="tok-string"', first)
        self.assertIn('class="tok-comment"', first)
        self.assertIn('class="tok-number"', first)

    def test_highlighting_never_changes_the_code_text(self) -> None:
        line = "x = \"<tag> & 'quote'\""
        html = hc.highlight(line, "python")
        self.assertIn("&lt;tag&gt; &amp;", html)
        self.assertEqual(bm.normalize_code_text(bm.render_code_rows([("ctx", 1, html)])), line + "\n")

    def test_unknown_extension_degrades_to_plain_text(self) -> None:
        self.assertEqual(hc.detect_language("file.unknownext"), "text")
        self.assertNotIn("<span", hc.highlight("plain text", "text"))


# --------------------------------------------------------------------------------------
# Fixture-specific regression anchors (R1, R2, C11, R7)
# --------------------------------------------------------------------------------------


class EnumerationRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._root = Path(tempfile.mkdtemp(prefix="xc-report-enum-"))
        self.addCleanup(shutil.rmtree, self._root, ignore_errors=True)

    def test_untracked_new_file_becomes_an_added_unit(self) -> None:
        harness = materialise("untracked-new-file", self._root)
        repo = harness["repo"]
        git_diff = subprocess.run(
            ["git", "diff", "--name-status", harness["commit"], "--"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout
        self.assertNotIn("brand-new.txt", git_diff)
        manifest = build_manifest_for(harness)
        entry = next(item for item in manifest["files"] if item["path"] == "brand-new.txt")
        self.assertEqual(entry["change_kind"], "added")
        self.assertTrue(entry["analyzable"])
        self.assertEqual(len(entry["hunks"]), 1)
        self.assertEqual(manifest["units_total"], 2)

    def test_rename_grouping_needs_exact_hashes_and_no_renames_flag(self) -> None:
        harness = materialise("rename", self._root)
        repo = harness["repo"]

        def name_status(*extra: str) -> str:
            return subprocess.run(
                ["git", "diff", *extra, "--name-status", harness["commit"], "--"],
                cwd=str(repo),
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout

        # Reproduce R1's measured evidence: with the additions in the index, git's own
        # similarity heuristic reports a rename by default and a delete+add with
        # --no-renames. The two runs must differ, which is why the enumeration forces
        # --no-renames and pairs by exact content hash itself.
        _git(repo, "add", "-A")
        try:
            with_renames = name_status()
            without = name_status("--no-renames")
            self.assertNotEqual(with_renames, without)
            self.assertIn("R100", with_renames)
        finally:
            _git(repo, "reset", "-q")

        manifest = build_manifest_for(harness)
        kinds = {item["path"]: item["change_kind"] for item in manifest["files"]}
        self.assertEqual(kinds["renamed.txt"], "renamed")
        self.assertEqual(kinds["b-moved.txt"], "added")
        self.assertEqual(kinds["b.txt"], "deleted")
        exact = next(item for item in manifest["files"] if item["path"] == "renamed.txt")
        self.assertEqual(exact["renamed_from"], "a.txt")
        self.assertEqual(len(exact["hunks"]), 1)

    def test_pre_existing_edits_are_split_out_of_the_change_set(self) -> None:
        harness = materialise("dirty-worktree", self._root)
        manifest = build_manifest_for(harness)
        self.assertEqual(manifest["units_total"], 3)
        self.assertEqual(manifest["pre_existing_total"], 2)
        self.assertEqual(sorted(manifest["pre_existing_files"]), ["far_apart.txt", "user_only.txt"])

        far = next(item for item in manifest["files"] if item["path"] == "far_apart.txt")
        self.assertEqual(far["analyzed_as"], "mixed")
        provenances = [hunk["provenance"] for hunk in far["hunks"]]
        self.assertIn("pre_existing", provenances)
        self.assertIn("work_order", provenances)

        shared = next(item for item in manifest["files"] if item["path"] == "shared.txt")
        self.assertTrue(any(hunk["overlaps_pre_existing"] for hunk in shared["hunks"]))

        # C4a: the file existed before the work order opened and never changed, so it is
        # not part of the change set at all; the snapshot exists so that a later deletion
        # of such a file stays recomputable (see the next test).
        self.assertNotIn("user_scratch.txt", [item["path"] for item in manifest["files"]])
        self.assertEqual(manifest["degradations"], [])

    def test_untracked_baseline_snapshot_drives_deletions(self) -> None:
        harness = materialise("dirty-worktree", self._root)
        scratch = harness["repo"] / "user_scratch.txt"
        scratch.unlink()
        manifest = build_manifest_for(harness)
        entry = next(item for item in manifest["files"] if item["path"] == "user_scratch.txt")
        self.assertEqual(entry["change_kind"], "deleted")
        self.assertEqual(entry["baseline_source"], "untracked_snapshot")
        self.assertEqual(len(entry["hunks"]), 1)

    def test_sensitive_and_encoding_paths_are_recorded(self) -> None:
        harness = materialise("exotic-content", self._root)
        manifest = build_manifest_for(harness)
        by_path = {item["path"]: item for item in manifest["files"]}
        for sensitive in (".env", "config/service-account.json", "keys/server.pem", "src/embedded_key.py"):
            self.assertEqual(by_path[sensitive]["exclude_reason"], "sensitive", sensitive)
            self.assertFalse(by_path[sensitive]["analyzable"], sensitive)
            self.assertEqual(by_path[sensitive]["hunks"], [], sensitive)
        latin = by_path["src/latin.py"]
        self.assertTrue(latin["encoding_unsupported"])
        self.assertTrue(latin["analyzable"])
        self.assertEqual(len(latin["hunks"]), 1)
        token = by_path["src/legacy_token.py"]
        self.assertTrue(token["analyzable"])
        self.assertTrue(any(hunk["redacted"] for hunk in token["hunks"]))
        self.assertIn(token["hunks"][0]["unit_index"], manifest["redacted_units"])

    def test_exotic_report_has_no_secret_text_and_marks_degradation(self) -> None:
        harness = materialise("exotic-content", self._root)
        manifest = build_manifest_for(harness)
        manifest_path = write_manifest(manifest, self._root / "m.json")
        analysis = make_analysis(manifest, harness["repo"])
        report = self._root / "r.html"
        page = render_report(manifest, manifest_path, harness["repo"], analysis, report)
        import html as html_module

        self.assertNotIn("ghp_ABCDEFGHIJKLMNOPQRSTUVWX", page)
        self.assertIn("<<redacted:sha256=", html_module.unescape(page))
        self.assertIn("not valid UTF-8", page)
        payload, _ = vr.validate(
            report_path=report,
            manifest_path=manifest_path,
            repo=harness["repo"],
            work_order_id=WORK_ORDER_ID,
            stage="coverage",
            verdicts_path=None,
            accuracy_open_issues=None,
            flow_spec_path=self._root / "absent-flow.json",
            golden_dir=None,
        )
        self.assertTrue(payload["ok"], payload["errors"])
        self.assertEqual(payload["details"]["gate"]["status"], "not_applicable")


# --------------------------------------------------------------------------------------
# Negative cases 1-26 from the design specification's verification strategy
# --------------------------------------------------------------------------------------


class NegativeCaseTests(ReportCase):
    def test_negative_v17_missing_purpose_section_fails(self) -> None:
        report, _ = self.build_purpose_page("nv17")
        page = re.sub(
            r'<section class="report-section" id="section-purposes">.*?</section>',
            "",
            report.read_text(encoding="utf-8"),
            flags=re.S,
        )
        out, manifest = self.mutated("nv17", page=page)
        payload = self.validate(report=out, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V17", error_ids(payload))

    def test_negative_v18_mismatched_purpose_tag_fails(self) -> None:
        report, first = self.build_purpose_page("nv18")
        page = report.read_text(encoding="utf-8").replace(
            f'id="unit-{first}" data-unit="{first}" data-purpose="p1"',
            f'id="unit-{first}" data-unit="{first}" data-purpose="p2"',
            1,
        )
        out, manifest = self.mutated("nv18", page=page)
        payload = self.validate(report=out, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V18", error_ids(payload))

    def test_negative_v19_missing_toc_unit_fails(self) -> None:
        report, first = self.build_purpose_page("nv19")
        page = re.sub(
            rf'<li class="report-toc-unit"><a href="#unit-{first}">.*?</li>',
            "",
            report.read_text(encoding="utf-8"),
            count=1,
            flags=re.S,
        )
        out, manifest = self.mutated("nv19", page=page)
        payload = self.validate(report=out, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V19", error_ids(payload))

    def test_negative_v20_context_block_missing_path_fails(self) -> None:
        report, _ = self.build_purpose_page("nv20")
        page = report.read_text(encoding="utf-8").replace(
            'data-path="src/app.py"', 'data-path=""', 1
        )
        out, manifest = self.mutated("nv20", page=page)
        payload = self.validate(report=out, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V20", error_ids(payload))

    def test_negative_01_missing_analysis_section_fails_v2(self) -> None:
        page = re.sub(
            r'<article class="report-unit" id="unit-2".*?</article>', "", self.page, flags=re.S
        )
        report, manifest = self.mutated("n01", page=page)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V2", error_ids(payload))
        self.assertTrue(any("#unit-2" in item["message"] for item in payload["errors"]))

    def test_negative_02_placeholder_analysis_fails_v4(self) -> None:
        page = self.page.replace(
            '<h4>Why it exists</h4><p>why: ', '<h4>Why it exists</h4><p>TODO ', 1
        )
        report, manifest = self.mutated("n02", page=page)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V4", error_ids(payload))
        self.assertTrue(any("placeholder" in item["message"] for item in payload["errors"]))

    def test_negative_02b_short_analysis_fails_v4(self) -> None:
        page = re.sub(
            r'(<div class="report-unit-field" data-field="tradeoffs"><h4>[^<]*</h4><p>)[^<]*(</p>)',
            r"\1too short\2",
            self.page,
            count=1,
        )
        report, manifest = self.mutated("n02b", page=page)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V4", error_ids(payload))

    def test_negative_03_stale_manifest_fails_v9_and_routes_to_the_refresh_edge(self) -> None:
        covered = self.harness["repo"] / "src" / "app.py"
        original = covered.read_text(encoding="utf-8")
        try:
            # write_bytes, not write_text: text mode would translate LF to CRLF on Windows
            # and permanently change the covered file, making every later test stale.
            covered.write_bytes((original + "\n# touched after generation\n").encode("utf-8"))
            report, manifest = self.mutated("n03")
            payload = self.validate(report=report, manifest=manifest)
        finally:
            covered.write_bytes(original.encode("utf-8"))
        self.assertFalse(payload["ok"])
        self.assertEqual(error_ids(payload), {"V9"})
        self.assertEqual(payload["next_action"], "refresh")
        self.assertIn("refresh edge", payload["errors"][0]["message"])

    def test_negative_04_dangling_anchor_fails_v6(self) -> None:
        page = self.page.replace(
            "</main>", '<p><a href="#unit-999">dangling link</a></p></main>', 1
        )
        report, manifest = self.mutated("n04", page=page)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V6", error_ids(payload))

    def test_negative_05_external_resources_fail_v7(self) -> None:
        injections = {
            "url": '<p>See https://example.invalid/docs for details.</p>',
            "link": '<link rel="stylesheet" href="theme.css">',
            "script": '<script src="app.js"></script>',
            "img": '<img src="logo.png" alt="logo">',
            "iframe": '<iframe src="frame.html"></iframe>',
        }
        for name, snippet in injections.items():
            with self.subTest(name=name):
                report, manifest = self.mutated(
                    f"n05-{name}", page=self.page.replace("</main>", snippet + "</main>", 1)
                )
                payload = self.validate(report=report, manifest=manifest)
                self.assertFalse(payload["ok"], name)
                self.assertIn("V7", error_ids(payload), name)

    def test_negative_06_unknown_diagram_type_fails_v8(self) -> None:
        page = self.page.replace(
            '"type": "sequence"', '"type": "timeline"', 1
        )
        report, manifest = self.mutated("n06", page=page)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V8", error_ids(payload))
        self.assertTrue(any("unsupported type" in item["message"] for item in payload["errors"]))

    def test_negative_07_out_of_scope_section_fails_v3(self) -> None:
        page = self.page.replace(
            "</section>\n<section class=\"report-section\" id=\"section-related-code\">",
            '</section><article class="report-unit" id="unit-99" data-unit="99" '
            'data-covers="#unit-99"></article>'
            '<section class="report-section" id="section-related-code">',
            1,
        )
        report, manifest = self.mutated("n07", page=page)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V3", error_ids(payload))

    def test_negative_08_structure_defects_fail_v5(self) -> None:
        cases = {
            "missing-section": re.sub(
                r'<section class="report-section" id="section-glossary">.*?</section>',
                "",
                self.page,
                flags=re.S,
            ),
            "missing-map-row": re.sub(
                r'<tr data-unit="1"[^>]*>.*?</tr>', "", self.page, count=1, flags=re.S
            ),
        }
        for name, page in cases.items():
            with self.subTest(name=name):
                report, manifest = self.mutated(f"n08-{name}", page=page)
                payload = self.validate(report=report, manifest=manifest)
                self.assertFalse(payload["ok"], name)
                self.assertIn("V5", error_ids(payload), name)

    def test_negative_09_manifest_corruption_fails_v1(self) -> None:
        cases: dict[str, Any] = {}
        cases["schema"] = json.loads(json.dumps(self.manifest))
        cases["schema"]["schema_version"] = 99
        cases["work_order"] = json.loads(json.dumps(self.manifest))
        cases["work_order"]["work_order_id"] = "some-other-work-order"
        cases["counts"] = json.loads(json.dumps(self.manifest))
        cases["counts"]["units_total"] = 99
        cases["enumeration"] = json.loads(json.dumps(self.manifest))
        cases["enumeration"]["enumeration"]["version"] = "v0"
        for name, manifest in cases.items():
            with self.subTest(name=name):
                report, manifest_path = self.mutated(f"n09-{name}", manifest=manifest)
                payload = self.validate(report=report, manifest=manifest_path)
                self.assertFalse(payload["ok"], name)
                self.assertIn("V1", error_ids(payload), name)

    def test_negative_10_diagram_referencing_a_missing_node_fails_v8(self) -> None:
        page = self.page.replace(
            '"to": "validate"', '"to": "does-not-exist"', 1
        )
        report, manifest = self.mutated("n10", page=page)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V8", error_ids(payload))
        self.assertTrue(any("unknown" in item["message"] for item in payload["errors"]))

    def test_negative_11_check_result_receipt_is_untrusted_self_report(self) -> None:
        """The runtime accepts a structurally valid receipt even when coverage is false."""
        page = re.sub(
            r'<article class="report-unit" id="unit-3".*?</article>', "", self.page, flags=re.S
        )
        report, manifest = self.mutated("n11", page=page)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])

        forged = {
            "schema_version": 1,
            "check": "xc-check-result-forged",
            "ok": True,
            "subject": str(report),
            "facts": {"units_total": 7},
        }
        accepted = runtime_core.parse_check_results([json.dumps(forged)])
        self.assertEqual(len(accepted), 1)
        self.assertTrue(accepted[0]["ok"])
        genuine = self.validate()["receipt"]
        self.assertEqual(set(genuine), set(forged))
        self.assertNotEqual(genuine["ok"], payload["receipt"]["ok"])

    def test_negative_12_untracked_new_file_must_be_an_added_unit(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="xc-report-n12-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        harness = materialise("untracked-new-file", root)
        manifest = build_manifest_for(harness)
        self.assertIn("brand-new.txt", [item["path"] for item in manifest["files"]])
        only_git_diff = subprocess.run(
            ["git", "diff", "--name-status", harness["commit"], "--"],
            cwd=str(harness["repo"]),
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout
        self.assertNotIn("brand-new.txt", only_git_diff)

    def test_negative_13_rename_grouping_drifts_without_no_renames(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="xc-report-n13-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        harness = materialise("rename", root)
        _git(harness["repo"], "add", "-A")
        try:
            default = subprocess.run(
                ["git", "diff", "--name-status", harness["commit"], "--"],
                cwd=str(harness["repo"]),
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout
            explicit = subprocess.run(
                ["git", "diff", "--no-renames", "--name-status", harness["commit"], "--"],
                cwd=str(harness["repo"]),
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout
        finally:
            _git(harness["repo"], "reset", "-q")
        self.assertNotEqual(default, explicit)
        manifest = build_manifest_for(harness)
        renamed = [item for item in manifest["files"] if item["change_kind"] == "renamed"]
        self.assertEqual(len(renamed), 1)
        self.assertEqual(renamed[0]["renamed_from"], "a.txt")
        changed = [
            item
            for item in manifest["files"]
            if item["path"] in {"b.txt", "b-moved.txt"}
        ]
        self.assertEqual(len(changed), 2)
        self.assertIn("--no-renames", json.dumps(manifest["enumeration"]))

    def test_negative_14_pre_existing_counted_as_work_order_fails(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="xc-report-n14-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        harness = materialise("dirty-worktree", root)
        manifest = build_manifest_for(harness)
        manifest_path = write_manifest(manifest, root / "m.json")
        analysis = make_analysis(manifest, harness["repo"])
        report = root / "r.html"
        render_report(manifest, manifest_path, harness["repo"], analysis, report)

        tampered = json.loads(json.dumps(manifest))
        next_index = tampered["units_total"]
        for entry in tampered["files"]:
            for hunk in entry["hunks"]:
                if hunk["provenance"] != "pre_existing":
                    continue
                next_index += 1
                hunk.update(
                    {
                        "provenance": "work_order",
                        "excluded": False,
                        "exclude_reason": "",
                        "unit_index": next_index,
                        "anchor": f"#unit-{next_index}",
                    }
                )
        tampered["units_total"] = next_index
        tampered_path = write_manifest(tampered, root / "tampered.json")
        payload, _ = vr.validate(
            report_path=report,
            manifest_path=tampered_path,
            repo=harness["repo"],
            work_order_id=WORK_ORDER_ID,
            stage="coverage",
            verdicts_path=None,
            accuracy_open_issues=None,
            flow_spec_path=root / "absent.json",
            golden_dir=None,
        )
        self.assertFalse(payload["ok"])
        self.assertIn("V1", error_ids(payload))
        self.assertIn("V5", error_ids(payload))

    def test_negative_15_excluded_entries_subtracted_twice_fails(self) -> None:
        tampered = json.loads(json.dumps(self.manifest))
        tampered["units_total"] = tampered["units_total"] - tampered["excluded_total"]
        report, manifest = self.mutated("n15", manifest=tampered)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V1", error_ids(payload))
        self.assertIn("V5", error_ids(payload))

    def test_negative_16_duplicate_unit_indexes_fail(self) -> None:
        # (a) per-file numbering would restart at 1 and duplicate #unit-1 in the manifest.
        tampered = json.loads(json.dumps(self.manifest))
        target = None
        for entry in tampered["files"]:
            for hunk in entry["hunks"]:
                if not hunk["excluded"] and hunk["unit_index"] == 3:
                    target = hunk
        self.assertIsNotNone(target)
        target["unit_index"] = 1
        target["anchor"] = "#unit-1"
        report, manifest = self.mutated("n16a", manifest=tampered)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V1", error_ids(payload))
        self.assertTrue(any("monotonic" in item["message"] for item in payload["errors"]))
        self.assertIn("V3", error_ids(payload))

        # (b) a page that reuses #unit-1 for a second section loses the real #unit-2 anchor.
        page = self.page.replace(
            '<article class="report-unit" id="unit-2" data-unit="2"',
            '<article class="report-unit" id="unit-1" data-unit="2"',
            1,
        )
        report, manifest = self.mutated("n16b", page=page)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V2", error_ids(payload))
        self.assertTrue(any("#unit-2" in item["message"] for item in payload["errors"]))

    def test_negative_17_filler_attack_fails_v11(self) -> None:
        filler = (
            "This unit performs some processing and handles the values that pass through it. "
            "The change keeps the behaviour stable for all other inputs and callers."
        )
        page = self.page
        for field in bm.FIELD_NAMES:
            page = re.sub(
                r'(<div class="report-unit-field" data-field="'
                + re.escape(field)
                + r'"><h4>[^<]*</h4><p>)[^<]*(</p>)',
                lambda match: match.group(1) + filler + match.group(2),
                page,
            )
        report, manifest = self.mutated("n17", page=page)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V11", error_ids(payload))
        self.assertTrue(any("Available tokens" in item["message"] for item in payload["errors"]))

    def test_negative_18_swapped_code_block_fails_v10(self) -> None:
        block_one = re.search(
            r'<pre class="report-code" data-unit="1"><code>.*?</code></pre>', self.page, re.S
        )
        block_two = re.search(
            r'<pre class="report-code" data-unit="2"><code>.*?</code></pre>', self.page, re.S
        )
        self.assertIsNotNone(block_one)
        self.assertIsNotNone(block_two)
        page = self.page.replace(block_one.group(0), "@@BLOCK_ONE@@")
        page = page.replace(block_two.group(0), "@@BLOCK_TWO@@")
        page = page.replace("@@BLOCK_ONE@@", block_two.group(0).replace('data-unit="2"', 'data-unit="1"'))
        page = page.replace("@@BLOCK_TWO@@", block_one.group(0).replace('data-unit="1"', 'data-unit="2"'))
        report, manifest = self.mutated("n18", page=page)
        payload = self.validate(report=report, manifest=manifest)
        self.assertFalse(payload["ok"])
        self.assertIn("V10", error_ids(payload))
        message = next(item["message"] for item in payload["errors"] if item["id"] == "V10")
        self.assertIn("expected content_sha256", message)
        self.assertIn("recomputed", message)

    def test_negative_19_external_fetches_outside_code_blocks_fail_v7(self) -> None:
        snippets = {
            "bare-url": "<p>https://example.invalid/one</p>",
            "css-url": '<div style="background: url(https://example.invalid/x.png)">x</div>',
            "iframe": '<iframe title="x"></iframe>',
            "svg-image": '<svg width="10" height="10"><image href="https://example.invalid/y.png" /></svg>',
            "svg-use": '<svg width="10" height="10"><use href="https://example.invalid/z.svg" /></svg>',
            "css-import": "<style>@import url(theme.css);</style>",
        }
        for name, snippet in snippets.items():
            with self.subTest(name=name):
                report, manifest = self.mutated(
                    f"n19-{name}", page=self.page.replace("</main>", snippet + "</main>", 1)
                )
                payload = self.validate(report=report, manifest=manifest)
                self.assertFalse(payload["ok"], name)
                self.assertIn("V7", error_ids(payload), name)

    def test_negative_19b_url_inside_a_code_block_is_exempt(self) -> None:
        self.assertIn("https://api.example.invalid/v1", self.page)
        payload = self.validate()
        self.assertNotIn("V7", error_ids(payload))

    def test_shipped_flow_spec_satisfies_v12(self) -> None:
        """The orchestration package's own spec must pass the routing contract.

        The latch pairing (O1/O4) is the specification's most heavily reviewed defect, so
        this asserts that the shipped spec is actually judged by it rather than reported as
        an undeclared, unassessed skip.
        """
        spec_path = SKILL_ROOT / "assets" / "change-report-flow.json"
        if not spec_path.is_file():
            self.skipTest("the orchestration package is built by a sibling node")
        payload = self.validate(flow=spec_path)
        self.assertNotIn("V12", error_ids(payload), payload["errors"])
        self.assertEqual(payload["details"]["gate"]["declared"], sorted(bm.REPORT_GATE_OUTCOMES))
        self.assertIn(payload["details"]["gate"]["route_source"], {"declared", "derived-booleans"})
        self.assertEqual(payload["details"]["gate"]["latch_pairing"], "checked")

    def test_shipped_flow_spec_declares_the_o4_latch_pairings(self) -> None:
        """O1/O4 mechanised: the declaration, the node contracts and the topology agree."""
        spec = json.loads(
            (SKILL_ROOT / "assets" / "change-report-flow.json").read_text(encoding="utf-8")
        )
        loop = next(
            child for child in spec["root"]["children"]
            if child["template_id"] == "report-pass-loop"
        )
        declared = json.loads(loop["metadata"]["rework_publishers"])
        by_path: dict[str, dict[str, str]] = {}
        for item in declared:
            by_path.setdefault(item["terminates_round"], {})[item["publishes"]] = item["node"]
        self.assertEqual(
            by_path,
            {
                # The gate contributes only the `true` that carries control back to the next
                # pass. The round it terminates has no reset by design, and validate-final writes
                # the value that ends the pass in every round the gate did not terminate.
                "gate-rework": {"true": "report-gate"},
                "review-loop-exit": {"true": "validate-final", "false": "validate-final"},
                "validate-final-stale": {"true": "validate-final", "false": "validate-final"},
            },
        )
        order = [child["template_id"] for child in loop["children"]]
        self.assertIn("report-gate", order)
        self.assertEqual(order[order.index("report-gate") + 1], "report-gate-recovery-group")
        self.assertLess(order.index("report-gate-recovery-group"), order.index("validate-final"))
        final = next(c for c in loop["children"] if c["template_id"] == "validate-final")
        self.assertEqual(final["when"], "report.gate_recovery_required == false")

    def test_negative_20_undeclared_gate_outcome_fails_v12(self) -> None:
        cases = {
            "fifth-value": flow_spec(
                declared=list(bm.REPORT_GATE_OUTCOMES) + ["escalated"],
                routes={
                    "accepted": "validate-final",
                    "revision-required": "report-gate-recovery-group",
                    "rejected": "report-gate-recovery-group",
                    "accepted-with-followup": "validate-final",
                },
            ),
            "missing-declared": flow_spec(
                declared=["accepted", "revision-required", "rejected"],
                routes={
                    "accepted": "validate-final",
                    "revision-required": "report-gate-recovery-group",
                    "rejected": "report-gate-recovery-group",
                    "accepted-with-followup": "validate-final",
                },
            ),
            "rework-on-outcome-string": flow_spec(
                rework_when="report.gate_outcome != accepted"
            ),
        }
        for name, spec in cases.items():
            with self.subTest(name=name):
                path = write_flow_spec(spec, self.case_dir(f"n20-{name}") / "flow.json")
                payload = self.validate(flow=path)
                self.assertFalse(payload["ok"], name)
                self.assertIn("V12", error_ids(payload), name)
        accepted_with_followup = write_flow_spec(
            flow_spec(), self.case_dir("n20-positive") / "flow.json"
        )
        payload = self.validate(flow=accepted_with_followup)
        self.assertTrue(payload["ok"], payload["errors"])

    def test_negative_20b_both_loops_must_escalate_instead_of_failing(self) -> None:
        """G-33: an exhausted quality loop escalates; it must never kill the work order.

        `retry-failed` requires a failed executable leaf and rejects a loop, so a quality loop
        that terminates `failed` is unrecoverable and takes its whole work order with it. Both
        loops are asserted independently, because a regression that flips only one of them is
        exactly the shape the previous value shipped in.
        """
        shipped = json.loads(
            (SKILL_ROOT / "assets" / "change-report-flow.json").read_text(encoding="utf-8")
        )
        by_template: dict[str, dict[str, Any]] = {}

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if "template_id" in node:
                    by_template[str(node["template_id"])] = node
                for child in node.get("children", []) or []:
                    walk(child)

        walk(shipped["root"])
        for template_id in ("report-pass-loop", "report-review-loop"):
            with self.subTest(loop=template_id):
                self.assertEqual(
                    str(by_template[template_id]["loop.on_limit"]),
                    "blocked",
                    f"{template_id} must escalate an exhausted loop instead of failing it",
                )

        for loop in ("outer", "inner"):
            with self.subTest(rejected=f"{loop} on_limit=failed"):
                spec = flow_spec(**{f"{loop}_on_limit": "failed"})
                path = write_flow_spec(spec, self.case_dir(f"n20b-{loop}") / "flow.json")
                payload = self.validate(flow=path)
                self.assertFalse(payload["ok"], loop)
                self.assertIn("V12", error_ids(payload), loop)

        blocked = write_flow_spec(flow_spec(), self.case_dir("n20b-positive") / "flow.json")
        payload = self.validate(flow=blocked)
        self.assertTrue(payload["ok"], payload["errors"])

    def test_negative_21_secret_and_encoding_rules_fail_v13(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="xc-report-n21-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        harness = materialise("exotic-content", root)
        manifest = build_manifest_for(harness)
        manifest_path = write_manifest(manifest, root / "m.json")
        analysis = make_analysis(manifest, harness["repo"])
        report = root / "r.html"
        page = render_report(manifest, manifest_path, harness["repo"], analysis, report)

        def run(manifest_file: Path, page_text: str, name: str) -> dict[str, Any]:
            directory = root / name
            directory.mkdir(parents=True, exist_ok=True)
            local_report = directory / "change-report.html"
            local_report.write_text(page_text, encoding="utf-8")
            payload, _ = vr.validate(
                report_path=local_report,
                manifest_path=manifest_file,
                repo=harness["repo"],
                work_order_id=WORK_ORDER_ID,
                stage="coverage",
                verdicts_path=None,
                accuracy_open_issues=None,
                flow_spec_path=root / "absent.json",
                golden_dir=None,
            )
            return payload

        tampered = json.loads(json.dumps(manifest))
        for entry in tampered["files"]:
            if entry["path"] == ".env":
                entry["analyzable"] = True
                entry["exclude_reason"] = ""
        tampered_path = write_manifest(tampered, root / "tampered.json")
        payload = run(tampered_path, page, "sensitive-analyzable")
        self.assertIn("V13", error_ids(payload))

        payload = run(manifest_path, page.replace("not valid UTF-8", "decoded"), "no-encoding-note")
        self.assertIn("V13", error_ids(payload))

        for secret in ("SERVICE_PASSWORD=not-a-real-secret", "placeholder for a certificate path"):
            self.assertNotIn(secret, page)

    def test_negative_22_accuracy_verdicts_missing_or_decoupled_fail_v14(self) -> None:
        directory = self.case_dir("n22")
        report = directory / "change-report.html"
        report.write_text(self.page, encoding="utf-8")
        manifest_path = directory / "change-report-manifest.json"
        write_manifest(self.manifest, manifest_path)

        payload = self.validate(
            report=report,
            manifest=manifest_path,
            stage="final",
            verdicts=directory / "absent-verdicts.json",
            accuracy="false",
        )
        self.assertIn("V14", error_ids(payload))

        partial = verdicts_payload(self.manifest)
        partial["verdicts"] = partial["verdicts"][:-1]
        partial_path = directory / "partial.json"
        partial_path.write_text(json.dumps(partial), encoding="utf-8")
        payload = self.validate(
            report=report, manifest=manifest_path, stage="final", verdicts=partial_path, accuracy="false"
        )
        self.assertIn("V14", error_ids(payload))

        invalid = verdicts_payload(self.manifest)
        invalid["verdicts"][0]["verdict"] = "probably-fine"
        invalid_path = directory / "invalid.json"
        invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
        payload = self.validate(
            report=report, manifest=manifest_path, stage="final", verdicts=invalid_path, accuracy="false"
        )
        self.assertIn("V14", error_ids(payload))

        no_reason = verdicts_payload(self.manifest, {1: "wrong"})
        no_reason["verdicts"][0]["reason"] = ""
        no_reason_path = directory / "no-reason.json"
        no_reason_path.write_text(json.dumps(no_reason), encoding="utf-8")
        payload = self.validate(
            report=report, manifest=manifest_path, stage="final", verdicts=no_reason_path, accuracy="false"
        )
        self.assertIn("V14", error_ids(payload))

        payload = self.validate(report=report, manifest=manifest_path, stage="final", accuracy="false")
        self.assertTrue(payload["ok"], payload["errors"])
        for decoupled in ("true", "TRUE", "yes"):
            with self.subTest(decoupled=decoupled):
                payload = self.validate(
                    report=report, manifest=manifest_path, stage="final", accuracy=decoupled
                )
                self.assertFalse(payload["ok"], decoupled)
                self.assertIn("V14", error_ids(payload), decoupled)

    def test_negative_23_threshold_boundaries(self) -> None:
        directory = self.case_dir("n23")
        report = directory / "change-report.html"
        report.write_text(self.page, encoding="utf-8")
        manifest_path = directory / "change-report-manifest.json"
        write_manifest(self.manifest, manifest_path)
        for verdict in ("wrong", "misleading"):
            with self.subTest(verdict=verdict):
                payload_file = directory / f"{verdict}.json"
                payload_file.write_text(
                    json.dumps(verdicts_payload(self.manifest, {1: verdict})), encoding="utf-8"
                )
                final = self.validate(
                    report=report,
                    manifest=manifest_path,
                    stage="final",
                    verdicts=payload_file,
                    accuracy="true",
                )
                self.assertFalse(final["ok"], verdict)
                self.assertIn("V14", error_ids(final))
        self.assertEqual(bm.MAX_WRONG, 0)
        self.assertEqual(bm.MAX_MISLEADING, 0)

    def test_negative_24_missing_reset_makes_the_latch_sticky(self) -> None:
        """O4: a terminating path that publishes `true` without a reset is a sticky latch.

        The declaration is spec-faithful apart from the missing `false`: the review-loop
        exit is owned by validate-final, so dropping only validate-final's reset must be
        what fails, not a non-conformant `true` on the review loop.
        """
        publishers = [
            {"node": "report-gate", "publishes": "true", "terminates_round": "gate-rework"},
            {"node": "validate-final", "publishes": "true", "terminates_round": "review-loop-exit"},
            {"node": "validate-final", "publishes": "true", "terminates_round": "validate-final-stale"},
            {"node": "validate-final", "publishes": "false", "terminates_round": "validate-final-stale"},
        ]
        path = write_flow_spec(
            flow_spec(publishers=publishers), self.case_dir("n24") / "flow.json"
        )
        payload = self.validate(flow=path)
        self.assertFalse(payload["ok"])
        self.assertIn("V12", error_ids(payload))
        self.assertTrue(any("reset it exactly once" in item["message"] for item in payload["errors"]))

    def test_negative_25_a_round_without_any_resetter(self) -> None:
        """Every terminating path must declare a reset; dropping one path's pair fails."""
        publishers = [
            {"node": "report-gate", "publishes": "true", "terminates_round": "gate-rework"},
            {"node": "validate-final", "publishes": "true", "terminates_round": "validate-final-stale"},
            {"node": "validate-final", "publishes": "false", "terminates_round": "validate-final-stale"},
        ]
        path = write_flow_spec(
            flow_spec(publishers=publishers), self.case_dir("n25") / "flow.json"
        )
        payload = self.validate(flow=path)
        self.assertFalse(payload["ok"])
        self.assertIn("V12", error_ids(payload))
        self.assertTrue(any("review-loop-exit" in item["message"] for item in payload["errors"]))

    def test_negative_25b_a_fourth_publisher_is_forbidden(self) -> None:
        publishers = [
            {"node": "report-gate", "publishes": "true", "terminates_round": "gate-rework"},
            {"node": "validate-final", "publishes": "true", "terminates_round": "review-loop-exit"},
            {"node": "validate-final", "publishes": "false", "terminates_round": "review-loop-exit"},
            {"node": "validate-final", "publishes": "true", "terminates_round": "validate-final-stale"},
            {"node": "validate-final", "publishes": "false", "terminates_round": "validate-final-stale"},
            {"node": "some-extra-node", "publishes": "false", "terminates_round": "adhoc-round"},
        ]
        path = write_flow_spec(
            flow_spec(publishers=publishers), self.case_dir("n25b") / "flow.json"
        )
        payload = self.validate(flow=path)
        self.assertFalse(payload["ok"])
        self.assertIn("V12", error_ids(payload))

    def test_negative_25c_an_undeclared_writer_of_the_latch_fails(self) -> None:
        """O1 forbids a fourth publisher: a node that claims the key must be declared."""
        spec = flow_spec()
        loop = spec["root"]["children"][0]
        loop["children"].insert(
            3,
            {
                "template_id": "adhoc-round-note",
                "type": "task",
                "role": "report-note",
                "executor": "tool",
                "instructions": "publish report.gate_rework_required=false when nothing is wrong",
                "deliverables": "a note",
                "acceptance": "the note exists",
            },
        )
        path = write_flow_spec(spec, self.case_dir("n25c") / "flow.json")
        payload = self.validate(flow=path)
        self.assertFalse(payload["ok"])
        self.assertIn("V12", error_ids(payload))
        self.assertTrue(
            any("not one of the declared publishers" in item["message"] for item in payload["errors"])
        )

    def test_negative_25d_a_recovery_group_outside_the_round_scope_fails(self) -> None:
        """R1: a recovery group outside the repeated round can never re-reach the gate."""
        spec = flow_spec()
        loop = spec["root"]["children"][0]
        recovery = next(
            child for child in loop["children"]
            if child["template_id"] == "report-gate-recovery-group"
        )
        loop["children"].remove(recovery)
        spec["root"]["children"].append(recovery)
        path = write_flow_spec(spec, self.case_dir("n25d") / "flow.json")
        payload = self.validate(flow=path)
        self.assertFalse(payload["ok"])
        self.assertIn("V12", error_ids(payload))
        self.assertTrue(
            any("must be a child of report-pass-loop" in item["message"] for item in payload["errors"])
        )

    def test_negative_25d2_a_recovery_group_that_resets_the_loop_key_ends_the_pass(self) -> None:
        """The trap on the other side: the recovery group's reset ends the refresh pass.

        report.gate_rework_required is the loop's continue condition. A recovery group that
        resets it leaves the loop with nothing to continue on, so the loop breaks after the
        rework and the gate never judges the reworked report. The declaration must name
        report-gate as the owner of both values on the gate-terminated round.
        """
        spec = flow_spec()
        loop = spec["root"]["children"][0]
        recovery = next(
            child for child in loop["children"]
            if child["template_id"] == "report-gate-recovery-group"
        )
        recovery["instructions"] = (
            "append the recovery; when it is complete publish "
            "report.gate_rework_required=false"
        )
        publishers = json.loads(loop["metadata"]["rework_publishers"])
        publishers.append(
            {
                "node": "report-gate-recovery-group",
                "publishes": "false",
                "terminates_round": "gate-rework",
            }
        )
        loop["metadata"]["rework_publishers"] = json.dumps(publishers)
        path = write_flow_spec(spec, self.case_dir("n25d2") / "flow.json")
        payload = self.validate(flow=path)
        self.assertFalse(payload["ok"])
        self.assertIn("V12", error_ids(payload))
        self.assertTrue(
            any(
                "carries control back to the next pass" in item["message"]
                for item in payload["errors"]
            ),
            payload["errors"],
        )

    def test_negative_25e_an_unguarded_finalizer_double_writes_the_latch(self) -> None:
        """O4: without the guard a gate-rework round has two writers of one latch."""
        spec = flow_spec()
        loop = spec["root"]["children"][0]
        final = next(
            child for child in loop["children"] if child["template_id"] == "validate-final"
        )
        final.pop("when")
        final.pop("when.policy")
        path = write_flow_spec(spec, self.case_dir("n25e") / "flow.json")
        payload = self.validate(flow=path)
        self.assertFalse(payload["ok"])
        self.assertIn("V12", error_ids(payload))
        self.assertTrue(
            any("report.gate_recovery_required == false" in item["message"]
                for item in payload["errors"])
        )

    def test_negative_27_an_unclosed_code_block_cannot_exempt_the_rest_of_the_page(self) -> None:
        """H37a: a bare URL outside a code block still fails when the block never closed."""
        cases = {
            "unclosed-pre": '<pre class="report-code">a<p>https://evil.example/x</p>',
            "unclosed-code": '<code class="report-diff-add"><p>https://evil.example/x</p>',
            "unclosed-then-block":
                '<pre class="report-code">a<div><p>https://evil.example/x</p></div>',
        }
        for name, snippet in cases.items():
            with self.subTest(name=name):
                report, manifest = self.mutated(
                    f"n27-{name}", page=self.page.replace("</main>", snippet + "</main>", 1)
                )
                payload = self.validate(report=report, manifest=manifest)
                self.assertFalse(payload["ok"], name)
                self.assertIn("V7", error_ids(payload), name)
        # The exemption itself must survive: a URL inside a closed code block still passes.
        inside = self.page.replace("https://api.example.invalid/v1", "https://api.example.invalid/v1")
        report, manifest = self.mutated("n27-inside", page=inside)
        payload = self.validate(report=report, manifest=manifest)
        self.assertTrue(payload["ok"], payload["errors"])

    def test_negative_26_reverse_case_a_wrong_explanation_still_passes_v14(self) -> None:
        """V14 passes even when an explanation is wrong: the mechanism's boundary, not its strength."""
        token = "handler_1"
        wrong_but_bound = (
            "what: this unit deletes the manifest instead of writing it. "
            f"The identifier {token} is removed everywhere and no caller can use it any more, "
            "which makes the report wrong on purpose while every mechanical check still passes."
        )
        page = re.sub(
            r'(<div class="report-unit-field" data-field="what"><h4>[^<]*</h4><p>)[^<]*(</p>)',
            lambda match: match.group(1) + wrong_but_bound + match.group(2),
            self.page,
            count=1,
        )
        directory = self.case_dir("n26")
        report = directory / "change-report.html"
        report.write_text(page, encoding="utf-8")
        manifest_path = directory / "change-report-manifest.json"
        write_manifest(self.manifest, manifest_path)
        verdicts = directory / "change-report-verdicts.json"
        verdicts.write_text(json.dumps(verdicts_payload(self.manifest)), encoding="utf-8")

        payload = self.validate(report=report, manifest=manifest_path, stage="final", accuracy="false")
        self.assertTrue(payload["ok"], payload["errors"])
        self.assertEqual(payload["facts"]["hash_bound"], payload["facts"]["units_total"])
        self.assertEqual(payload["facts"]["token_bound"], payload["facts"]["units_total"])
        self.assertEqual(payload["details"]["accuracy"]["wrong"], 0)
        self.assertIn("deletes the manifest", report.read_text(encoding="utf-8"))

    def test_negative_28_pre_existing_hunk_without_excluded_fails_v1(self) -> None:
        """V1 is the field-level gate: a pre-existing hunk must carry excluded=true.

        Without the field-level check such a manifest passes V1 and is then reported at V10
        as `unit None: exactly one recomputation code block is required, found 0`, which
        names a code-block defect for what is a manifest field corruption.
        """
        root = Path(tempfile.mkdtemp(prefix="xc-report-n28-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        harness = materialise("dirty-worktree", root)
        manifest = build_manifest_for(harness)
        manifest_path = write_manifest(manifest, root / "change-report-manifest.json")
        analysis = make_analysis(manifest, harness["repo"])
        report = root / "change-report.html"
        render_report(manifest, manifest_path, harness["repo"], analysis, report)

        def run(manifest_file: Path) -> dict[str, Any]:
            payload, _ = vr.validate(
                report_path=report,
                manifest_path=manifest_file,
                repo=harness["repo"],
                work_order_id=WORK_ORDER_ID,
                stage="coverage",
                verdicts_path=None,
                accuracy_open_issues=None,
                flow_spec_path=root / "absent.json",
                golden_dir=None,
            )
            return payload

        baseline = run(manifest_path)
        self.assertTrue(baseline["ok"], baseline["errors"])

        flipped = json.loads(json.dumps(manifest))
        changed = 0
        for entry in flipped["files"]:
            for hunk in entry["hunks"]:
                if hunk.get("provenance") == "pre_existing":
                    hunk["excluded"] = False
                    changed += 1
        self.assertGreater(changed, 0, "the dirty-worktree fixture must contain a pre-existing hunk")
        payload = run(write_manifest(flipped, root / "flipped-manifest.json"))
        self.assertFalse(payload["ok"])
        self.assertIn("V1", error_ids(payload))
        messages = [item["message"] for item in payload["errors"] if item["id"] == "V1"]
        self.assertTrue(any("excluded=true" in message for message in messages), messages)
        self.assertTrue(any("pre_existing" in message for message in messages), messages)
        # The defect is named at the field level. Before this check the only signal was
        # V10's "unit None: exactly one recomputation code block is required, found 0",
        # which reported a manifest field corruption as a code-block defect.
        self.assertTrue(any("provenance=pre_existing" in message for message in messages), messages)


# --------------------------------------------------------------------------------------
# Line-ending regression: a CRLF worktree must bind exactly like an LF worktree
# --------------------------------------------------------------------------------------


class CrlfWorktreeTests(unittest.TestCase):
    """A worktree that stores its files with CRLF must not break the V10 hash binding.

    Measured defect this class pins: the skeleton writes the repository's own bytes into the
    page, so a CRLF code line puts a CR before the row span closes. The builder hashed the bare
    line (`content_sha256` over `line\\n`), but `validate_report.validate` read the page with
    universal-newline translation, which turned that `line\\r\\n` into `line\\n` inside the span
    and left `normalize_code_text` with one extra newline per code line. The recomputed hash
    could then never equal the manifest's, so every unit of every CRLF worktree failed V10 while
    the skeleton's own self-check passed inside the same run. Identical repositories with LF
    endings passed, and rebuilds were byte-identical, so it was not a build problem.
    """

    fixture = "sample-diff"

    def setUp(self) -> None:
        self._root = Path(tempfile.mkdtemp(prefix="xc-report-crlf-"))
        self.addCleanup(shutil.rmtree, self._root, ignore_errors=True)

    def render(self, label: str) -> tuple[Path, Path, Path]:
        """Materialise `label`'s worktree, build the manifest and the page, return the paths."""
        root = self._root / label
        harness = materialise(self.fixture, root / "fixture", line_endings="\r\n")
        manifest = build_manifest_for(harness, tmp_dir=root / "tmp")
        manifest_path = write_manifest(manifest, root / "change-report-manifest.json")
        analysis = make_analysis(manifest, harness["repo"])
        report_path = root / "change-report.html"
        render_report(manifest, manifest_path, harness["repo"], analysis, report_path)
        return harness["repo"], manifest_path, report_path

    def test_crlf_worktree_binds_every_unit_at_the_coverage_stage(self) -> None:
        repo, manifest_path, report_path = self.render("crlf")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        # Guard the fixture itself. If the page held no CR before a row span closes, the page
        # would not describe a CRLF worktree and the rest of this test would prove nothing.
        page_bytes = report_path.read_bytes()
        self.assertIn(b"\r</span>", page_bytes, "the page must carry the CRLF worktree's own bytes")

        payload = vr.validate(
            report_path=report_path,
            manifest_path=manifest_path,
            repo=repo,
            work_order_id=WORK_ORDER_ID,
            stage="coverage",
            verdicts_path=None,
            accuracy_open_issues=None,
            flow_spec_path=None,
            golden_dir=None,
        )[0]
        self.assertTrue(payload["ok"], payload["errors"])
        facts = payload["facts"]
        self.assertGreater(facts["units_total"], 0)
        self.assertEqual(facts["hash_bound"], facts["units_total"])
        self.assertEqual(facts["coverage"], "complete")

    def test_crlf_and_lf_worktrees_hash_the_same_logical_content(self) -> None:
        """The canonical unit text belongs to the repository, not to its line endings."""
        crlf = build_manifest_for(materialise(self.fixture, self._root / "c" / "fixture", "\r\n"))
        lf = build_manifest_for(materialise(self.fixture, self._root / "l" / "fixture", "\n"))
        crlf_hashes = {
            (entry["path"], hunk["unit_index"]): hunk["content_sha256"]
            for entry in crlf["files"]
            for hunk in entry["hunks"]
            if not hunk["excluded"]
        }
        lf_hashes = {
            (entry["path"], hunk["unit_index"]): hunk["content_sha256"]
            for entry in lf["files"]
            for hunk in entry["hunks"]
            if not hunk["excluded"]
        }
        self.assertEqual(sorted(crlf_hashes), sorted(lf_hashes))
        self.assertEqual(crlf_hashes, lf_hashes)

    def test_the_crlf_page_is_validated_through_the_cli_entry_point(self) -> None:
        """The same run through `validate_report.py --stage coverage`, with its exit code."""
        repo, manifest_path, report_path = self.render("cli")
        json_out = self._root / "cli" / "validate-coverage.json"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "validate_report.py"),
                "--report",
                str(report_path),
                "--manifest",
                str(manifest_path),
                "--repo",
                str(repo),
                "--work-order-id",
                WORK_ORDER_ID,
                "--stage",
                "coverage",
                "--json-out",
                str(json_out),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(json_out.read_text(encoding="utf-8"))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(payload["ok"], payload["errors"])
        self.assertEqual(payload["facts"]["hash_bound"], payload["facts"]["units_total"])

    def test_an_altered_crlf_code_block_still_fails_v10(self) -> None:
        """The binding must stay meaningful: normalisation must not become a free pass."""
        repo, manifest_path, report_path = self.render("altered")
        page = report_path.read_bytes().decode("utf-8")
        anchor = '<span class="tok-number">3</span>'
        self.assertIn(anchor, page, "the fixture must render the number the tamper replaces")
        tampered_path = self._root / "altered" / "change-report-tampered.html"
        tampered_path.write_bytes(page.replace(anchor, '<span class="tok-number">4</span>', 1).encode("utf-8"))
        payload = vr.validate(
            report_path=tampered_path,
            manifest_path=manifest_path,
            repo=repo,
            work_order_id=WORK_ORDER_ID,
            stage="coverage",
            verdicts_path=None,
            accuracy_open_issues=None,
            flow_spec_path=None,
            golden_dir=None,
        )[0]
        self.assertFalse(payload["ok"])
        self.assertIn("V10", [item["id"] for item in payload["errors"]])


class ScratchPlacementTests(ReportCase):
    """H4/C37: intermediate files land under the workbench tmp directory, not the OS temp dir."""

    def test_manifest_and_skeleton_scratch_lands_in_the_supplied_tmp_dir(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="xc-report-n29-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        harness = materialise("sample-diff", root / "fixture")
        workbench_tmp = root / "workbench" / "tmp"
        workbench_tmp.mkdir(parents=True)

        manifest = build_manifest_for(harness, tmp_dir=workbench_tmp)
        manifest_path = write_manifest(manifest, root / "change-report-manifest.json")
        analysis = make_analysis(manifest, harness["repo"])
        report = root / "change-report.html"

        # Look only for this package's own C37 scratch, not for temporary files in general: a
        # whole-directory snapshot races with every other process and reports their files as
        # this render's. `--tmp-dir` is what keeps these names out of the OS temp directory.
        system_tmp = Path(tempfile.gettempdir())
        scratch_names = ("no-index-left.tmp", "no-index-right.tmp")

        page = bs.build_report(
            repo=harness["repo"],
            manifest=manifest,
            analysis=analysis,
            template_text=(SKILL_ROOT / "assets" / "change-report-template.html").read_text(encoding="utf-8"),
            css_text=(SKILL_ROOT / "assets" / "change-report.css").read_text(encoding="utf-8"),
            generated_at="2026-09-15T18:00:00Z",
            manifest_bytes=manifest_path.read_bytes(),
            tmp_dir=workbench_tmp,
        )
        report.write_bytes(page.encode("utf-8"))
        for name in scratch_names:
            self.assertFalse(
                (system_tmp / name).exists(),
                f"{name} landed in the OS temp directory instead of --tmp-dir",
            )

        payload = self.validate(report=report, manifest=manifest_path, repo=harness["repo"])
        self.assertTrue(payload["ok"], payload["errors"])

    def test_both_scripts_accept_the_tmp_dir_flag(self) -> None:
        for script in ("build_manifest.py", "build_skeleton.py"):
            with self.subTest(script=script):
                proc = subprocess.run(
                    [sys.executable, str(SCRIPTS / script), "--help"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("--tmp-dir", proc.stdout)

    def test_skill_publishes_the_tmp_dir_flag_in_its_command_block(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        commands = content.split("```text", 1)[1].split("```", 1)[0]
        manifest_command = commands.split("build_manifest.py", 1)[1].split("build_skeleton.py", 1)[0]
        skeleton_command = commands.split("build_skeleton.py", 1)[1].split("validate_report.py", 1)[0]
        self.assertIn("--tmp-dir", manifest_command)
        self.assertIn("--tmp-dir", skeleton_command)
        self.assertGreaterEqual(content.count("--tmp-dir"), 2)


# --------------------------------------------------------------------------------------
# Analysis-depth layer (A18-A20, V21/V22)
# --------------------------------------------------------------------------------------


class AnalysisDepthTests(ReportCase):
    ANSWER = (
        "This function is the read entry point of the status flow and owns the response shape "
        "that downstream callers rely on."
    )

    def _depth_analysis(self, *, dims=None, blocks=None, change_class="function"):
        analysis = json.loads(json.dumps(self.analysis))
        indices = [hunk["unit_index"] for entry, hunk in unit_pairs(self.manifest)]
        first = str(indices[0])
        unit = analysis["units"][first]
        unit["change_class"] = change_class
        unit["design_lead"] = (
            "Before, the status path returned a partial view; after this unit it returns the "
            "complete configuration in one pass."
        )
        if dims is None:
            dims = [
                {"key": "role", "answer": self.ANSWER},
                {"key": "motivation", "answer": self.ANSWER},
                {"key": "before_after", "answer": self.ANSWER},
                {"key": "upstream_downstream", "answer": self.ANSWER},
                {"key": "tradeoffs", "not_applicable": True,
                 "reason": "no material trade-off; the change is a pure additive read path"},
            ]
        unit["design_dimensions"] = dims
        if blocks is None:
            blocks = [
                {"kind": "call_relations", "unit_label": "get_status()",
                 "callers": [{"label": "handle_request", "loc": "src/app.py:20"}],
                 "callees": [{"label": "load_batch", "loc": "src/store.py:8"}]},
                {"kind": "before_after", "title": "Status flow",
                 "rows": [
                     {"step": "read", "before": "partial", "after": "complete", "change": "modified"},
                     {"step": "return", "before": "dict", "after": "dict", "change": "unchanged"}]},
                {"kind": "lifecycle", "resource": "self._cache", "complete": True,
                 "phases": [{"phase": "init", "loc": "src/app.py:5", "action": "assign",
                             "state": "empty", "note": "constructed once"}]},
            ]
        unit["depth_blocks"] = blocks
        return analysis, int(first)

    def _render(self, name, analysis):
        out = self.case_dir(name) / "change-report.html"
        render_report(self.manifest, self.manifest_path, self.harness["repo"], analysis, out)
        return out

    def test_analysis_depth_renders_and_validates(self):
        analysis, first = self._depth_analysis()
        out = self._render("depth-ok", analysis)
        page = out.read_text(encoding="utf-8")
        self.assertIn('class="report-change-class"', page)
        self.assertIn('data-change-class="function"', page)
        self.assertIn('class="report-design-lead"', page)
        self.assertIn('data-dimension="role"', page)
        self.assertIn('class="report-depth-block"', page)
        self.assertIn('data-kind="call_relations"', page)
        self.assertIn('data-kind="before_after"', page)
        self.assertIn('data-kind="lifecycle"', page)
        payload = self.validate(report=out)
        self.assertTrue(payload["ok"], payload["errors"])
        self.assertNotIn("V21", error_ids(payload))
        self.assertNotIn("V22", error_ids(payload))
        # V10 must be unaffected: depth blocks are not report-code.
        self.assertEqual(payload["facts"]["units_total"], payload["facts"]["hash_bound"])

    def test_missing_required_dimension_fails_v21(self):
        analysis, first = self._depth_analysis(dims=[
            {"key": "role", "answer": self.ANSWER},
            {"key": "motivation", "answer": self.ANSWER},
            # 'before_after', 'upstream_downstream', 'tradeoffs' required for 'function' are absent
        ])
        out = self._render("depth-missing", analysis)
        payload = self.validate(report=out)
        self.assertFalse(payload["ok"])
        self.assertIn("V21", error_ids(payload))

    def test_illegal_change_class_fails_v21(self):
        analysis, first = self._depth_analysis(change_class="not-a-real-class")
        out = self._render("depth-illegal-class", analysis)
        payload = self.validate(report=out)
        self.assertFalse(payload["ok"])
        self.assertIn("V21", error_ids(payload))

    def test_not_applicable_without_reason_fails_v21(self):
        analysis, first = self._depth_analysis(dims=[
            {"key": "role", "answer": self.ANSWER},
            {"key": "motivation", "answer": self.ANSWER},
            {"key": "before_after", "answer": self.ANSWER},
            {"key": "upstream_downstream", "answer": self.ANSWER},
            {"key": "tradeoffs", "not_applicable": True, "reason": "no"},
        ])
        out = self._render("depth-na-noreason", analysis)
        payload = self.validate(report=out)
        self.assertFalse(payload["ok"])
        self.assertIn("V21", error_ids(payload))

    def test_short_dimension_answer_fails_v21(self):
        analysis, first = self._depth_analysis(dims=[
            {"key": "role", "answer": "too short"},
            {"key": "motivation", "answer": self.ANSWER},
            {"key": "before_after", "answer": self.ANSWER},
            {"key": "upstream_downstream", "answer": self.ANSWER},
            {"key": "tradeoffs", "not_applicable": True,
             "reason": "no material trade-off in this additive read path"},
        ])
        out = self._render("depth-short", analysis)
        payload = self.validate(report=out)
        self.assertFalse(payload["ok"])
        self.assertIn("V21", error_ids(payload))

    def test_depth_block_bad_unit_binding_fails_v22(self):
        analysis, first = self._depth_analysis()
        out = self._render("depth-badunit", analysis)
        page = out.read_text(encoding="utf-8")
        # rebind one depth block to a non-existent unit
        broken = page.replace('data-kind="call_relations">', 'data-kind="call_relations">', 1)
        broken = page.replace(
            f'data-unit="{first}" data-kind="call_relations"',
            'data-unit="9999" data-kind="call_relations"', 1)
        report_path, manifest_path = self.mutated("depth-badunit2", page=broken)
        payload = self.validate(report=report_path, manifest=manifest_path)
        self.assertFalse(payload["ok"])
        self.assertIn("V22", error_ids(payload))

    def test_before_after_illegal_change_fails_v22(self):
        analysis, first = self._depth_analysis(blocks=[
            {"kind": "before_after", "title": "Status flow",
             "rows": [{"step": "read", "before": "a", "after": "b", "change": "frobnicated"}]},
        ])
        out = self._render("depth-badchange", analysis)
        payload = self.validate(report=out)
        self.assertFalse(payload["ok"])
        self.assertIn("V22", error_ids(payload))

    def test_no_change_class_is_backward_compatible(self):
        # The base analysis declares no change_class; V21/V22 must be vacuous.
        payload = self.validate()
        self.assertTrue(payload["ok"], payload["errors"])
        self.assertNotIn("V21", error_ids(payload))
        self.assertNotIn("V22", error_ids(payload))

    def test_reference_and_contract_carry_the_depth_series(self):
        contract = (SKILL_ROOT / "references" / "change-report-contract.md").read_text(encoding="utf-8")
        for token in ("A18", "A19", "A20", "V21", "V22", "change_class", "design_dimensions", "depth_blocks"):
            self.assertIn(token, contract, token)
        depth = (SKILL_ROOT / "references" / "analysis-depth.md").read_text(encoding="utf-8")
        for token in ("CHANGE_CLASSES", "REQUIRED_DIMENSIONS", "before_after", "lifecycle", "call_relations"):
            self.assertIn(token, depth, token)


# --------------------------------------------------------------------------------------
# Presentation rebuild: top-down funnel order + overflow-safe before/after cards
# --------------------------------------------------------------------------------------


class PresentationRebuildTests(AnalysisDepthTests):
    def test_section_order_is_top_down_funnel(self):
        # The macro system before/after must render before the detailed change-map index.
        self.assertLess(
            bm.SECTION_IDS.index("section-process-position"),
            bm.SECTION_IDS.index("section-change-map"),
            "process-position must come before change-map (macro before detail)",
        )
        # SECTION_IDS is the single source; the rendered page follows it.
        analysis, first = self._depth_analysis()
        out = self._render("funnel-order", analysis)
        page = out.read_text(encoding="utf-8")
        self.assertLess(
            page.index('id="section-process-position"'),
            page.index('id="section-change-map"'),
            "the rendered section order must match SECTION_IDS",
        )
        payload = self.validate(report=out)
        self.assertTrue(payload["ok"], payload["errors"])
        self.assertNotIn("V5", error_ids(payload))

    def test_before_after_renders_as_cards_not_a_narrow_table(self):
        analysis, first = self._depth_analysis(blocks=[
            {"kind": "before_after", "title": "Status flow", "rows": [
                {"step": "read", "before": "returned a partial view of the configuration",
                 "after": "returns the complete configuration in a single pass", "change": "modified"},
                {"step": "return", "before": "dict", "after": "dict", "change": "unchanged"}]},
        ])
        out = self._render("ba-cards", analysis)
        page = out.read_text(encoding="utf-8")
        # The full-width card carrier is used, carrying the change on each step card.
        self.assertIn('class="report-ba-steps"', page)
        self.assertIn('class="report-ba-step"', page)
        self.assertIn('data-change="modified"', page)
        self.assertIn('class="report-ba-panel report-ba-before"', page)
        self.assertIn('class="report-ba-panel report-ba-after"', page)
        # The before_after figure must NOT fall back to a bare depth table.
        fig_start = page.index('data-kind="before_after"')
        fig_end = page.index("</figure>", fig_start)
        self.assertNotIn("report-depth-table", page[fig_start:fig_end])
        # V22 still binds to the card change vocabulary.
        payload = self.validate(report=out)
        self.assertTrue(payload["ok"], payload["errors"])
        self.assertNotIn("V22", error_ids(payload))

    def test_wide_tables_are_wrapped_for_overflow_safety(self):
        analysis, first = self._depth_analysis()
        out = self._render("scroll-wrap", analysis)
        page = out.read_text(encoding="utf-8")
        # The change map and the lifecycle/call-relations tables live inside a scroll wrapper.
        self.assertIn('class="report-table-scroll"', page)
        # The change map itself is inside such a wrapper.
        map_at = page.index('id="change-map"')
        self.assertIn("report-table-scroll", page[max(0, map_at - 120):map_at])

    def test_css_carries_overflow_guard_and_card_classes(self):
        css = (SKILL_ROOT / "assets" / "change-report.css").read_text(encoding="utf-8")
        self.assertIn("overflow-x: hidden", css)          # page-level guard
        self.assertIn("report-table-scroll", css)          # table scroll container
        self.assertIn("overflow-wrap: anywhere", css)      # cell wrapping
        self.assertIn("report-ba-panels", css)             # before/after card grid
        # Narrow breakpoint stacks the before/after panels.
        self.assertIn("max-width: 720px", css)

    def test_contract_carries_the_rebuilt_presentation_tokens(self):
        contract = (SKILL_ROOT / "references" / "change-report-contract.md").read_text(encoding="utf-8")
        for token in ("report-ba-step", "report-table-scroll", "full-width comparison",
                      "carrier-agnostic"):
            self.assertIn(token, contract, token)


# --------------------------------------------------------------------------------------
# Prefer-diagrams: A20 derivation (D21), sequence SVG (D22), suitability advisory (A21/D20)
# --------------------------------------------------------------------------------------


class DerivedDiagramTests(unittest.TestCase):
    def test_call_relations_derives_a_layered_callgraph_flow(self) -> None:
        analysis = {"units": {"3": {"depth_blocks": [
            {"kind": "call_relations", "unit_label": "fn()",
             "callers": [{"label": "caller_a", "loc": "a.py:1"}],
             "callees": [{"label": "callee_x", "loc": "x.py:2"}, {"label": "callee_y", "loc": "y.py:3"}]}]}}}
        derived = bs.derive_depth_block_diagrams(analysis)
        ids = [d["id"] for d in derived]
        self.assertIn("diagram-callgraph-unit-3", ids)
        spec = next(d for d in derived if d["id"] == "diagram-callgraph-unit-3")
        self.assertEqual(spec["type"], "flow")
        self.assertEqual(spec["render_mode"], "svg")
        # renders deterministically as SVG
        first = rd.render_diagram(spec)
        self.assertEqual(first, rd.render_diagram(spec))
        self.assertIn('class="report-diagram-svg"', first)

    def test_before_after_derives_paired_before_and_after_flows(self) -> None:
        analysis = {"units": {"4": {"depth_blocks": [
            {"kind": "before_after", "title": "flow",
             "rows": [{"step": "s1", "before": "old a", "after": "new a", "change": "modified"},
                      {"step": "s2", "before": "old b", "after": "new b", "change": "unchanged"}]}]}}}
        ids = [d["id"] for d in bs.derive_depth_block_diagrams(analysis)]
        self.assertIn("diagram-before-unit-4", ids)
        self.assertIn("diagram-after-unit-4", ids)

    def test_opt_out_and_minimal_suppress_derivation(self) -> None:
        analysis = {"units": {"5": {"depth_blocks": [
            {"kind": "call_relations", "unit_label": "fn()", "derive_diagram": False,
             "callers": [{"label": "c", "loc": "a:1"}], "callees": [{"label": "d", "loc": "b:2"}]}]}}}
        self.assertEqual(bs.derive_depth_block_diagrams(analysis), [])

    def test_long_derived_label_truncates_but_keeps_full_text_in_title(self) -> None:
        # A derived flow node whose label exceeds the character cap must render a truncated
        # visible label AND keep the full text in <title>; the V8 truncation-consistency clause
        # must accept it (regression: the old predicate rejected every genuine truncation).
        long_text = "this before/after step description is deliberately much longer than the node cap"
        self.assertGreater(len(long_text), rd.MAX_TEXT_NODE_CHARS)
        spec = {
            "id": "diagram-before-unit-9", "type": "flow", "render_mode": "svg",
            "title": "Unit 9: before flow", "summary": "one step per node",
            "nodes": [{"id": "n0", "label": long_text, "layer": 0, "kind": "unit"}],
            "edges": [],
        }
        html = rd.render_diagram(spec)
        self.assertIn("\u2026", html)
        self.assertIn(f"<title>{long_text}</title>", html)


class SequenceSvgTests(unittest.TestCase):
    def test_sequence_svg_renders_deterministically_and_matches_golden(self) -> None:
        spec = json.loads((GOLDEN_DIR / "sequence-svg-spec.json").read_text(encoding="utf-8"))
        first = rd.render_diagram(spec)
        self.assertEqual(first, rd.render_diagram(spec))
        self.assertIn('class="report-diagram-svg"', first)
        golden = (GOLDEN_DIR / "sequence-svg-golden.svg").read_text(encoding="utf-8").strip()
        svg = re.search(r"<svg class=\"report-diagram-svg\".*?</svg>", first, re.S)
        self.assertIsNotNone(svg)
        self.assertEqual(svg.group(0).strip(), golden)

    def test_sequence_table_still_default_and_supported(self) -> None:
        spec = json.loads((GOLDEN_DIR / "sequence-spec.json").read_text(encoding="utf-8"))
        html = rd.render_diagram(spec)
        self.assertIn('class="report-diagram-table"', html)
        self.assertNotIn("<svg class=\"report-diagram-svg\"", html)

    def test_sequence_svg_unknown_participant_raises(self) -> None:
        spec = {"id": "d", "type": "sequence", "render_mode": "svg",
                "participants": ["A"], "messages": [{"from": "A", "to": "B", "message": "x"}]}
        with self.assertRaises(rd.DiagramError):
            rd.render_diagram(spec)


class DiagramSuitabilityAdvisoryTests(ReportCase):
    def _analysis_with(self, change_class, *, depth_blocks=None, dims=None):
        analysis = json.loads(json.dumps(self.analysis))
        indices = [hunk["unit_index"] for entry, hunk in unit_pairs(self.manifest)]
        first = str(indices[0])
        unit = analysis["units"][first]
        unit["change_class"] = change_class
        long = "This unit belongs to the status flow and its behaviour is described here at length."
        base_dims = [
            {"key": k, "answer": long} for k in
            ("role", "motivation", "before_after", "upstream_downstream", "tradeoffs",
             "alternatives", "lifecycle", "impact_risk")
        ]
        unit["design_dimensions"] = dims if dims is not None else base_dims
        if depth_blocks is not None:
            unit["depth_blocks"] = depth_blocks
        return analysis, int(first)

    def _render(self, name, analysis):
        out = self.case_dir(name) / "change-report.html"
        render_report(self.manifest, self.manifest_path, self.harness["repo"], analysis, out)
        return out

    def test_advisory_is_non_blocking_and_present_when_preferred_class_has_no_diagram(self):
        analysis, first = self._analysis_with("function", depth_blocks=None)
        out = self._render("adv-present", analysis)
        payload = self.validate(report=out)
        self.assertTrue(payload["ok"], payload["errors"])  # advisory never fails
        self.assertNotIn("A21", error_ids(payload))
        adv_ids = [a["id"] for a in payload.get("advisories", [])]
        self.assertIn("A21", adv_ids)

    def test_no_advisory_when_a_diagram_is_derived_for_the_unit(self):
        blocks = [{"kind": "call_relations", "unit_label": "fn()",
                   "callers": [{"label": "c", "loc": "a:1"}], "callees": [{"label": "d", "loc": "b:2"}]}]
        analysis, first = self._analysis_with("function", depth_blocks=blocks)
        out = self._render("adv-diagram", analysis)
        payload = self.validate(report=out)
        self.assertTrue(payload["ok"], payload["errors"])
        adv = [a for a in payload.get("advisories", []) if a["id"] == "A21" and f"unit {first} " in a["message"]]
        self.assertEqual(adv, [])

    def test_no_advisory_for_light_change_class(self):
        analysis, first = self._analysis_with("constant-config", depth_blocks=None,
                                              dims=[{"key": k, "answer": "x" * 45} for k in ("role", "motivation", "impact_risk")])
        out = self._render("adv-light", analysis)
        payload = self.validate(report=out)
        self.assertTrue(payload["ok"], payload["errors"])
        adv = [a for a in payload.get("advisories", []) if f"unit {first} " in a["message"]]
        self.assertEqual(adv, [])

    def test_no_advisory_when_diagram_dimensions_are_waived(self):
        dims = [{"key": "role", "answer": "x" * 45}, {"key": "motivation", "answer": "x" * 45},
                {"key": "before_after", "not_applicable": True, "reason": "no flow change in this unit"},
                {"key": "upstream_downstream", "not_applicable": True, "reason": "no caller or callee change"},
                {"key": "tradeoffs", "answer": "x" * 45}]
        analysis, first = self._analysis_with("function", depth_blocks=None, dims=dims)
        out = self._render("adv-waived", analysis)
        payload = self.validate(report=out)
        self.assertTrue(payload["ok"], payload["errors"])
        adv = [a for a in payload.get("advisories", []) if a["id"] == "A21" and f"unit {first} " in a["message"]]
        self.assertEqual(adv, [])

    def test_contract_carries_prefer_diagram_series(self):
        contract = (SKILL_ROOT / "references" / "change-report-contract.md").read_text(encoding="utf-8")
        self.assertIn("A21", contract)
        diagrams = (SKILL_ROOT / "references" / "diagram-spec.md").read_text(encoding="utf-8")
        for token in ("D20", "D21", "D22", "DIAGRAM_PREFERRED_CLASSES", "sequence-svg-golden.svg"):
            self.assertIn(token, diagrams, token)
        depth = (SKILL_ROOT / "references" / "analysis-depth.md").read_text(encoding="utf-8")
        self.assertIn("suitability by change class", depth)


# --------------------------------------------------------------------------------------
# Skill package contract tests
# --------------------------------------------------------------------------------------


class SkillPackageTests(unittest.TestCase):
    def test_skill_declares_the_public_authoring_default_phrase(self) -> None:
        content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("public `xc-document` human-readable authoring default", content)

    def test_every_deliverable_including_the_orchestration_package_exists(self) -> None:
        for relative in (
            "SKILL.md",
            "references/change-report-contract.md",
            "references/analysis-depth.md",
            "references/coverage-protocol.md",
            "references/diagram-spec.md",
            "assets/change-report-template.html",
            "assets/change-report.css",
            # The flow specification is the single source of truth and the template XML is
            # built from it by the sibling orchestration node; both are part of the package,
            # and the template XML must never be hand-written.
            "assets/change-report-flow.json",
            "assets/change-report-template.xml",
            "scripts/build_manifest.py",
            "scripts/build_skeleton.py",
            "scripts/highlight_code.py",
            "scripts/render_diagram.py",
            "scripts/validate_report.py",
        ):
            self.assertTrue((SKILL_ROOT / relative).is_file(), relative)

    def test_scripts_import_only_the_standard_library_and_siblings(self) -> None:
        allowed = {"build_manifest", "highlight_code", "render_diagram"}
        for path in sorted((SKILL_ROOT / "scripts").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            for match in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z_][\w.]*)", source, re.M):
                module = match.group(1).split(".")[0]
                if module in allowed or module in sys.stdlib_module_names:
                    continue
                self.fail(f"{path.name} imports non-standard module {module!r}")

    def test_references_carry_every_contract_series(self) -> None:
        contract = (SKILL_ROOT / "references" / "change-report-contract.md").read_text(encoding="utf-8")
        for token in ("H41", "H37a", "H26a", "A15", "V14"):
            self.assertIn(token, contract, token)
        coverage = (SKILL_ROOT / "references" / "coverage-protocol.md").read_text(encoding="utf-8")
        for token in ("C38", "C29", "C24b", "pre_existing", "enumeration"):
            self.assertIn(token, coverage, token)
        diagrams = (SKILL_ROOT / "references" / "diagram-spec.md").read_text(encoding="utf-8")
        for token in ("D18", "render_mode", "svg", "table"):
            self.assertIn(token, diagrams, token)

    def test_cli_scripts_run_against_a_fixture(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="xc-report-cli-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        harness = materialise("untracked-new-file", root)
        manifest_path = root / "change-report-manifest.json"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "build_manifest.py"),
                "--repo",
                str(harness["repo"]),
                "--work-order-id",
                WORK_ORDER_ID,
                "--baseline-commit",
                harness["commit"],
                "--baseline-worktree-dir",
                str(harness["baseline_worktree"]),
                "--baseline-untracked-dir",
                str(harness["baseline_untracked"]),
                "--out",
                str(manifest_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["units_total"], 2)


# --------------------------------------------------------------------------------------
# F2: the page writer on a path that is not valid UTF-8
# --------------------------------------------------------------------------------------


class PageEncodingTests(unittest.TestCase):
    """The page writer must render a surrogate-escaped path instead of raising.

    A wave-one change made path handling lossless: `build_manifest.decode_path` returns a path
    that is not valid UTF-8 as a lone surrogate per raw byte, and the manifest writer survives
    that because it is pinned to `ensure_ascii=True`. The page is a UTF-8 document, and an
    unencodable character has no UTF-8 encoding, so `page.encode("utf-8")` raised
    `UnicodeEncodeError` and the whole report failed to build. The page renders each such
    character as the escape the manifest already uses for the same byte.
    """

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="xc-report-page-encoding-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

        self.repo = self.root / "repo"
        self.repo.mkdir(parents=True)
        _git(self.repo, "init", "-q")
        _git(self.repo, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(self.repo, "config", "user.email", "fixture@example.invalid")
        _git(self.repo, "config", "user.name", "fixture")
        _git(self.repo, "config", "core.autocrlf", "false")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "app.py").write_bytes(b"value = 1\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "baseline")
        self.commit = _git(self.repo, "rev-parse", "HEAD").strip()

        (self.repo / "src" / "app.py").write_bytes(b"value = 2\n")
        # The path whose name is rewritten below, so that the page renders it as a name without
        # rendering a code block for it.
        (self.repo / "payload.bin").write_bytes(b"\x00\x01\x02binary\n")

        self.snapshot = self.root / "baseline-worktree"
        (self.snapshot / "src").mkdir(parents=True)
        shutil.copy2(self.repo / "src" / "app.py", self.snapshot / "src" / "app.py")
        self.untracked = self.root / "baseline-untracked"
        self.untracked.mkdir()

        self.manifest = bm.build_manifest(
            repo_path=self.repo,
            work_order_id=WORK_ORDER_ID,
            baseline_commit=self.commit,
            baseline_digest=bm.digest_from_hashes(
                [("src/app.py", bm.sha256_hex((self.snapshot / "src" / "app.py").read_bytes()))]
            ),
            baseline_algorithm=bm.DIGEST_ALGORITHM,
            baseline_worktree_dir=self.snapshot,
            baseline_untracked_dir=self.untracked,
            tmp_dir=self.root / "tmp",
            captured_at="2026-09-15T17:45:00Z",
            generated_at="2026-09-15T18:00:00Z",
            strength="standard",
        )

    def render(self, name: str) -> tuple[int, Path]:
        """Run the real writer over the current manifest and return its exit code and output."""
        manifest_path = self.root / f"{name}-manifest.json"
        # The manifest writer's own pinning (`ensure_ascii=True`), which is what makes a
        # surrogate-escaped path serialisable at all: `ensure_ascii=False` cannot encode it.
        manifest_path.write_bytes(
            (json.dumps(self.manifest, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
        )
        out = self.root / f"{name}-change-report.html"
        code = bs.main(
            [
                "--repo",
                str(self.repo),
                "--manifest",
                str(manifest_path),
                "--out",
                str(out),
                "--generated-at",
                "2026-09-15T18:00:00Z",
                "--tmp-dir",
                str(self.root / "tmp"),
            ]
        )
        return code, out

    def test_page_writer_renders_a_path_that_is_not_valid_utf8(self) -> None:
        entries = {entry["path"]: entry for entry in self.manifest["files"]}
        self.assertEqual(
            sorted(entries),
            ["payload.bin", "src/app.py"],
            "the fixture must enumerate the excluded path the page renders by name",
        )
        self.assertEqual(entries["payload.bin"]["exclude_reason"], "binary")

        # Control: with an ordinary path the page writes and names the path literally, so the
        # escape below is not a blanket rewriting of every page.
        code, ordinary_out = self.render("ordinary")
        self.assertEqual(code, 0)
        ordinary_page = ordinary_out.read_bytes().decode("utf-8")
        self.assertIn("<code>payload.bin</code>", ordinary_page)
        self.assertNotIn("\\udcff", ordinary_page)

        # The measured shape: byte 0xFF has no UTF-8 decoding, so the enumeration hands the page
        # writer `payload\udcff.bin`. The character has no UTF-8 encoding at all.
        raw = b"payload\xff.bin"
        escaped = bm.decode_path(raw)
        self.assertEqual(escaped.encode("utf-8", "surrogateescape"), raw)
        with self.assertRaises(UnicodeEncodeError):
            escaped.encode("utf-8")
        entries["payload.bin"]["path"] = escaped

        code, escaped_out = self.render("escaped")
        self.assertEqual(code, 0, "the page writer must not raise on an unencodable path")
        page_bytes = escaped_out.read_bytes()
        # The deliverable is a UTF-8 document, so the rendering has to be encodable, not merely
        # written: the validator reads it back with a strict UTF-8 decode.
        page = page_bytes.decode("utf-8")
        # ... and it spells the byte the way the manifest does, so the two artefacts name the
        # same path.
        self.assertIn("<code>payload\\udcff.bin</code>", page)
        manifest_bytes = (self.root / "escaped-manifest.json").read_bytes()
        self.assertTrue(manifest_bytes.isascii())
        self.assertIn(b"payload\\udcff.bin", manifest_bytes)

    def test_page_text_leaves_an_encodable_page_alone(self) -> None:
        """The writer's rendering is a pass-through for every character that can be encoded."""
        page = "<html><body>caf\u00e9 \u4e2d\u6587 &amp; plain ascii</body></html>"
        self.assertEqual(bs.page_text(page), page)

    def test_manifest_writer_keeps_its_ascii_pinning(self) -> None:
        """The fix belongs to the page side: the manifest stays an ASCII-only document.

        The manifest is the lossless record of the change set and survives a path that is not
        valid UTF-8 only because its writer is pinned to `ensure_ascii=True`. Escaping the
        character in the page must not be paid for by weakening that writer, so this reads a
        manifest the writer really produced for a repository whose path is not ASCII.
        """
        repo = self.root / "non-ascii"
        repo.mkdir(parents=True)
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "fixture@example.invalid")
        _git(repo, "config", "user.name", "fixture")
        _git(repo, "config", "core.autocrlf", "false")
        name = "caf\u00e9.txt"
        (repo / name).write_bytes("h\u00e9llo\n".encode("utf-8"))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "baseline")
        commit = _git(repo, "rev-parse", "HEAD").strip()
        (repo / name).write_bytes("goodbye\n".encode("utf-8"))

        snapshot = self.root / "non-ascii-baseline-worktree"
        snapshot.mkdir()
        (snapshot / name).write_bytes("h\u00e9llo\n".encode("utf-8"))
        untracked = self.root / "non-ascii-baseline-untracked"
        untracked.mkdir()

        out = self.root / "non-ascii-manifest.json"
        code = bm.main(
            [
                "--repo",
                str(repo),
                "--work-order-id",
                WORK_ORDER_ID,
                "--baseline-commit",
                commit,
                "--baseline-worktree-dir",
                str(snapshot),
                "--baseline-untracked-dir",
                str(untracked),
                "--tmp-dir",
                str(self.root / "tmp"),
                "--out",
                str(out),
            ]
        )
        self.assertEqual(code, 0)
        manifest_bytes = out.read_bytes()
        self.assertTrue(
            manifest_bytes.isascii(),
            "the manifest writer must stay pinned to ensure_ascii=True",
        )
        # The non-ASCII name survives as its escape, which is the spelling the page uses too.
        self.assertIn(b"caf\\u00e9.txt", manifest_bytes)


class LiteralBraceGuardTests(unittest.TestCase):
    """A change set that quotes a literal brace pair must still render (G-43).

    `build_report`'s residual-placeholder check used to run over the assembled page, so any
    unit whose quoted source contains `{{` or `}}` -- a Python f-string, a JSON object
    literal, a JavaScript block -- aborted the whole report with `template placeholders
    remain after substitution`, even though the braces are quoted content and no template
    placeholder is unresolved. The check now reads the template, and the second half of this
    case proves it still rejects a template token the declared placeholder set cannot cover.
    """

    HEAD_SOURCE = (
        'name = "world"\n'
        'print(f"hello {{name}}")\n'
        'payload = {"outer": {"inner": 1}}\n'
        'snippet = "function () { return {{ ok: true }}; }"\n'
    )

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="xc-report-literal-braces-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

        self.repo = self.root / "repo"
        self.repo.mkdir(parents=True)
        _git(self.repo, "init", "-q")
        _git(self.repo, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(self.repo, "config", "user.email", "fixture@example.invalid")
        _git(self.repo, "config", "user.name", "fixture")
        _git(self.repo, "config", "core.autocrlf", "false")
        source = self.repo / "src" / "app.py"
        source.parent.mkdir()
        source.write_bytes(b'name = "world"\nprint("hello")\n')
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "baseline")
        self.commit = _git(self.repo, "rev-parse", "HEAD").strip()

        source.write_bytes(self.HEAD_SOURCE.encode("utf-8"))

        self.snapshot = self.root / "baseline-worktree"
        (self.snapshot / "src").mkdir(parents=True)
        (self.snapshot / "src" / "app.py").write_bytes(b'name = "world"\nprint("hello")\n')
        self.untracked = self.root / "baseline-untracked"
        self.untracked.mkdir()

        self.manifest = bm.build_manifest(
            repo_path=self.repo,
            work_order_id=WORK_ORDER_ID,
            baseline_commit=self.commit,
            baseline_digest=bm.digest_from_hashes(
                [("src/app.py", bm.sha256_hex((self.snapshot / "src" / "app.py").read_bytes()))]
            ),
            baseline_algorithm=bm.DIGEST_ALGORITHM,
            baseline_worktree_dir=self.snapshot,
            baseline_untracked_dir=self.untracked,
            tmp_dir=self.root / "tmp",
            captured_at="2026-09-15T17:45:00Z",
            generated_at="2026-09-15T18:00:00Z",
            strength="standard",
        )
        self.manifest_path = write_manifest(
            self.manifest, self.root / "change-report-manifest.json"
        )
        self.analysis = make_analysis(self.manifest, self.repo)
        self.template = (SKILL_ROOT / "assets" / "change-report-template.html").read_text(
            encoding="utf-8"
        )

    # -- helpers -----------------------------------------------------------------
    def render(self, template_path: Path | None = None) -> tuple[int, Path]:
        out = self.root / "change-report.html"
        argv = [
            "--repo",
            str(self.repo),
            "--manifest",
            str(self.manifest_path),
            "--out",
            str(out),
            "--generated-at",
            "2026-09-15T18:00:00Z",
            "--tmp-dir",
            str(self.root / "tmp"),
        ]
        if template_path is not None:
            argv += ["--template", str(template_path)]
        return bs.main(argv), out

    def test_the_quoted_lines_reach_the_page_and_render(self) -> None:
        code, out = self.render()
        self.assertEqual(code, 0, "quoted literal braces must not stop the report from building")
        page = out.read_bytes().decode("utf-8")
        braces = page.count("{{") + page.count("}}")
        self.assertGreater(braces, 0, "the fixture must really quote a literal brace pair")
        # Every brace pair the page carries is quoted source inside a `report-code` block;
        # none of them is a surviving `{{NAME}}` template token.
        blocks = re.findall(r'<pre class="report-code"[^>]*>.*?</pre>', page, re.S)
        self.assertEqual(
            sum(block.count("{{") + block.count("}}") for block in blocks),
            braces,
            "the only brace pairs in the page are the quoted ones",
        )
        self.assertEqual(re.findall(r"\{\{[A-Z][A-Z0-9_]*\}\}", page), [])

    def test_an_undeclared_template_token_still_fails(self) -> None:
        broken = self.template.replace("{{UNITS}}", "{{UNITS}}<p>{{UNITS_TTILE}}</p>")
        path = self.root / "undeclared-template.html"
        path.write_text(broken, encoding="utf-8")
        with self.assertRaises(bs.SkeletonError) as caught:
            bs.build_report(
                repo=self.repo,
                manifest=self.manifest,
                analysis=self.analysis,
                template_text=broken,
                css_text=(SKILL_ROOT / "assets" / "change-report.css").read_text(encoding="utf-8"),
                generated_at="2026-09-15T18:00:00Z",
                manifest_bytes=self.manifest_path.read_bytes(),
            )
        self.assertIn("UNITS_TTILE", str(caught.exception))
        code, _ = self.render(path)
        self.assertEqual(code, 1, "the writer must fail rather than ship an unresolved token")

    def test_the_residual_check_reads_the_template_not_the_page(self) -> None:
        self.assertEqual(bs.template_residue(self.template), [])
        self.assertEqual(bs.template_residue("{{UNITS}} and {{NOT_DECLARED}}"), ["{{NOT_DECLARED}}"])
        # A declared name only resolves in its exact spelling; anything else survives the
        # substitution loop and is reported instead of being silently shipped.
        self.assertEqual(bs.template_residue("{{ units }}"), ["{{ units }}"])
        self.assertEqual(
            bs.template_residue("<p>a {{ b</p>"), ["unbalanced '{{' or '}}' outside a placeholder token"]
        )
        # Content carried in by a replacement is not the template's business: the guard is a
        # template check, so a value that quotes braces does not make it fail.
        self.assertEqual(bs.template_residue("{{UNITS}}"), [])


if __name__ == "__main__":
    unittest.main()
