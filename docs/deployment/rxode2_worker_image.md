# rxode2 Worker Image

## Purpose

Use a dedicated worker image for `.R` PBPK model modules that depend on `rxode2`.

This is the recommended path because:

- the standard worker already works well for PK-Sim / MoBi `.pkml`
- `rxode2` and its compiled dependencies are significantly heavier than the OSPSuite runtime
- source-compiling `rxode2` inside a capped runtime worker is likely to fail under memory pressure

For the current local packaged and source-overlay operator workflows layered on top of this image, see [`runtime_patch_flow.md`](runtime_patch_flow.md).

## Image Layout

The dedicated worker image is defined in:

- `docker/rxode2-worker.Dockerfile`

It extends:

- `pbpk_mcp-worker:latest`

and then bakes in:

- the current `mcp-bridge` package installed into site-packages from this repo
- the `rxode2` R package
- the workspace `src/` tree at `/app/src` for the explicit overlay profile only
- the runtime overlay hook in `scripts/runtime_src_overlay.pth` for the explicit source-overlay maintainer profile
- the hybrid bridge in `scripts/ospsuite_bridge.R`
- the reference cisplatin model module in `cisplatin_models/cisplatin_population_rxode2_model.R`

The current `0.4.x` debt-reduction step removes the old image-build patch installer from this path. The worker Dockerfile now copies those baseline runtime assets directly into their final locations and validates the overlay hook plus both R files during the image build itself.

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
- `docker-compose.overlay.yml`
- `scripts/deploy_rxode2_stack.sh`
- `scripts/deploy_source_overlay_stack.sh`

This local stack uses `pbpk_mcp-worker-rxode2:latest` for both the API and the Celery worker so one machine can execute both `.pkml` and `.R` models without a second worker pool.

Bring the stack up or recreate it with:

```bash
./scripts/deploy_rxode2_stack.sh
```

Current local runtime behavior:

- `pbpk_mcp-worker-1` runs with a `4 GiB` memory cap
- the worker healthcheck uses `pgrep` against the Celery worker process
- PK-Sim / MoBi `.pkml` models remain supported on the same worker
- `scripts/deploy_rxode2_stack.sh` recreates the packaged local stack and keeps the workspace `var/` tree mounted for models and artifacts
- `scripts/deploy_source_overlay_stack.sh` is the explicit maintainer path when workspace `src/` and `scripts/` should override the baked image
- the local implementation is therefore packaged by default, with a thinner source-overlay development mode still available when needed

Longer-term, separate worker pools are still the cleaner production shape when OSPSuite-only and `rxode2` workloads need different scaling or isolation.
