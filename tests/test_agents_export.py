from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPORTER = REPOSITORY_ROOT / "agents-src" / "export_agents.py"


class AgentExportTests(unittest.TestCase):
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

        self.assertIn(body, claude)
        self.assertIn(body, opencode)
        self.assertIn("developer_instructions", codex)
        self.assertIn("You execute one delegated task.", codex)


if __name__ == "__main__":
    unittest.main()
