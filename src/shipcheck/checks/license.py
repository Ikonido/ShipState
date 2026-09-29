from pathlib import Path

from shipcheck.models import Finding

_LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt")


def check_license(root: Path) -> Finding:
    present = next((name for name in _LICENSE_NAMES if (root / name).is_file()), None)
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
