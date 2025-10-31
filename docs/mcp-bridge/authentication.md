# Authentication & Access Control Design

## 1. Objectives

- Authenticate every HTTP request to the MCP Bridge using signed tokens.
- Authorise callers based on a least-privilege role model aligned with tool risk.
- Provide contextual identity metadata to the audit trail (Task 18) and logging.
- Support both production (OIDC/JWT) and developer (shared secret) deployments.

## 2. Token Strategy

| Aspect | Decision |
| --- | --- |
| Protocol | OAuth 2.0 client credentials and authorization code flows backed by an OpenID Connect (OIDC) identity provider (e.g., Azure AD, Auth0, Okta). |
| Token format | JWT (RS256 signature) containing `sub`, `iss`, `aud`, `exp`, `iat`, and custom `roles`/`scopes` claims; include `jti` to enable replay protection. |
| Verification | FastAPI dependency validates signature against JWKS endpoint, checks issuer/audience, expiry, and optional nonce to prevent replay. |
| Rotation | JWKS cache with TTL ≤ 15 minutes; tokens short-lived (≤ 15 minutes). Refresh handled by client via standard OAuth flows. |
| Local development | Optional HS256-signed tokens using `AUTH_DEV_SECRET`. When enabled, the server trusts tokens signed with the shared secret to ease local testing. |

### Token Acquisition

1. **Service accounts / agents** – use OAuth2 client credentials to obtain tokens scoped for automation (e.g., `mcp:operator`).
2. **Human analysts** – use authorization code + PKCE via a CLI helper or a UI. Resulting access token carries the analyst’s identity and roles.

Identity provider configuration (issuer URL, JWKS endpoint, expected audience) is supplied via environment variables. Production deployments **must** provide `AUTH_ISSUER_URL`, `AUTH_AUDIENCE`, and `AUTH_JWKS_URL`; the developer shortcut `AUTH_DEV_SECRET` is rejected outside `development`/`local` environments. Replay protection and rate limiting are controlled through `AUTH_REPLAY_WINDOW_SECONDS`, `AUTH_RATE_LIMIT_PER_MINUTE`, and `AUTH_CLOCK_SKEW_SECONDS`. Set `AUTH_ALLOW_ANONYMOUS=true` only for local automation or test harnesses—validation now rejects this flag in staging/production profiles to prevent accidental anonymous exposure. Tokens without an `exp` claim or those reusing the same `jti` inside the replay window are rejected.

## 3. Role Model

| Role | Capabilities | Description |
| --- | --- | --- |
| `viewer` | `list_parameters`, `get_parameter_value`, `get_job_status`, `get_simulation_results`, `get_population_results`, `calculate_pk_parameters` | Read-only access for analysts reviewing simulations. |
| `operator` | All viewer endpoints + `load_simulation`, `set_parameter_value`, `run_simulation`, `run_population_simulation`, `cancel_job` | Trusted users who can modify models and launch jobs. |
| `admin` | Operator rights + management endpoints (future), configuration reloads, health, metrics. |
| `system` | Non-interactive automation accounts (LangGraph agent, CI). Typically same permissions as `operator` but flagged as service accounts for auditing. |

Roles are conveyed via the `roles` claim (array of strings). Scopes (e.g., `mcp:read`, `mcp:operate`) can be used alternatively for providers that prefer OAuth scopes; a mapping layer will translate scopes to roles.

### Endpoint Enforcement

- Each FastAPI route declares required roles via a decorator/helper (`@require_roles("operator")`).
- The dependency verifies the token, attaches an `AuthContext` object to the request state (`request.state.auth`) including `subject`, `roles`, `token_id`, and `is_service_account` flag.
- Unauthorized requests receive `401` (missing/invalid token) or `403` (insufficient role) responses with error codes aligned to the existing error taxonomy.
- MCP tools invoked via LangGraph also consult the `AuthContext`; mutating tools re-check authorization to prevent bypassing route-level checks.

## 4. Implementation Plan

1. **Auth middleware & dependency**
   - Introduce `AuthContext` model and FastAPI dependency in `src/mcp_bridge/security/auth.py`.
   - Validate bearer tokens using `python-jose` or `authlib`; cache JWKS.
   - Populate request state and raise standardized exceptions on failure.

2. **Role enforcement**
   - Utility decorator / dependency to assert required roles.
   - Update route definitions in `src/mcp_bridge/routes/simulation.py` (and future routes) to declare required roles.

3. **Configuration**
   - Extend `AppConfig` with auth-related settings (issuer, audience, JWKS URL, dev secret, allowed clock skew).
   - Provide `.env` examples showing production vs. development configuration.

4. **Testing**
   - Unit tests for token verification (valid/invalid signature, expired, wrong audience, missing roles).
   - Integration tests hitting key endpoints with mock tokens to verify 401/403 handling.

5. **Logging & Audit Integration**
   - Include `AuthContext` fields (subject, roles, token id) in structured logs.
   - Pass identity details to the audit trail events (Task 18) via shared data structures.

## 5. Threat Mitigations

- **Replay attacks** – short-lived tokens, optional `jti` claim with replay cache for high-assurance deployments.
- **Privilege escalation** – fixed mapping of roles to endpoints; no implicit superuser role. Admin tasks separated.
- **Token leakage** – encourage TLS-only deployments; redact tokens in logs; support token revocation via IdP (respect `exp` and optionally call introspection endpoint for long-running requests).
- **Brute-force / abuse** – per-client rate limiting (`AUTH_RATE_LIMIT_PER_MINUTE`) throttles repeated authentication attempts and general API usage.
- **Development mode safeguards** – dev secret path is opt-in, disabled by default; warnings logged when active to prevent accidental production use.

## 6. Operational Runbook

- **Provisioning** – create clients/roles in IdP; document process to onboard analysts and service accounts.
- **Rotation** – schedule rotation for client secrets every 90 days; JWKS rotation handled automatically by cache.
- **Incident response** – ability to revoke tokens or disable clients; redeploy with updated `AUTH_ISSUER_URL` or `AUTH_JWKS_CACHE_SECONDS` as needed.

This design completes Task 17.1 and informs later implementation subtasks covering middleware, enforcement, and documentation.

## 7. Testing & Local Development

- **Dev tokens** – set `AUTH_DEV_SECRET` to enable HS256-signed tokens. The integration test suite uses this path (`tests/integration/test_auth_rbac.py`).
- **Environment guardrails** – the configuration rejects `AUTH_DEV_SECRET` unless `ENVIRONMENT` is `development`/`local`, preventing accidental deployment of shared secrets to staging or production environments.
- **Negative paths** – tests verify missing tokens (401), role denials (403), and signature tampering (401). Extend the suite with provider-specific failure cases as production integration progresses.
- **Manual checks** – generate tokens via `python -c 'from mcp_bridge.security.simple_jwt import jwt; print(jwt.encode({"sub": "local-op", "roles": ["operator"]}, "dev-secret", "HS256"))'` and call the API using `curl` with the `Authorization` header.
