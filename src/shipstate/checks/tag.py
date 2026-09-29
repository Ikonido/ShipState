from pathlib import Path

from shipstate.git import GitContext, version_tag_commit
from shipstate.models import Finding


def check_tag(path: Path, version: str, git: GitContext) -> Finding:
    tag = f"v{version}"
    commit = version_tag_commit(path, version)
    if commit is None:
        return Finding(
            code="missing_version_tag",
            severity="fail",
            source="git",
            message=f"Git tag {tag} does not exist.",
            expected=tag,
        )
    if commit != git.head:
        return Finding(
            code="tag_commit_mismatch",
            severity="fail",
            source=f"tag:{tag}",
            message=f"Git tag {tag} points to a different commit than HEAD.",
            actual=commit,
            expected=git.head,
        )
    return Finding(
        code="version_tag_matches_head",
        severity="pass",
        source=f"tag:{tag}",
        message=f"Git tag {tag} points to HEAD.",
        actual=commit,
        expected=git.head,
    )
