# Runtime Patch Flow

## Purpose

`v0.3.1` keeps a patch-first runtime on purpose.

That means the authoritative live MCP contract is defined in:

- `patches/`
- `scripts/ospsuite_bridge.R`
- bundled MCP-ready `.R` model modules such as `cisplatin_models/cisplatin_population_rxode2_model.R`

and then applied into the running API and worker containers.

This document explains how that patch-first deployment works and how to operate it safely.

## Why This Exists

The current PBPK MCP contract converged faster than the underlying packaged source layout.

So for this stage:

- the user-facing and tested runtime contract is real
- the local stack is reproducible
- the image build and hot-patch flow use the same patch manifest
- migration into a pure packaged `src/` implementation is explicitly deferred

This is an operating model, not the long-term destination.

## Canonical Files

The shared runtime patch set is defined in:

- `scripts/runtime_patch_manifest.py`

That manifest is consumed by:

- `scripts/install_runtime_patches.py`
- `scripts/apply_rxode2_patch.py`
- `docker/rxode2-worker.Dockerfile`

It now carries both:

- patched runtime code
- published contract artifacts such as the capability matrix and PBPK-side object schemas/examples used by the live MCP resource surface

The important rule is:

- do not duplicate the runtime patch file list in new places
- update the shared manifest instead

## Operator Entry Points

Use these in order of preference:

### 1. Normal local redeploy

```bash
./scripts/deploy_rxode2_stack.sh
```

Use this when:

- you changed the current workspace patch set
- you want the running API and worker to match the current workspace state
- you recreated the containers and want the live MCP surface to stay aligned

What it does:

- recreates `redis`, `api`, and `worker`
- reapplies the shared runtime patch set to `pbpk_mcp-api-1` and `pbpk_mcp-worker-1`
- restarts the patched containers
- waits for stable `/health` and `/mcp/list_tools` responses before returning so follow-on live checks do not race a still-settling API process

### 2. Hardened local or operator redeploy

```bash
AUTH_ISSUER_URL="https://issuer.example" \
AUTH_AUDIENCE="pbpk-mcp" \
AUTH_JWKS_URL="https://issuer.example/.well-known/jwks.json" \
./scripts/deploy_hardened_stack.sh
```

Use this when:

- you want the same patch-first runtime contract with stricter auth defaults
- you are testing a non-anonymous deployment posture locally
- you want the API port bound through `PBPK_BIND_HOST` / `PBPK_BIND_PORT` instead of the base compose defaults

What it does:

- layers `docker-compose.hardened.yml` over `docker-compose.celery.yml`
- requires explicit auth settings before compose startup will succeed
- sets `AUTH_ALLOW_ANONYMOUS=false` and `ENVIRONMENT=production`
- reapplies the shared runtime patch set to `pbpk_mcp-api-1` and `pbpk_mcp-worker-1`
- waits for stable `/health` and `/mcp/list_tools` responses at the configured bind host/port before returning

### 3. Patch-only recovery

```bash
python3 scripts/apply_rxode2_patch.py --restart
```

Use this when:

- the containers are already running
- you changed only the patch-first runtime files
- you do not want a full stack recreate

By default it patches:

- `pbpk_mcp-api-1`
- `pbpk_mcp-worker-1`

### 4. Rebuild the worker image baseline

```bash
./scripts/build_rxode2_worker_image.sh
```

Use this when:

- the baked baseline image itself should change
- `rxode2` or image-baked patch assets need to be updated
- you want the image and the hot-patch path to start from the same newer baseline

This does not replace the patch-first flow. It updates the baseline image that the patch-first flow starts from.

## Verification Workflow

After deploy or patch:

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

`./scripts/deploy_rxode2_stack.sh` now includes a built-in readiness wait through `scripts/wait_for_runtime_ready.py`. That helper requires several consecutive successful `/health` and `/mcp/list_tools` probes before the deploy command exits, which reduces transient connection resets immediately after patch-driven restarts.

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

- lightweight CI for patch/runtime contract checks
- separate model-smoke workflow for Docker-backed live execution and uploaded smoke artifacts

## Failure Modes To Watch

### Container recreate dropped new tools

Symptom:

- `/mcp/list_tools` is missing a documented tool such as `validate_model_manifest`

Typical cause:

- the containers were recreated from the image but the runtime patch set was not reapplied

Fix:

```bash
python3 scripts/apply_rxode2_patch.py --restart
```

### Image build and hot-patch path diverged

Symptom:

- the image behaves differently from the patched running stack

Typical cause:

- a file list was changed in one place but not in the shared manifest-driven flow

Fix:

- update `scripts/runtime_patch_manifest.py`
- rebuild the image if needed
- redeploy with `./scripts/deploy_rxode2_stack.sh`

### Runtime format policy drift

Symptom:

- `.pksim5` or `.mmd` starts loading with inconsistent behavior

Fix:

- verify `patches/mcp/tools/load_simulation.py`
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

This flow should eventually be retired in favor of a pure packaged implementation.

That later milestone should:

- move the active runtime code out of `patches/`
- make `src/` the canonical implementation surface
- remove the need for runtime hot patching in normal local operation

Until then, this runtime patch flow is the supported maintainership path for the local PBPK MCP stack.
