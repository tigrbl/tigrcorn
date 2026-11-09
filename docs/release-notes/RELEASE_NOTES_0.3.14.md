# Release notes - tigrcorn 0.3.14

`tigrcorn` `0.3.14` is a patch release for the consolidated all-package publication lane.

## What changed

- refreshes CI release validation to use the current governed test filenames
- adds the probe package repository URL required by npm provenance verification
- preserves the manual workflow-dispatch surface for GitHub Release, PyPI, npmjs, and package selection
- bumps the Tigrcorn Python distributions to `0.3.14`
- bumps `@tigrcorn/wt-peer-probes` to `0.1.5`

## Publication target

This patch release is intended to publish all Tigrcorn Python distributions and all probe packages through the consolidated workflow with:

- GitHub Release enabled
- PyPI publication enabled
- npmjs publication enabled
- package selection set to `all`
