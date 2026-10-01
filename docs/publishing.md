# Publishing checks for ShipState

Creating a `v*` Git tag runs Tests and the release-consistency job. It does not
publish a package. Publishing a GitHub Release runs `.github/workflows/publish.yml`
and, if its build job succeeds, attempts a production PyPI upload.

## Expected production Trusted Publisher

The repository side expects the following values. On 2026-10-01, the matching
pending publisher was verified in the maintainer's PyPI account, and the first
production upload succeeded using Trusted Publishing.

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

The separate `.github/workflows/publish-test.yml` uses manual `workflow_dispatch`
and environment `testpypi`. Register a TestPyPI publisher with project `shipstate`,
owner `Ikonido`, repository `ShipState`, workflow filename `publish-test.yml`,
and environment `testpypi`. These are separate from the production publisher.

Create `testpypi` with Required reviewers before running it. Dispatch the workflow
from `main`, with input `tag: v0.1.1`; dispatches from other refs are skipped.
If restricting deployment refs for this test environment, allow **branch `main`**:
environment rules check the workflow run's ref, while the build explicitly checks
out `refs/tags/<input tag>`. This permits testing a tag created before the workflow
was added. Keep production `pypi` restricted to **tags `v*`**.

The build verifies the tag/version/commit, runs tests and self-checks, builds and
smoke-tests the distributions. Only the publishing job has `id-token: write`; it
downloads those artifacts from the same run and uploads to TestPyPI. A final job
reads dependencies from the tested tag, installs them from production PyPI, fetches
the wheel from TestPyPI without dependencies, compares it byte-for-byte with the
built wheel, and checks the installed package. The production workflow is unchanged.
On 2026-10-01, the publisher registration and upload were verified for `v0.1.1`
at commit `d228049513f313c57cf78ae51eaa179180a32b3a`.
[TestPyPI run 36840245358](https://github.com/Ikonido/ShipState/actions/runs/36840245358)
passed all three jobs: 609 tests, self-check, build/twine, wheel/sdist smoke tests,
and installation of the published wheel with a byte-for-byte artifact comparison.

After the workflow is merged into `main` and the remote tag's CI is green:

```sh
gh workflow run publish-test.yml --ref main -f tag=v0.1.1
```

Wait for all three jobs to succeed before publishing the production Release.
If verification fails after the upload, inspect the failure first: TestPyPI also
does not allow reusing uploaded filenames, so rerunning the upload is not a remedy.

After a deliberate TestPyPI upload, run the following from a clean checkout of
the intended release tag, with Python 3.11 or newer. Read runtime dependencies
from that tag's `[project].dependencies` in pyproject.toml; do not copy them by
hand or read them from a newer main checkout. The version is read from the same
metadata. Install dependencies from production PyPI and the test package
separately, without mixing indexes:

```sh
python -m venv /tmp/shipstate-testpypi
/tmp/shipstate-testpypi/bin/python - <<'PY'
import tomllib
from pathlib import Path

project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
output = Path("/tmp/shipstate-testpypi")
(output / "runtime-requirements.txt").write_text(
    "\n".join(project.get("dependencies", [])) + "\n", encoding="utf-8"
)
(output / "version.txt").write_text(project["version"], encoding="utf-8")
PY
/tmp/shipstate-testpypi/bin/python -m pip install --index-url https://pypi.org/simple/ -r /tmp/shipstate-testpypi/runtime-requirements.txt
VERSION=$(cat /tmp/shipstate-testpypi/version.txt)
/tmp/shipstate-testpypi/bin/python -m pip install --index-url https://test.pypi.org/simple/ --no-deps "shipstate==$VERSION"
/tmp/shipstate-testpypi/bin/python -m pip check
/tmp/shipstate-testpypi/bin/shipstate --version
/tmp/shipstate-testpypi/bin/shipstate --help
/tmp/shipstate-testpypi/bin/shipstate check .
```

These are reviewable instructions, not commands executed by this review.

## Configure the GitHub approval gate first

Before publishing any GitHub Release, open this repository's **Settings →
Environments**, create or edit the `pypi` environment, enable **Required reviewers**,
add the maintainer who must approve production uploads, and save the protection
rules. Configure this explicitly: the workflow's `environment: pypi` reference
alone does not create an approval rule. If GitHub creates a missing environment
automatically, it has no protection rules by default.

The `publish` job must wait for approval before starting. Only one listed reviewer
needs to approve, so list only maintainers trusted to authorize PyPI uploads.
Disable **Allow administrators to bypass configured protection rules** if the
confirmation must not be bypassed. Enable **Prevent self-review** only when another
reviewer can approve; leave it disabled for a sole maintainer.

Under **Deployment branches and tags**, choose **Selected branches and tags**,
add a rule with **Ref type: Tag**, pattern **`v*`**, and remove any branch rules.
The production environment must not allow branch deployments. GitHub treats tag
and branch rules separately; a branch named `v0.1.1` must not qualify as a tag.
Required reviewers are available for public repositories on current GitHub plans;
availability is more restrictive for private repositories.

On 2026-10-01, both environments were configured and verified in GitHub Settings:
Required reviewers includes `Ikonido`, Prevent self-review is disabled, and
administrator bypass is disabled. Production `pypi` allows only Tag `v*` rules
(0 branch rules); `testpypi` allows only Branch `main` (0 tag rules). Recheck these
settings before publishing: repository settings can change independently of Git.
Publisher registration and uploads on both TestPyPI and PyPI were subsequently
verified for `v0.1.1` on the same date.

## Release order: remote tag, draft, review, publish

1. Create and push the intended release tag first. For this release it is `v0.1.1`.
   Verify it exists **on GitHub** and resolves to the intended release commit;
   a local tag alone is insufficient. Do not move the existing `v0.1.0` tag.
2. Wait for the tag's Tests run, including `release-consistency`, to succeed.
3. Create the GitHub Release as a **draft**, selecting that existing remote tag.
   Do not use Release creation to make a missing tag automatically: it may create
   one at the selected target commit, which bypasses the intended tag-first order.
4. Review the draft's tag, release notes, version and artifacts, the production
   Trusted Publisher fields, name availability, and the `pypi` approval gate.
5. Publish the reviewed draft only as a deliberate production decision. This emits
   the `published` event and starts `publish.yml`. After its build succeeds, the
   production publishing job must still wait for the required review approval.
6. Review that workflow run and its tag-derived artifacts before approving the
   `pypi` deployment. Confirm the PyPI upload result afterwards.

Saving or editing a draft does not trigger this repository's workflow, which
subscribes only to `release: types: [published]`. Publishing a draft, including
one marked as a pre-release, does trigger it; a pre-release is not a dry run.

For a maintainer using GitHub CLI, after the tag has already been pushed:

```sh
git ls-remote --exit-code origin refs/tags/v0.1.1
gh release create v0.1.1 --verify-tag --draft --title "ShipState v0.1.1" --generate-notes
```

`--verify-tag` aborts if the tag is missing remotely. `--draft` lets you review the
notes and tag before publishing. These commands are instructions, not operations
executed by this review.

## Artifact provenance and publishing permissions

Keep these requirements in `publish.yml`:

- The `build` job checks out the exact `github.event.release.tag_name`, verifies
  its version and commit, runs tests and the self-check, and builds the wheel and
  sdist from that checkout. Upload only those distributions as `shipstate-dists`.
- The `publish` job has `needs: build` and downloads `shipstate-dists` **from that
  successful build job in the same workflow run**. Do not download artifacts from
  another run, branch or tag, or rebuild packages in the publishing job.
- Default and build permissions remain `contents: read`. Grant `id-token: write`
  **only to the publishing job**, after the environment approval gate. Build and
  test jobs must not have OIDC publishing permission.

The current workflow already follows these artifact and permission rules: its
artifact download uses the same run by default, and only the `publish` job has
`id-token: write`. Environment Required reviewers are a separate GitHub setting;
their presence cannot be established from the YAML alone.

Uploaded filenames cannot be reused, including after deleting files.

## Verified first production release

On 2026-10-01, the existing remote tag `v0.1.1` was verified at commit
`d228049513f313c57cf78ae51eaa179180a32b3a`, and its Tests run passed on Python
3.11 and 3.12, including release-consistency. The GitHub Release was saved as a
draft, reviewed, and then published. After the production build passed 609 tests,
self-check, build/twine, and wheel/sdist smoke tests, the publishing job waited
for the required `pypi` approval before uploading its artifacts.

[Production run 36843723825](https://github.com/Ikonido/ShipState/actions/runs/36843723825)
succeeded, publishing the wheel and sdist to
[PyPI 0.1.1](https://pypi.org/project/shipstate/0.1.1/).
A fresh Python 3.11 environment installed `shipstate==0.1.1` from production PyPI;
`pip check` found no broken requirements, `shipstate --version` returned 0.1.1,
and `shipstate check .` on a clean checkout of the release tag returned PASS/0
with the five expected workflow-scanning warnings.
The README now documents PyPI installation and includes a PyPI version badge.
Its repository-file links use absolute GitHub URLs pinned to `v0.1.1`, so they
resolve independently of the page hosting the rendered README. The already
published 0.1.1 distributions contain the original README with relative links;
the revised description will be included in the next release, without replacing
0.1.1 or moving its tag.

References:

- [Creating a project through Trusted Publishing](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
- [Adding a GitHub Trusted Publisher](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
- [Publishing to TestPyPI with Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [Using TestPyPI](https://packaging.python.org/en/latest/guides/using-testpypi/)
- [Name retention and blocked names](https://docs.pypi.org/project-management/name-retention/)
- [GitHub release events and drafts](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#release)
- [Configuring environment Required reviewers](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
- [GitHub CLI release creation and --verify-tag](https://cli.github.com/manual/gh_release_create)
