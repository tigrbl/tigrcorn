# Release notes - tigrcorn 0.3.13

`tigrcorn` `0.3.13` is a patch release for the consolidated all-package publication lane.

## What changed

- builds the WebTransport peer probe package before browser API validation in publish and reusable CI jobs
- keeps generated release workspace directories out of mutable tree governance scans
- preserves the manual workflow-dispatch surface for GitHub Release, PyPI, npmjs, and package selection
- bumps the Tigrcorn Python distributions to `0.3.13`
- bumps `@tigrcorn/wt-peer-probes` to `0.1.4`

## Publication target

This patch release is intended to publish all Tigrcorn Python distributions and all probe packages through the consolidated workflow with:

- GitHub Release enabled
- PyPI publication enabled
- npmjs publication enabled
- package selection set to `all`
