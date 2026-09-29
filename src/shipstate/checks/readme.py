import re
from pathlib import Path

from packaging.version import InvalidVersion, Version

from shipstate.checks.pins import extract_pins
from shipstate.models import Finding, InputError

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")
_CHANGELOG_SECTION = re.compile(r"^(?:changelog|release notes?)(?:\b.*)?$", re.IGNORECASE)
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def _without_changelog_sections(text: str) -> str:
    kept: list[str] = []
    changelog_level: int | None = None
    fence_char: str | None = None
    fence_size = 0
    for line in text.splitlines():
        fence = _FENCE.match(line)
        if fence_char is not None:
            if fence and fence.group(1)[0] == fence_char and len(fence.group(1)) >= fence_size and not line[fence.end() :].strip():
                fence_char = None
                fence_size = 0
            if changelog_level is None:
                kept.append(line)
            continue
        if fence:
            fence_char = fence.group(1)[0]
            fence_size = len(fence.group(1))
            if changelog_level is None:
                kept.append(line)
            continue
        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if changelog_level is not None and level <= changelog_level:
                changelog_level = None
            if changelog_level is None and _CHANGELOG_SECTION.fullmatch(heading.group(2).strip()):
                changelog_level = level
        if changelog_level is None:
            kept.append(line)
    return "\n".join(kept)


def _same_version(actual: str, expected: str) -> bool:
    try:
        return Version(actual) == Version(expected)
    except InvalidVersion:
        return False


def check_readme(root: Path, project_name: str, version: str) -> list[Finding]:
    path = root / "README.md"
    if not path.is_file():
        return [
            Finding(
                code="readme_missing",
                severity="warn",
                source="README.md",
                message="README.md was not found.",
            )
        ]
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InputError("readme_unreadable", "README.md could not be read as UTF-8.") from exc

    pins = extract_pins(_without_changelog_sections(text), project_name)
    if not pins:
        return [
            Finding(
                code="readme_pin_not_found",
                severity="pass",
                source="README.md",
                message=f"No pinned install of {project_name} was found.",
            )
        ]

    findings: list[Finding] = []
    matching = sorted({pin for pin in pins if _same_version(pin, version)})
    drifting = sorted({pin for pin in pins if not _same_version(pin, version)})
    if matching:
        findings.append(
            Finding(
                code="readme_pin_matches",
                severity="pass",
                source="README.md",
                message=f"README.md pins {project_name} to version {version}.",
                actual=matching[0],
                expected=version,
            )
        )
    for actual in drifting:
        findings.append(
            Finding(
                code="readme_version_drift",
                severity="fail",
                source="README.md",
                message=f"README.md pins {project_name} to {actual}; expected {version}.",
                actual=actual,
                expected=version,
            )
        )
    return findings
