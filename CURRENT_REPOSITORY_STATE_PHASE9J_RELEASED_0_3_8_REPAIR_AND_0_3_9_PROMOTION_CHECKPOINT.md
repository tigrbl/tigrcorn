# Current repository state — Phase 9J released-0.3.8 repair and 0.3.9 promotion checkpoint

This checkpoint restores the originally released `0.3.8` conformance documentation from the released archive, creates a separate canonical `0.3.9` release root for the updated package line, and promotes `0.3.9` as the current release.

Current truth:

- historical released root preserved: `docs/review/conformance/releases/0.3.8/release-0.3.8`
- canonical current root: `docs/review/conformance/releases/0.3.9/release-0.3.9`
- public package version: `0.3.9`
- release notes: `RELEASE_NOTES_0.3.9.md`
- compileall: `True`
- targeted strict-validation pytest suite: `True` (`27` passed)
- broader certification-refresh pytest matrix: `True` (`99` passed)
- authoritative gate: `True`
- strict gate: `True`
- promotion target: `True`
- restored 0.3.8 tree identical to the released archive: `True` (`1308` files matched by hash)
