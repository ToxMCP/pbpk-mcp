# GitHub Branch Protection

This repository assumes `main` is protected in GitHub, not only by repository files.

## Intended `main` Ruleset

Use an active branch ruleset that targets `main` explicitly.

- require a pull request before merging
- require at least 1 approval
- require review from Code Owners
- dismiss stale approvals when new commits are pushed
- require conversation resolution before merging
- require status checks to pass
- require branches to be up to date before merging
- require linear history
- block force pushes
- restrict deletions

## Merge Policy

Preferred merge policy:

- allow squash merge
- optionally allow rebase merge
- avoid merge commits on `main`
- automatically delete merged head branches

If the repository is maintained primarily by one code owner, be careful with extra reviewer constraints that can block normal self-maintenance. `Require approval of the most recent reviewable push` should only be enabled when there is another trusted reviewer who can satisfy it.

## Required Checks

Use the actual workflow/check names that appear in GitHub for the current branch.

Minimum required checks should include the fast contributor gate:

- `CI`
- any check that covers lint/runtime-contract enforcement for normal PRs

Use the slower live-stack or release workflows as additional gates only when they are configured to run predictably on pull requests.

## Bypass Policy

Default recommendation:

- keep the bypass list empty

If an admin or automation app must bypass the ruleset, document that exception in release or maintainer notes. The repository intent is that trust-bearing changes reach `main` through review, not direct push.

## Why This Matters Here

`CODEOWNERS`, contributor docs, trust-surface tests, and release checks define the intended governance model, but GitHub branch protection is what actually enforces final control on `main`.
