from __future__ import annotations

import http.client
import json
import os
import socket
import tempfile
import threading
import unittest
from contextlib import contextmanager
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

import sys

sys.path.insert(0, str(SOURCE_ROOT))

from xcoding.daemon import protocol, server
from xcoding.runtime import application


TOKEN = "test-token-value"


class DaemonServerTests(unittest.TestCase):
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
                "daemon-test",
                "--name",
                "Daemon Test",
            ],
            self.environment(),
        )
        self.assertEqual(result.exit_code, 0, result.payload)
        return runtime_root / "orchestration.xml"

    @contextmanager
    def running(self, paths: list[Path]):
        state, httpd, url = server.create_server(
            paths,
            TOKEN,
            port=0,
        )
        thread = threading.Thread(
            target=httpd.serve_forever,
            kwargs={"poll_interval": 0.05},
            daemon=True,
        )
        thread.start()
        try:
            yield state, httpd, url
        finally:
            state.request_shutdown()
            thread.join(timeout=3)
            httpd.server_close()
            self.assertFalse(thread.is_alive())

    def request(
        self,
        httpd,
        method: str,
        target: str,
        *,
        headers: list[tuple[str, str]] | None = None,
        body: bytes = b"",
        include_host: bool = True,
        include_authorization: bool = True,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        host, port = httpd.server_address[:2]
        connection = http.client.HTTPConnection(host, port, timeout=3)
        connection.putrequest(method, target, skip_host=True)
        if include_host:
            connection.putheader("Host", f"{host}:{port}")
        if include_authorization:
            connection.putheader(
                "Authorization",
                f"Bearer {TOKEN}",
            )
        supplied_headers = headers or []
        for name, value in supplied_headers:
            connection.putheader(name, value)
        if body and not any(
            name.lower() == "content-length"
            for name, _ in supplied_headers
        ):
            connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body if body else None)
        response = connection.getresponse()
        data = response.read()
        response_headers = {
            name.lower(): value
            for name, value in response.getheaders()
        }
        connection.close()
        return (
            response.status,
            json.loads(data),
            response_headers,
        )

    def query_request(
        self,
        httpd,
        payload: object,
    ) -> tuple[int, dict[str, object], dict[str, str]]:
        body = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")
        return self.request(
            httpd,
            "POST",
            "/v1/query",
            headers=[("Content-Type", "application/json")],
            body=body,
        )

    def test_registry_requires_valid_physical_runtime_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tree = self.initialize(root)
            registry = server.RuntimeRegistry([tree, tree])
            self.assertEqual(len(registry.list()), 1)

            invalid_cases = (
                Path("relative.xml"),
                root,
                root / "other.txt",
                MINIMAL_TEMPLATE,
            )
            (root / "other.txt").write_text("not xml", encoding="utf-8")
            for path in invalid_cases:
                with self.subTest(path=path):
                    with self.assertRaises(protocol.ProtocolError):
                        server.RuntimeRegistry([path])

            link = root / "runtime-link.xml"
            try:
                link.symlink_to(tree)
            except OSError:
                link = None
            if link is not None:
                with self.assertRaises(protocol.ProtocolError) as raised:
                    server.RuntimeRegistry([link])
                self.assertEqual(
                    raised.exception.code,
                    "unsafe_tree_path",
                )

    def test_server_rejects_non_loopback_and_falls_back_from_port(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            with self.assertRaises(ValueError):
                server.create_server(
                    [tree],
                    TOKEN,
                    host="0.0.0.0",
                )
            with socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM,
            ) as occupied:
                occupied.bind((server.DEFAULT_HOST, 0))
                occupied.listen()
                requested = occupied.getsockname()[1]
                state, httpd, _ = server.create_server(
                    [tree],
                    TOKEN,
                    port=requested,
                )
                try:
                    self.assertNotEqual(
                        httpd.server_address[1],
                        requested,
                    )
                finally:
                    state.shutdown_requested.set()
                    httpd.server_close()

    def test_health_requires_token_host_and_matching_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            with self.running([tree]) as (_, httpd, _):
                status, payload, headers = self.request(
                    httpd,
                    "GET",
                    "/v1/health",
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload["ok"])
                self.assertEqual(
                    payload["result"],
                    {"status": "ready"},
                )
                self.assertEqual(headers["cache-control"], "no-store")
                self.assertEqual(
                    headers["x-content-type-options"],
                    "nosniff",
                )
                self.assertNotIn(
                    "access-control-allow-origin",
                    headers,
                )

                status, payload, _ = self.request(
                    httpd,
                    "GET",
                    "/v1/health",
                    include_authorization=False,
                )
                self.assertEqual(status, 401)
                self.assertEqual(
                    payload["error"]["code"],
                    "invalid_authorization",
                )
                self.assertNotIn(str(tree), json.dumps(payload))

                status, payload, _ = self.request(
                    httpd,
                    "GET",
                    "/v1/health",
                    headers=[
                        ("Authorization", "Bearer wrong"),
                    ],
                    include_authorization=False,
                )
                self.assertEqual(status, 401)
                self.assertEqual(
                    payload["error"]["code"],
                    "unauthorized",
                )

                status, payload, _ = self.request(
                    httpd,
                    "GET",
                    "/v1/health",
                    headers=[("Host", "evil.example")],
                    include_host=False,
                )
                self.assertEqual(status, 403)
                self.assertEqual(
                    payload["error"]["code"],
                    "forbidden_host",
                )

                status, payload, _ = self.request(
                    httpd,
                    "GET",
                    "/v1/health",
                    headers=[("Origin", "http://evil.example")],
                )
                self.assertEqual(status, 403)
                self.assertEqual(
                    payload["error"]["code"],
                    "forbidden_origin",
                )

                host, port = httpd.server_address[:2]
                status, payload, _ = self.request(
                    httpd,
                    "GET",
                    "/v1/health",
                    headers=[("Origin", f"http://{host}:{port}")],
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload["ok"])

    def test_runtime_listing_uses_opaque_ids_without_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            with self.running([tree]) as (_, httpd, _):
                status, payload, _ = self.request(
                    httpd,
                    "GET",
                    "/v1/runtimes",
                )
                self.assertEqual(status, 200)
                runtimes = payload["result"]["runtimes"]
                self.assertEqual(len(runtimes), 1)
                self.assertEqual(len(runtimes[0]["tree_id"]), 32)
                self.assertNotIn(str(tree), json.dumps(payload))

    def test_query_preserves_application_result_and_runtime_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            before = tree.read_bytes()
            with self.running([tree]) as (_, httpd, _):
                _, listing, _ = self.request(
                    httpd,
                    "GET",
                    "/v1/runtimes",
                )
                tree_id = listing["result"]["runtimes"][0]["tree_id"]
                status, payload, _ = self.query_request(
                    httpd,
                    {
                        "tree_id": tree_id,
                        "command": "summary",
                        "parameters": {"limit": 2},
                    },
                )
                self.assertEqual(status, 200)
                result = payload["result"]
                self.assertEqual(result["exit_code"], 0)
                self.assertTrue(result["payload"]["ok"])

                status, payload, _ = self.query_request(
                    httpd,
                    {
                        "tree_id": tree_id,
                        "command": "start",
                        "parameters": {},
                    },
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    payload["result"]["exit_code"],
                    2,
                )
                self.assertEqual(
                    payload["result"]["payload"]["error"]["code"],
                    "invalid_query",
                )
            self.assertEqual(tree.read_bytes(), before)

    def test_query_rejects_unknown_tree_and_malformed_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            with self.running([tree]) as (_, httpd, _):
                status, payload, _ = self.query_request(
                    httpd,
                    {
                        "tree_id": "unknown",
                        "command": "summary",
                        "parameters": {},
                    },
                )
                self.assertEqual(status, 404)
                self.assertEqual(
                    payload["error"]["code"],
                    "unknown_tree",
                )

                cases = (
                    (
                        "POST",
                        "/v1/query",
                        [("Content-Type", "text/plain")],
                        b"{}",
                        "invalid_content_type",
                    ),
                    (
                        "POST",
                        "/v1/query",
                        [("Content-Type", "application/json")],
                        b'{"a":1,"a":2}',
                        "duplicate_json_key",
                    ),
                    (
                        "GET",
                        "/v1/health?query=1",
                        [],
                        b"",
                        "invalid_request_target",
                    ),
                    (
                        "OPTIONS",
                        "/v1/health",
                        [],
                        b"",
                        "method_not_allowed",
                    ),
                )
                for method, target, headers, body, code in cases:
                    with self.subTest(code=code):
                        status, payload, _ = self.request(
                            httpd,
                            method,
                            target,
                            headers=headers,
                            body=body,
                        )
                        self.assertGreaterEqual(status, 400)
                        self.assertEqual(
                            payload["error"]["code"],
                            code,
                        )

    def test_request_and_response_limits_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            with self.running([tree]) as (state, httpd, _):
                status, payload, _ = self.request(
                    httpd,
                    "POST",
                    "/v1/query",
                    headers=[
                        ("Content-Type", "application/json"),
                        (
                            "Content-Length",
                            str(protocol.MAX_BODY_BYTES + 1),
                        ),
                    ],
                )
                self.assertEqual(status, 413)
                self.assertEqual(
                    payload["error"]["code"],
                    "request_too_large",
                )

                status, payload, _ = self.request(
                    httpd,
                    "GET",
                    "/v1/health",
                    headers=[
                        (
                            "X-Large",
                            "x" * (server.MAX_HEADER_VALUE_BYTES + 1),
                        )
                    ],
                )
                self.assertEqual(status, 413)
                self.assertEqual(
                    payload["error"]["code"],
                    "headers_too_large",
                )

                with (
                    mock.patch.object(
                        protocol,
                        "MAX_JSON_RESPONSE_BYTES",
                        32,
                    ),
                    mock.patch.object(
                        protocol,
                        "request_id",
                        return_value="fixed-request",
                    ),
                ):
                    status, payload, _ = self.request(
                        httpd,
                        "GET",
                        "/v1/health",
                    )
                self.assertEqual(status, 413)
                self.assertEqual(
                    payload["error"]["code"],
                    "response_too_large",
                )
                self.assertEqual(
                    payload["request_id"],
                    "fixed-request",
                )

                acquired = [
                    state.request_slots.acquire(blocking=False)
                    for _ in range(server.MAX_CONCURRENT_REQUESTS)
                ]
                self.assertTrue(all(acquired))
                try:
                    status, payload, _ = self.request(
                        httpd,
                        "GET",
                        "/v1/health",
                    )
                finally:
                    for _ in acquired:
                        state.request_slots.release()
                self.assertEqual(status, 429)
                self.assertEqual(
                    payload["error"]["code"],
                    "server_busy",
                )

    def test_duplicate_authorization_and_arbitrary_method_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            with self.running([tree]) as (_, httpd, _):
                status, payload, _ = self.request(
                    httpd,
                    "GET",
                    "/v1/health",
                    headers=[
                        ("Authorization", f"Bearer {TOKEN}"),
                        ("Authorization", f"Bearer {TOKEN}"),
                    ],
                    include_authorization=False,
                )
                self.assertEqual(status, 401)
                self.assertEqual(
                    payload["error"]["code"],
                    "invalid_authorization",
                )

                status, payload, headers = self.request(
                    httpd,
                    "BREW",
                    "/v1/health",
                )
                self.assertEqual(status, 501)
                self.assertEqual(
                    payload["error"]["code"],
                    "malformed_http_request",
                )
                self.assertEqual(headers["cache-control"], "no-store")
                self.assertNotIn("python", headers["server"].lower())

                status, payload, _ = self.request(
                    httpd,
                    "BREW",
                    "/v1/health",
                    include_authorization=False,
                )
                self.assertEqual(status, 401)
                self.assertEqual(
                    payload["error"]["code"],
                    "invalid_authorization",
                )

                status, payload, _ = self.request(
                    httpd,
                    "BREW",
                    "/v1/health",
                    headers=[("Authorization", "Bearer wrong")],
                    include_authorization=False,
                )
                self.assertEqual(status, 401)
                self.assertEqual(
                    payload["error"]["code"],
                    "unauthorized",
                )

                status, payload, _ = self.request(
                    httpd,
                    "BREW",
                    "/v1/health",
                    headers=[("Host", "evil.example")],
                    include_host=False,
                )
                self.assertEqual(status, 403)
                self.assertEqual(
                    payload["error"]["code"],
                    "forbidden_host",
                )

    def test_sse_is_bounded_summary_only_and_has_no_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            with self.running([tree]) as (state, httpd, _):
                _, listing, _ = self.request(
                    httpd,
                    "GET",
                    "/v1/runtimes",
                )
                tree_id = listing["result"]["runtimes"][0]["tree_id"]
                host, port = httpd.server_address[:2]

                status, payload, _ = self.request(
                    httpd,
                    "GET",
                    f"/v1/runtimes/{tree_id}/events",
                    headers=[("Last-Event-ID", "previous")],
                )
                self.assertEqual(status, 400)
                self.assertEqual(
                    payload["error"]["code"],
                    "event_replay_unsupported",
                )

                with (
                    mock.patch.object(
                        server,
                        "SSE_MAX_AGE_SECONDS",
                        0.2,
                    ),
                    mock.patch.object(
                        server,
                        "SSE_HEARTBEAT_SECONDS",
                        0.05,
                    ),
                    mock.patch.object(
                        server,
                        "EVENT_POLL_SECONDS",
                        0.02,
                    ),
                ):
                    connection = http.client.HTTPConnection(
                        host,
                        port,
                        timeout=2,
                    )
                    connection.putrequest(
                        "GET",
                        f"/v1/runtimes/{tree_id}/events",
                        skip_host=True,
                    )
                    connection.putheader("Host", f"{host}:{port}")
                    connection.putheader(
                        "Authorization",
                        f"Bearer {TOKEN}",
                    )
                    connection.endheaders()
                    response = connection.getresponse()
                    data = response.read().decode("utf-8")
                    connection.close()

                self.assertEqual(response.status, 200)
                self.assertTrue(
                    response.getheader("Content-Type").startswith(
                        "text/event-stream"
                    )
                )
                self.assertIn("event: ready\n", data)
                self.assertIn("event: runtime\n", data)
                self.assertIn(": heartbeat\n\n", data)
                self.assertNotIn("\nid:", data)
                self.assertNotIn(str(tree), data)
                self.assertEqual(state.active_sse_clients(), 0)

    def test_sse_capacity_and_shutdown_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            with self.running([tree]) as (state, httpd, _):
                _, listing, _ = self.request(
                    httpd,
                    "GET",
                    "/v1/runtimes",
                )
                tree_id = listing["result"]["runtimes"][0]["tree_id"]
                acquired = [
                    state.sse_slots.acquire(blocking=False)
                    for _ in range(server.MAX_SSE_CLIENTS)
                ]
                self.assertTrue(all(acquired))
                try:
                    status, payload, _ = self.request(
                        httpd,
                        "GET",
                        f"/v1/runtimes/{tree_id}/events",
                    )
                finally:
                    for _ in acquired:
                        state.sse_slots.release()
                self.assertEqual(status, 429)
                self.assertEqual(
                    payload["error"]["code"],
                    "sse_capacity_exhausted",
                )

    def test_lifecycle_loop_requests_idle_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tree = self.initialize(Path(temporary))
            state, httpd, _ = server.create_server(
                [tree],
                TOKEN,
                port=0,
            )
            serving = threading.Thread(
                target=httpd.serve_forever,
                kwargs={"poll_interval": 0.02},
                daemon=True,
            )
            serving.start()
            try:
                with (
                    mock.patch.object(
                        server,
                        "IDLE_SHUTDOWN_SECONDS",
                        0.05,
                    ),
                    mock.patch.object(
                        server,
                        "EVENT_POLL_SECONDS",
                        0.01,
                    ),
                ):
                    watcher = threading.Thread(
                        target=server.lifecycle_loop,
                        args=(state,),
                        daemon=True,
                    )
                    watcher.start()
                    watcher.join(timeout=2)
                serving.join(timeout=2)
                self.assertFalse(watcher.is_alive())
                self.assertFalse(serving.is_alive())
                self.assertEqual(state.shutdown_reason, "idle")
            finally:
                state.shutdown_requested.set()
                httpd.server_close()


if __name__ == "__main__":
    unittest.main()
