"""Stable, non-secret error vocabulary for delegation operations."""

from __future__ import annotations

from typing import Any


class DelegationError(RuntimeError):
    """A fail-closed delegation error safe for public JSON envelopes."""

    def __init__(
        self,
        code: str,
        phase: str,
        message: str,
        *,
        retryable: bool = False,
        remediation_category: str = "input",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.phase = phase
        self.retryable = retryable
        self.remediation_category = remediation_category
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "phase": self.phase,
            "message": str(self),
            "retryable": self.retryable,
            "remediation_category": self.remediation_category,
            "details": self.details,
        }


def fail(
    code: str,
    phase: str,
    message: str,
    *,
    retryable: bool = False,
    remediation_category: str = "input",
    **details: Any,
) -> None:
    raise DelegationError(
        code,
        phase,
        message,
        retryable=retryable,
        remediation_category=remediation_category,
        details=details,
    )


__all__ = ["DelegationError", "fail"]
