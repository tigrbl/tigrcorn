# Release notes - tigrcorn 0.3.12

`tigrcorn` `0.3.12` is a patch release for the consolidated all-package publication lane.

## What changed

- removes the publish workflow dependency on inaccessible external `cobycloud/actions` reusable actions
- runs release validation through `bash ./scripts/ci/validate.sh` so executable bits do not block Linux runners
- keeps the manual workflow-dispatch surface for GitHub Release, PyPI, npmjs, and package selection
- bumps the Tigrcorn Python distributions to `0.3.12`
- bumps `@tigrcorn/wt-peer-probes` to `0.1.3`

## Publication target

This patch release is intended to publish all Tigrcorn Python distributions and all probe packages through the consolidated workflow with:

- GitHub Release enabled
- PyPI publication enabled
- npmjs publication enabled
- package selection set to `all`
