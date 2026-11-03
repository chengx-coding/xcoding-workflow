"""Behavior checks for the sample provenance gate."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "xc-workflow-evolution" / "scripts" / "check_sample_provenance.py"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class SampleProvenanceTest(unittest.TestCase):
    def run_gate(self, seed: Path, project: Path, prior: list[Path], out: Path) -> tuple[int, dict]:
        cmd = [sys.executable, str(SCRIPT), "--seed", str(seed), "--project", str(project),
               "--out", str(out)]
        for item in prior:
            cmd += ["--prior", str(item)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}

    def test_clean_project_passes_and_derived_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed"; project = root / "project"; prior = root / "prior"
            for p in (seed, project, prior):
                write(p / "seed.txt", "seed")
            write(seed / "world.js", "seed")
            write(project / "world.js", "clean")
            write(project / "README.md", "clean readme")
            write(prior / "world.js", "prior")
            write(prior / "README.md", "prior readme")
            code, report = self.run_gate(seed, project, [prior], root / "clean.json")
            self.assertEqual(code, 0, report)
            self.assertTrue(report["clean"])
            self.assertFalse(report["derived"])

            write(project / "README.md", "prior readme")
            code, report = self.run_gate(seed, project, [prior], root / "derived.json")
            self.assertEqual(code, 1, report)
            self.assertFalse(report["clean"])
            self.assertTrue(report["derived"])
            self.assertIn("README.md", report["overlap"])

    def test_archive_root_and_multiple_priors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed"; project = root / "project"; artifact = root / "artifact"
            write(seed / "seed.txt", "seed")
            write(project / "app.js", "derived")
            write(artifact / "metadata.json", "meta")
            write(artifact / "project" / "app.js", "derived")
            code, report = self.run_gate(seed, project, [artifact], root / "archive.json")
            self.assertEqual(code, 1, report)
            self.assertTrue(report["derived"])

    def test_missing_or_empty_inputs_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed = root / "seed"; project = root / "project"; prior = root / "prior"
            for p in (seed, project, prior):
                write(p / "marker", "x")
            code, report = self.run_gate(seed, project, [prior], root / "ok.json")
            self.assertEqual(code, 0)
            code, report = self.run_gate(seed / "missing", project, [prior], root / "missing.json")
            self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
