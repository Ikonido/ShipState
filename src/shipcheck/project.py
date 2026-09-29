"""Read and validate static Python project metadata."""

import re
import tomllib
from pathlib import Path

from packaging.version import InvalidVersion, Version

from shipcheck.models import InputError, Project

_PROJECT_NAME_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?\Z")


def load_project(path: Path) -> Project:
    if not path.exists():
        raise InputError("project_path_missing", "The project path does not exist.")
    if not path.is_dir():
        raise InputError("project_path_invalid", "The project path must be a directory.")

    pyproject = path / "pyproject.toml"
    if not pyproject.is_file():
        raise InputError("pyproject_missing", "pyproject.toml was not found.")
    try:
        raw_text = pyproject.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InputError("pyproject_unreadable", "pyproject.toml could not be read as UTF-8.") from exc
    try:
        data = tomllib.loads(raw_text)
    except tomllib.TOMLDecodeError as exc:
        raise InputError("invalid_pyproject", f"pyproject.toml is not valid TOML: {exc}") from exc

    metadata = data.get("project")
    if not isinstance(metadata, dict):
        raise InputError("project_metadata_missing", "pyproject.toml must contain a [project] table.")

    dynamic = metadata.get("dynamic", [])
    if isinstance(dynamic, list) and "version" in dynamic:
        raise InputError(
            "dynamic_version_not_supported",
            "Dynamic project versions are not supported; set a static [project].version.",
        )

    name = metadata.get("name")
    if not isinstance(name, str) or not name.strip():
        raise InputError("project_name_missing", "[project].name is required and must be a non-empty string.")
    name = name.strip()
    if not _PROJECT_NAME_RE.fullmatch(name):
        raise InputError("project_name_invalid", "[project].name is not a valid Python distribution name.")

    version = metadata.get("version")
    if not isinstance(version, str) or not version.strip():
        raise InputError("project_version_missing", "[project].version is required and must be a non-empty string.")
    try:
        normalized_version = str(Version(version.strip()))
    except InvalidVersion as exc:
        raise InputError("invalid_project_version", "[project].version must be a valid PEP 440 version.") from exc

    return Project(
        name=name,
        version=normalized_version,
        root=str(path),
        has_build_system=isinstance(data.get("build-system"), dict),
    )
