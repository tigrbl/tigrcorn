# Commit governance

## Commit format

Preferred format:

- `feat(t): ...`
- `feat(p): ...`
- `feat(a): ...`
- `feat(d): ...`
- `feat(r): ...`
- `fix(t): ...`
- `fix(p): ...`
- `docs(gov): ...`
- `docs(readme): ...`
- `test(scope): ...`
- `cert(scope): ...`
- `rel(0.3.9): ...`

## Commit rules

- one commit should address one coherent unit of behavior or documentation
- boundary changes must not be hidden inside broad mixed commits
- release-promotion commits must mention the version and release root
- immutable-folder edits are forbidden; create a new versioned root instead

## Required commit notes

Each substantive commit should make the boundary impact obvious:

- in-bounds / out-of-bounds / no-boundary-change
- mutable folders touched
- tests or gates run
- version effect, if any
