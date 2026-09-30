# Changelog

## Unreleased

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
