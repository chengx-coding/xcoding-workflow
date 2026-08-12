from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import shutil
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPORTER = REPOSITORY_ROOT / "agents-src" / "export_agents.py"


class AgentExportTests(unittest.TestCase):
    def test_host_mapping_declares_stable_agent_and_skill_targets(self) -> None:
        configuration = json.loads(
            (
                REPOSITORY_ROOT
                / "build_support"
                / "host_adapters.json"
            ).read_text(encoding="utf-8")
        )
        mappings = {
            adapter["adapter_id"]: (
                adapter["project_agents_root"],
                adapter["project_skills_root"],
            )
            for adapter in configuration["adapters"]
        }

        self.assertEqual(
            mappings,
            {
                "claude-code": (".claude/agents", ".claude/skills"),
                "codex": (".codex/agents", ".agents/skills"),
                "opencode": (".opencode/agents", ".agents/skills"),
                "trae": (".trae/agents", ".agents/skills"),
            },
        )
        trae = next(
            adapter
            for adapter in configuration["adapters"]
            if adapter["adapter_id"] == "trae"
        )
        self.assertEqual(trae["generated_root"], "agents-src/trae-agents")
        self.assertEqual(trae["bundle_root"], "adapters/trae")

    def test_generated_agents_are_current_and_share_worker_body(self) -> None:
        result = subprocess.run(
            [sys.executable, str(EXPORTER), "--check"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

        source = (REPOSITORY_ROOT / "agents-src" / "agents" / "delegate-agent.md").read_text(encoding="utf-8")
        body = source.split("---", 2)[2].strip()
        claude = (REPOSITORY_ROOT / "agents-src" / "claude-agents" / "delegate-agent.md").read_text(encoding="utf-8")
        opencode = (REPOSITORY_ROOT / "agents-src" / "opencode-agents" / "delegate-agent.md").read_text(encoding="utf-8")
        codex = (REPOSITORY_ROOT / "agents-src" / "codex-agents" / "delegate-agent.toml").read_text(encoding="utf-8")
        trae = (REPOSITORY_ROOT / "agents-src" / "trae-agents" / "delegate-agent.md").read_text(encoding="utf-8")

        self.assertIn(body, claude)
        self.assertIn(body, opencode)
        self.assertIn("developer_instructions", codex)
        self.assertIn("You execute one delegated task.", codex)
        self.assertTrue(trae.startswith("---\nname: delegate-agent\n"))
        self.assertIn(body, trae)

    def test_check_rejects_extra_missing_and_stale_generated_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "agents-src"
            shutil.copytree(REPOSITORY_ROOT / "agents-src", root)
            exporter = root / "export_agents.py"
            generated = subprocess.run(
                [sys.executable, str(exporter)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(
                generated.returncode,
                0,
                generated.stderr or generated.stdout,
            )
            extra = root / "trae-agents" / "obsolete-agent.md"
            extra.write_text("obsolete\n", encoding="utf-8")

            checked = subprocess.run(
                [sys.executable, str(exporter), "--check"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

            self.assertEqual(checked.returncode, 1)
            self.assertIn("trae-agents/obsolete-agent.md", checked.stderr)

            extra.unlink()
            expected = root / "trae-agents" / "delegate-agent.md"
            expected.unlink()
            missing = subprocess.run(
                [sys.executable, str(exporter), "--check"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(missing.returncode, 1)
            self.assertIn("trae-agents/delegate-agent.md", missing.stderr)

            regenerated = subprocess.run(
                [sys.executable, str(exporter)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(regenerated.returncode, 0)
            expected.write_text("stale\n", encoding="utf-8")
            stale = subprocess.run(
                [sys.executable, str(exporter), "--check"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(stale.returncode, 1)
            self.assertIn("trae-agents/delegate-agent.md", stale.stderr)


if __name__ == "__main__":
    unittest.main()
