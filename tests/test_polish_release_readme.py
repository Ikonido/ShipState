from pathlib import Path

import pytest
from conftest import git

from shipstate.checks.changelog import check_changelog
from shipstate.checks.readme import check_readme
from shipstate.checks.tag import check_tag
from shipstate.git import get_git_context


@pytest.mark.parametrize('release,equivalent', [
    ('1.0', True), ('1.0.0', True), ('1.0.0.0', True), ('01.0', True),
    ('1.0.1', False), ('1.0rc1', False), ('1.0.post1', False),
    ('1.0.dev1', False), ('1.0+local', False), ('2!1.0', False),
])
def test_release_version_equivalence(project_factory, release, equivalent):
    root = project_factory(version='1.0.0', tag=False)
    git(root, 'tag', f'v{release}')
    finding = check_tag(root, '1.0.0', get_git_context(root))
    assert (finding.severity == 'pass') is equivalent
    (root / 'CHANGELOG.md').write_text(f'## [{release}] - 2026-09-30\n')
    assert (check_changelog(root, '1.0.0').severity == 'pass') is equivalent


def test_equivalent_annotated_tag(project_factory):
    root = project_factory(version='1.0.0', tag=False)
    git(root, 'tag', '-a', 'v1.0', '-m', 'release')
    assert check_tag(root, '1.0.0', get_git_context(root)).severity == 'pass'


def test_equivalent_tags_cannot_hide_wrong_commit(project_factory):
    root = project_factory(version='1.0.0')
    (root / 'new.txt').write_text('next commit\n')
    git(root, 'add', '.')
    git(root, 'commit', '-m', 'next commit')
    git(root, 'tag', 'v1.0')
    assert check_tag(root, '1.0.0', get_git_context(root)).code == 'tag_commit_mismatch'


def test_invalid_and_unprefixed_tags_ignored(project_factory):
    root = project_factory(version='1.0.0', tag=False)
    git(root, 'tag', 'vnot-a-version')
    git(root, 'tag', '1.0')
    assert check_tag(root, '1.0.0', get_git_context(root)).code == 'missing_version_tag'


@pytest.mark.parametrize('text,drift', [
    ('pip install shipstate==0.0.1', True),
    ('pip3 install shipstate==0.0.1', True),
    ('python -m pip install shipstate==0.0.1', True),
    ('python3 -m pip install shipstate==0.0.1', True),
    ('uv pip install shipstate==0.0.1', True),
    ('`pip install shipstate==0.0.1`', True),
    ('```bash\npip install shipstate==0.0.1\n```', True),
    ('~~~text\nshipstate==0.0.1\n~~~', True),
    ('Dependencies: `shipstate==0.0.1`', True),
    ('Upgrading from shipstate==0.0.1', False),
    ('Previously documented shipstate==0.0.1', False),
    ('Version shipstate==0.0.1 was released last year', False),
    ('https://example.invalid/?q=shipstate==0.0.1', False),
    ('value="shipstate==0.0.1"', False),
    ('pip install shipstate==0.1.0', False),
    ('pip install myshipstate==0.0.1', False),
    ('pip install shipstate2==0.0.1', False),
    ('pip install shipstate-plugin==0.0.1', False),
    ('Install with pip install shipstate[dev]==0.0.1', True),
    ('- pip install shipstate==0.0.1', True),
    ('$ pip install shipstate==0.0.1', True),
    ('Example: ``pip install shipstate==0.0.1``', True),
    ('````text\n```\nshipstate==0.0.1\n```\n````', True),
])
def test_readme_context_matrix(tmp_path: Path, text, drift):
    (tmp_path / 'README.md').write_text(text + '\n')
    findings = check_readme(tmp_path, 'shipstate', '0.1.0')
    assert any(f.code == 'readme_version_drift' for f in findings) is drift


@pytest.mark.parametrize('name', ['ship-state', 'ship_state', 'ship.state', 'SHIP___STATE'])
def test_readme_equivalent_distribution_spelling(tmp_path, name):
    (tmp_path / 'README.md').write_text(f'pip install {name}==0.0.1\n')
    assert any(f.code == 'readme_version_drift' for f in check_readme(tmp_path, 'ship-state', '0.1.0'))


def test_readme_separators_are_not_optional(tmp_path):
    (tmp_path / 'README.md').write_text('pip install shipstate==0.0.1\n')
    assert not any(f.code == 'readme_version_drift' for f in check_readme(tmp_path, 'ship-state', '0.1.0'))
