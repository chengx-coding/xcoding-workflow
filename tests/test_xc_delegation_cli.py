from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import shutil
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPOSITORY_ROOT / "skills" / "xc-delegation"
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "delegation"

sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from xcoding.delegation.json_codec import canonical_json_bytes
from xcoding.delegation.resolver import resolve_profile


class DelegationCliTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(REPOSITORY_ROOT / "src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, "-B", "-m", "xcoding", "delegate", *arguments],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.stderr, "")
        self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)
        return result, json.loads(result.stdout)

    def test_validate_and_prepare_emit_stable_public_envelopes(self) -> None:
        result, payload = self.run_cli(
            "validate-profile",
            "--skill-root",
            str(SKILL_ROOT),
            "--profile-id",
            "read-only-evidence",
            "--json",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIs(payload["result"]["dispatch_authoritative"], False)

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "envelope.json"
            result, payload = self.run_cli(
                "prepare",
                "--skill-root",
                str(SKILL_ROOT),
                "--profile-id",
                "read-only-evidence",
                "--node-packet-json",
                str(FIXTURE_ROOT / "node-packet-v1.json"),
                "--node-profile-ref-json",
                str(FIXTURE_ROOT / "node-profile-ref-v1.json"),
                "--project-policy-json",
                str(FIXTURE_ROOT / "project-policy-v1.json"),
                "--adapter-id",
                "codex",
                "--caller-constraints-json",
                str(FIXTURE_ROOT / "caller-constraints-v1.json"),
                "--out",
                str(output),
                "--json",
            )
            self.assertEqual(result.returncode, 0, payload)
            self.assertIs(payload["result"]["dispatch_authoritative"], True)
            envelope = json.loads(output.read_text(encoding="utf-8"))
            self.assertIs(envelope["authority"]["dispatch_authoritative"], True)
            self.assertEqual(output.read_bytes(), canonical_json_bytes(envelope))
            self.assertEqual(list(output.parent.glob("*.xcoding-delegation-tmp")), [])

    def test_noncanonical_input_fails_without_dispatch_output_or_secret_echo(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bad = Path(temporary) / "caller.json"
            bad.write_text('{ "token": "do-not-echo" }\n', encoding="utf-8")
            output = Path(temporary) / "must-not-exist.json"
            result, payload = self.run_cli(
                "prepare",
                "--skill-root",
                str(SKILL_ROOT),
                "--profile-id",
                "read-only-evidence",
                "--node-packet-json",
                str(FIXTURE_ROOT / "node-packet-v1.json"),
                "--node-profile-ref-json",
                str(FIXTURE_ROOT / "node-profile-ref-v1.json"),
                "--project-policy-json",
                str(FIXTURE_ROOT / "project-policy-v1.json"),
                "--adapter-id",
                "codex",
                "--caller-constraints-json",
                str(bad),
                "--out",
                str(output),
                "--json",
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["error"]["code"], "json_not_canonical")
            self.assertNotIn("do-not-echo", json.dumps(payload))
            self.assertFalse(output.exists())

    def test_compile_envelope_is_explicitly_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resolved = root / "resolved.json"
            resolved.write_bytes(
                canonical_json_bytes(resolve_profile(SKILL_ROOT, "read-only-evidence"))
            )
            output = root / "diagnostic-envelope.json"
            result, payload = self.run_cli(
                "compile-envelope",
                "--resolved-profile-json",
                str(resolved),
                "--node-packet-json",
                str(FIXTURE_ROOT / "node-packet-v1.json"),
                "--node-profile-ref-json",
                str(FIXTURE_ROOT / "node-profile-ref-v1.json"),
                "--project-policy-json",
                str(FIXTURE_ROOT / "project-policy-v1.json"),
                "--adapter-capabilities-json",
                str(SKILL_ROOT / "assets/adapters/codex.json"),
                "--caller-constraints-json",
                str(FIXTURE_ROOT / "caller-constraints-v1.json"),
                "--out",
                str(output),
                "--json",
            )
            self.assertEqual(result.returncode, 0, payload)
            self.assertIs(payload["result"]["dispatch_authoritative"], False)
            envelope = json.loads(output.read_text(encoding="utf-8"))
            self.assertIs(envelope["authority"]["dispatch_authoritative"], False)

    def test_scan_legacy_is_read_only_and_json_is_mandatory(self) -> None:
        result, payload = self.run_cli(
            "scan-legacy",
            "--source-root",
            str(REPOSITORY_ROOT),
            "--json",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIs(payload["result"]["writes_performed"], False)
        self.assertIs(payload["result"]["content_included"], False)
        agent_finding = next(
            finding
            for finding in payload["result"]["findings"]
            if finding["path"]
            == "agents-src/agents/xc-delegated-agent.md"
        )
        self.assertEqual(
            {marker["id"] for marker in agent_finding["markers"]},
            {"<agent_definition>", "<agent_prompt>", "xc-delegated-agent"},
        )
        self.assertNotIn(
            "temporary role",
            json.dumps(payload["result"], ensure_ascii=False),
        )
        result, payload = self.run_cli(
            "validate-profile",
            "--skill-root",
            str(SKILL_ROOT),
            "--profile-id",
            "read-only-evidence",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["error"]["code"], "json-required")
        result, payload = self.run_cli("--help")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["error"]["code"], "invalid_arguments")

    def test_installed_package_route_loads_adapter_from_bundled_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            install = Path(temporary) / "install"
            shutil.copytree(REPOSITORY_ROOT / "src/xcoding", install / "xcoding")
            bundled = install / "xcoding/_bundle/skills/xc-delegation"
            shutil.copytree(SKILL_ROOT, bundled)
            output = Path(temporary) / "installed-envelope.json"
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(install)
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "xcoding",
                    "delegate",
                    "prepare",
                    "--skill-root",
                    str(SKILL_ROOT),
                    "--profile-id",
                    "read-only-evidence",
                    "--node-packet-json",
                    str(FIXTURE_ROOT / "node-packet-v1.json"),
                    "--node-profile-ref-json",
                    str(FIXTURE_ROOT / "node-profile-ref-v1.json"),
                    "--project-policy-json",
                    str(FIXTURE_ROOT / "project-policy-v1.json"),
                    "--adapter-id",
                    "codex",
                    "--caller-constraints-json",
                    str(FIXTURE_ROOT / "caller-constraints-v1.json"),
                    "--out",
                    str(output),
                    "--json",
                ],
                cwd=Path(temporary),
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout or result.stderr)
            self.assertEqual(result.stderr, "")
            payload = json.loads(result.stdout)
            self.assertIs(payload["result"]["dispatch_authoritative"], True)
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
