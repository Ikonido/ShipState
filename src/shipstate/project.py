"""Read and validate static Python project metadata."""

import re
import tomllib
from pathlib import Path, PureWindowsPath

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

from shipstate.models import InputError, Project
from shipstate.paths import resolve_project_file

_PROJECT_NAME_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?\Z")
_BACKEND_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*(?::[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)?\Z"
)


def load_project(path: Path) -> Project:
    if not path.exists():
        raise InputError("project_path_missing", "The project path does not exist.")
    if not path.is_dir():
        raise InputError("project_path_invalid", "The project path must be a directory.")

    pyproject = resolve_project_file(path, "pyproject.toml")
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
    if not isinstance(dynamic, list) or any(not isinstance(item, str) for item in dynamic):
        raise InputError("invalid_project_dynamic", "[project].dynamic must be an array of strings.")
    if "version" in dynamic:
        raise InputError(
            "dynamic_version_not_supported",
            "Dynamic project versions are not supported; set a static [project].version.",
        )

    name = metadata.get("name")
    if not isinstance(name, str) or not name.strip():
        raise InputError("project_name_missing", "[project].name is required and must be a non-empty string.")
    if not _PROJECT_NAME_RE.fullmatch(name):
        raise InputError("project_name_invalid", "[project].name is not a valid Python distribution name.")

    version = metadata.get("version")
    if not isinstance(version, str) or not version.strip():
        raise InputError("project_version_missing", "[project].version is required and must be a non-empty string.")
    if version != version.strip():
        raise InputError("invalid_project_version", "[project].version must not contain surrounding whitespace.")
    try:
        normalized_version = str(Version(version))
    except InvalidVersion as exc:
        raise InputError("invalid_project_version", "[project].version must be a valid PEP 440 version.") from exc

    build_system = data.get("build-system")
    build_system_issue = None
    build_system_warnings: list[str] = []
    if "build-system" in data:
        if not isinstance(build_system, dict):
            build_system_issue = "[build-system] must be a table."
        else:
            if "requires" not in build_system:
                build_system_warnings.append("build_system_requires_missing")
            else:
                requirements = build_system["requires"]
                if not isinstance(requirements, list) or any(
                    not isinstance(item, str) or not item.strip() for item in requirements
                ):
                    build_system_issue = "[build-system].requires must be an array of valid requirement strings."
                else:
                    try:
                        for requirement in requirements:
                            Requirement(requirement)
                    except InvalidRequirement:
                        build_system_issue = "[build-system].requires contains an invalid requirement."

            if "build-backend" not in build_system:
                build_system_warnings.append("build_backend_missing")
            else:
                backend = build_system["build-backend"]
                if not isinstance(backend, str) or not backend.strip():
                    build_system_issue = build_system_issue or "[build-system].build-backend must be a non-empty string."
                elif not _BACKEND_RE.fullmatch(backend):
                    build_system_issue = build_system_issue or "[build-system].build-backend must be a valid module or module:object reference."

            backend_path = build_system.get("backend-path")
            if backend_path is not None and (
                not isinstance(backend_path, list)
                or any(not isinstance(item, str) or not item.strip() for item in backend_path)
            ):
                build_system_issue = build_system_issue or "[build-system].backend-path must be an array of non-empty strings."
            elif backend_path is not None:
                try:
                    root = path.resolve()
                    for item in backend_path:
                        candidate = Path(item)
                        resolved = (root / candidate).resolve()
                        if (
                            candidate.is_absolute()
                            or PureWindowsPath(item).is_absolute()
                            or not resolved.is_relative_to(root)
                            or not resolved.is_dir()
                        ):
                            build_system_issue = build_system_issue or (
                                "[build-system].backend-path entries must be relative paths "
                                "to existing directories inside the project."
                            )
                            break
                except (OSError, RuntimeError, ValueError):
                    build_system_issue = build_system_issue or "[build-system].backend-path could not be resolved."

    return Project(
        name=name,
        version=normalized_version,
        root=str(path),
        has_build_system="build-system" in data,
        build_system_issue=build_system_issue,
        build_system_warnings=tuple(build_system_warnings),
    )
