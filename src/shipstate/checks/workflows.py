import re
from pathlib import Path

from packaging.version import InvalidVersion, Version

from shipstate.checks.pins import dynamic_pin_pattern, extract_pins
from shipstate.models import Finding, InputError

_PIP_INSTALL = re.compile(
    r"\b(?:python(?:[0-9.]*)[ \t]+-m[ \t]+)?pip(?:[0-9.]*)[ \t]+install\b",
    re.IGNORECASE,
)
_RUN_BLOCK = re.compile(
    r"^(?P<indent>[ \t]*)(?:-[ \t]+)?run[ \t]*:[ \t]*(?:&[A-Za-z0-9_-]+[ \t]+)?"
    r"(?P<style>[|>])[+-]?(?:[ \t]+&[A-Za-z0-9_-]+)?[ \t]*(?:#.*)?$"
)


def _without_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote != "'":
            escaped = True
            continue
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index]
    return line


def _command_chunks(text: str) -> list[str]:
    lines = text.splitlines()
    chunks: list[str] = []
    index = 0
    while index < len(lines):
        block = _RUN_BLOCK.fullmatch(lines[index])
        if block is None:
            chunks.append(lines[index])
            index += 1
            continue
        key_indent = len(block.group("indent"))
        body: list[str] = []
        index += 1
        while index < len(lines):
            line = lines[index]
            if line.strip() and len(line) - len(line.lstrip(" \t")) <= key_indent:
                break
            body.append(line.strip())
            index += 1
        separator = " " if block.group("style") == ">" else "\n"
        chunks.append(separator.join(body))
    return chunks


def _logical_commands(text: str) -> list[str]:
    commands: list[str] = []
    for chunk in _command_chunks(text):
        pending = ""
        for line in chunk.splitlines() or [chunk]:
            cleaned = _without_comment(line).strip()
            if not cleaned:
                continue
            pending = f"{pending} {cleaned}".strip()
            trailing_slashes = len(pending) - len(pending.rstrip("\\"))
            if trailing_slashes % 2:
                pending = pending[:-1].rstrip()
                continue
            commands.append(pending)
            pending = ""
        if pending:
            commands.append(pending)
    return commands


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
    dynamic_pins: list[tuple[str, str]] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise InputError(
                "workflow_unreadable",
                f"{path.relative_to(root).as_posix()} could not be read as UTF-8.",
            ) from exc
        for command in _logical_commands(text):
            if _PIP_INSTALL.search(command):
                source = path.relative_to(root).as_posix()
                pins.extend((source, pin) for pin in extract_pins(command, project_name))
                dynamic_pins.extend(
                    (source, match.group("version"))
                    for match in dynamic_pin_pattern(project_name).finditer(command)
                )

    if not pins and not dynamic_pins:
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
    for source, actual in sorted(set(dynamic_pins)):
        findings.append(
            Finding(
                code="workflow_dynamic_version",
                severity="fail",
                source=source,
                message=f"Workflow install uses an unresolvable {project_name} version {actual}.",
                actual=actual,
                expected=version,
            )
        )
    return findings
