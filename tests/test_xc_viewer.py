from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from xcoding.runtime import core
from xcoding.viewer import server


class PackageViewerTests(unittest.TestCase):
    def write_config(self, root: Path) -> Path:
        path = root / "viewer.json"
        path.write_text(
            json.dumps(
                {
                    "git": {"auto_commit": False},
                    "viewer": {
                        "host": "127.0.0.1",
                        "port": 0,
                        "watch_interval_seconds": 1,
                        "heartbeat_seconds": 1,
                        "idle_shutdown_seconds": 30,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def write_tree(self, root: Path) -> Path:
        config = core.load_config(root, self.write_config(root))
        template = core.parse_xml(
            SOURCE_ROOT
            / "xcoding"
            / "runtime"
            / "assets"
            / "minimal-template.xml"
        )
        tree = core.instantiate_runtime_tree(
            template,
            "package-viewer",
            "Package Viewer",
            [],
            config,
        )
        core.stabilize(tree.getroot())
        path = root / "runtime" / "orchestration.xml"
        core.write_managed_tree(
            tree,
            path,
            "runtime",
            config,
            "test",
            commit_on_write=False,
        )
        return path

    def request_json(self, url: str) -> dict[str, object]:
        with urllib.request.urlopen(url, timeout=2) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read())

    def stop_process(self, pid: int) -> None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/pid", str(pid), "/t", "/f"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                return
            time.sleep(0.05)

    def environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SOURCE_ROOT)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return environment

    def test_package_resources_and_child_modules_are_owned_by_xcoding(
        self,
    ) -> None:
        self.assertEqual(
            sorted(path.name for path in server.STATIC_DIR.iterdir()),
            ["app.css", "app.js", "index.html"],
        )
        args = server.build_parser().parse_args(
            ["--tree", "tree.xml", "--port", "0"]
        )
        command = server.child_command(args, Path("ready.json"))
        self.assertEqual(
            command[:3],
            [sys.executable, "-m", "xcoding.viewer.server"],
        )

        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {"ok": True, "selected": False, "path": ""}
            ),
            stderr="",
        )
        with mock.patch.object(
            server.subprocess,
            "run",
            return_value=completed,
        ) as run:
            self.assertIsNone(server.select_tree_file())
        self.assertEqual(
            run.call_args.args[0],
            [sys.executable, "-m", "xcoding.viewer.picker"],
        )

    def test_registry_serves_health_snapshot_svg_and_static(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            tree = self.write_tree(root)
            config = core.load_config(root, self.write_config(root))
            registry = server.TreeRegistry(config, [root])
            entry = registry.register(str(tree), add_parent_root=True)
            state = server.ViewerState(registry, config)
            httpd = server.create_server("127.0.0.1", 0, state)
            state.server = httpd
            thread = threading.Thread(
                target=httpd.serve_forever,
                daemon=True,
            )
            thread.start()
            url = f"http://127.0.0.1:{httpd.server_address[1]}/"
            try:
                self.assertTrue(self.request_json(f"{url}api/health")["ok"])
                snapshot = self.request_json(
                    f"{url}api/trees/{entry.tree_id}/snapshot"
                )
                self.assertEqual(
                    snapshot["snapshot"]["metadata"]["artifact_kind"],
                    "runtime",
                )
                with urllib.request.urlopen(
                    f"{url}api/trees/{entry.tree_id}/svg",
                    timeout=2,
                ) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(b"<svg", response.read())
                with urllib.request.urlopen(url, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(b"<!doctype html>", response.read().lower())
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=2)

    def test_background_module_launch_returns_one_result_and_serves(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            tree = self.write_tree(root)
            launched = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "xcoding",
                    "viewer",
                    "--tree",
                    str(tree),
                    "--port",
                    "0",
                    "--no-browser",
                ],
                cwd=root,
                env=self.environment(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
                check=False,
            )
            self.assertEqual(
                launched.returncode,
                0,
                launched.stderr or launched.stdout,
            )
            self.assertEqual(launched.stderr, "")
            lines = launched.stdout.splitlines()
            self.assertEqual(len(lines), 1, launched.stdout)
            payload = json.loads(lines[0])
            try:
                self.assertEqual(payload["mode"], "background")
                self.assertTrue(
                    self.request_json(f"{payload['url']}api/health")["ok"]
                )
            finally:
                self.stop_process(int(payload["pid"]))


if __name__ == "__main__":
    unittest.main()
