"""The explicit line-ending contract for agent-authored repository files.

A managed repository text file is stored with LF endings. When a process writes
one through a host text layer that translates newlines -- the default on
Windows -- a three-line edit rewrites every line in the file, and a reviewer
sees a whole-file diff instead of the change. `git diff --check`, which this
project's bridge requires before delivery, then reports one trailing-whitespace
hit per line.

Nothing mechanical prevented that, and the repository drifted accordingly: some
scripts passed an explicit newline and some did not. These tests make the rule
checkable, so the contract cannot quietly rot back into a split.

The scan covers production code only. `tests/` is excluded deliberately: a test
fixture is not agent-authoring guidance, and several fixtures write CRLF content
on purpose -- `test_xc_change_report.py` materialises a CRLF worktree to prove
the change report handles one. Scanning them would force either broken fixtures
or a suppression list, and would not reduce the risk this contract addresses.
"""

from __future__ import annotations

import ast
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOTS = ("skills", "src", "agents-src")
PRODUCTION_FILES = ("build_agents.py",)

DOCUMENT_SKILL = REPOSITORY_ROOT / "skills" / "xc-document" / "SKILL.md"
IMPLEMENTATION_SKILL = REPOSITORY_ROOT / "skills" / "xc-implementation" / "SKILL.md"

TEXT_WRITE_METHODS = {"write_text"}
OPEN_CALLS = {"open", "fdopen"}


def production_sources() -> list[Path]:
    paths: list[Path] = []
    for folder in PRODUCTION_ROOTS:
        paths.extend(sorted((REPOSITORY_ROOT / folder).rglob("*.py")))
    for name in PRODUCTION_FILES:
        paths.append(REPOSITORY_ROOT / name)
    return [p for p in paths if p.exists() and "__pycache__" not in p.parts]


def called_name(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def open_mode(call: ast.Call) -> str:
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
        value = call.args[1].value
        if isinstance(value, str):
            return value
    for keyword in call.keywords:
        if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value)
    return ""


def translating_writes(path: Path) -> list[tuple[int, str]]:
    """Return (line, description) for text writes that do not pin the newline."""
    source = path.read_text(encoding="utf-8")
    findings: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = called_name(node.func)
        keywords = {keyword.arg for keyword in node.keywords}
        if name in TEXT_WRITE_METHODS:
            if "newline" not in keywords:
                findings.append((node.lineno, "write_text"))
            continue
        if name in OPEN_CALLS:
            mode = open_mode(node)
            if "b" in mode:
                continue
            if "w" not in mode and "a" not in mode and "x" not in mode:
                continue
            if "newline" not in keywords:
                findings.append((node.lineno, f"{name}({mode!r})"))
    return findings


class ProductionWritesPinTheirLineEndings(unittest.TestCase):
    """V2-a. Every production text write states the newline it intends."""

    def test_no_production_text_write_relies_on_the_host_default(self) -> None:
        offenders: list[str] = []
        for path in production_sources():
            for line, description in translating_writes(path):
                offenders.append(f"{path.relative_to(REPOSITORY_ROOT)}:{line}  {description}")
        self.assertEqual(
            offenders,
            [],
            "these writes inherit the host newline translation; pass an explicit "
            "newline argument:\n  " + "\n  ".join(offenders),
        )

    def test_the_scan_detects_a_translating_write(self) -> None:
        """Control: the scan above is only meaningful if it can still fail.

        A scan that has been satisfied once can rot into one that matches
        nothing. This feeds it a known-bad and a known-good source.
        """
        with tempfile.TemporaryDirectory(prefix="xc-lf-scan-") as temporary:
            bad = Path(temporary) / "bad.py"
            bad.write_text(
                "from pathlib import Path\n"
                "Path('x').write_text('body', encoding='utf-8')\n"
                "with open('y', 'w', encoding='utf-8') as handle:\n"
                "    handle.write('body')\n",
                encoding="utf-8",
                newline="\n",
            )
            self.assertEqual(
                [description for _, description in translating_writes(bad)],
                ["write_text", "open('w')"],
            )

            good = Path(temporary) / "good.py"
            good.write_text(
                "from pathlib import Path\n"
                "Path('x').write_text('body', encoding='utf-8', newline='\\n')\n"
                "Path('y').write_bytes(b'body')\n"
                "with open('z', 'wb') as handle:\n"
                "    handle.write(b'body')\n",
                encoding="utf-8",
                newline="\n",
            )
            self.assertEqual(translating_writes(good), [])


class TheContractIsStated(unittest.TestCase):
    """V2-b. The rule lives in one Skill and is cited, not duplicated, by the other."""

    def flat(self, path: Path) -> str:
        return " ".join(path.read_text(encoding="utf-8").split())

    def test_xc_document_states_the_line_ending_rule(self) -> None:
        document = self.flat(DOCUMENT_SKILL)
        self.assertIn("## Line Endings in Authored Files", document)
        # The substance: LF, and a local edit that does not rewrite untouched lines.
        self.assertIn("LF", document)
        self.assertIn("unchanged lines", document)
        # The cause an author has to recognise, and the check that catches it.
        self.assertIn("newline translation", document)
        self.assertIn("git diff --check", document)

    def test_the_rule_is_stated_by_outcome_rather_than_bound_to_one_language(self) -> None:
        """A generic Skill must not require a particular implementation language."""
        document = DOCUMENT_SKILL.read_text(encoding="utf-8")
        section = document.split("## Line Endings in Authored Files", 1)[1]
        section = section.split("\n## ", 1)[0]
        self.assertIn("LF", section)
        # A language-specific call may appear as an example, but only as one.
        if "newline=" in section:
            self.assertIn("example", section.lower())

    def test_xc_implementation_cites_the_rule_without_restating_it(self) -> None:
        implementation = self.flat(IMPLEMENTATION_SKILL)
        self.assertIn("Line Endings in Authored Files", implementation)
        self.assertIn("xc-document", implementation)
        # Citation, not duplication: the mechanism belongs to the owning Skill.
        self.assertNotIn("newline=", implementation)


class TheContractPreventsTheDamageItDescribes(unittest.TestCase):
    """V2-c. The behavioural control behind the rule.

    Without this, the two checks above would assert that a rule exists without
    ever establishing that following it matters.
    """

    def git(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def edit(self, text: str) -> str:
        for index in range(0, 100, 10):
            text = text.replace(f"line {index:04d} content", f"line {index:04d} CHANGED")
        return text

    def test_an_explicit_lf_edit_touches_only_the_edited_lines(self) -> None:
        with tempfile.TemporaryDirectory(prefix="xc-lf-behaviour-") as temporary:
            repo = Path(temporary)
            self.git(["init", "-q"], repo)
            self.git(["config", "user.email", "lf@example.invalid"], repo)
            self.git(["config", "user.name", "LF Test"], repo)
            self.git(["config", "core.autocrlf", "false"], repo)

            managed = repo / "managed.md"
            body = "\n".join(f"line {index:04d} content" for index in range(100)) + "\n"
            managed.write_bytes(body.encode("utf-8"))
            self.git(["add", "-A"], repo)
            self.git(["commit", "-qm", "baseline"], repo)

            managed.write_text(
                self.edit(managed.read_text(encoding="utf-8")),
                encoding="utf-8",
                newline="\n",
            )

            numstat = self.git(["diff", "--numstat"], repo).stdout.split()
            self.assertEqual(numstat[:2], ["10", "10"], "only the edited lines may change")
            check = self.git(["diff", "--check"], repo)
            self.assertEqual(check.returncode, 0, check.stdout)
            self.assertNotIn(b"\r", managed.read_bytes())


if __name__ == "__main__":
    unittest.main()
