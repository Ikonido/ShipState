import re
from pathlib import Path

from packaging.version import InvalidVersion, Version

from shipstate.checks.pins import extract_pins
from shipstate.models import Finding, InputError

def _same_version(actual: str, expected: str) -> bool:
    try:
        return Version(actual) == Version(expected)
    except InvalidVersion:
        return False


_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_INLINE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")
_INSTALL = re.compile(
    r"^(?:(?:[-*+] |\d+[.)] )?(?:\$ )?|Install (?:with |using )?)"
    r"(?:pip(?:3|\d+\.\d+)?|python(?:3|\d+\.\d+)?\s+-m\s+pip|uv\s+pip)\s+install\s+",
    re.IGNORECASE,
)


def _pin_contexts(text: str) -> str:
    """Extract code examples and explicit install lines, excluding ordinary prose."""
    contexts = []
    fence_char = None
    fence_size = 0
    for line in text.splitlines():
        # Remove quote markers before recognizing fences and install examples.
        line = re.sub(r"^ {0,3}(?:>[ \t]*)+", "", line)
        fence = _FENCE.match(line)
        if fence_char:
            if fence and fence.group(1)[0] == fence_char and len(fence.group(1)) >= fence_size and not fence.group(2).strip():
                fence_char = None
            else:
                contexts.append(line)
            continue
        if fence:
            fence_char = fence.group(1)[0]
            fence_size = len(fence.group(1))
            continue
        contexts.extend(match.group(2) for match in _INLINE.finditer(line))
        if _INSTALL.match(line.strip()):
            contexts.append(line)
    return "\n".join(contexts)


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

    pins = extract_pins(_pin_contexts(text), project_name)
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
