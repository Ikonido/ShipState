# Contributing to ShipState

## Development environment

Use Python 3.11 or newer and the local Git CLI:

```sh
python -m venv .venv
# On Windows, activate with .venv\Scripts\activate instead.
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

The `dev` extra provides pytest. CI runs the suite on Python 3.11 and 3.12;
run both versions when available. Ruff, mypy, and Black are not configured.
Do not add new runtime dependencies or network access to the checker.

## Check ShipState itself

```sh
shipstate check .
shipstate check . --format json
```

A missing current-version tag or a matching tag on an older commit is a FAIL
(exit code 1). This is expected during development: release tags belong to
release commits. Do not move existing tags to make a development check pass.
A dirty working tree and unpinned local workflow installs can produce WARN;
warnings allow exit code 0 but do not establish pin consistency.
CI runs the full self-check on `v*` tag pushes and before publishing artifacts.

## Commits and pull requests

Create a topic branch and keep each logical change in a separate Conventional
Commit, for example `fix: ...`, `test: ...`, `docs: ...`, or `ci: ...`.
Describe the problem, resulting behavior, and validation in the PR.
Confirm reported issues against the code before changing it. Add a regression
test for each bug fix and run the full suite after each block.
Preserve CLI exit codes, text output, and JSON schemas unless fixing a proven bug.
Record user-visible changes under `## Unreleased` in CHANGELOG.md.

## Release checklist (maintainer only)

1. Choose an unused version; never replace or move an existing release tag.
2. Set the static `[project].version` in pyproject.toml. Update `__version__`
   in src/shipstate/__init__.py and the README's `ShipState X.Y.Z` example to match.
3. Turn the Unreleased notes into the first version heading in CHANGELOG.md.
   Update any actual self-package installation pins; leave test fixture versions alone.
4. Run `python -m pytest` on Python 3.11 and 3.12. Optionally install `build twine`,
   run `python -m build`, and run `python -m twine check dist/*` in a clean output directory.
5. Commit the complete release metadata, then create `vX.Y.Z` on that commit.
6. Run `shipstate check .` and its JSON form; require exit code 0 and no FAIL.
7. Push the release commit and tag. Wait for Tests, including release-consistency.
8. Before creating a GitHub Release, verify the `pypi` environment and PyPI Trusted
   Publishing configuration. The existing publish.yml runs on a **published
   GitHub Release** and attempts publication to PyPI; configure required approval
   if publication must be gated. Publishing is a separate maintainer decision.
9. After a successful PyPI publication, update the README's
   “PyPI releases are not available yet” statement and installation instructions.
