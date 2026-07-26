#!/usr/bin/env python3
"""Read-only local viewer for managed orchestration runtime trees."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import unquote, urlparse

import runtime_core as core


STATIC_DIR = Path(__file__).resolve().parents[1] / "viewer" / "static"


def json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def tree_id_for(path: Path) -> str:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]
    return f"tree-{digest}"


@dataclass
class TreeEntry:
    tree_id: str
    path: Path
    snapshot: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    mtime_ns: int = -1
    size: int = -1
    refreshed_at: float = 0.0

    def listing(self) -> Dict[str, Any]:
        metadata = (self.snapshot or {}).get("metadata", {})
        return {
            "tree_id": self.tree_id,
            "path": str(self.path),
            "name": metadata.get("name", self.path.stem),
            "run_id": metadata.get("run_id", ""),
            "status": metadata.get("status", "unavailable"),
            "version": (self.snapshot or {}).get("version", ""),
            "updated_at": metadata.get("updated_at", ""),
            "integrity": (self.snapshot or {}).get("integrity", {}),
            "error": self.error,
            "refreshed_at": self.refreshed_at,
        }


class TreeRegistry:
    """Thread-safe registry with retained last-valid snapshots."""

    def __init__(self, config: Dict[str, Any], allow_roots: Iterable[Path]) -> None:
        self.config = config
        self.allow_roots = {root.resolve() for root in allow_roots}
        self.entries: Dict[str, TreeEntry] = {}
        self.lock = threading.RLock()

    def is_allowed(self, path: Path) -> bool:
        return any(is_within(path, root) for root in self.allow_roots)

    def register(self, raw_path: str, add_parent_root: bool = False) -> TreeEntry:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise core.RuntimeErrorBase("tree path does not exist or is not a file", {"path": str(path)})
        if path.suffix.lower() != ".xml":
            raise core.RuntimeErrorBase("viewer only registers XML tree files", {"path": str(path)})
        with self.lock:
            if add_parent_root:
                self.allow_roots.add(path.parent)
            if not self.is_allowed(path):
                raise core.RuntimeErrorBase(
                    "tree path is outside the viewer allow roots",
                    {"path": str(path), "allow_roots": [str(root) for root in sorted(self.allow_roots)]},
                )
            tree_id = tree_id_for(path)
            entry = self.entries.get(tree_id)
            if entry is None:
                entry = TreeEntry(tree_id, path)
                self.entries[tree_id] = entry
        self.refresh(tree_id, force=True)
        return entry

    def remove(self, tree_id: str) -> None:
        with self.lock:
            if tree_id not in self.entries:
                raise core.RuntimeErrorBase("unknown viewer tree", {"tree_id": tree_id})
            del self.entries[tree_id]

    def get(self, tree_id: str) -> TreeEntry:
        with self.lock:
            entry = self.entries.get(tree_id)
            if entry is None:
                raise core.RuntimeErrorBase("unknown viewer tree", {"tree_id": tree_id})
            return entry

    def list(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [self.entries[key].listing() for key in sorted(self.entries)]

    def refresh(self, tree_id: str, force: bool = False) -> TreeEntry:
        entry = self.get(tree_id)
        try:
            stat = entry.path.stat()
        except OSError as exc:
            with self.lock:
                entry.error = {"code": "tree_unavailable", "message": str(exc)}
                entry.refreshed_at = time.time()
            return entry
        if not force and stat.st_mtime_ns == entry.mtime_ns and stat.st_size == entry.size:
            return entry
        try:
            snapshot = core.tree_snapshot(entry.path, self.config)
        except core.RuntimeErrorBase as exc:
            with self.lock:
                entry.error = {"code": exc.code, "message": str(exc), "details": exc.details}
                entry.mtime_ns = stat.st_mtime_ns
                entry.size = stat.st_size
                entry.refreshed_at = time.time()
            return entry
        with self.lock:
            entry.snapshot = snapshot
            entry.error = None
            entry.mtime_ns = stat.st_mtime_ns
            entry.size = stat.st_size
            entry.refreshed_at = time.time()
        return entry

    def refresh_all(self) -> None:
        with self.lock:
            identifiers = list(self.entries)
        for tree_id in identifiers:
            self.refresh(tree_id)


class ViewerState:
    def __init__(self, registry: TreeRegistry, config: Dict[str, Any]) -> None:
        self.registry = registry
        self.config = config
        self.clients: Dict[str, float] = {}
        self.started_at = time.monotonic()
        self.shutdown_requested = threading.Event()
        self.server: Optional[ThreadingHTTPServer] = None
        self.lock = threading.RLock()

    @property
    def heartbeat_seconds(self) -> int:
        return self.config["viewer"]["heartbeat_seconds"]

    @property
    def idle_shutdown_seconds(self) -> int:
        return self.config["viewer"]["idle_shutdown_seconds"]

    def open_client(self) -> Dict[str, Any]:
        client_id = uuid.uuid4().hex
        with self.lock:
            self.clients[client_id] = time.monotonic()
        return {"client_id": client_id, "heartbeat_seconds": self.heartbeat_seconds}

    def heartbeat(self, client_id: str) -> None:
        with self.lock:
            if client_id not in self.clients:
                raise core.RuntimeErrorBase("unknown viewer client", {"client_id": client_id})
            self.clients[client_id] = time.monotonic()

    def active_clients(self) -> int:
        now = time.monotonic()
        timeout = max(self.heartbeat_seconds * 2, 1)
        with self.lock:
            self.clients = {
                client_id: seen_at
                for client_id, seen_at in self.clients.items()
                if now - seen_at <= timeout
            }
            return len(self.clients)

    def request_shutdown(self) -> None:
        if self.shutdown_requested.is_set():
            return
        self.shutdown_requested.set()
        if self.server is not None:
            threading.Thread(target=self.server.shutdown, daemon=True).start()


class ViewerRequestHandler(BaseHTTPRequestHandler):
    server_version = "OrchestrationViewer/1"
    state: ViewerState

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "active_clients": self.state.active_clients(),
                    "allow_roots": [str(root) for root in sorted(self.state.registry.allow_roots)],
                },
            )
            return
        if parsed.path == "/api/trees":
            self.send_json(HTTPStatus.OK, {"ok": True, "trees": self.state.registry.list()})
            return
        if parsed.path.startswith("/api/trees/") and parsed.path.endswith("/snapshot"):
            tree_id = parsed.path.split("/")[3]
            try:
                entry = self.state.registry.get(tree_id)
            except core.RuntimeErrorBase as exc:
                self.send_runtime_error(exc, HTTPStatus.NOT_FOUND)
                return
            if entry.snapshot is None:
                self.send_json(
                    HTTPStatus.CONFLICT,
                    {"ok": False, "error": entry.error or {"code": "snapshot_unavailable", "message": "No valid snapshot yet."}},
                )
                return
            self.send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "tree": entry.listing(),
                    "snapshot": entry.snapshot,
                    "refresh_error": entry.error,
                },
            )
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self.read_json()
            if parsed.path == "/api/trees":
                path = payload.get("path", "")
                if not isinstance(path, str) or not path:
                    raise core.RuntimeErrorBase("path is required")
                entry = self.state.registry.register(path)
                self.send_json(HTTPStatus.CREATED, {"ok": True, "tree": entry.listing()})
                return
            if parsed.path == "/api/clients":
                self.send_json(HTTPStatus.CREATED, {"ok": True, **self.state.open_client()})
                return
            if parsed.path.startswith("/api/clients/") and parsed.path.endswith("/heartbeat"):
                client_id = parsed.path.split("/")[3]
                self.state.heartbeat(client_id)
                self.send_json(HTTPStatus.OK, {"ok": True})
                return
            if parsed.path.startswith("/api/trees/") and parsed.path.endswith("/refresh"):
                tree_id = parsed.path.split("/")[3]
                entry = self.state.registry.refresh(tree_id, force=True)
                self.send_json(HTTPStatus.OK, {"ok": True, "tree": entry.listing(), "error": entry.error})
                return
        except core.RuntimeErrorBase as exc:
            self.send_runtime_error(exc, HTTPStatus.BAD_REQUEST)
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": {"code": "not_found", "message": "Unknown API route."}})

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/trees/"):
            tree_id = parsed.path.split("/")[3]
            try:
                self.state.registry.remove(tree_id)
            except core.RuntimeErrorBase as exc:
                self.send_runtime_error(exc, HTTPStatus.NOT_FOUND)
                return
            self.send_json(HTTPStatus.OK, {"ok": True, "tree_id": tree_id})
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": {"code": "not_found", "message": "Unknown API route."}})

    def read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise core.RuntimeErrorBase("request body must be JSON", {"error": str(exc)}) from exc
        if not isinstance(payload, dict):
            raise core.RuntimeErrorBase("request JSON root must be an object")
        return payload

    def send_runtime_error(self, error: core.RuntimeErrorBase, status: HTTPStatus) -> None:
        self.send_json(status, {"ok": False, "error": {"code": error.code, "message": str(error), "details": error.details}})

    def send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body = json_bytes(payload)
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, raw_path: str) -> None:
        relative = "index.html" if raw_path in {"", "/"} else unquote(raw_path.lstrip("/"))
        candidate = (STATIC_DIR / relative).resolve()
        if not is_within(candidate, STATIC_DIR.resolve()) or not candidate.is_file():
            self.send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": {"code": "not_found", "message": "Static asset not found."}})
            return
        data = candidate.read_bytes()
        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def polling_loop(state: ViewerState) -> None:
    interval = max(state.config["viewer"]["watch_interval_seconds"], 1)
    while not state.shutdown_requested.wait(interval):
        state.registry.refresh_all()
        if state.active_clients() == 0 and time.monotonic() - state.started_at >= state.idle_shutdown_seconds:
            state.request_shutdown()
            return


def create_server(host: str, port: int, state: ViewerState) -> ThreadingHTTPServer:
    handler = type("BoundViewerRequestHandler", (ViewerRequestHandler,), {"state": state})
    try:
        return ThreadingHTTPServer((host, port), handler)
    except OSError:
        if port == 0:
            raise
        return ThreadingHTTPServer((host, 0), handler)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the local, read-only orchestration viewer.")
    parser.add_argument("--tree", action="append", default=[], help="Initial managed runtime XML tree. May be repeated.")
    parser.add_argument("--allow-root", action="append", default=[], help="Directory eligible for later tree registration. May be repeated.")
    parser.add_argument("--config", default="", help="Optional xc-orchestration-runtime TOML path.")
    parser.add_argument("--host", default="", help="Loopback host override; only 127.0.0.1 is accepted.")
    parser.add_argument("--port", type=int, default=None, help="Preferred port; occupied ports fall back to an ephemeral port.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    context_path = Path(args.tree[0]) if args.tree else Path.cwd()
    config = core.load_config(context_path, Path(args.config) if args.config else None)
    host = args.host or config["viewer"]["host"]
    if host != "127.0.0.1":
        raise SystemExit("viewer host must be 127.0.0.1")
    port = config["viewer"]["port"] if args.port is None else args.port
    if port < 0 or port > 65535:
        raise SystemExit("viewer port must be between 0 and 65535")
    allow_roots = [Path(value) for value in args.allow_root]
    registry = TreeRegistry(config, allow_roots)
    for raw_path in args.tree:
        registry.register(raw_path, add_parent_root=True)
    state = ViewerState(registry, config)
    server = create_server(host, port, state)
    state.server = server
    actual_port = server.server_address[1]
    url = f"http://{host}:{actual_port}/"
    print(json.dumps({"ok": True, "url": url, "trees": registry.list()}, ensure_ascii=False), flush=True)
    watcher = threading.Thread(target=polling_loop, args=(state,), daemon=True)
    watcher.start()
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        state.request_shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
