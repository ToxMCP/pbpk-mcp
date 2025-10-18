# MCP Bridge Contracts Overview

This directory holds the API and interaction artefacts agreed for the MCP Bridge:

- `openapi.json` — comprehensive REST contract covering tool interfaces, schemas, and error payloads.
- `sequencediagrams.md` — sequence diagrams for core synchronous and asynchronous flows.
- `error-taxonomy.md` — mapped error codes, HTTP statuses, and logging expectations.

All responses include an `X-Correlation-Id` header and propagate structured errors as defined in the OpenAPI specification.
