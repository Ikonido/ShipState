"""Local Git inspection. This module never reads or contacts a remote."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from shipstate.models import InputError


@dataclass(frozen=True, slots=True)
class GitContext:
    root: Path
    head: str


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise InputError("git_unavailable", "The Git CLI could not be found.") from exc
    except subprocess.TimeoutExpired as exc:
        raise InputError("git_timeout", "The local Git command timed out.") from exc
    except OSError as exc:
        raise InputError("git_execution_failed", "The local Git command could not be started.") from exc


def get_git_context(path: Path) -> GitContext:
    root_result = _git(["rev-parse", "--show-toplevel"], path)
    if root_result.returncode != 0:
        raise InputError("not_git_repository", "The project directory is not inside a Git repository.")
    head_result = _git(["rev-parse", "--verify", "HEAD"], path)
    if head_result.returncode != 0:
        raise InputError("git_head_unavailable", "The Git repository does not have a readable HEAD commit.")
    try:
        root = Path(root_result.stdout.strip()).resolve()
    except OSError as exc:
        raise InputError("git_root_unavailable", "The Git repository root could not be resolved.") from exc
    return GitContext(root=root, head=head_result.stdout.strip())


def version_tag_commit(path: Path, version: str) -> str | None:
    tag_ref = f"refs/tags/v{version}^{{}}"
    result = _git(["rev-parse", "--verify", "--quiet", tag_ref], path)
    return result.stdout.strip() if result.returncode == 0 else None
