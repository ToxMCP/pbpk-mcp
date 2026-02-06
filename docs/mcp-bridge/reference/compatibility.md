# Compatibility Matrix

The MCP bridge is validated against multiple OSPSuite releases to ensure the
subprocess adapter remains compatible with future upgrades. The table below is
maintained automatically by the `OSPSuite matrix` GitHub Actions job and should
be reviewed before cutting a release.

| OSPSuite Release | Container/Base Image | CI Job | Notes |
| --- | --- | --- | --- |
| 12.0.0 | `python:3.11-slim` (default Docker build) | `OSPSUITE matrix (12.0.0)` | Default runtime published with container artefacts. |
| 11.0.0 | `python:3.11-slim` | `OSPSUITE matrix (11.0.0)` | Legacy compatibility – ensures subprocess adapter handles older automation APIs. |

All matrix runs execute the adapter contract suite (`tests/unit/test_adapter_interface.py`) and
job service smoke (`tests/unit/test_job_service.py`). For additional coverage:

- Enable `MCP_RUN_R_TESTS=1` in the matrix job once OSPSuite binaries are available on the runner.
- Add OS-specific entries if Windows/macOS builds become part of the deployment strategy.

## Upgrading the matrix

1. Update the version list in `.github/workflows/ci.yml` under the `compatibility` job.
2. Bump the default `OSPSUITE_VERSION` build argument in the `Dockerfile`.
3. Rebuild the container (`make build-image`) and run `pytest tests/unit/test_adapter_interface.py` locally.
4. Once CI passes across all entries, update the table above.

## Troubleshooting

- **Version mismatch**: If the subprocess adapter requires new R libraries, document the dependency under `docs/mcp-bridge/reference/configuration.md` and update the Dockerfile installation steps.
- **CI failures**: Check `actions-runner` logs for environment variable mismatches (ensure `OSPSUITE_VERSION` propagates). Set `ACTIONS_STEP_DEBUG=true` for additional diagnostics.
- **Deprecations**: Note API changes in the OSPSuite changelog and link relevant issues; add regression tests where appropriate.

## Related resources

- [Configuration Reference](configuration.md)
- [Service Runbook](../../operations/runbook.md)
- [Change Management Checklist](../operations/change-management.md)
