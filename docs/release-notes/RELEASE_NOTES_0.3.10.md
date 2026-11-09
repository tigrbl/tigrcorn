# Release notes - tigrcorn 0.3.10

`tigrcorn` `0.3.10` is a patch release for the consolidated all-package publication lane.

## What changed

- added `.github/workflows/publish-all-packages.yml` as the single release flow for all Python Tigrcorn packages and probe packages
- replaced the separate PyPI and WebTransport probe publish workflows with one workflow-dispatch surface
- added dispatch checkboxes for GitHub Release, PyPI, and npmjs publication
- added package selection for all packages, Tigrcorn Python packages, probes, or one named package
- configured publication secrets as `PYPI_API_TOKEN` for TestPyPI/PyPI and `NPM_API_TOKEN` for npmjs
- bumped the Tigrcorn Python distributions to `0.3.10`
- bumped `@tigrcorn/wt-peer-probes` to `0.1.1`

## Publication target

This patch release is intended to publish all Tigrcorn Python distributions and all probe packages through the consolidated workflow with:

- GitHub Release enabled
- PyPI publication enabled
- npmjs publication enabled
- package selection set to `all`
