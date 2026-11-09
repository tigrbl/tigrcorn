# Release notes - tigrcorn 0.3.11

`tigrcorn` `0.3.11` is a patch release for the fixed consolidated all-package publication lane.

## What changed

- repairs the all-package publication workflow so local Tigrcorn workspace packages are installed in one editable resolver pass
- points `cobycloud/actions` reusable action calls at the repository's existing `master` branch
- preserves the single workflow-dispatch surface for GitHub Release, PyPI, npmjs, and package selection
- bumps the Tigrcorn Python distributions to `0.3.11`
- bumps `@tigrcorn/wt-peer-probes` to `0.1.2`

## Publication target

This patch release is intended to publish all Tigrcorn Python distributions and all probe packages through the consolidated workflow with:

- GitHub Release enabled
- PyPI publication enabled
- npmjs publication enabled
- package selection set to `all`
