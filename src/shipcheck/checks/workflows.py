import re
from pathlib import Path

from packaging.version import InvalidVersion, Version

from shipcheck.checks.pins import extract_pins
from shipcheck.models import Finding, InputError

_PIP_INSTALL = re.compile(r"\bpip[ \t]+install\b", re.IGNORECASE)


def _same_version(actual: str, expected: str) -> bool:
    try:
        return Version(actual) == Version(expected)
    except InvalidVersion:
        return False


def check_workflows(root: Path, project_name: str, version: str) -> list[Finding]:
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        files: list[Path] = []
    else:
        files = sorted(
            (path for path in workflow_dir.iterdir() if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}),
            key=lambda item: item.name.casefold(),
        )

    pins: list[tuple[str, str]] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise InputError(
                "workflow_unreadable",
                f"{path.relative_to(root).as_posix()} could not be read as UTF-8.",
            ) from exc
        for line in text.splitlines():
            if line.lstrip().startswith("#"):
                continue
            if _PIP_INSTALL.search(line):
                pins.extend((path.relative_to(root).as_posix(), pin) for pin in extract_pins(line, project_name))

    if not pins:
        return [
            Finding(
                code="workflow_pin_not_found",
                severity="pass",
                source=".github/workflows",
                message=f"No pinned workflow install of {project_name} was found.",
            )
        ]

    findings: list[Finding] = []
    matching = [(source, pin) for source, pin in pins if _same_version(pin, version)]
    drifting = sorted({(source, pin) for source, pin in pins if not _same_version(pin, version)})
    if matching:
        source, actual = sorted(matching)[0]
        findings.append(
            Finding(
                code="workflow_pin_matches",
                severity="pass",
                source=source,
                message=f"Workflow install pins {project_name} to version {version}.",
                actual=actual,
                expected=version,
            )
        )
    for source, actual in drifting:
        findings.append(
            Finding(
                code="workflow_version_drift",
                severity="fail",
                source=source,
                message=f"Workflow install pins {project_name} to {actual}; expected {version}.",
                actual=actual,
                expected=version,
            )
        )
    return findings
