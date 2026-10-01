import pytest

from shipstate.checks.readme import check_readme


def readme_findings(tmp_path, text):
    (tmp_path / 'README.md').write_text(text)
    return check_readme(tmp_path, 'shipstate', '0.1.0')


@pytest.mark.parametrize('marker', ['```', '~~~', '````', '~~~~'])
@pytest.mark.parametrize('fake_prefix', ['> ', '>> ', '> > '])
def test_quote_looking_content_cannot_close_ordinary_fence(tmp_path, marker, fake_prefix):
    text = f'{marker}text\n{fake_prefix}{marker}\n{marker}\nUpgrading from shipstate==0.0.1'
    assert not any(f.code == 'readme_version_drift' for f in readme_findings(tmp_path, text))


@pytest.mark.parametrize('quote', ['> ', '>> ', '> > '])
@pytest.mark.parametrize('marker', ['```', '~~~'])
@pytest.mark.parametrize('version', ['0.0.1', '0.1.0'])
def test_fence_closes_in_its_own_quote_container(tmp_path, quote, marker, version):
    text = f'{quote}{marker}bash\n{quote}pip install shipstate=={version}\n{quote}{marker}\nHistorical shipstate==0.0.2'
    findings = readme_findings(tmp_path, text)
    assert any(f.actual == version for f in findings)
    assert [f.actual for f in findings if f.code == 'readme_version_drift'] == (['0.0.1'] if version == '0.0.1' else [])


@pytest.mark.parametrize('start,end', [('> ', ''), ('>> ', '> '), ('> > ', ''), ('> > > ', '> > ')])
@pytest.mark.parametrize('marker', ['```', '~~~'])
def test_quote_exit_ends_unclosed_fence(tmp_path, start, end, marker):
    text = f'{start}{marker}bash\n{start}pip install shipstate==0.1.0\n{end}Previously we used shipstate==0.0.1'
    findings = readme_findings(tmp_path, text)
    assert any(f.code == 'readme_pin_matches' for f in findings)
    assert not any(f.code == 'readme_version_drift' for f in findings)


@pytest.mark.parametrize('marker,other', [('```', '~~~'), ('~~~', '```'), ('````', '```'), ('~~~~', '~~~')])
@pytest.mark.parametrize('quote', ['', '> ', '>> '])
def test_wrong_type_or_short_marker_does_not_close_fence(tmp_path, marker, other, quote):
    text = f'{quote}{marker}text\n{quote}{other}\n{quote}shipstate==0.0.1\n{quote}{marker}\nHistorical shipstate==0.0.2'
    assert [f.actual for f in readme_findings(tmp_path, text) if f.code == 'readme_version_drift'] == ['0.0.1']


def test_quote_looking_install_is_literal_ordinary_fence_content(tmp_path):
    # Broad fenced-code pin semantics intentionally remain unchanged.
    findings = readme_findings(tmp_path, '```text\n> pip install shipstate==0.0.1\n```')
    assert any(f.code == 'readme_version_drift' for f in findings)


def test_extra_quote_marker_inside_quote_fence_is_literal_content(tmp_path):
    findings = readme_findings(tmp_path, '> ```text\n>> ```\n> shipstate==0.0.1\n> ```\nHistorical shipstate==0.0.2')
    assert [f.actual for f in findings if f.code == 'readme_version_drift'] == ['0.0.1']
