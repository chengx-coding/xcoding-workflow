"""Authenticated loopback HTTP server for read-only runtime queries."""

from __future__ import annotations

import hmac
import secrets
import stat
import threading
import time
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit

from xcoding.runtime import application, query

from . import protocol


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 20669
MAX_TARGET_BYTES = 4096
MAX_HEADER_COUNT = 64
MAX_HEADER_VALUE_BYTES = 8192
MAX_CONCURRENT_REQUESTS = 16
SOCKET_TIMEOUT_SECONDS = 5
REQUEST_QUEUE_SIZE = 16


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def _is_junction(path: Path) -> bool:
    predicate = getattr(path, "is_junction", None)
    return bool(predicate is not None and predicate())


def _path_error(
    code: str,
    message: str,
    *,
    path: Path | None = None,
) -> protocol.ProtocolError:
    details: dict[str, object] = {}
    if path is not None:
        details["path"] = str(path)
    return protocol.ProtocolError(
        HTTPStatus.BAD_REQUEST,
        code,
        message,
        details,
    )


def validate_runtime_path(raw_path: Path) -> Path:
    if not raw_path.is_absolute():
        raise _path_error(
            "invalid_tree_path",
            "runtime tree path must be absolute",
        )
    try:
        metadata = raw_path.lstat()
    except OSError as error:
        raise _path_error(
            "tree_unavailable",
            "runtime tree cannot be inspected",
            path=raw_path,
        ) from error
    if (
        raw_path.is_symlink()
        or _is_junction(raw_path)
        or not stat.S_ISREG(metadata.st_mode)
    ):
        raise _path_error(
            "unsafe_tree_path",
            "runtime tree must be a regular physical file",
            path=raw_path,
        )
    if raw_path.suffix.lower() != ".xml":
        raise _path_error(
            "invalid_tree_path",
            "runtime tree must use the .xml suffix",
            path=raw_path,
        )
    try:
        resolved = raw_path.resolve(strict=True)
    except OSError as error:
        raise _path_error(
            "tree_unavailable",
            "runtime tree cannot be resolved",
            path=raw_path,
        ) from error
    if resolved.is_symlink() or _is_junction(resolved):
        raise _path_error(
            "unsafe_tree_path",
            "runtime tree resolution produced a link",
            path=raw_path,
        )
    return resolved


@dataclass(frozen=True)
class RuntimeEntry:
    tree_id: str
    path: Path


class RuntimeRegistry:
    """Process-local registry of explicitly supplied runtime trees."""

    def __init__(self, paths: Iterable[Path]) -> None:
        self._environment = application.RuntimeEnvironment(Path())
        self._entries: dict[str, RuntimeEntry] = {}
        self._path_ids: dict[Path, str] = {}
        self._lock = threading.RLock()
        for path in paths:
            self._register(path)
        if not self._entries:
            raise protocol.ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "tree_required",
                "at least one runtime tree is required",
                {},
            )

    def _register(self, raw_path: Path) -> RuntimeEntry:
        path = validate_runtime_path(raw_path)
        with self._lock:
            existing_id = self._path_ids.get(path)
            if existing_id is not None:
                return self._entries[existing_id]
        validation = query.execute_query(
            "validate",
            path,
            {},
            self._environment,
        )
        payload = validation.payload
        if (
            validation.exit_code != 0
            or not payload.get("ok")
            or payload.get("artifact_kind") != "runtime"
            or payload.get("valid") is not True
        ):
            raise protocol.ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_runtime_tree",
                "registered path is not a valid runtime tree",
                {},
            )
        tree_id = secrets.token_hex(16)
        entry = RuntimeEntry(tree_id=tree_id, path=path)
        with self._lock:
            existing_id = self._path_ids.get(path)
            if existing_id is not None:
                return self._entries[existing_id]
            self._entries[tree_id] = entry
            self._path_ids[path] = tree_id
        return entry

    def get(self, tree_id: str) -> RuntimeEntry:
        with self._lock:
            entry = self._entries.get(tree_id)
        if entry is None:
            raise protocol.ProtocolError(
                HTTPStatus.NOT_FOUND,
                "unknown_tree",
                "runtime tree is not registered",
                {},
            )
        current = validate_runtime_path(entry.path)
        if current != entry.path:
            raise protocol.ProtocolError(
                HTTPStatus.CONFLICT,
                "tree_identity_changed",
                "runtime tree path identity changed",
                {},
            )
        return entry

    def query(
        self,
        tree_id: str,
        command: str,
        parameters: dict[str, object],
    ) -> application.CommandResult:
        entry = self.get(tree_id)
        return query.execute_query(
            command,
            entry.path,
            parameters,
            self._environment,
        )

    def listing(self, entry: RuntimeEntry) -> dict[str, object]:
        try:
            entry = self.get(entry.tree_id)
        except protocol.ProtocolError as error:
            return {
                "tree_id": entry.tree_id,
                "status": "unavailable",
                "error_code": error.code,
            }
        result = query.execute_query(
            "snapshot",
            entry.path,
            {},
            self._environment,
        )
        if result.exit_code != 0 or not result.payload.get("ok"):
            error = result.payload.get("error", {})
            code = (
                str(error.get("code", "runtime_unavailable"))
                if isinstance(error, dict)
                else "runtime_unavailable"
            )
            return {
                "tree_id": entry.tree_id,
                "status": "unavailable",
                "error_code": code,
            }
        metadata = result.payload.get("metadata", {})
        integrity = result.payload.get("integrity", {})
        return {
            "tree_id": entry.tree_id,
            "name": (
                str(metadata.get("name", ""))
                if isinstance(metadata, dict)
                else ""
            ),
            "work_order_id": (
                str(metadata.get("work_order_id", ""))
                if isinstance(metadata, dict)
                else ""
            ),
            "status": (
                str(metadata.get("status", ""))
                if isinstance(metadata, dict)
                else ""
            ),
            "version": str(result.payload.get("version", "")),
            "updated_at": (
                str(metadata.get("updated_at", ""))
                if isinstance(metadata, dict)
                else ""
            ),
            "integrity_status": (
                str(integrity.get("status", ""))
                if isinstance(integrity, dict)
                else ""
            ),
            "error_code": "",
        }

    def list(self) -> list[dict[str, object]]:
        with self._lock:
            entries = [
                self._entries[key]
                for key in sorted(self._entries)
            ]
        return [self.listing(entry) for entry in entries]


class DaemonState:
    def __init__(self, registry: RuntimeRegistry, token: str) -> None:
        if not token:
            raise ValueError("daemon token must not be empty")
        self.registry = registry
        self.token = token
        self.request_slots = threading.BoundedSemaphore(
            MAX_CONCURRENT_REQUESTS
        )
        self.shutdown_requested = threading.Event()
        self.server: BoundedThreadingHTTPServer | None = None
        self.started_at = time.monotonic()
        self.last_activity = self.started_at
        self.lock = threading.RLock()

    @property
    def expected_host(self) -> str:
        if self.server is None:
            raise RuntimeError("daemon server is not bound")
        host, port = self.server.server_address[:2]
        return f"{host}:{port}"

    @property
    def expected_origin(self) -> str:
        return f"http://{self.expected_host}"

    def touch(self) -> None:
        with self.lock:
            self.last_activity = time.monotonic()

    def request_shutdown(self) -> None:
        if self.shutdown_requested.is_set():
            return
        self.shutdown_requested.set()
        server = self.server
        if server is not None:
            threading.Thread(
                target=server.shutdown,
                daemon=True,
            ).start()


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = REQUEST_QUEUE_SIZE


class DaemonRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "XCDaemon"
    sys_version = ""
    state: DaemonState

    def version_string(self) -> str:
        return self.server_version

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        del message, explain
        identifier = protocol.request_id()
        if (
            getattr(self, "command", None)
            and getattr(self, "headers", None) is not None
        ):
            try:
                self._validate_request(identifier)
            except protocol.ProtocolError as error:
                self._send_error_payload(identifier, error)
                return
        status = (
            HTTPStatus(code)
            if code in HTTPStatus._value2member_map_
            else HTTPStatus.BAD_REQUEST
        )
        self._send_json(
            status,
            protocol.error_payload(
                identifier,
                "malformed_http_request",
                "HTTP request could not be processed",
                {},
            ),
            enforce_limit=False,
        )

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(SOCKET_TIMEOUT_SECONDS)

    def do_GET(self) -> None:
        self._run(self._handle_get)

    def do_POST(self) -> None:
        self._run(self._handle_post)

    def do_HEAD(self) -> None:
        self._run(self._method_not_allowed)

    def do_OPTIONS(self) -> None:
        self._run(self._method_not_allowed)

    def do_PUT(self) -> None:
        self._run(self._method_not_allowed)

    def do_PATCH(self) -> None:
        self._run(self._method_not_allowed)

    def do_DELETE(self) -> None:
        self._run(self._method_not_allowed)

    def do_TRACE(self) -> None:
        self._run(self._method_not_allowed)

    def do_CONNECT(self) -> None:
        self._run(self._method_not_allowed)

    def _run(self, operation: Callable[[str, str], None]) -> None:
        identifier = protocol.request_id()
        if not self.state.request_slots.acquire(blocking=False):
            self._send_error_payload(
                identifier,
                protocol.ProtocolError(
                    HTTPStatus.TOO_MANY_REQUESTS,
                    "server_busy",
                    "daemon request capacity is exhausted",
                    {},
                ),
            )
            return
        try:
            path = self._validate_request(identifier)
            operation(identifier, path)
            self.state.touch()
        except protocol.ProtocolError as error:
            self._send_error_payload(identifier, error)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            return
        except Exception:
            self._send_error_payload(
                identifier,
                protocol.ProtocolError(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "internal_error",
                    "unclassified daemon failure",
                    {},
                ),
            )
        finally:
            self.state.request_slots.release()

    def _validate_request(self, identifier: str) -> str:
        del identifier
        if len(self.path.encode("utf-8")) > MAX_TARGET_BYTES:
            raise protocol.ProtocolError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "target_too_large",
                "request target exceeds the configured limit",
                {"maximum_bytes": MAX_TARGET_BYTES},
            )
        parsed = urlsplit(self.path)
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
        ):
            raise protocol.ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_request_target",
                "request target must be a local path without query",
                {},
            )
        headers = list(self.headers.raw_items())
        if len(headers) > MAX_HEADER_COUNT:
            raise protocol.ProtocolError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "headers_too_large",
                "request contains too many headers",
                {"maximum": MAX_HEADER_COUNT},
            )
        for _, value in headers:
            if len(value.encode("utf-8")) > MAX_HEADER_VALUE_BYTES:
                raise protocol.ProtocolError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "headers_too_large",
                    "request header exceeds the configured limit",
                    {"maximum_bytes": MAX_HEADER_VALUE_BYTES},
                )
        self._single_header(
            "Host",
            required=True,
            invalid_code="invalid_host",
        )
        if self.headers["Host"] != self.state.expected_host:
            raise protocol.ProtocolError(
                HTTPStatus.FORBIDDEN,
                "forbidden_host",
                "request Host does not match the bound daemon",
                {},
            )
        authorization = self._single_header(
            "Authorization",
            required=True,
            invalid_code="invalid_authorization",
        )
        prefix = "Bearer "
        supplied = (
            authorization[len(prefix):]
            if authorization.startswith(prefix)
            else ""
        )
        if not supplied or not hmac.compare_digest(
            supplied,
            self.state.token,
        ):
            raise protocol.ProtocolError(
                HTTPStatus.UNAUTHORIZED,
                "unauthorized",
                "valid bearer authorization is required",
                {},
            )
        origins = self.headers.get_all("Origin") or []
        if len(origins) > 1:
            raise protocol.ProtocolError(
                HTTPStatus.FORBIDDEN,
                "forbidden_origin",
                "request Origin is invalid",
                {},
            )
        if origins and origins[0] != self.state.expected_origin:
            raise protocol.ProtocolError(
                HTTPStatus.FORBIDDEN,
                "forbidden_origin",
                "request Origin does not match the bound daemon",
                {},
            )
        if self.headers.get_all("Transfer-Encoding"):
            raise protocol.ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "unsupported_transfer_encoding",
                "Transfer-Encoding is not supported",
                {},
            )
        return parsed.path

    def _single_header(
        self,
        name: str,
        *,
        required: bool,
        invalid_code: str,
    ) -> str:
        values = self.headers.get_all(name) or []
        if len(values) != 1:
            status = (
                HTTPStatus.UNAUTHORIZED
                if name == "Authorization"
                else HTTPStatus.BAD_REQUEST
            )
            raise protocol.ProtocolError(
                status,
                invalid_code,
                f"request must contain exactly one {name} header",
                {},
            )
        if required and not values[0]:
            raise protocol.ProtocolError(
                HTTPStatus.BAD_REQUEST,
                invalid_code,
                f"{name} header must not be empty",
                {},
            )
        return values[0]

    def _content_length(
        self,
        *,
        required: bool,
    ) -> int:
        values = self.headers.get_all("Content-Length") or []
        if not values:
            if required:
                raise protocol.ProtocolError(
                    HTTPStatus.BAD_REQUEST,
                    "content_length_required",
                    "Content-Length is required",
                    {},
                )
            return 0
        if len(values) != 1:
            raise protocol.ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_content_length",
                "request must contain one Content-Length header",
                {},
            )
        try:
            length = int(values[0])
        except ValueError as error:
            raise protocol.ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_content_length",
                "Content-Length must be a decimal integer",
                {},
            ) from error
        if length < 0:
            raise protocol.ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_content_length",
                "Content-Length must not be negative",
                {},
            )
        if length > protocol.MAX_BODY_BYTES:
            raise protocol.ProtocolError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "request_too_large",
                "request body exceeds the configured limit",
                {"maximum_bytes": protocol.MAX_BODY_BYTES},
            )
        return length

    def _handle_get(self, identifier: str, path: str) -> None:
        if self._content_length(required=False) != 0:
            raise protocol.ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "unexpected_body",
                "GET requests must not contain a body",
                {},
            )
        if path == "/v1/health":
            self._send_success(
                identifier,
                {"status": "ready"},
            )
            return
        if path == "/v1/runtimes":
            self._send_success(
                identifier,
                {"runtimes": self.state.registry.list()},
            )
            return
        raise protocol.ProtocolError(
            HTTPStatus.NOT_FOUND,
            "not_found",
            "unknown daemon route",
            {},
        )

    def _handle_post(self, identifier: str, path: str) -> None:
        if path != "/v1/query":
            raise protocol.ProtocolError(
                HTTPStatus.NOT_FOUND,
                "not_found",
                "unknown daemon route",
                {},
            )
        content_types = self.headers.get_all("Content-Type") or []
        if (
            len(content_types) != 1
            or content_types[0].split(";", 1)[0].strip().lower()
            != "application/json"
        ):
            raise protocol.ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "invalid_content_type",
                "query requests require application/json",
                {},
            )
        length = self._content_length(required=True)
        try:
            data = self.rfile.read(length)
        except OSError as error:
            raise protocol.ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "request_body_unavailable",
                "request body could not be read",
                {},
            ) from error
        if len(data) != length:
            raise protocol.ProtocolError(
                HTTPStatus.BAD_REQUEST,
                "request_body_incomplete",
                "request body ended before Content-Length",
                {},
            )
        payload = protocol.parse_json_object(data)
        tree_id, command, parameters = protocol.parse_query_request(
            payload
        )
        result = self.state.registry.query(
            tree_id,
            command,
            parameters,
        )
        self._send_success(
            identifier,
            {
                "tree_id": tree_id,
                "command": command,
                "exit_code": result.exit_code,
                "payload": result.payload,
            },
        )

    def _method_not_allowed(
        self,
        identifier: str,
        path: str,
    ) -> None:
        del identifier, path
        raise protocol.ProtocolError(
            HTTPStatus.METHOD_NOT_ALLOWED,
            "method_not_allowed",
            "HTTP method is not supported",
            {},
        )

    def _send_success(
        self,
        identifier: str,
        result: object,
    ) -> None:
        self._send_json(
            HTTPStatus.OK,
            protocol.success_payload(identifier, result),
            limit_request_id=identifier,
        )

    def _send_error_payload(
        self,
        identifier: str,
        error: protocol.ProtocolError,
    ) -> None:
        self._send_json(
            error.status,
            protocol.error_payload(
                identifier,
                error.code,
                error.message,
                error.details,
            ),
            enforce_limit=False,
        )

    def _send_json(
        self,
        status: HTTPStatus,
        payload: object,
        *,
        enforce_limit: bool = True,
        limit_request_id: str | None = None,
    ) -> None:
        body = protocol.json_bytes(payload)
        if (
            enforce_limit
            and len(body) > protocol.MAX_JSON_RESPONSE_BYTES
        ):
            self._send_error_payload(
                limit_request_id or protocol.request_id(),
                protocol.ProtocolError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "response_too_large",
                    "daemon response exceeds the configured limit",
                    {
                        "maximum_bytes": (
                            protocol.MAX_JSON_RESPONSE_BYTES
                        )
                    },
                ),
            )
            return
        self.send_response(status.value)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True


def create_server(
    paths: Iterable[Path],
    token: str,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> tuple[DaemonState, BoundedThreadingHTTPServer, str]:
    if host != DEFAULT_HOST:
        raise ValueError("daemon host must be 127.0.0.1")
    if port < 0 or port > 65535:
        raise ValueError("daemon port must be between 0 and 65535")
    registry = RuntimeRegistry(paths)
    state = DaemonState(registry, token)
    handler = type(
        "BoundDaemonRequestHandler",
        (DaemonRequestHandler,),
        {"state": state},
    )
    try:
        server = BoundedThreadingHTTPServer((host, port), handler)
    except OSError:
        if port == 0:
            raise
        server = BoundedThreadingHTTPServer((host, 0), handler)
    state.server = server
    url = f"http://{host}:{server.server_address[1]}"
    return state, server, url


def serve_foreground(
    paths: Iterable[Path],
    token: str,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    ready: Callable[[dict[str, object]], None] | None = None,
) -> int:
    state, server, url = create_server(
        paths,
        token,
        host=host,
        port=port,
    )
    if ready is not None:
        ready(
            {
                "ok": True,
                "url": url,
                "runtimes": state.registry.list(),
            }
        )
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        state.shutdown_requested.set()
    finally:
        state.shutdown_requested.set()
        server.server_close()
    return 0


__all__ = [
    "BoundedThreadingHTTPServer",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DaemonRequestHandler",
    "DaemonState",
    "MAX_CONCURRENT_REQUESTS",
    "MAX_HEADER_COUNT",
    "MAX_HEADER_VALUE_BYTES",
    "MAX_TARGET_BYTES",
    "REQUEST_QUEUE_SIZE",
    "RuntimeEntry",
    "RuntimeRegistry",
    "SOCKET_TIMEOUT_SECONDS",
    "create_server",
    "generate_token",
    "serve_foreground",
    "validate_runtime_path",
]
