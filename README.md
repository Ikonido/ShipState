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

ShipState 0.1.x supports Python projects with a static version in pyproject.toml.
It reads local files and invokes the local Git CLI only. It does not require a
remote or make network requests. Release tags and changelog headings use PEP 440
version equivalence. If multiple
equivalent tags exist, each must point to HEAD. README pin detection is regex-based
and limited to fenced/inline code and explicit install lines; ordinary prose is
ignored. Code spans and blocks are treated as examples, including dependency
snippets, so historical pins in code can still be reported. Package
names follow Python distribution normalization: `ship-state`, `ship_state` and
`ship.state` are equivalent, while `shipstate` is a different name.

Workflow YAML is parsed safely before inspecting a limited static bash/sh syntax.
Shell commands, GitHub expressions and environment variables are never executed.
Static exact self-package pins are compared with the project version. Dynamic
versions, ranges, direct URLs and local project installs warn rather than claiming
a version match. Warnings keep exit code 0 and the existing JSON status; they do
not prove that an unchecked install is consistent.

The scanner respects workflow/job/step shell and working-directory defaults.
Explicit bash/sh and known Linux/macOS runner defaults are supported; missing
runner declarations in workflow excerpts assume bash. Other shells and unknown
runner defaults warn when an install may involve the project. Quoted chain
operators are preserved. Here-documents, multiline quoting, substitutions,
functions, sourced code and other unsupported shell flow warn when relevant.
ShipState does not interpret `cd`, `pushd` or similar directory changes: subsequent
requirements paths and local installs warn instead of being read from a guessed
working directory. Wrapped directory commands and shell grouping also warn when
local requirement paths cannot be verified. Arbitrary scripts and their effects
are not inspected.

Known safe pip global options are accepted before `install`, with their declared
argument counts. Unknown options, opaque executables and unsupported install-like
commands warn instead of claiming that no pin exists. Explicit `PIP_*` settings
in workflow/job/step `env`, inline assignments or preceding exports are treated
as configuration ambiguity. This includes `PIP_REQUIREMENT`, `PIP_CONSTRAINT`,
index settings and `PIP_CONFIG_FILE`: their values and referenced files are not
interpreted or read. The scanner does not inspect ambient runner configuration;
even `--isolated` with explicit pip environment settings conservatively warns.
These warnings do not suppress a proven stale exact pin in the command's inline
arguments. POSIX backslash-newline continuations are removed without adding a
space; quoted assignment names are not treated as shell assignment prefixes.

Local `-r` includes request packages; `-c` includes only constrain versions and
never establish a self-package install on their own. A bare explicit self-package
request can use an unambiguous exact constraint in the same pip command. General
dependency/constraint resolution is not implemented; conflicting or conditional
constraints warn. Static requirement pins are inspected as declared; requirement
markers are not evaluated against a hypothetical CI environment.

Nested includes resolve relative to their file. Missing files, cycles, dynamic
paths and requirements paths outside the project warn. Workflow files and
directories outside the resolved project root are not read, including symlink
escapes. Non-string directory fields warn rather than being coerced to paths.

Missing build-system tables or required fields warn, and malformed fields fail;
backend-path directories must exist inside the project after resolving symlinks.
ShipState does not invoke a package build or import the configured backend, and it
does not verify remote tags, releases, or registry contents.

## Roadmap

- Improve diagnostics for more packaging and workflow layouts.
- Add optional checks for release artifacts without introducing network access.
- Consider other package ecosystems only after the Python checks are stable.
