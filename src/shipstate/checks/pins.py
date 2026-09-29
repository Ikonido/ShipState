"""Conservative, line-oriented package pin detection shared by README and CI checks."""

import re

from packaging.utils import canonicalize_name


def _package_prefix(project_name: str) -> str:
    normalized = canonicalize_name(project_name)
    parts = normalized.split("-")
    package = r"[-_.]+".join(re.escape(part) for part in parts)
    extras = r"(?:\[[A-Za-z0-9_.-]+(?:[ \t]*,[ \t]*[A-Za-z0-9_.-]+)*\])?"
    return rf"(?<![A-Za-z0-9_.-]){package}{extras}(?![A-Za-z0-9_.-])"


def package_pin_pattern(project_name: str) -> re.Pattern[str]:
    package = _package_prefix(project_name)
    return re.compile(
        rf"{package}[ \t]*==[ \t]*(?P<version>[A-Za-z0-9][A-Za-z0-9.!+_-]*)",
        re.IGNORECASE,
    )


def dynamic_pin_pattern(project_name: str) -> re.Pattern[str]:
    dynamic_version = r"(?:\$\{\{[^}]+\}\}|\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_]*|\$\([^)]*\))"
    return re.compile(
        rf"{_package_prefix(project_name)}[ \t]*==[ \t]*(?P<version>{dynamic_version})",
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
