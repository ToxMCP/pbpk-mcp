# MCP Bridge Threat Model

## 1. Scope and Context
- **System**: Python FastAPI service embedding an ospsuite-backed R runtime via `rpy2`, exposing Model Context Protocol (MCP) tools.
- **Data**: Proprietary PBPK models (.pkml), parameter sets, simulation outputs, and audit logs.
- **Actors**: MCP Host agent, authenticated analysts, platform operators.
- **Trust Boundaries**:
  1. External callers → MCP Bridge HTTP API.
  2. Bridge service → R Adapter (`rpy2` bridge inside the container).
  3. Bridge → async job queue/worker subsystem.
  4. Bridge → storage for results and audit trail.

Security posture assumes containerised deployment on an internal network with enforced API authentication (Task 17) and audit requirements (Task 18).

## 2. Assets & Entry Points
| Asset / Interface | Description | Primary Threats |
| --- | --- | --- |
| Bridge API surface (`/load_simulation`, `/set_parameter_value`, etc.) | Authoritative control plane for simulations. | Spoofing, tampering, DoS |
| R runtime + ospsuite packages | Executes models and reads files. | Tampering, elevation of privilege |
| Job queue + workers | Runs long-lived simulations and retains handles. | Repudiation, DoS |
| Result storage | Holds time-series outputs, PK metrics. | Information disclosure, tampering |
| Audit trail | Immutable log of tool invocations. | Tampering, repudiation |

## 3. Key Assumptions
- API requests are mutually authenticated and authorised (implementation tracked in Task 17).
- Bridge container has read-only access to curated model directories; uploads are explicitly disallowed.
- R environment is pre-hardened with only required libraries.
- Underlying infrastructure provides TLS termination and network ACLs.

## 4. STRIDE Analysis & Mitigations

| Component | STRIDE | Threat Scenario | Mitigations (Current / Planned) | Validation Hooks | Residual Risk (Follow-up) |
| --- | --- | --- | --- | --- | --- |
| Bridge API Gateway | S | Attacker replays captured tokens to invoke mutation tools. | Enforce short-lived signed tokens, nonce checking, and correlationId logging. (Tasks 2 + 17) | Integration tests using expired/duplicate tokens; security scanner for replay | Requires auth scaffolding in Task 2 repo; token rotation policy TBD. |
| Bridge API Gateway | T | Crafted payload escalates to arbitrary file read via `load_simulation`. | Input validation + allow-listed model paths; drop `..`/UNC patterns; separate runtime identity for file IO. | Static analysis + `pytest` guardrail suite for traversal cases. | Need container FS policy to be codified in Task 2. |
| Bridge API Gateway | R | User denies issuing `set_parameter_value` that broke model. | Append immutable audit event with hashed payload and correlationId (Task 18). | Contract tests comparing logs to request/response. | Need log signing / WORM storage design (Task 18). |
| Bridge API Gateway | I | Force-run brute-force load to leak outputs. | Rate limiting per token, quotas, and job cap per simulation; degrade gracefully with 429. | Chaos test that spawns many jobs, observe throttle. | Rate limiter implementation scheduled in Task 2 backlog. |
| Bridge API Gateway | D | Flood of `/run_simulation` jobs starves legitimate workloads. | Bounded worker pool, queue length alerts, kill-switch to reject when queue > threshold. | Load test harness measuring latency vs. saturation. | Burst absorption policies depend on infra capacity sizing. |
| Bridge API Gateway | E | Overly broad privileges allow altering any model. | Role-based permissions aligning tools to roles (Task 17). | RBAC policy unit tests; attempt forbidden mutation in CI. | Policy authoring guidelines outstanding. |
| R Adapter (`rpy2`) | T | Malicious pkml executes R code during load. | Run R in sandboxed process namespace, disable `source()` from arbitrary directories, pre-validate pkml using schema checks. | PoC test using crafted pkml to confirm rejection. | Need deterministic pkml validator (Task 2). |
| R Adapter (`rpy2`) | I | Unbounded runtime hogs CPU/memory. | Enforce per-call timeout/CPU quotas via subprocess manager; kill hung sessions. | Stress simulation tests measuring resource ceilings. | Hardened cgroup limits to be wired in container spec (Task 2). |
| R Adapter (`rpy2`) | D | Crash propagates and tears down bridge. | Supervisor restarts adapter, circuit breaker trips after N failures. | Chaos experiment terminating R process. | Warm standby R session design still TBD. |
| Job Queue & Worker | R | No record of job submission parameters. | Persist job descriptors + digests alongside audit trail; include correlationId. | Worker integration test verifying log completeness. | Immutable store integration pending Task 18. |
| Job Queue & Worker | I | Attacker injects fake job result into queue. | Sign job payloads, verify before processing; restrict queue credentials to bridge identity. | Security test publishing forged message to staging queue. | Signature/credential management implemented with Task 2 infra. |
| Result Storage | I | Leakage of simulation outputs to unauthorised consumers. | Encrypt at rest, scoped access tokens, redact absolute paths before returning data. | Pen-test retrieving results with downgraded role. | Key management + KMS integration tracked for Task 2/17. |
| Audit Trail | T | Operator alters logs to hide misuse. | Append-only log store, periodic hash-chains, offloading to WORM storage. | Scheduled job verifying hash chain integrity. | Final WORM target selection assigned to Task 18. |
| Observability Pipeline | D | Log volume DoS due to verbose debug mode. | Dynamic log level controls, rate limiting of structured payloads, drop high-frequency debug fields in prod. | Chaos test toggling debug under load. | Logging backpressure design resides in Task 2. |

## 5. Logging & Tamper-Evidence Checkpoints
- Every tool invocation yields two log records: entry (validated input hash) and exit (result hash + outcome). Both carry `X-Correlation-Id` and caller identity.
- Audit trail snapshots are sealed hourly with SHA-256 hash chains and stored in read-only object storage.
- Parameter mutations capture pre/post values, caller metadata, unit conversions, and validation decisions for later reconstruction.

## 6. Validation & Testing Hooks
- **Static analysis**: linters enforce allow-listed filesystem paths and forbid raw `R` command execution outside the adapter boundary.
- **Integration tests**: simulate missing R runtime, malformed pkml, and queue saturation to verify error taxonomy alignment with OpenAPI definitions.
- **Chaos drills**: periodically kill the R process and validate automatic recovery without data loss.
- **Penetration tests**: focus on auth bypass, job forgery, and result leakage scenarios every release.

## 7. Residual Risks & Follow-up Actions
1. **Repository scaffolding (Task 2)** must codify file ACLs, resource cgroup settings, and queue credential isolation referenced above.
2. **Audit trail implementation (Task 18)** must supply WORM storage integration, log signing, and replay tooling to fulfil repudiation mitigations.
3. **Authentication & RBAC (Task 17)** remains critical for Spoofing/Elevation mitigations; align policy definitions with tool criticality.
4. **Key management** for encryption at rest awaits infra coordination; track under Task 2 deliverables.

This document should be revisited after the initial implementation of Tasks 2, 17, and 18 to confirm mitigations and update residual risks.
