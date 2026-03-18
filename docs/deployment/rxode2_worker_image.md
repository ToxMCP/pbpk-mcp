# rxode2 Worker Image

## Purpose

Use a dedicated worker image for `.R` PBPK model modules that depend on `rxode2`.

This is the recommended path because:

- the standard worker already works well for PK-Sim / MoBi `.pkml`
- `rxode2` and its compiled dependencies are significantly heavier than the OSPSuite runtime
- source-compiling `rxode2` inside a capped runtime worker is likely to fail under memory pressure

## Image Layout

The dedicated worker image is defined in:

- `docker/rxode2-worker.Dockerfile`

It extends:

- `pbpk_mcp-worker:latest`

and then bakes in:

- the `rxode2` R package
- the hybrid bridge in `scripts/ospsuite_bridge.R`
- the patched adapter in `patches/mcp_bridge/adapter/ospsuite.py`
- the patched validator in `patches/mcp/tools/load_simulation.py`
- the reference cisplatin model module in `cisplatin_models/cisplatin_population_rxode2_model.R`

## Build

From the workspace root:

```bash
./scripts/build_rxode2_worker_image.sh
```

With explicit tags:

```bash
BASE_IMAGE=pbpk_mcp-worker:latest IMAGE_TAG=pbpk_mcp-worker-rxode2:latest ./scripts/build_rxode2_worker_image.sh
```

The helper script defaults to:

- `PLATFORM=linux/amd64`

That matches the current local worker image. If the base worker image changes architecture later, override `PLATFORM` when building.

## Resource Guidance

Recommended practice:

- allow enough memory during image build for the `rxode2` compile
- keep the runtime worker capped conservatively after the image is built

That means:

- build time can use a larger builder or less constrained Docker Desktop configuration
- runtime can still stay around `4 GiB` if normal workloads fit there

## Validation

After build, check that `rxode2` is present:

```bash
docker run --rm pbpk_mcp-worker-rxode2:latest Rscript -e "cat(requireNamespace('rxode2', quietly=TRUE), '\n')"
```

You can also validate that the patched files were baked in:

```bash
docker run --rm pbpk_mcp-worker-rxode2:latest python -c "from mcp_bridge.adapter.ospsuite import SubprocessOspsuiteAdapter; print(sorted(SubprocessOspsuiteAdapter.SUPPORTED_EXTENSIONS))"
```

Expected output:

```text
['.pkml', '.r']
```

## Runtime Guidance

Keep the user-facing MCP unified and route by backend:

- `.pkml` models to the standard OSPSuite worker
- `.R` models to the dedicated `rxode2` worker

Do not treat raw Berkeley Madonna `.mmd` files as directly executable runtime inputs.

## Local Compose Deployment

For the current local workspace deployment, the repo now includes:

- `docker-compose.celery.yml`
- `scripts/deploy_rxode2_stack.sh`

This local stack uses `pbpk_mcp-worker-rxode2:latest` for both the API and the Celery worker so one machine can execute both `.pkml` and `.R` models without a second worker pool.

Bring the stack up or recreate it with:

```bash
./scripts/deploy_rxode2_stack.sh
```

Current local runtime behavior:

- `pbpk_mcp-worker-1` runs with a `4 GiB` memory cap
- the worker healthcheck uses `pgrep` against the Celery worker process
- PK-Sim / MoBi `.pkml` models remain supported on the same worker
- `rxode2` `.R` models work without hot-patching the running container

Longer-term, separate worker pools are still the cleaner production shape when OSPSuite-only and `rxode2` workloads need different scaling or isolation.
