"""In-process single-use terminal authority for assigned runtime nodes."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import stat
import threading
import time
import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import application, assignment, core
from ..delegation.paths import stable_read_bytes
from ..delegation.errors import DelegationError


DEFAULT_TTL_SECONDS = 300
MAX_TTL_SECONDS = 600
MAX_REQUEST_BYTES = 64 * 1024
MAX_CHECK_RESULT_BYTES = 16 * 1024
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 4096
MAX_JSON_STRING_BYTES = 16 * 1024
MAX_JSON_CONTAINER_ITEMS = 256
TERMINAL_OPERATIONS = frozenset({"block", "complete", "fail"})
TERMINAL_STATUS = {
    "block": "blocked",
    "complete": "succeeded",
    "fail": "failed",
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_WINDOWS_DEVICE = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z", re.IGNORECASE)


class TerminalAuthorityError(core.RuntimeErrorBase):
    """A terminal authority request failed closed."""

    code = "terminal_authority_error"


class TerminalCapability:
    """Opaque in-memory bearer whose representation never includes its secret."""

    __slots__ = ("capability_id", "__secret")

    def __init__(self, capability_id: str, secret: bytes) -> None:
        self.capability_id = capability_id
        self.__secret = secret

    def __repr__(self) -> str:
        return f"TerminalCapability(capability_id={self.capability_id!r}, secret=<redacted>)"

    def __reduce__(self) -> Any:
        raise TypeError("terminal capabilities must not be serialized")

    def _authenticate(self, digest: bytes) -> bool:
        return hmac.compare_digest(hashlib.sha256(self.__secret).digest(), digest)


@dataclass
class _Authority:
    capability_id: str
    secret_sha256: bytes
    tree_path: Path
    tree_identity: str
    repository_root: Path
    work_order_id: str
    node_id: str
    attempt: int
    profile_sha256: str
    allowed_operations: frozenset[str]
    artifact_bindings: dict[str, Path]
    artifact_identities: dict[str, tuple[int, int] | None]
    envelope_sha256: str
    prepare_receipt_id: str
    prepare_receipt_sha256: str
    expires_at: float
    state: str = "active"
    lock: threading.Lock = field(default_factory=threading.Lock)


def _reject(message: str, reason: str, **details: Any) -> None:
    raise TerminalAuthorityError(message, {"reason": reason, **details})


def _digest(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        _reject(f"{field_name} must be a lowercase SHA-256 digest", "invalid_digest")
    return value


def _bounded_text(
    value: object,
    *,
    field_name: str,
    maximum: int = 8192,
    nonempty: bool = True,
) -> str:
    if (
        not isinstance(value, str)
        or (nonempty and not value.strip())
        or len(value.encode("utf-8")) > maximum
    ):
        _reject(f"{field_name} must be a bounded string", "invalid_request_field", field=field_name)
    return value


def _logical_path(value: object) -> str:
    if not isinstance(value, str) or not value or value != unicodedata.normalize("NFC", value):
        _reject("artifact path must be a canonical relative path", "invalid_artifact_path")
    if "\\" in value or value.startswith("/") or re.match(r"[A-Za-z]:", value):
        _reject("artifact path must use relative POSIX syntax", "invalid_artifact_path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        _reject("artifact path contains an unsafe segment", "invalid_artifact_path")
    if any(any(ord(character) < 32 for character in part) for part in parts):
        _reject("artifact path contains a control character", "invalid_artifact_path")
    if any(
        ":" in part
        or part.endswith((".", " "))
        or _WINDOWS_DEVICE.fullmatch(part) is not None
        for part in parts
    ):
        _reject("artifact path contains a non-portable Windows segment", "invalid_artifact_path")
    if len(value.encode("utf-8")) > 1024:
        _reject("artifact path is too large", "invalid_artifact_path")
    return value


def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    os_is_junction = getattr(os.path, "isjunction", None)
    if os_is_junction is not None and os_is_junction(path):
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _require_contained_path(repository_root: Path, target: Path) -> Path:
    if not target.is_absolute():
        _reject("artifact bindings must use absolute paths", "artifact_path_not_absolute")
    resolved_root = repository_root.resolve(strict=True)
    lexical_target = Path(os.path.abspath(target))
    try:
        lexical_relative = lexical_target.relative_to(resolved_root)
    except ValueError:
        _reject("artifact binding is outside the workshop repository", "artifact_outside_repository")
    current = resolved_root
    if _is_reparse(current):
        _reject("workshop repository must not be a reparse point", "artifact_reparse_forbidden")
    for part in lexical_relative.parts:
        current /= part
        if current.exists() and _is_reparse(current):
            _reject("artifact path traverses a reparse point", "artifact_reparse_forbidden")
    resolved_target = target.resolve(strict=False)
    try:
        relative = resolved_target.relative_to(resolved_root)
    except ValueError:
        _reject("artifact binding is outside the workshop repository", "artifact_outside_repository")
    current = resolved_root
    for part in relative.parts:
        current /= part
        if current.exists() and _is_reparse(current):
            _reject("artifact path traverses a reparse point", "artifact_reparse_forbidden")
    return resolved_target


def _path_key(path: Path) -> str:
    return os.path.normcase(unicodedata.normalize("NFC", os.path.normpath(str(path))))


def _exact_artifact_binding(
    repository_root: Path,
    workbench_root: Path,
    logical: str,
    raw_path: object,
) -> Path:
    try:
        raw_text = os.fspath(raw_path)
    except TypeError:
        _reject("artifact binding path is invalid", "invalid_artifact_bindings")
    if not isinstance(raw_text, str) or raw_text != unicodedata.normalize("NFC", raw_text):
        _reject("artifact binding path must be an NFC string", "invalid_artifact_bindings")
    supplied = Path(raw_text)
    if not supplied.is_absolute():
        _reject("artifact bindings must use absolute paths", "artifact_path_not_absolute")
    expected = workbench_root.joinpath(*logical.split("/"))
    lexical_supplied = Path(os.path.abspath(supplied))
    lexical_expected = Path(os.path.abspath(expected))
    if _path_key(lexical_supplied) != _path_key(lexical_expected):
        _reject(
            "artifact binding does not match its logical workbench path",
            "artifact_binding_mismatch",
            artifact=logical,
        )
    physical = _require_contained_path(repository_root, supplied)
    resolved_expected = _require_contained_path(repository_root, expected)
    if _path_key(physical) != _path_key(resolved_expected):
        _reject(
            "artifact binding resolves away from its logical workbench path",
            "artifact_binding_mismatch",
            artifact=logical,
        )
    return physical


def _artifact_identity_if_present(target: Path) -> tuple[int, int] | None:
    if not target.exists():
        return None
    try:
        metadata = target.lstat()
    except OSError as exc:
        _reject("artifact binding is unavailable", "artifact_unavailable", error=type(exc).__name__)
    if not stat.S_ISREG(metadata.st_mode) or _is_reparse(target):
        _reject("artifact binding must target a regular non-reparse file", "artifact_not_regular")
    return (metadata.st_dev, metadata.st_ino)


def _validate_bounded_json(
    value: object,
    *,
    depth: int = 1,
    counter: list[int] | None = None,
    active: set[int] | None = None,
) -> None:
    if counter is None:
        counter = [0]
    if active is None:
        active = set()
    counter[0] += 1
    if counter[0] > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
        _reject("check_results exceed structural limits", "invalid_request_field", field="check_results")
    if isinstance(value, str):
        if value != unicodedata.normalize("NFC", value) or len(value.encode("utf-8")) > MAX_JSON_STRING_BYTES:
            _reject("check_results contain an invalid string", "invalid_request_field", field="check_results")
        return
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if value.bit_length() > 55_000:
            _reject("check_results contain an oversized integer", "invalid_request_field", field="check_results")
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _reject("check_results contain a non-finite number", "invalid_request_field", field="check_results")
        return
    if isinstance(value, (list, dict)):
        if len(value) > MAX_JSON_CONTAINER_ITEMS:
            _reject("check_results contain an oversized container", "invalid_request_field", field="check_results")
        identity = id(value)
        if identity in active:
            _reject("check_results contain a cycle", "invalid_request_field", field="check_results")
        active.add(identity)
        try:
            if isinstance(value, list):
                for item in value:
                    _validate_bounded_json(
                        item,
                        depth=depth + 1,
                        counter=counter,
                        active=active,
                    )
            else:
                for key, item in value.items():
                    if not isinstance(key, str):
                        _reject("check_results object keys must be strings", "invalid_request_field", field="check_results")
                    _validate_bounded_json(
                        key,
                        depth=depth + 1,
                        counter=counter,
                        active=active,
                    )
                    _validate_bounded_json(
                        item,
                        depth=depth + 1,
                        counter=counter,
                        active=active,
                    )
        finally:
            active.remove(identity)
        return
    _reject("check_results contain a non-JSON value", "invalid_request_field", field="check_results")


def _stable_artifact_digest(
    repository_root: Path,
    target: Path,
    expected_identity: tuple[int, int] | None,
) -> str:
    if not target.is_absolute():
        _reject("artifact bindings must use absolute paths", "artifact_path_not_absolute")
    root = repository_root.resolve(strict=True)
    lexical = Path(os.path.abspath(target))
    try:
        relative = lexical.relative_to(root).as_posix()
    except ValueError:
        _reject("artifact binding is outside the workshop repository", "artifact_outside_repository")
    try:
        data = stable_read_bytes(
            root,
            relative,
            max_bytes=None,
            expected_identity=expected_identity,
        )
    except DelegationError as exc:
        reason = {
            "path_reparse_forbidden": "artifact_reparse_forbidden",
            "path_not_regular": "artifact_not_regular",
            "path_not_directory": "artifact_reparse_forbidden",
            "path_containment_failed": "artifact_outside_repository",
            "resource_changed": "artifact_replaced" if expected_identity is not None else "artifact_changed",
            "path_unavailable": "artifact_unavailable",
        }.get(exc.code, "artifact_unavailable")
        _reject("artifact could not be read stably", reason, error=exc.code)
    except TerminalAuthorityError:
        raise
    except OSError as exc:
        _reject("artifact could not be read stably", "artifact_unavailable", error=type(exc).__name__)
    return hashlib.sha256(data).hexdigest()


def _request(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _reject("terminal request must be an object", "request_not_object")
    request = dict(value)
    operation = request.get("operation")
    common = {"schema_version", "operation", "artifacts"}
    expected = (
        common | {"summary", "validation", "check_results"}
        if operation == "complete"
        else common | {"reason"}
    )
    if request.get("schema_version") != 1 or operation not in TERMINAL_OPERATIONS or set(request) != expected:
        _reject("terminal request has an invalid shape", "invalid_request_shape")
    raw_artifacts = request.get("artifacts")
    if not isinstance(raw_artifacts, list):
        _reject("artifacts must be an array", "invalid_request_field", field="artifacts")
    artifacts = [_logical_path(item) for item in raw_artifacts]
    if len(artifacts) > 32 or len(artifacts) != len(set(artifacts)):
        _reject("artifacts must be bounded and unique", "invalid_request_field", field="artifacts")
    normalized: dict[str, Any] = {
        "schema_version": 1,
        "operation": operation,
        "artifacts": artifacts,
    }
    if operation == "complete":
        normalized["summary"] = _bounded_text(request["summary"], field_name="summary")
        normalized["validation"] = _bounded_text(request["validation"], field_name="validation")
        check_results = request["check_results"]
        if not isinstance(check_results, list) or len(check_results) > 32 or any(
            not isinstance(item, dict) for item in check_results
        ):
            _reject("check_results must be a bounded object array", "invalid_request_field", field="check_results")
        aggregate_counter = [1]
        aggregate_active: set[int] = set()
        for item in check_results:
            _validate_bounded_json(
                item,
                counter=aggregate_counter,
                active=aggregate_active,
            )
            try:
                item_bytes = assignment.canonical_json_bytes(item)
            except (assignment.AssignmentError, RecursionError, TypeError, ValueError, OverflowError, UnicodeError) as exc:
                _reject(
                    "check_results are not canonical JSON data",
                    "invalid_request_field",
                    field="check_results",
                    error=type(exc).__name__,
                )
            if len(item_bytes) > MAX_CHECK_RESULT_BYTES:
                _reject("check_results item exceeds its byte limit", "invalid_request_field", field="check_results")
        normalized["check_results"] = check_results
    else:
        normalized["reason"] = _bounded_text(request["reason"], field_name="reason")
    try:
        encoded = assignment.canonical_json_bytes(normalized)
        if len(encoded) > MAX_REQUEST_BYTES:
            _reject("terminal request exceeds its byte limit", "invalid_request_field", field="request")
    except (assignment.AssignmentError, RecursionError, TypeError, ValueError, OverflowError, UnicodeError) as exc:
        _reject(
            "terminal request is not canonical JSON data",
            "invalid_request_field",
            error=type(exc).__name__,
        )
    return normalized


class TerminalBroker:
    """Process-local registry for one-shot assigned-node terminal authority."""

    def __init__(
        self,
        *,
        config_path: Path | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config_path = config_path
        self._monotonic = monotonic
        self._registry: dict[str, _Authority] = {}
        self._active_bindings: dict[tuple[str, str, int], str] = {}
        self._lock = threading.Lock()

    def _environment(self) -> application.RuntimeEnvironment:
        return application.RuntimeEnvironment(
            default_template=Path("."),
            config_path=self._config_path,
        )

    def _runtime_args(self, authority: _Authority) -> argparse.Namespace:
        return argparse.Namespace(
            tree=str(authority.tree_path),
            config="",
            json=False,
            expected_revision=None,
            _runtime_environment=self._environment(),
        )

    def _release_binding(self, authority: _Authority) -> None:
        binding = (authority.tree_identity, authority.node_id, authority.attempt)
        with self._lock:
            if self._active_bindings.get(binding) == authority.capability_id:
                del self._active_bindings[binding]

    def _expire_existing_binding(self, binding: tuple[str, str, int]) -> None:
        with self._lock:
            capability_id = self._active_bindings.get(binding)
            authority = self._registry.get(capability_id or "")
        if authority is None:
            return
        if not authority.lock.acquire(blocking=False):
            _reject("a terminal authority is already consuming", "authority_already_active")
        try:
            if authority.state == "active" and self._monotonic() >= authority.expires_at:
                authority.state = "expired"
                self._release_binding(authority)
            elif authority.state in {"active", "consuming"}:
                _reject("an active terminal authority already exists", "authority_already_active")
        finally:
            authority.lock.release()

    def _authority_for(self, capability: TerminalCapability) -> _Authority:
        if not isinstance(capability, TerminalCapability):
            _reject("terminal capability is invalid", "unauthenticated")
        with self._lock:
            authority = self._registry.get(capability.capability_id)
        if authority is None or not capability._authenticate(authority.secret_sha256):
            _reject("terminal capability authentication failed", "unauthenticated")
        return authority

    def issue(
        self,
        *,
        tree_path: Path,
        node_id: str,
        attempt: int,
        allowed_operations: Sequence[str],
        artifact_bindings: Mapping[str, Path],
        envelope_sha256: str,
        prepare_receipt_id: str,
        prepare_receipt_sha256: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> TerminalCapability:
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= MAX_TTL_SECONDS:
            _reject(
                "terminal capability TTL is outside the allowed range",
                "invalid_ttl",
                maximum=MAX_TTL_SECONDS,
            )
        if type(attempt) is not int or attempt < 1:
            _reject("attempt must be a positive integer", "invalid_attempt")
        if isinstance(allowed_operations, (str, bytes)) or not isinstance(
            allowed_operations,
            Sequence,
        ):
            _reject("allowed operations must be a sequence", "invalid_operations")
        if not isinstance(artifact_bindings, Mapping):
            _reject("artifact bindings must be an object", "invalid_artifact_bindings")
        operations = list(allowed_operations)
        if not operations or operations != sorted(set(operations)) or any(
            item not in TERMINAL_OPERATIONS for item in operations
        ):
            _reject("allowed operations must be a sorted non-empty subset", "invalid_operations")
        _digest(envelope_sha256, field_name="envelope_sha256")
        _digest(prepare_receipt_sha256, field_name="prepare_receipt_sha256")
        receipt_id = _bounded_text(
            prepare_receipt_id,
            field_name="prepare_receipt_id",
            maximum=256,
        )

        resolved_tree = Path(tree_path).resolve(strict=True)
        config = core.load_config(resolved_tree, self._config_path)
        tree, integrity = core.read_tree_with_integrity(resolved_tree, config, "runtime")
        core.require_target_runtime_schema(tree.getroot())
        core.require_writable_integrity(integrity)
        core.require_valid_control_metadata(tree.getroot())
        errors = core.validate_runtime_root(tree.getroot(), check_integrity=False)
        if errors:
            raise core.TreeValidationError("runtime structural validation failed", {"errors": errors})
        root = tree.getroot()
        node = core.require_executable_leaf(root, node_id)
        if (
            core.node_type(node) != "task"
            or node.get("executor") != "subagent"
            or node.get("status") != "running"
        ):
            _reject("terminal authority requires a running subagent task", "node_not_dispatchable")
        if core.attempt_number(node) != attempt:
            _reject("terminal authority attempt is stale", "attempt_mismatch")
        runtime_assignment = assignment.build_assignment_packet(root, node_id, attempt)
        reference = runtime_assignment["node_profile_ref"]
        profile_sha256 = assignment.canonical_digest(reference)
        grants = {
            grant["id"]: set(grant["values"])
            for grant in runtime_assignment["node_packet"]["authorization"]["capabilities"]
        }
        node_terminal_operations = grants.get(
            "runtime.terminal.assigned-node",
            set(),
        )
        if not set(operations) <= node_terminal_operations:
            _reject(
                "terminal authority exceeds the node-owned authorization",
                "operation_not_node_authorized",
            )
        repository_root = core.git_root_for(resolved_tree)
        if repository_root is None:
            _reject("runtime is not inside a workshop Git repository", "repository_unavailable")
        if resolved_tree.name != "orchestration.xml" or resolved_tree.parent.name != "runtime":
            _reject("runtime tree does not use the managed workbench layout", "invalid_runtime_layout")
        workbench_root = resolved_tree.parent.parent.resolve(strict=True)
        _require_contained_path(repository_root, workbench_root)

        logical_seen: dict[str, str] = {}
        physical_seen: set[str] = set()
        normalized_bindings: dict[str, Path] = {}
        artifact_identities: dict[str, tuple[int, int] | None] = {}
        for raw_logical, raw_path in artifact_bindings.items():
            logical = _logical_path(raw_logical)
            if logical not in grants.get("workbench.write.artifact", set()):
                _reject(
                    "artifact binding exceeds the node-owned authorization",
                    "artifact_not_node_authorized",
                    artifact=logical,
                )
            folded = logical.casefold()
            if folded in logical_seen:
                _reject("artifact bindings contain a path collision", "artifact_path_collision")
            logical_seen[folded] = logical
            physical = _exact_artifact_binding(
                repository_root,
                workbench_root,
                logical,
                raw_path,
            )
            physical_key = os.path.normcase(str(physical))
            if physical_key in physical_seen:
                _reject("artifact bindings alias the same physical path", "artifact_path_collision")
            physical_seen.add(physical_key)
            normalized_bindings[logical] = physical
            artifact_identities[logical] = _artifact_identity_if_present(physical)
        if len(normalized_bindings) > 32:
            _reject("artifact bindings exceed the supported limit", "too_many_artifacts")

        tree_identity = os.path.normcase(str(resolved_tree))
        binding = (tree_identity, node_id, attempt)
        self._expire_existing_binding(binding)
        capability_id = uuid.uuid4().hex
        secret = secrets.token_bytes(32)
        authority = _Authority(
            capability_id=capability_id,
            secret_sha256=hashlib.sha256(secret).digest(),
            tree_path=resolved_tree,
            tree_identity=tree_identity,
            repository_root=repository_root,
            work_order_id=root.get("work_order_id", ""),
            node_id=node_id,
            attempt=attempt,
            profile_sha256=profile_sha256,
            allowed_operations=frozenset(operations),
            artifact_bindings=normalized_bindings,
            artifact_identities=artifact_identities,
            envelope_sha256=envelope_sha256,
            prepare_receipt_id=receipt_id,
            prepare_receipt_sha256=prepare_receipt_sha256,
            expires_at=self._monotonic() + ttl_seconds,
        )
        with self._lock:
            existing_id = self._active_bindings.get(binding)
            if existing_id is not None:
                existing = self._registry.get(existing_id)
                if existing is not None and existing.state in {"active", "consuming"}:
                    _reject("an active terminal authority already exists", "authority_already_active")
                self._active_bindings.pop(binding, None)
            self._registry[capability_id] = authority
            self._active_bindings[binding] = capability_id
        return TerminalCapability(capability_id, secret)

    def revoke(self, capability: TerminalCapability) -> None:
        authority = self._authority_for(capability)
        with authority.lock:
            if authority.state == "active" and self._monotonic() >= authority.expires_at:
                authority.state = "expired"
                self._release_binding(authority)
            if authority.state != "active":
                _reject("terminal authority is no longer active", "authority_not_active", state=authority.state)
            authority.state = "revoked"
            self._release_binding(authority)

    def state(self, capability: TerminalCapability) -> str:
        authority = self._authority_for(capability)
        with authority.lock:
            if authority.state == "active" and self._monotonic() >= authority.expires_at:
                authority.state = "expired"
                self._release_binding(authority)
            return authority.state

    def consume(
        self,
        capability: TerminalCapability,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        authority = self._authority_for(capability)
        with authority.lock:
            if authority.state != "active":
                _reject("terminal authority is no longer active", "authority_not_active", state=authority.state)
            if self._monotonic() >= authority.expires_at:
                authority.state = "expired"
                self._release_binding(authority)
                _reject("terminal authority has expired", "authority_expired")
            authority.state = "consuming"
            try:
                normalized = _request(request)
                operation = normalized["operation"]
                if operation not in authority.allowed_operations:
                    _reject("terminal operation is not authorized", "operation_not_authorized")
                unauthorized = sorted(
                    set(normalized["artifacts"]) - set(authority.artifact_bindings)
                )
                if unauthorized:
                    _reject(
                        "terminal request includes an unauthorized artifact",
                        "artifact_not_authorized",
                        artifacts=unauthorized,
                    )

                args = self._runtime_args(authority)
                with application.runtime_mutation(args, operation) as (path, tree, config):
                    root = tree.getroot()
                    if os.path.normcase(str(path.resolve())) != authority.tree_identity:
                        _reject("runtime tree identity changed", "tree_identity_mismatch")
                    if root.get("work_order_id", "") != authority.work_order_id:
                        _reject("work-order identity changed", "work_order_mismatch")
                    node = core.require_executable_leaf(root, authority.node_id)
                    if (
                        node.get("status") != "running"
                        or node.get("executor") != "subagent"
                        or core.node_type(node) != "task"
                    ):
                        _reject("assigned node is no longer dispatchable", "node_state_changed")
                    if core.attempt_number(node) != authority.attempt:
                        _reject("assigned node attempt changed", "attempt_mismatch")
                    if assignment.canonical_digest(core.worker_profile_ref_for_node(node)) != authority.profile_sha256:
                        _reject("worker profile metadata changed", "profile_changed")

                    artifact_records: list[dict[str, str]] = []
                    physical_artifacts: list[str] = []
                    for logical in normalized["artifacts"]:
                        physical = authority.artifact_bindings[logical]
                        digest = _stable_artifact_digest(
                            authority.repository_root,
                            physical,
                            authority.artifact_identities[logical],
                        )
                        artifact_records.append({"path": logical, "sha256": digest})
                        physical_artifacts.append(str(physical))

                    if operation == "complete":
                        check_results = [
                            json.dumps(
                                item,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                                allow_nan=False,
                            )
                            for item in normalized["check_results"]
                        ]
                        node = core.complete_node(
                            root,
                            authority.node_id,
                            normalized["summary"],
                            physical_artifacts,
                            normalized["validation"],
                            check_results=check_results,
                        )
                    elif operation == "fail":
                        node = core.fail_node(
                            root,
                            authority.node_id,
                            normalized["reason"],
                            physical_artifacts,
                        )
                    else:
                        node = core.block_node(
                            root,
                            authority.node_id,
                            normalized["reason"],
                            physical_artifacts,
                        )
                    core.deduplicate_result_artifacts(node)
                    record = {
                        "schema_version": 1,
                        "kind": core.TERMINAL_AUTHORITY_KIND,
                        "capability_id": authority.capability_id,
                        "node_id": authority.node_id,
                        "attempt": authority.attempt,
                        "operation": operation,
                        "consumed_at": core.utc_now(),
                        "envelope_sha256": authority.envelope_sha256,
                        "prepare_receipt_id": authority.prepare_receipt_id,
                        "prepare_receipt_sha256": authority.prepare_receipt_sha256,
                        "artifacts": artifact_records,
                        "terminal_status": TERMINAL_STATUS[operation],
                        "request_sha256": assignment.canonical_digest(normalized),
                    }
                    core.append_terminal_authority(node, record)
                    payload = application.write_terminal_runtime(
                        tree,
                        path,
                        config,
                        operation,
                        {
                            "node": core.snapshot_node(root, node),
                            "counts": core.status_counts(root),
                        },
                        commit_paths=[Path(item) for item in physical_artifacts],
                    )
                return {
                    "schema_version": 1,
                    "kind": "xc-node-terminal-result/v1",
                    "capability_id": authority.capability_id,
                    "node_id": authority.node_id,
                    "attempt": authority.attempt,
                    "operation": operation,
                    "terminal_status": TERMINAL_STATUS[operation],
                    "revision": payload["revision"],
                }
            finally:
                authority.state = "consumed"
                self._release_binding(authority)


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "MAX_TTL_SECONDS",
    "MAX_CHECK_RESULT_BYTES",
    "MAX_REQUEST_BYTES",
    "TerminalAuthorityError",
    "TerminalBroker",
    "TerminalCapability",
]
