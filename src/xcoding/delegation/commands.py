"""Machine-readable ``xcoding delegate`` command surface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .application import (
    compile_diagnostic,
    load_input_document,
    prepare,
    write_canonical_output,
)
from .errors import DelegationError
from .json_codec import canonical_digest
from .migration import scan_legacy
from .resolver import resolve_profile


EXIT_SUCCESS = 0
EXIT_INPUT = 2
EXIT_READINESS = 4
EXIT_INTERNAL = 5


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise DelegationError("invalid_arguments", "cli", message)


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(add_help=False)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate-profile", add_help=False)
    validate.add_argument("--skill-root", required=True)
    validate.add_argument("--profile-id", required=True)
    validate.add_argument("--json", action="store_true", dest="json_output")

    resolve = commands.add_parser("resolve-profile", add_help=False)
    resolve.add_argument("--skill-root", required=True)
    resolve.add_argument("--profile-id", required=True)
    resolve.add_argument("--dynamic-overlay")
    resolve.add_argument("--json", action="store_true", dest="json_output")

    compile_command = commands.add_parser("compile-envelope", add_help=False)
    compile_command.add_argument("--resolved-profile-json", required=True)
    compile_command.add_argument("--node-packet-json", required=True)
    compile_command.add_argument("--node-profile-ref-json", required=True)
    compile_command.add_argument("--project-policy-json", required=True)
    compile_command.add_argument("--adapter-capabilities-json", required=True)
    compile_command.add_argument("--caller-constraints-json", required=True)
    compile_command.add_argument("--out", required=True)
    compile_command.add_argument("--json", action="store_true", dest="json_output")

    prepare_command = commands.add_parser("prepare", add_help=False)
    prepare_command.add_argument("--skill-root", required=True)
    prepare_command.add_argument("--profile-id", required=True)
    prepare_command.add_argument("--node-packet-json", required=True)
    prepare_command.add_argument("--node-profile-ref-json", required=True)
    prepare_command.add_argument("--project-policy-json", required=True)
    prepare_command.add_argument("--adapter-id", required=True)
    prepare_command.add_argument("--caller-constraints-json", required=True)
    prepare_command.add_argument("--dynamic-overlay")
    prepare_command.add_argument("--out", required=True)
    prepare_command.add_argument("--json", action="store_true", dest="json_output")

    scan = commands.add_parser("scan-legacy", add_help=False)
    scan.add_argument("--source-root", required=True)
    scan.add_argument("--json", action="store_true", dest="json_output")
    return parser


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def _success(command: str, result: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": 1, "ok": True, "command": f"delegate {command}", "result": result}


def _execute(arguments: argparse.Namespace) -> dict[str, Any]:
    if not arguments.json_output:
        raise DelegationError("json-required", "cli", "delegate commands require an explicit --json option")
    if arguments.command == "validate-profile":
        resolved = resolve_profile(Path(arguments.skill_root).absolute(), arguments.profile_id)
        return {
            "valid": True,
            "owner_skill": resolved["profile"]["owner_skill"],
            "profile_id": resolved["profile"]["profile_id"],
            "profile_sha256": resolved["resolved_profile_sha256"],
            "resource_count": len(resolved["resources"]),
            "dispatch_authoritative": False,
        }
    if arguments.command == "resolve-profile":
        return {
            "resolved_profile": resolve_profile(
                Path(arguments.skill_root).absolute(),
                arguments.profile_id,
                dynamic_overlay=(
                    Path(arguments.dynamic_overlay).absolute()
                    if arguments.dynamic_overlay
                    else None
                ),
            ),
            "dispatch_authoritative": False,
        }
    if arguments.command == "compile-envelope":
        envelope = compile_diagnostic(
            resolved_profile=load_input_document(arguments.resolved_profile_json),
            node_packet=load_input_document(arguments.node_packet_json),
            node_profile_ref=load_input_document(arguments.node_profile_ref_json),
            project_policy=load_input_document(arguments.project_policy_json),
            adapter_statement=load_input_document(arguments.adapter_capabilities_json),
            caller_constraints=load_input_document(arguments.caller_constraints_json),
        )
        output = write_canonical_output(arguments.out, envelope)
        return {
            "dispatch_authoritative": False,
            "envelope_sha256": canonical_digest(envelope),
            "out": str(output),
        }
    if arguments.command == "prepare":
        prepared = prepare(
            skill_root=Path(arguments.skill_root).absolute(),
            profile_id=arguments.profile_id,
            node_packet=load_input_document(arguments.node_packet_json),
            node_profile_ref=load_input_document(arguments.node_profile_ref_json),
            project_policy=load_input_document(arguments.project_policy_json),
            adapter_id=arguments.adapter_id,
            caller_constraints=load_input_document(arguments.caller_constraints_json),
            dynamic_overlay=(
                Path(arguments.dynamic_overlay).absolute()
                if arguments.dynamic_overlay
                else None
            ),
        )
        output = write_canonical_output(arguments.out, prepared["envelope"])
        return {
            "dispatch_authoritative": True,
            "envelope_sha256": prepared["envelope_sha256"],
            "prepare_receipt": prepared["prepare_receipt"],
            "prepare_receipt_sha256": prepared["prepare_receipt_sha256"],
            "overlay_cleanup": prepared["overlay_cleanup"],
            "out": str(output),
        }
    if arguments.command == "scan-legacy":
        return scan_legacy(Path(arguments.source_root).absolute())
    raise DelegationError("invalid_arguments", "cli", "unknown delegate command")


def _exit_for(error: DelegationError) -> int:
    if error.remediation_category in {"policy", "readiness", "runtime-state"}:
        return EXIT_READINESS
    return EXIT_INPUT


def main(argv: Sequence[str] | None = None) -> int:
    command = ""
    try:
        arguments = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
        command = str(arguments.command)
        result = _execute(arguments)
    except DelegationError as error:
        _emit(
            {
                "schema_version": 1,
                "ok": False,
                "command": f"delegate {command}" if command else "delegate",
                "error": error.as_dict(),
            }
        )
        return _exit_for(error)
    except Exception as error:
        _emit(
            {
                "schema_version": 1,
                "ok": False,
                "command": f"delegate {command}" if command else "delegate",
                "error": {
                    "code": "internal_error",
                    "phase": "internal",
                    "message": "unclassified delegation command failure",
                    "retryable": False,
                    "remediation_category": "internal",
                    "details": {"exception": type(error).__name__},
                },
            }
        )
        return EXIT_INTERNAL
    _emit(_success(command, result))
    return EXIT_SUCCESS


__all__ = ["EXIT_INPUT", "EXIT_INTERNAL", "EXIT_READINESS", "EXIT_SUCCESS", "main"]
