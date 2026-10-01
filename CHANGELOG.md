# Changelog

## Unreleased

- Report cyclic input file symlinks as `project_file_unresolvable` on Python 3.13, where `Path.resolve()` no longer raises.
- Fix mypy errors, remove unused imports and sort imports; add ruff and mypy configuration.
- Declare Python 3.13 in the package classifiers.

## 0.1.1

- Reject top-level input file symlinks outside the project before reading their contents; report an input error while preserving internal symlink support.
- Bound release build/publish jobs and release-script Git subprocesses with timeouts.
- Include release documentation and test fixtures in source distributions.

- Keep workflow finding order deterministic when file names differ only by case.
- Check repository version metadata in tests and full release consistency in CI on version tags.
- Move detailed limitations to docs and document development and release procedures.

- Compare local release tags and changelog versions using PEP 440 equivalence.
- Limit README pin checks to code examples and explicit install commands to reduce prose false positives.
- Restrict test workflow permissions and pin its actions to immutable commits.

- Preserve distribution-name separators during pin normalization.
- Parse workflow YAML run steps and inspect local requirements/constraints includes.
- Warn about unresolved includes and uncommitted Git changes.
- Reject backend-path entries outside the project or pointing to missing directories.

## 0.1.0

- Add Python release-consistency checks for project metadata, Git tags on HEAD, changelog version headings, and supported non-empty LICENSE files.
- Detect stale README self-package pins with normalized package-name case and separators.
- Detect stale GitHub Actions self-package pins, including extras and multiline install commands; warn when workflow versions are dynamic.
- Warn when the build-system table, `requires`, or `build-backend` is missing; report malformed build-system fields as failures.
- Provide deterministic text and JSON output with distinct exit codes for passing checks, consistency failures, and input or tool errors.
