from __future__ import annotations

import http.client
import json
import os
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
MINIMAL_TEMPLATE = (
    REPOSITORY_ROOT
    / "skills"
    / "xc-orchestration-runtime"
    / "assets"
    / "minimal-template.xml"
)

sys.path.insert(0, str(SOURCE_ROOT))

from xcoding.daemon import cli as daemon_cli
from xcoding.runtime import application


class DaemonLifecycleTests(unittest.TestCase):
    def environment(self) -> application.RuntimeEnvironment:
        return application.RuntimeEnvironment(MINIMAL_TEMPLATE)

    def initialize(self, root: Path) -> Path:
        runtime_root = root / "runtime"
        result = application.execute(
            [
                "init",
                "--runtime-path",
                str(runtime_root),
                "--work-order-id",
                "daemon-lifecycle",
                "--name",
                "Daemon Lifecycle",
            ],
            self.environment(),
        )
        self.assertEqual(result.exit_code, 0, result.payload)
        return runtime_root / "orchestration.xml"

    def process_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SOURCE_ROOT)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONNOUSERSITE"] = "1"
        return environment

    def read_line(
        self,
        stream,
        *,
        timeout: float = 5,
    ) -> str:
        result: queue.Queue[str | BaseException] = queue.Queue()

        def reader() -> None:
            try:
                result.put(stream.readline())
            except BaseException as error:
                result.put(error)

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        value = result.get(timeout=timeout)
        if isinstance(value, BaseException):
            raise value
        return value

    def authorized_health(self, payload: dict[str, object]) -> bool:
        url = str(payload["url"])
        parsed = url.removeprefix("http://")
        host, raw_port = parsed.split(":", 1)
        connection = http.client.HTTPConnection(
            host,
            int(raw_port),
            timeout=2,
        )
        try:
            connection.request(
                "GET",
                "/v1/health",
                headers={
                    "Host": parsed,
                    "Authorization": f"Bearer {payload['token']}",
                },
            )
            response = connection.getresponse()
            body = json.loads(response.read())
            return response.status == 200 and body.get("ok") is True
        except OSError:
            return False
        finally:
            connection.close()

    def terminate_pid(self, pid: int) -> None:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                return
            time.sleep(0.05)

    def test_child_command_and_readiness_never_contain_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tree = self.initialize(root)
            ready = root / "ready.json"
            arguments = daemon_cli.build_parser().parse_args(
                [
                    "serve",
                    "--tree",
                    str(tree),
                ]
            )
            command = daemon_cli.child_command(arguments, ready)
            self.assertNotIn(daemon_cli.TOKEN_ENV, command)
            self.assertNotIn("secret-token", command)

            environment = os.environ.copy()
            os.environ[daemon_cli.TOKEN_ENV] = "secret-token"

            def fake_serve(
                paths,
                token,
                **options,
            ) -> int:
                self.assertEqual(token, "secret-token")
                self.assertNotIn(daemon_cli.TOKEN_ENV, os.environ)
                options["ready"](
                    {
                        "ok": True,
                        "url": "http://127.0.0.1:1",
                        "runtimes": [],
                    }
                )
                return 0

            child_arguments = daemon_cli.build_parser().parse_args(
                [
                    "serve",
                    "--tree",
                    str(tree),
                    "--_child",
                    "--ready-file",
                    str(ready),
                ]
            )
            try:
                with mock.patch.object(
                    daemon_cli.server,
                    "serve_foreground",
                    side_effect=fake_serve,
                ):
                    self.assertEqual(
                        daemon_cli.run_background_child(
                            child_arguments
                        ),
                        0,
                    )
            finally:
                os.environ.clear()
                os.environ.update(environment)
            payload = daemon_cli.read_readiness(ready)
            self.assertTrue(payload["ok"])
            self.assertNotIn("token", payload)
            self.assertNotIn("secret-token", ready.read_text("utf-8"))

    def test_readiness_reader_rejects_secret_or_invalid_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ready.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaises(daemon_cli.DaemonCliError):
                daemon_cli.read_readiness(path)
            path.write_text(
                '{"ok":true,"token":"secret"}',
                encoding="utf-8",
            )
            with self.assertRaises(daemon_cli.DaemonCliError) as raised:
                daemon_cli.read_readiness(path)
            self.assertEqual(
                raised.exception.code,
                "readiness_secret_exposure",
            )

    def test_foreground_process_publishes_token_and_serves(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "xcoding",
                    "daemon",
                    "serve",
                    "--tree",
                    str(tree),
                    "--port",
                    "0",
                    "--foreground",
                ],
                env=self.process_environment(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            try:
                line = self.read_line(process.stdout)
                payload = json.loads(line)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["mode"], "foreground")
                self.assertEqual(payload["pid"], process.pid)
                self.assertGreaterEqual(len(payload["token"]), 32)
                self.assertTrue(self.authorized_health(payload))
            finally:
                process.terminate()
                stdout, stderr = process.communicate(timeout=5)
            self.assertIsNotNone(process.returncode)
            self.assertEqual(stderr, "")
            self.assertNotIn(str(payload["token"]), stdout)

    def test_background_process_returns_one_result_and_serves(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "xcoding",
                    "daemon",
                    "serve",
                    "--tree",
                    str(tree),
                    "--port",
                    "0",
                ],
                env=self.process_environment(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            lines = result.stdout.splitlines()
            self.assertEqual(len(lines), 1, result.stdout)
            payload = json.loads(lines[0])
            self.assertEqual(payload["mode"], "background")
            pid = int(payload["pid"])
            try:
                self.assertTrue(self.authorized_health(payload))
            finally:
                self.terminate_pid(pid)

    def test_public_cli_reports_bounded_startup_errors(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "xcoding",
                "daemon",
                "serve",
                "--tree",
                "relative.xml",
                "--foreground",
            ],
            env=self.process_environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(
            payload["error"]["code"],
            "invalid_tree_path",
        )
        self.assertNotIn("Traceback", result.stdout)


if __name__ == "__main__":
    unittest.main()
