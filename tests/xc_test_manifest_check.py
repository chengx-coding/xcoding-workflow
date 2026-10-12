#!/usr/bin/env python3
"""Mechanical integrity checks for the test-suite structure.

This checker is what keeps the structure from drifting. Its most important job
is M1: every test that is actually collected must have exactly one declared
cluster, so a reorganisation cannot silently stop running a test while the
suite still reports success.

Usage:
    python tests/xc_test_manifest_check.py
    python tests/xc_test_manifest_check.py --json
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(REPO_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tests"))

from tests.support import tiers  # noqa: E402


REPRESENTATIVE_PATHS = {
    "runtime": "src/xcoding/runtime/core.py",
    "governance": "skills/xc-work/src/classify.py",
    "lifecycle": "skills/xc-change-report/assets/change-report-flow.json",
    "change_report": "skills/xc-change-report/scripts/build_manifest.py",
    "documents": "skills/xc-document/scripts/validate_document.py",
    "packaging": "pyproject.toml",
    "daemon": "src/xcoding/daemon/server.py",
    "viewer": "src/xcoding/viewer/server.py",
    "delegation": "src/xcoding/delegation/gateway.py",
}

# Process / isolation signals that disqualify a test from the gate tier.
SUBPROCESS_NAMES = {"subprocess", "Popen", "run", "check_output", "check_call", "call"}
TEMP_REPO_SIGNALS = {"git"}


class Finding(dict):
    pass


def _iter_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def _dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _string_args(node: ast.Call) -> list[str]:
    values: list[str] = []
    for arg in list(node.args):
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            values.append(arg.value)
    for keyword in node.keywords:
        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            values.append(keyword.value.value)
        if isinstance(keyword.value, (ast.List, ast.Tuple)):
            for element in keyword.value.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    values.append(element.value)
    return values


def _function_index(tree: ast.Module) -> dict[str, ast.AST]:
    """Map function and method names to their definitions."""
    index: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            index[node.name] = node
    return index


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for call in _iter_calls(node):
        dotted = _dotted(call.func)
        if dotted:
            names.add(dotted)
            names.add(dotted.split(".")[-1])
    return names


def _reachable_functions(entry: ast.AST, index: dict[str, ast.AST]) -> set[str]:
    """Follow local helper calls from a test entry point, one level deep per hop."""
    seen: set[str] = set()
    queue = [entry]
    while queue:
        current = queue.pop()
        for name in _called_names(current):
            if name in index and name not in seen:
                seen.add(name)
                queue.append(index[name])
    return seen


def analyse_module(path: Path) -> dict:
    """Return static signals used by the gate-tier checks.

    Reports module-level facts plus a per-test map so a module that contains one
    process-bound test does not disqualify its in-process tests.
    """
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return {"parse_error": str(error), "source": text}
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    signals = {"spawns_process": False, "touches_real_worktree": False, "imports": imports,
               "tests": {}, "source": text}
    for node in _iter_calls(tree):
        if _dotted(node.func).startswith("subprocess."):
            signals["spawns_process"] = True
            argv = _string_args(node)
            if "git" in argv and any(flag in " ".join(argv) for flag in ("ls-files", "status", "diff")):
                if any(keyword.arg == "cwd" for keyword in node.keywords):
                    signals["touches_real_worktree"] = True

    index = _function_index(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not item.name.startswith("test_"):
                continue
            scope = [item] + [index[name] for name in _reachable_functions(item, index)]
            spawns = False
            real_worktree = False
            for part in scope:
                for call in _iter_calls(part):
                    if _dotted(call.func).startswith("subprocess."):
                        spawns = True
                        argv = _string_args(call)
                        if "git" in argv and any(
                            flag in " ".join(argv) for flag in ("ls-files", "status", "diff")
                        ):
                            real_worktree = True
            signals["tests"][f"{node.name}.{item.name}"] = {
                "spawns_process": spawns,
                "touches_real_worktree": real_worktree,
            }
    return signals


def module_short(identity: str) -> str:
    return tiers.module_of(identity).rsplit(".", 1)[-1]


def module_dotted(identity: str) -> str:
    return tiers.module_of(identity)


def run_checks(plan: tiers.Plan, suite: unittest.TestSuite) -> list[dict]:
    findings: list[dict] = []

    def fail(code: str, message: str, **extra) -> None:
        findings.append({"code": code, "message": message, **extra})

    collected = list(tiers.iter_tests(suite))
    collected_modules = sorted({module_short(test.id()) for test in collected})
    declared_modules = set(plan.all_test_modules())

    # M1a — the collected test count must equal the declared expectation.
    # Without this, a stale duplicate copy of a module (for example one left at
    # the old path by a Git restore) raises the count while every module still
    # has a unique declared cluster, and the suite silently runs tests twice.
    expected = plan.expected_collected_tests
    if expected is not None and len(collected) != expected:
        fail(
            "M1",
            f"collected test count is {len(collected)}, expected {expected}",
            collected=len(collected),
            expected=expected,
        )

    # M1 — every collected module has exactly one declared cluster.
    for short in collected_modules:
        matches = [
            name for name, body in plan.clusters.items() if short in body["modules"]
        ]
        if short in plan.kernel_modules:
            matches.append("governance")
        if len(matches) != 1:
            fail(
                "M1",
                f"collected module must have exactly one cluster: {short} -> {matches}",
                module=short,
            )
    for short in sorted(declared_modules - set(collected_modules)):
        fail("M1", f"declared module was not collected: {short}", module=short)

    # M2 — declared module files exist.
    for short in sorted(declared_modules):
        if plan.module_file(short) is None:
            fail("M2", f"declared module file does not exist: {short}", module=short)

    cluster_names = set(plan.clusters)

    # M3 — every rule points at real clusters.
    for rule in plan.selection_rules:
        for cluster in rule.get("clusters", []):
            if cluster != tiers.ALL_CLUSTERS_SENTINEL and cluster not in cluster_names:
                fail(
                    "M3",
                    f"selection rule references an unknown cluster: {cluster}",
                    prefix=rule.get("prefix"),
                )

    # M4 — every cluster is reachable by at least one rule.
    reachable: set[str] = set(plan.global_clusters)
    for rule in plan.selection_rules:
        clusters = rule.get("clusters", [])
        if tiers.ALL_CLUSTERS_SENTINEL in clusters:
            reachable.update(cluster_names)
        else:
            reachable.update(clusters)
    for cluster in sorted(cluster_names - reachable):
        fail("M4", f"cluster is unreachable by every selection rule: {cluster}", cluster=cluster)

    # M5 / M9 — gate-tier tests must be cheap and must not touch the worktree.
    gate_selectors: list[str] = []
    for entry in plan.tiers["gate"]["selection"]:
        value = entry["value"]
        gate_selectors.extend(value if isinstance(value, list) else [value])
    gate_tests = [
        test
        for test in collected
        if any(tiers._matches(test.id(), module_dotted(test.id()), sel) for sel in gate_selectors)
    ]
    #: The mandatory private-workshop citation guard must run at the gate tier
    #: even though it enumerates the Git index through a subprocess. It is the
    #: one declared exception, and it is cheap (well under one second).
    gate_process_exceptions = {
        "tests.test_xc_workflow_governance.PrivateWorkshopCitationGuardTests"
    }
    signal_cache: dict[str, dict] = {}
    for test in gate_tests:
        identity = test.id()
        dotted = module_dotted(identity)
        short = module_short(identity)
        if any(identity.startswith(exception) for exception in gate_process_exceptions):
            continue
        path = plan.module_file(short)
        if path is None:
            continue
        if short not in signal_cache:
            signal_cache[short] = analyse_module(path)
        signals = signal_cache[short]
        if signals.get("parse_error"):
            fail("M5", f"gate-tier module does not parse: {short}", module=short)
            continue
        # A test identity ends with `<Class>.<method>`; the per-test map is keyed
        # exactly that way.
        parts = identity.split(".")
        key = ".".join(parts[-2:])
        per_test = signals["tests"].get(key)
        spawns = per_test["spawns_process"] if per_test else signals["spawns_process"]
        real = per_test["touches_real_worktree"] if per_test else signals["touches_real_worktree"]
        if spawns:
            fail(
                "M5",
                f"gate-tier test starts a process, which the gate tier forbids: {identity}",
                test=identity,
            )
        if real:
            fail(
                "M9",
                f"gate-tier test operates on the real repository worktree: {identity}",
                test=identity,
            )

    # M6 — frozen paths stay in place.
    for relative in plan.frozen_paths:
        if not (REPO_ROOT / relative).is_file():
            fail("M6", f"frozen path is missing or was moved: {relative}", path=relative)

    # M7 — each cluster that the design converts to in-process calls must still
    # keep at least one process-bound sentinel, so "the CLI works as a program"
    # never stops being observed.
    sentinel_free_clusters = {"documents", "viewer", "daemon"}
    for cluster, body in sorted(plan.clusters.items()):
        if cluster in sentinel_free_clusters:
            continue
        has_sentinel = False
        for short in body["modules"]:
            path = plan.module_file(short)
            if path is None:
                continue
            signals = signal_cache.get(short) or analyse_module(path)
            signal_cache[short] = signals
            if signals.get("spawns_process"):
                has_sentinel = True
                break
        if not has_sentinel:
            fail(
                "M7",
                f"cluster has no process-bound sentinel test: {cluster}",
                cluster=cluster,
            )

    # M8 — coupled-cluster annotations agree with the selection rules.
    for short, body in sorted(plan.coupled_modules.items()):
        if plan.cluster_of_module(short) != body["cluster"]:
            fail(
                "M8",
                f"coupled module cluster disagrees with its declared cluster: {short}",
                module=short,
            )
        owning = plan.cluster_of_module(short)
        for coupled in body.get("coupled_clusters", []):
            reachable_from: set[str] = set()
            for rule in plan.selection_rules:
                clusters = rule.get("clusters", [])
                if owning in clusters or tiers.ALL_CLUSTERS_SENTINEL in clusters:
                    reachable_from.update(clusters)
            declared = set(plan.clusters[owning].get("coupled_clusters", []))
            if coupled not in declared:
                fail(
                    "M8",
                    f"coupled cluster {coupled} is not declared on cluster {owning}",
                    module=short,
                )

    # M10 — each cluster resolves from its representative source path.
    for cluster, path in sorted(REPRESENTATIVE_PATHS.items()):
        resolved, unmatched = tiers.clusters_for_paths(plan, [path])
        if unmatched:
            fail("M10", f"representative path matched no rule: {path}", cluster=cluster)
        elif cluster not in resolved:
            fail(
                "M10",
                f"representative path does not resolve to its cluster: {path} -> {sorted(resolved)}",
                cluster=cluster,
            )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    plan = tiers.load_plan()
    suite = tiers.discover_suite(plan)
    collected = len(list(tiers.iter_tests(suite)))
    findings = run_checks(plan, suite)

    payload = {
        "schema_version": 1,
        "ok": not findings,
        "collected_tests": collected,
        "clusters": len(plan.clusters),
        "declared_modules": len(plan.all_test_modules()),
        "findings": findings,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(
            f"manifest check: collected={collected} clusters={payload['clusters']} "
            f"modules={payload['declared_modules']} findings={len(findings)}"
        )
        for finding in findings:
            print(f"  [{finding['code']}] {finding['message']}")
        print("OK" if payload["ok"] else "FAILED")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
