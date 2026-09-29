import re
from pathlib import Path

from shipstate.models import Finding, InputError

_ATX_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def _has_version_heading(text: str, version: str) -> bool:
    escaped = re.escape(version)
    version_heading = re.compile(
        rf"^(?:v{escaped}|{escaped}|\[v?{escaped}\](?:\([^)]*\))?(?:\[[^]]*\])?)(?:[ \t]+.*)?$",
        re.IGNORECASE,
    )
    fence_char: str | None = None
    fence_size = 0
    for line in text.splitlines():
        fence = _FENCE.match(line)
        if fence_char is not None:
            if fence and fence.group(1)[0] == fence_char and len(fence.group(1)) >= fence_size and not fence.group(2).strip():
                fence_char = None
                fence_size = 0
            continue
        if fence:
            fence_char = fence.group(1)[0]
            fence_size = len(fence.group(1))
            continue
        heading = _ATX_HEADING.match(line)
        if heading and version_heading.fullmatch(heading.group(2).strip()):
            return True
    return False


def check_changelog(root: Path, version: str) -> Finding:
    path = root / "CHANGELOG.md"
    if not path.is_file():
        return Finding(
            code="changelog_missing",
            severity="fail",
            source="CHANGELOG.md",
            message="CHANGELOG.md was not found.",
            expected=version,
        )
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InputError("changelog_unreadable", "CHANGELOG.md could not be read as UTF-8.") from exc

    if _has_version_heading(text, version):
        return Finding(
            code="changelog_version_found",
            severity="pass",
            source="CHANGELOG.md",
            message=f"CHANGELOG.md contains a heading for {version}.",
            actual=version,
            expected=version,
        )
    return Finding(
        code="changelog_version_missing",
        severity="fail",
        source="CHANGELOG.md",
        message=f"CHANGELOG.md has no supported heading for {version}.",
        expected=version,
    )
