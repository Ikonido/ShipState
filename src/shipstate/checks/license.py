from pathlib import Path

from shipstate.paths import resolve_project_file
from shipstate.models import Finding, InputError

_LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt")


def check_license(root: Path) -> Finding:
    present = None
    for name in _LICENSE_NAMES:
        path = resolve_project_file(root, name)
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > 0:
                present = name
                break
        except OSError as exc:
            raise InputError("license_unreadable", f"{name} could not be inspected.") from exc
    if present is None:
        return Finding(
            code="license_missing",
            severity="warn",
            source=".",
            message="No supported LICENSE file was found.",
        )
    return Finding(
        code="license_present",
        severity="pass",
        source=present,
        message=f"{present} was found.",
    )
