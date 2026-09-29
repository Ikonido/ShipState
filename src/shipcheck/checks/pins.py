"""Conservative, line-oriented package pin detection shared by README and CI checks."""

import re

from packaging.utils import canonicalize_name


def package_pin_pattern(project_name: str) -> re.Pattern[str]:
    normalized = canonicalize_name(project_name)
    parts = normalized.split("-")
    package = r"[-_.]+".join(re.escape(part) for part in parts)
    return re.compile(
        rf"(?<![A-Za-z0-9_.-]){package}(?![A-Za-z0-9_.-])[ \t]*==[ \t]*(?P<version>[A-Za-z0-9][A-Za-z0-9.!+_-]*)",
        re.IGNORECASE,
    )


def extract_pins(text: str, project_name: str) -> list[str]:
    pattern = package_pin_pattern(project_name)
    versions: list[str] = []
    for match in pattern.finditer(text):
        version = match.group("version").rstrip(".,;:!?)]}'\"")
        if version:
            versions.append(version)
    return versions
