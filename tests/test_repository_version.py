"""Keep repository release metadata and user-facing version examples in sync."""

import re
import tomllib
from pathlib import Path

from shipstate import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_repository_release_versions_agree():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = metadata["project"]["version"]
    assert "version" not in metadata["project"].get("dynamic", [])
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    first_release = re.search(r"^## \[?v?(\d[^\s\]]*)\]?(?:\s.*)?$", changelog, re.MULTILINE)
    assert first_release is not None, "CHANGELOG.md needs a version heading"
    assert __version__ == version == first_release.group(1)


def test_readme_tool_version_matches_repository():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    examples = re.findall(r"^\s+ShipState (\d[^\s]*)$", readme, re.MULTILINE)
    assert examples, "README.md needs the tool's example output"
    assert all(version == __version__ for version in examples)


def test_readme_versioned_links_match_project_version():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = metadata["project"]["version"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    linked_versions = re.findall(
        r"https://github\.com/Ikonido/ShipState/blob/v([^/\s)]+)/", readme
    )
    assert linked_versions, "README.md needs versioned repository-file links"
    assert all(linked_version == version for linked_version in linked_versions)
