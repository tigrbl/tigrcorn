# Release notes - tigrcorn 0.3.15

`tigrcorn` `0.3.15` is a patch release for the consolidated all-package publication lane.

## What changed

- refreshes the generated legacy unittest inventory so release gates pass on the current tree
- updates the structured-fields stale-reference allowlist for the current package layout
- preserves the manual workflow-dispatch surface for GitHub Release, PyPI, npmjs, and package selection
- bumps the Tigrcorn Python distributions to `0.3.15`
- bumps `@tigrcorn/wt-peer-probes` to `0.1.6`

## Publication target

This patch release is intended to publish all Tigrcorn Python distributions and all probe packages through the consolidated workflow with:

- GitHub Release enabled
- PyPI publication enabled
- npmjs publication enabled
- package selection set to `all`
