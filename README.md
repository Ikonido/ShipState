# ShipState

Keep release state consistent before you ship.

ShipState checks that your Python package version, Git tag, CHANGELOG, README install examples and CI workflow pins agree.

## Install from source

Python 3.11 or newer is required. PyPI releases are not available yet.

    git clone https://github.com/Ikonido/ShipState.git
    cd ShipState
    python -m pip install .

## Usage

    shipstate check .
    shipstate check /path/to/project
    shipstate check . --format json
    shipstate --version
    shipstate --help

ShipState runs locally. It does not contact GitHub, PyPI, or any other service.

## What it checks

- The static project name and PEP 440 version in pyproject.toml.
- Whether the matching vVERSION Git tag points to the current HEAD commit.
- Whether the Git working tree is clean; uncommitted changes produce a warning.
- Whether CHANGELOG.md has a real Markdown heading for the current version (headings in fenced examples are ignored).
- Whether pinned installs of the project itself in README.md use the current version, with distribution-name case and separator variants normalized.
- Whether static exact self-package pins in YAML workflow `run` steps use the current version, including extras and local requirements files; dynamic/non-exact installs, unsupported shell constructs and unresolved paths produce warnings. Constraints do not request installation by themselves.
- Whether a supported, non-empty license file and a structurally valid [build-system] table are present.

For example, given a project named meshcontract at version 0.2.1:

    $ shipstate check .
    ShipState 0.1.0

    Project: meshcontract
    Version: 0.2.1

    PASS package version: 0.2.1
    PASS git tag: v0.2.1
    PASS changelog: 0.2.1 found
    FAIL README pin: meshcontract==0.2.0
    PASS workflow pin: meshcontract==0.2.1
    WARN license: LICENSE not found
    PASS build system: present

    Release consistency: FAIL

## Exit codes

- 0: required consistency checks pass; warnings are allowed.
- 1: at least one release consistency check fails.
- 2: invalid project configuration, unsupported dynamic version, non-Git directory, or another tool/input error.

## JSON mode

Use --format json for stable machine-readable output. Successful checks return a top-level shipstate_version, status, project object, and findings array. Each finding has code, severity, source, message, actual, and expected fields. Input and tool errors return status=error with an error code and message.

## Scope and limitations

ShipState 0.1.x supports Python projects with a static version in `pyproject.toml`.
It reads local files and uses only the local Git CLI, without network access.
README pin detection uses regexes in code examples and explicit install lines.
Workflow scanning supports a limited static subset of bash/sh; it executes no code.
Dynamic or unchecked workflow installs produce WARN, never proof of a matching pin.
Warnings allow exit code 0; a missing tag or a tag on another commit is a FAIL.
ShipState does not build packages or verify remote tags, releases, or registries.
See [the complete scope and limitations](docs/limitations.md) for parsing details.

## Roadmap

- Improve diagnostics for more packaging and workflow layouts.
- Add optional checks for release artifacts without introducing network access.
- Consider other package ecosystems only after the Python checks are stable.
