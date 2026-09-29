"""Backend-independent result types for ShipCheck checks."""

from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "fail", "warn", "pass"]


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: Severity
    message: str
    source: str
    actual: str | None = None
    expected: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "severity": self.severity,
            "source": self.source,
            "message": self.message,
            "actual": self.actual,
            "expected": self.expected,
        }


@dataclass(frozen=True, slots=True)
class Project:
    name: str
    version: str
    root: str
    has_build_system: bool


@dataclass(frozen=True, slots=True)
class CheckResult:
    project: Project
    findings: tuple[Finding, ...]

    @property
    def status(self) -> Literal["pass", "fail"]:
        return "fail" if any(item.severity == "fail" for item in self.findings) else "pass"

    def to_dict(self, shipcheck_version: str) -> dict[str, object]:
        return {
            "shipcheck_version": shipcheck_version,
            "status": self.status,
            "project": {"name": self.project.name, "version": self.project.version},
            "findings": [item.to_dict() for item in self.findings],
        }


class InputError(Exception):
    """A user-correctable input, project configuration, or tool error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self, shipcheck_version: str) -> dict[str, object]:
        return {
            "shipcheck_version": shipcheck_version,
            "status": "error",
            "error": {"code": self.code, "message": self.message},
        }
