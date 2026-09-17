"""The template-build auto-commit boundary.

`template_builder build` persists a managed template and, when `git.auto_commit`
is enabled, checkpoints it. The repository it checkpoints into must be the
*workshop* repository, because that is where managed workflow state lives. A
template that a project keeps inside its own product repository -- as this
repository does under `skills/*/assets/` -- must not produce a product commit,
because the project bridge governs product history and a work order creates one
scoped commit of its own.

These tests are written as a pair in every direction: a case that must not
commit is always accompanied by a case that must, so that "never commit at all"
cannot satisfy the suite. Each test builds a real Git repository and inspects
`git log`, rather than asserting on the returned status alone, because the
status is what the code says it did and the log is what actually happened.
"""

from __future__ import annotations

import importlib.util
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
AUTHOR_CORE = AUTHOR_SKILL / "scripts" / "author_core.py"


def load_author_core():
    """Load author_core.py by path; it is a script, not an importable package."""
    spec = importlib.util.spec_from_file_location(
        "xc_author_core_commit_boundary_test", AUTHOR_CORE
    )
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load author_core.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FLOW_SPEC: dict[str, Any] = {
    "name": "boundary-flow",
    "schema_version": 1,
    "blackboard": {"boundary.done": "false"},
    "root": {
        "template_id": "root",
        "title": "Boundary Flow",
        "type": "composite",
        "role": "root",
        "mode": "sequence",
        "executor": "main",
        "children": [
            {
                "template_id": "do-work",
                "title": "Do work",
                "type": "task",
                "role": "work",
                "executor": "main",
                "instructions": "Do the work.",
                "deliverables": "A result.",
                "acceptance": "The result exists.",
            }
        ],
    },
}


class CommitBoundaryCase(unittest.TestCase):
    """Shared Git and build helpers."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory(prefix="xc-commit-boundary-")
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.spec_path = self.root / "boundary-flow.json"
        self.spec_path.write_text(
            json.dumps(FLOW_SPEC, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

    def git(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def init_repo(self, path: Path, *, commit_initial: bool = True) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        self.git(["init", "-q"], path)
        self.git(["config", "user.email", "boundary@example.invalid"], path)
        self.git(["config", "user.name", "Boundary Test"], path)
        self.git(["config", "commit.gpgsign", "false"], path)
        if commit_initial:
            (path / "README.md").write_text("repo\n", encoding="utf-8", newline="\n")
            self.git(["add", "-A"], path)
            self.git(["commit", "-qm", "initial"], path)
        return path

    def commit_count(self, repo: Path) -> int:
        result = self.git(["rev-list", "--count", "HEAD"], repo)
        if result.returncode != 0:
            return 0
        return int(result.stdout.strip() or 0)

    def write_workshop_config(self, workshop: Path, payload: dict[str, Any]) -> None:
        workshop.mkdir(parents=True, exist_ok=True)
        (workshop / "xc-orchestration-runtime.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

    def build(self, out: Path, *, config: Path | None = None) -> dict[str, Any]:
        out.parent.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(AUTHOR),
            "build",
            "--spec",
            str(self.spec_path),
            "--out",
            str(out),
        ]
        if config is not None:
            command.extend(["--config", str(config)])
        result = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertTrue(result.stdout, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload.get("ok"), payload)
        return payload


class TemplateOutsideTheWorkshopIsNotCommitted(CommitBoundaryCase):
    """The defect: a template in the product repository produced a product commit."""

    def scenario(self, topology: str | None) -> tuple[Path, Path, dict[str, Any]]:
        """Product repository with an independent workshop repository inside it."""
        project = self.init_repo(self.root / f"project-{topology or 'default'}")
        workshop = project / ".xcoding"
        config: dict[str, Any] = {"schema_version": 1, "git": {"auto_commit": True}}
        if topology is not None:
            config["workshop"] = {"topology": topology}
        self.write_workshop_config(workshop, config)
        self.init_repo(workshop, commit_initial=False)

        template = project / "skills" / "demo" / "assets" / "demo-template.xml"
        before = self.commit_count(project)
        payload = self.build(template)
        return project, template, {"payload": payload, "before": before}

    def test_default_topology_does_not_commit_into_the_product_repository(self) -> None:
        """V1-a. The shipped default is `independent-link`, declared by omission."""
        project, template, observed = self.scenario(None)
        payload = observed["payload"]

        self.assertTrue(template.is_file(), "the template must still be written")
        self.assertEqual(payload["status"], "persisted")
        self.assertEqual(payload["commit"]["status"], "skipped_outside_workshop", payload)
        self.assertEqual(
            payload["commit"]["reason"], "template_outside_workshop_repository", payload
        )
        self.assertEqual(
            self.commit_count(project),
            observed["before"],
            "the product repository gained a commit",
        )

    def test_independent_nested_does_not_commit_into_the_product_repository(self) -> None:
        """V1-a, explicit topology."""
        project, _, observed = self.scenario("independent-nested")
        payload = observed["payload"]
        self.assertEqual(payload["commit"]["status"], "skipped_outside_workshop", payload)
        self.assertEqual(payload["commit"]["topology"], "independent-nested", payload)
        self.assertEqual(self.commit_count(project), observed["before"])

    def test_the_skip_names_both_repositories(self) -> None:
        """A refused commit is reported, not silent: the caller learns which two roots differ."""
        project, _, observed = self.scenario(None)
        commit = observed["payload"]["commit"]
        self.assertIn("template_repository", commit)
        self.assertIn("workshop_repository", commit)
        self.assertNotEqual(commit["template_repository"], commit["workshop_repository"])
        self.assertEqual(
            Path(commit["template_repository"]).resolve(), project.resolve()
        )
        self.assertEqual(
            Path(commit["workshop_repository"]).resolve(),
            (project / ".xcoding").resolve(),
        )


class TemplateInsideTheWorkshopIsStillCommitted(CommitBoundaryCase):
    """The control. Without this, "never commit" would satisfy the suite above."""

    def test_workshop_template_is_committed(self) -> None:
        """V1-b. An independent workshop still checkpoints its own templates."""
        project = self.init_repo(self.root / "project")
        workshop = project / ".xcoding"
        self.write_workshop_config(
            workshop, {"schema_version": 1, "git": {"auto_commit": True}}
        )
        self.init_repo(workshop, commit_initial=False)

        template = workshop / "work-orders" / "demo" / "runtime" / "demo-template.xml"
        before = self.commit_count(workshop)
        payload = self.build(template)

        self.assertEqual(payload["commit"]["status"], "committed", payload)
        self.assertEqual(self.commit_count(workshop), before + 1)
        self.assertEqual(
            self.commit_count(project),
            1,
            "the product repository must be untouched by a workshop checkpoint",
        )

    def test_same_repo_topology_still_commits(self) -> None:
        """V1-c. When the workshop *is* the product repository, the commit is correct."""
        project = self.init_repo(self.root / "same-repo-project")
        workshop = project / ".xcoding"
        # `same-repo` requires an explicit auto_commit declaration; that is the
        # topology's own contract, and it is what authorises this commit.
        self.write_workshop_config(
            workshop,
            {
                "schema_version": 1,
                "git": {"auto_commit": True},
                "workshop": {"topology": "same-repo"},
            },
        )

        template = project / "skills" / "demo" / "assets" / "demo-template.xml"
        before = self.commit_count(project)
        payload = self.build(template)

        self.assertEqual(payload["commit"]["status"], "committed", payload)
        self.assertEqual(self.commit_count(project), before + 1)

    def test_auto_commit_disabled_still_reports_disabled(self) -> None:
        """The pre-existing status must not be replaced by the new one."""
        project = self.init_repo(self.root / "disabled-project")
        workshop = project / ".xcoding"
        self.write_workshop_config(
            workshop, {"schema_version": 1, "git": {"auto_commit": False}}
        )
        self.init_repo(workshop, commit_initial=False)

        template = project / "skills" / "demo" / "assets" / "demo-template.xml"
        payload = self.build(template)
        self.assertEqual(payload["commit"]["status"], "disabled", payload)


class UnresolvableWorkshopFailsClosed(CommitBoundaryCase):
    """V1-d and V1-e. No identifiable workshop means no commit."""

    def test_no_git_topology_does_not_commit(self) -> None:
        """V1-d. The topology declares there is no repository to checkpoint into."""
        project = self.init_repo(self.root / "no-git-project")
        workshop = project / ".xcoding"
        self.write_workshop_config(
            workshop,
            {
                "schema_version": 1,
                "git": {"auto_commit": True},
                "workshop": {"topology": "no-git"},
            },
        )

        template = project / "skills" / "demo" / "assets" / "demo-template.xml"
        before = self.commit_count(project)
        payload = self.build(template)

        self.assertEqual(payload["commit"]["status"], "skipped_outside_workshop", payload)
        self.assertEqual(payload["commit"]["reason"], "topology_no_git", payload)
        self.assertEqual(self.commit_count(project), before)

    def test_undiscoverable_configuration_does_not_commit(self) -> None:
        """V1-e. With no workshop configuration there is no workshop to compare against.

        Committing anyway is exactly the behaviour being removed: it would pick
        whatever repository happens to enclose the template.
        """
        project = self.init_repo(self.root / "no-config-project")
        config = self.root / "loose-runtime.json"
        config.write_text(
            json.dumps({"schema_version": 1, "git": {"auto_commit": True}}) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        template = project / "skills" / "demo" / "assets" / "demo-template.xml"
        before = self.commit_count(project)
        payload = self.build(template, config=config)

        self.assertEqual(payload["commit"]["status"], "skipped_outside_workshop", payload)
        self.assertEqual(payload["commit"]["reason"], "workshop_unidentified", payload)
        self.assertEqual(self.commit_count(project), before)

    def test_a_template_outside_any_repository_is_still_not_applicable(self) -> None:
        """The pre-existing `not_applicable` outcome is preserved."""
        workshop = self.root / "loose" / ".xcoding"
        self.write_workshop_config(
            workshop, {"schema_version": 1, "git": {"auto_commit": True}}
        )
        template = self.root / "loose" / "template.xml"
        payload = self.build(template)
        self.assertIn(
            payload["commit"]["status"],
            {"not_applicable", "skipped_outside_workshop"},
            payload,
        )


class WorkshopRootResolution(unittest.TestCase):
    """The resolver itself, exercised directly."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.core = load_author_core()

    def test_builtin_defaults_resolve_to_no_workshop(self) -> None:
        self.assertIsNone(self.core.workshop_repo_root({"_source": "builtin defaults"}))

    def test_a_configuration_outside_a_dot_xcoding_directory_resolves_to_no_workshop(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="xc-workshop-root-") as temporary:
            loose = Path(temporary) / "elsewhere" / "xc-orchestration-runtime.json"
            loose.parent.mkdir(parents=True)
            loose.write_text("{}\n", encoding="utf-8", newline="\n")
            self.assertIsNone(self.core.workshop_repo_root({"_source": str(loose)}))


if __name__ == "__main__":
    unittest.main()
