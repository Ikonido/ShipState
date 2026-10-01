
import pytest

from shipstate.checks.readme import check_readme


@pytest.mark.parametrize('tokens', [
    ['pip', 'install'], ['pip3', 'install'],
    ['python', '-m', 'pip', 'install'], ['python3', '-m', 'pip', 'install'],
    ['uv', 'pip', 'install'],
])
@pytest.mark.parametrize('space', [' ', '  ', '\t', ' \t  '])
@pytest.mark.parametrize('version,code', [('0.0.1', 'readme_version_drift'), ('0.1.0', 'readme_pin_matches')])
def test_install_argument_whitespace(tmp_path, tokens, space, version, code):
    (tmp_path / 'README.md').write_text(space.join(tokens + [f'shipstate=={version}']))
    assert code in {f.code for f in check_readme(tmp_path, 'shipstate', '0.1.0')}


@pytest.mark.parametrize('prefix', ['> ', '>> ', '> > ', '>   ', '>\t>\t', '>'])
@pytest.mark.parametrize('fence', [None, '```bash', '```', '~~~sh'])
def test_blockquote_install_examples(tmp_path, prefix, fence):
    command = 'python\t-m  pip install shipstate==0.0.1'
    text = prefix + command
    if fence:
        text = '\n'.join([prefix + fence, text, prefix + fence[:3],
                         prefix + 'Previously we used shipstate==0.0.2'])
    (tmp_path / 'README.md').write_text(text)
    findings = check_readme(tmp_path, 'shipstate', '0.1.0')
    assert [f.actual for f in findings if f.code == 'readme_version_drift'] == ['0.0.1']


@pytest.mark.parametrize('text', [
    '> Upgrading from shipstate==0.0.1', '>> Previously we used shipstate==0.0.1',
    'Upgrading from shipstate==0.0.1', 'https://example.com/?q=shipstate==0.0.1',
    '{"package":"shipstate==0.0.1"}', '| old | shipstate==0.0.1 |',
    '> | old | shipstate==0.0.1 |', 'python-m pip install shipstate==0.0.1',
    'uvpip install shipstate==0.0.1', 'python -m pipinstall shipstate==0.0.1',
    '> pip install myshipstate==0.0.1', '> pip install shipstate2==0.0.1',
    '> pip install shipstate-plugin==0.0.1',
])
def test_quote_and_whitespace_do_not_expand_pin_contexts(tmp_path, text):
    (tmp_path / 'README.md').write_text(text)
    assert not any(f.code == 'readme_version_drift' for f in check_readme(tmp_path, 'shipstate', '0.1.0'))


@pytest.mark.parametrize('name', ['ship-state', 'ship_state', 'ship.state'])
def test_blockquoted_distribution_normalization(tmp_path, name):
    (tmp_path / 'README.md').write_text(f'> uv\tpip install {name}==0.0.1')
    assert any(f.code == 'readme_version_drift' for f in check_readme(tmp_path, 'ship-state', '0.1.0'))
