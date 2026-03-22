# Runtime Overlay Flow

## Purpose

The local PBPK MCP stack now runs as a source-overlay development runtime.

That means the authoritative live contract comes from:

- the packaged `src/` implementation in the image
- the workspace `src/` tree bind-mounted at `/app/src`
- `scripts/runtime_src_overlay.pth`, which promotes `/app/src` ahead of the installed package
- the worker-image baseline assets baked by `docker/rxode2-worker.Dockerfile`
- the published packaged contract artifacts exposed through `mcp_bridge.contract`

This document explains how that local overlay deployment works and how to operate it safely.

## Why This Exists

The `0.4.x` line is reducing the old patch-first debt without breaking the live contract.

At the current stage:

- the user-facing and tested MCP contract is real
- the generic runtime now lives in packaged `src/`
- the worker image bakes the baseline R assets directly
- the local compose stack overlays workspace source through bind mounts instead of patch-copying files into running containers
- pure packaged runtime deployment is still the longer-term destination

This is a transitional operator model, but it is now materially simpler than the earlier hot-patch flow.

## Canonical Files

The local source-overlay stack is defined by:

- `docker-compose.celery.yml`
- `docker-compose.hardened.yml`
- `scripts/deploy_rxode2_stack.sh`
- `scripts/deploy_hardened_stack.sh`
- `scripts/wait_for_runtime_ready.py`
- `scripts/runtime_src_overlay.pth`
- `docker/rxode2-worker.Dockerfile`

The worker image now bakes:

- `src/` at `/app/src`
- `scripts/runtime_src_overlay.pth`
- `scripts/ospsuite_bridge.R`
- `cisplatin_models/cisplatin_population_rxode2_model.R`

The local compose stack then bind-mounts:

- `./src:/app/src`
- `./scripts:/app/scripts`
- `./var:/app/var`
- `./scripts/runtime_src_overlay.pth:/usr/local/lib/python3.11/site-packages/pbpk_mcp_runtime_src.pth:ro`

The live schema, capability-matrix, and contract-manifest resources now treat packaged `mcp_bridge.contract` content as authoritative. `scripts/check_installed_package_contract.py` is the maintainer gate that proves the generated package fallback still matches the published JSON artifacts after a non-editable local install.

## Operator Entry Points

Use these in order of preference.

### 1. Normal local redeploy

```bash
./scripts/deploy_rxode2_stack.sh
```

Use this when:

- you changed the current workspace source or runtime helper files
- you want the running API and worker to match the current workspace state
- you recreated the containers and want the live MCP surface to stay aligned

What it does:

- recreates `redis`, `api`, and `worker`
- keeps the local `src/`, `scripts/`, `var/`, and overlay `.pth` bind mounts in place
- waits for stable `/health` and `/mcp/list_tools` responses before returning so follow-on live checks do not race a still-settling API process

### 2. Hardened local or operator redeploy

```bash
AUTH_ISSUER_URL="https://issuer.example" \
AUTH_AUDIENCE="pbpk-mcp" \
AUTH_JWKS_URL="https://issuer.example/.well-known/jwks.json" \
./scripts/deploy_hardened_stack.sh
```

Use this when:

- you want the same local runtime contract with stricter auth defaults
- you are testing a non-anonymous deployment posture locally
- you want the API port bound through `PBPK_BIND_HOST` / `PBPK_BIND_PORT` instead of the base compose defaults

What it does:

- layers `docker-compose.hardened.yml` over `docker-compose.celery.yml`
- requires explicit auth settings before compose startup will succeed
- sets `AUTH_ALLOW_ANONYMOUS=false` and `ENVIRONMENT=production`
- waits for stable `/health` and `/mcp/list_tools` responses at the configured bind host/port before returning

### 3. Rebuild the worker image baseline

```bash
./scripts/build_rxode2_worker_image.sh
```

Use this when:

- the baked baseline image itself should change
- `rxode2` or image-baked runtime assets need to be updated
- you want the image baseline to catch up with the current packaged runtime

This does not replace the source-overlay workflow. It updates the baseline image that local overlays build on top of.

## Verification Workflow

After deploy:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/mcp/list_tools
python3 scripts/release_readiness_check.py
python3 scripts/workspace_model_smoke.py
```

These checks should confirm:

- the live version marker is correct
- the documented tool surface is present
- discovery, validation, deterministic results, and OECD report export still work
- `.pksim5` rejection still carries explicit conversion guidance
- the currently discovered runtime-supported models still load and execute through the live API

`./scripts/deploy_rxode2_stack.sh` includes a built-in readiness wait through `scripts/wait_for_runtime_ready.py`. That helper requires several consecutive successful `/health` and `/mcp/list_tools` probes before the deploy command exits, which reduces transient connection resets immediately after container recreate.

`./scripts/deploy_hardened_stack.sh` uses the same readiness helper, but targets the base URL derived from `PBPK_BIND_HOST` and `PBPK_BIND_PORT`. This lets the hardened overlay validate the same runtime contract without assuming the default `127.0.0.1:8000` bind target.

When you specifically want to exercise declared `rxode2` population support too, run:

```bash
python3 scripts/workspace_model_smoke.py --include-population
```

This emits `var/workspace_model_smoke_report.json` and gives you a catalog-wide view of:

- manifest state
- qualification state
- deterministic execution status
- stored result retrieval
- optional population smoke status

In the GitHub repository, the same smoke path should be treated as a release-grade verification step rather than a lightweight PR check. The recommended automation split is:

- lightweight CI for contract and packaging checks
- separate model-smoke workflow for Docker-backed live execution and uploaded smoke artifacts

## Failure Modes To Watch

### Container recreate is serving stale behavior

Symptom:

- `/mcp/list_tools` or `/mcp/resources/contract-manifest` does not reflect the current workspace state

Typical cause:

- the stack was not recreated after changing the local source-overlay files
- the wrong compose project or stale container is still running

Fix:

- rerun `./scripts/deploy_rxode2_stack.sh`
- verify `/health` and `/mcp/list_tools` again

### Image baseline and local overlay diverged

Symptom:

- the local stack works, but a clean image-based run does not

Typical cause:

- the workspace overlay is masking an out-of-date worker image baseline

Fix:

- rebuild with `./scripts/build_rxode2_worker_image.sh`
- rerun `./scripts/deploy_rxode2_stack.sh`
- rerun `python3 scripts/release_readiness_check.py`

### Runtime format policy drift

Symptom:

- `.pksim5` or `.mmd` starts loading with inconsistent behavior

Fix:

- verify `src/mcp/tools/load_simulation.py`
- rerun `python3 scripts/release_readiness_check.py`
- rerun `python3 scripts/workspace_model_smoke.py`

### Hardened overlay fails before startup

Symptom:

- `docker compose` aborts immediately when using `docker-compose.hardened.yml`

Typical cause:

- one or more required auth variables are unset:
  - `AUTH_ISSUER_URL`
  - `AUTH_AUDIENCE`
  - `AUTH_JWKS_URL`

Fix:

- export the required variables
- optionally set `PBPK_BIND_HOST` / `PBPK_BIND_PORT`
- rerun `./scripts/deploy_hardened_stack.sh`

## Deferred Work

This local overlay flow should eventually give way to a cleaner packaged runtime boundary.

That later milestone should:

- keep reducing the remaining local overlay-specific runtime surface
- make the packaged image/runtime boundary authoritative by default
- reduce the amount of local source overlay needed for normal development

Until then, this source-overlay flow is the supported maintainership path for the local PBPK MCP stack.
