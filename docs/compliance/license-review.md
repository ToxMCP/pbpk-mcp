# License & SBOM Review

## Overview

This bridge depends on a Python stack (FastAPI, Celery, LangChain, OSPSuite adapters, etc.) and
on OSPSuite binaries distributed separately. To support auditability and downstream customer
reviews we now provide:

- A CycloneDX‐compatible software bill of materials generated from the current Python runtime.
- A quick reference of the dominant licenses and actions required for redistribution or SaaS
  deployments.

## SBOM generation

```
make sbom
```

The target executes `scripts/generate_sbom.py` which enumerates installed Python distributions
via `importlib.metadata` and emits `compliance/sbom.json`. The schema includes package name,
version, and discovered license metadata (from `License` field or `License ::` classifiers).

> Best practice: run `make sbom` on every release tag (and any environment with optional extras)
to capture the exact dependency graph alongside release artefacts.

## License highlights

- **FastAPI / Starlette** – MIT.
- **Pydantic** – MIT.
- **Celery / Kombu / Billiard** – BSD.
- **LangChain / LangGraph** – MIT.
- **Structlog** – Apache 2.0.
- **Redis client** – MIT.
- **Prometheus client** – Apache 2.0.
- **Boto3 / Botocore** – Apache 2.0 (ensure AWS SDK usage complies with AWS terms).
- **python-jose / cryptography** – MIT / Apache 2.0 and dual license; redistribution permitted.
- **pytest, ruff, black, mypy** – MIT style licenses (development only).

No copyleft GPL dependencies were detected in the Python environment. The generated SBOM should be
supplied with any binary or container distribution along with OSPSuite licence documentation.

## OSPSuite / PK-Sim® considerations

The OSPSuite automation components are distributed separately under their own licence terms. Ensure
redistribution or hosted access complies with Open Systems Pharmacology requirements. Include the
following in your deployment checklist:

1. Link to the OSPSuite EULA and version numbers bundled.
2. Document how PK-Sim/MoBi assets are sourced and validated (see parity suite artefacts).
3. Provide a contact for licence renewal/compliance questions.

## Next steps

- Automate SBOM generation in CI (export artefact on release workflow).
- Include third-party acknowledgement section in public documentation.
- Record acceptance from the legal/compliance stakeholder for each release train.
