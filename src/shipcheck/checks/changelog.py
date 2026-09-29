import re
from pathlib import Path

from shipcheck.models import Finding, InputError


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

    escaped = re.escape(version)
    heading = re.compile(
        rf"^(?:##|#)[ \t]+(?:\[{escaped}\]|{escaped})(?:[ \t]+.*)?$",
        re.MULTILINE,
    )
    if heading.search(text):
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
