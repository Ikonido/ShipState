import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def project_factory(tmp_path: Path):
    def create(
        *,
        name: str = "meshcontract",
        version: str = "0.2.1",
        changelog: str | None = "## 0.2.1\n\nRelease notes.\n",
        readme: str | None = "Install with pip install meshcontract==0.2.1\n",
        workflow: str | None = "run: python -m pip install meshcontract==0.2.1\n",
        license_file: bool = True,
        build_system: bool = True,
        dynamic: str | None = None,
        initialize_git: bool = True,
        tag: bool = True,
    ) -> Path:
        root = tmp_path / "project"
        root.mkdir(exist_ok=True)
        lines = ["[project]", f'name = "{name}"']
        if dynamic is not None:
            lines.append(f'dynamic = ["{dynamic}"]')
        else:
            lines.append(f'version = "{version}"')
        if build_system:
            lines.extend(["", "[build-system]", 'requires = ["setuptools"]', 'build-backend = "setuptools.build_meta"'])
        (root / "pyproject.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")

        if changelog is not None:
            (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
        if readme is not None:
            (root / "README.md").write_text(readme, encoding="utf-8")
        if workflow is not None:
            workflow_dir = root / ".github" / "workflows"
            workflow_dir.mkdir(parents=True, exist_ok=True)
            (workflow_dir / "ci.yml").write_text(workflow, encoding="utf-8")
        if license_file:
            (root / "LICENSE").write_text("MIT License\n", encoding="utf-8")

        if initialize_git:
            git(root, "init", "-q")
            git(root, "config", "user.name", "ShipCheck tests")
            git(root, "config", "user.email", "shipcheck-tests@example.invalid")
            git(root, "add", ".")
            git(root, "commit", "-m", "initial project")
            if tag:
                git(root, "tag", f"v{version}")
        return root

    return create


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()
