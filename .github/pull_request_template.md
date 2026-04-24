## Summary

- what changed
- why it changed

## Validation

- [ ] I ran the relevant local tests for this change
- [ ] I updated docs when behavior, contracts, or workflow expectations changed
- [ ] I kept generated artifacts, secrets, and machine-local paths out of the patch

## Trust Surface

- [ ] This change does not widen scientific or regulatory claims
- [ ] If this change touched contracts, packaging, or trust-bearing summaries, I ran `make runtime-contract-test`
- [ ] If this change is release-facing, I reviewed `docs/release_readiness.md` and the linked publication/audit docs

## Notes For Reviewers

- any follow-up risk, migration note, or manual check
