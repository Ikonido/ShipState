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
- Whether pip install pins for the project itself in YAML workflow `run` steps use the current version, including multiline commands, extras and local requirements/constraints files; dynamic versions or unresolved includes produce a warning.
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

Version 0.1 supports Python projects with a static version in pyproject.toml. It reads local files and invokes the local Git CLI only. It does not require a remote or make network requests. README pin detection is regex-based. Package names follow Python distribution normalization: `ship-state`, `ship_state` and `ship.state` are equivalent, while `shipstate` is a different name. Workflow YAML is parsed before analyzing shell install commands; commands and environment variables are never executed. Local requirements and constraints includes are checked relative to a step's static working directory (including workflow/job defaults), with nested includes resolved relative to their file. Paths outside the project, missing files, cycles and dynamic paths warn. Shell directory changes and arbitrary scripts are not interpreted. Missing build-system tables or required fields warn, and malformed fields fail; backend-path directories must exist inside the project. ShipState does not invoke a package build or import the configured backend, and it does not verify remote tags, releases, or registry contents.

## Roadmap

- Improve diagnostics for more packaging and workflow layouts.
- Add optional checks for release artifacts without introducing network access.
- Consider other package ecosystems only after the Python checks are stable.
