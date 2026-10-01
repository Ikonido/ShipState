# Scope and limitations

## Project and version

ShipState 0.1.x supports Python projects with a static version in pyproject.toml.
It reads local files and invokes the local Git CLI only. It does not require a
remote or make network requests.

## Git tags and changelog

Release tags and changelog headings use PEP 440
version equivalence. If multiple
equivalent tags exist, each must point to HEAD.

## README pin detection

README pin detection is regex-based
and limited to fenced/inline code and explicit install lines; ordinary prose is
ignored. Code spans and blocks are treated as examples, including dependency
snippets, so historical pins in code can still be reported. Package
names follow Python distribution normalization: `ship-state`, `ship_state` and
`ship.state` are equivalent, while `shipstate` is a different name.

## Workflow scanning

Workflow YAML is parsed safely before inspecting a limited static bash/sh syntax.
Shell commands, GitHub expressions and environment variables are never executed.
Static exact self-package pins are compared with the project version. Dynamic
versions, ranges, direct URLs and local project installs warn rather than claiming
a version match. Warnings keep exit code 0 and the existing JSON status; they do
not prove that an unchecked install is consistent.

Warnings alone allow exit code 0. If another finding is a FAIL, the combined
result remains `status=fail` with exit code 1.

## Shell syntax support

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

## pip options and PIP_* environment

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

## Requirements files and constraints

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

The root-confinement rules above apply to workflow files, requirements files,
and backend paths. The top-level pyproject, README, changelog, and license checks
currently follow file symlinks, including targets outside the project.

When an exact request also has conflicting or conditional self-package
constraints, the scanner reports that ambiguity rather than verifying that pin.

## Build system checks

Missing build-system tables or required fields warn, and malformed fields fail;
backend-path directories must exist inside the project after resolving symlinks.
ShipState does not invoke a package build or import the configured backend, and it
does not verify remote tags, releases, or registry contents.
