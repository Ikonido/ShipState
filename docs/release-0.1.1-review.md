# ShipState 0.1.1 follow-up review

This follows the historical [repository review](repository-review.md). The
maintainer authorized preparing version 0.1.1, merging PR #7, and adding a new tag
on the resulting commit. The old v0.1.0 tag must remain unchanged. A published
GitHub Release and PyPI/TestPyPI uploads are outside this follow-up's actions.

## Changes

- Bump the static pyproject version, __version__, README tool-output example, and
  first versioned changelog heading to 0.1.1. Fixed fixture versions remain intact.
- Reject external symlinks in pyproject.toml, README.md, CHANGELOG.md, and all three
  license filenames with InputError: code 2, JSON status=error. This addresses the
  reproduced read outside the root from the original review. Internal symlinks
  and an explicitly symlinked project root remain supported. Cyclic input file
  symlinks are reported as input errors. No new runtime dependency or network call.
- Add release build/publish job time limits of 15/10 minutes and timeout=10 to both
  Git subprocesses in the publish workflow's verification script.
- Document exact Trusted Publisher fields and a separate TestPyPI procedure in
  [publishing.md](publishing.md). Both indices returned 404 for the public shipstate
  JSON endpoint; account settings cannot be verified with the available tools.

## Meaning of the migrated limitations

Compared every original topic with the final docs, not just word counts:

| Topic | Content preserved |
| --- | --- |
| Project and version | Static Python metadata, local files/Git, no remote or network requirement |
| Git tags and changelog | PEP 440 equivalence, all equivalent tags must identify HEAD |
| README pins | Code/install contexts, prose exclusion, historical code pins, name separators |
| Workflow scanning | Safe YAML, no execution, exact versus dynamic/non-exact/local pins |
| Shell syntax | Defaults, Linux/macOS bash/sh, unsupported shells/flow, quoted operators, cwd changes |
| pip environment/options | Option arity, opaque commands, explicit PIP_* ambiguity, no ambient config evaluation, inline drift, continuation/assignment rules |
| Requirements/constraints | Request versus constraint, bare-request exact constraints, markers, nested paths, cycles, missing/dynamic paths, escapes and non-string directories |
| Build system | Missing fields WARN, malformed fields FAIL, existing confined backend directories, no backend execution or remote registry checks |

Added clarifications retain existing caveats: warnings alone allow exit code 0;
a combined FAIL still exits 1; conflicting/conditional constraints are not a
verified pin. The only intentionally changed statement is the reproduced external
symlink behavior, now rejected under the maintainer's chosen stricter policy.

## CI gate and permissions

`tests.yml` runs tests on every push and pull_request. `release-consistency` has
`if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')`.
Thus it is deliberately SKIPPED for ordinary branch pushes and PRs, and blocks
v-prefixed tag runs if `shipstate check .` exits nonzero. There is no
continue-on-error. Missing tags still cause FAIL locally before tagging.

`publish.yml` runs only for published GitHub Releases. Its self-check is before
artifact builds. The publishing job needs the successful build job; a failed
self-check blocks publishing. No new publishing trigger was added.

All default/test/build permissions are contents: read. Only the publishing job
also has id-token: write, which PyPI Trusted Publishing requires. Existing action
SHA pins are unchanged. The old tag is never moved to satisfy a development check.

## Validation before merge

- Baseline: 584 passed on Python 3.12 before the follow-up.
- After symlink guard, CI timeouts, and version metadata blocks: 609 passed each.
- Final local suite: 609 passed on Python 3.11 and 3.12.
- 25 new regression cases cover all six input filenames, outside and dangling
  outside targets without content reads, internal targets, cyclic targets, and
  symlinked project roots.
- CLI text/JSON fields and exits remain intact, except the explicitly authorized
  rejection of external top-level input symlinks; version output becomes 0.1.1.

Merge SHA, remote tag creation, and post-tag CI are verified externally after this
review commit, to avoid inserting a self-referential commit SHA into the file.
