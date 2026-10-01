"""Resolve top-level input files without reading outside the project."""

from pathlib import Path

from shipstate.models import InputError


def resolve_project_file(root: Path, name: str) -> Path:
    try:
        resolved_root = root.resolve()
        target = (resolved_root / name).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise InputError("project_file_unresolvable", f"{name} could not be resolved.") from exc
    if not target.is_relative_to(resolved_root):
        raise InputError(
            "project_file_outside_project",
            f"{name} resolves outside the project; external file symlinks are not supported.",
        )
    return target
