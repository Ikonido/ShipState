from pathlib import Path

from shipstate.git import GitContext, equivalent_version_tags, version_tag_commit
from shipstate.models import Finding


def check_tag(path: Path, version: str, git: GitContext) -> Finding:
    tag = f"v{version}"
    tags = equivalent_version_tags(path, version)
    if not tags:
        return Finding(
            code="missing_version_tag",
            severity="fail",
            source="git",
            message=f"Git tag {tag} does not exist.",
            expected=tag,
        )
    # Every equivalent release tag must point to HEAD; do not hide conflicting aliases.
    commits = [(name, version_tag_commit(path, name[1:])) for name in tags]
    tag, commit = next(((name, sha) for name, sha in commits if sha != git.head), commits[0])
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
