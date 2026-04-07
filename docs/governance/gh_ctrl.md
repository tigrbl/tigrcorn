# GitHub control plane

## Purpose

This document defines the GitHub-side control plane required for the mutable working tree.

## Required controls

- protect `main` with PR-only merges and required checks
- protect `release/*` with required checks and disallow direct pushes
- protect version tags from force-update or deletion
- require GitHub Actions workflows to use full commit SHAs for external actions
- enable Dependabot, CodeQL, and artifact attestations
- define environments: `ci`, `staging`, `testpypi`, `pypi`, `docs`

## Repository-local implementation

The repository now contains:

- reusable and pinned GitHub Actions workflows under `.github/workflows/`
- a composite local action under `.github/actions/ci-shell/`
- repo-local CI entrypoints under `scripts/ci/`
- repo-local certification status tooling under `tools/cert/`

## Manual GitHub activation still required

The following settings cannot be enforced from this working tree alone and must be activated in the GitHub repository settings UI or by an authenticated GitHub administrator:

- rulesets for `main`, `release/*`, and tags
- required-status-check lists bound to those rulesets
- environment protection rules and secrets for `ci`, `staging`, `testpypi`, `pypi`, and `docs`
- organization or repository toggles for Dependabot alerts, CodeQL workflow execution, and artifact attestations

Until those settings are active on GitHub itself, the repository is not honest to claim that branch protection or environment policy is enforced remotely.
