# Publishing checks for ShipState

Creating a `v*` Git tag runs Tests and the release-consistency job. It does not
publish a package. Publishing a GitHub Release runs `.github/workflows/publish.yml`
and, if its build job succeeds, attempts a production PyPI upload.

## Expected production Trusted Publisher

The repository side currently expects the following values. The matching
configuration inside the maintainer's PyPI account has **not** been verified.

| Field | Expected value |
| --- | --- |
| PyPI project / distribution name | `shipstate` |
| Repository owner | `Ikonido` |
| Repository | `ShipState` |
| Workflow filename | `publish.yml` |
| GitHub environment | `pypi` |

Compare all five fields with the existing or pending publisher before publishing
a GitHub Release. The workflow display name is not the workflow filename.
For a new project, configure a pending publisher under the account's Publishing
settings. Pending publishers do not reserve a package name.

On 2026-10-01, both `https://pypi.org/pypi/shipstate/json` and
`https://test.pypi.org/pypi/shipstate/json` returned HTTP 404. No public project was
found on either index at that time. This does not prove the name is available:
PyPI can block names, and availability can change before the first upload.

## TestPyPI first

TestPyPI supports Trusted Publishing with the same PyPA publish action and
`repository-url: https://test.pypi.org/legacy/`. It has separate accounts and
publisher configuration from production PyPI. A TestPyPI upload does not test the
production account's publisher registration.

Use a separate manually triggered test workflow/environment (for example,
`publish-test.yml` / `testpypi`) and register **those exact values** on TestPyPI;
keep the existing production workflow unchanged. Give only the test publishing
job `id-token: write` and download distributions built and tested from the intended
tag. This document prepares the procedure; no test publishing workflow or upload
has been created or executed.

After a deliberate TestPyPI upload, install runtime dependencies from production
PyPI and the test package separately, without mixing indexes:

```sh
python -m venv /tmp/shipstate-testpypi
/tmp/shipstate-testpypi/bin/python -m pip install 'packaging>=23.2' 'PyYAML>=6.0'
/tmp/shipstate-testpypi/bin/python -m pip install --index-url https://test.pypi.org/simple/ --no-deps 'shipstate==0.1.1'
/tmp/shipstate-testpypi/bin/shipstate --version
/tmp/shipstate-testpypi/bin/shipstate --help
/tmp/shipstate-testpypi/bin/shipstate check /path/to/ShipState
```

These are reviewable instructions, not commands executed by this review.

## Production decision

Before creating a published GitHub Release, confirm the production publisher,
name availability, environment approval policy, the intended Git tag, and the
artifacts' metadata. Uploaded filenames cannot be reused, including after deleting
files. Treat publication as a separate decision. Keep the README's “PyPI releases
are not available yet” statement until a production upload has succeeded.

References:

- [Creating a project through Trusted Publishing](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
- [Adding a GitHub Trusted Publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- [Publishing to TestPyPI with Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [Using TestPyPI](https://packaging.python.org/en/latest/guides/using-testpypi/)
- [Name retention and blocked names](https://docs.pypi.org/project-management/name-retention/)
