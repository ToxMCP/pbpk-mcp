"""Fail-closed Node bridge to the vendored schema-spine policy engine.

The engine (``vendor/schema-spine/policy-validator.mjs``, re-exported by
``index.mjs``) is pure JS with no runtime deps; the single-object CLI
``run-policy.mjs`` reads one JSON object on stdin and prints
``{"valid": bool, "failures": [...]}``.

This module shells out to that CLI and is **fail-closed by construction**: every
failure mode is turned into a BLOCKING synthetic finding, never a skip or a
pass. Specifically:

* missing ``node`` / non-zero exit / empty or unparseable stdout / timeout
  -> ``ENGINE_UNAVAILABLE`` (block);
* a vendored file whose sha256 no longer matches ``VENDORED_FROM.json``
  -> ``VENDOR_DIGEST_MISMATCH`` (block), checked BEFORE the engine runs;
* a submitted object whose ``schemaId`` is not in the engine's recognized set
  -> ``UNRECOGNIZED_SPINE_SCHEMA_ID`` (block), checked BEFORE trusting
  ``valid:true`` (the engine returns ``valid:true`` for unknown ids — a silent
  no-op this closes).

Only when the digest check passes, the schemaId is recognized, the subprocess
exits 0, and stdout parses to the documented shape is a ``valid:true`` trusted.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from governance.errors import (
    ENGINE_UNAVAILABLE,
    UNRECOGNIZED_SPINE_SCHEMA_ID,
    VENDOR_DIGEST_MISMATCH,
    BlockingFinding,
)

# --- vendored engine locations ----------------------------------------------

# .../governance/spine_bridge.py -> repo root is parents[1].
_REPO_ROOT = Path(__file__).resolve().parents[1]
_VENDOR_ROOT = _REPO_ROOT / "vendor" / "schema-spine"
_RUN_POLICY_CLI = _VENDOR_ROOT / "run-policy.mjs"
_INDEX_MJS = _VENDOR_ROOT / "index.mjs"
_VENDORED_FROM = _VENDOR_ROOT / "VENDORED_FROM.json"
_SCHEMA_MANIFEST = _VENDOR_ROOT / "schema-manifest.json"
_MANIFEST_NAME = "VENDORED_FROM.json"

# Bounded resource limits (fail closed at the boundary).
_TIMEOUT_SECONDS = 20.0
_MAX_INPUT_BYTES = 2 * 1024 * 1024  # 2 MiB cap on the serialized object


@dataclass(frozen=True)
class PolicyResult:
    """Outcome of validating one projected object via the bridge.

    ``valid`` is True ONLY when the engine returned ``valid:true`` AND every
    fail-closed guard (digest, recognized schemaId, healthy subprocess) passed.
    Any blocking finding (scientific or meta) forces ``valid`` False.
    """

    valid: bool
    findings: tuple[BlockingFinding, ...]

    @property
    def blocking_codes(self) -> tuple[str, ...]:
        return tuple(f.code for f in self.findings)


def _node_executable() -> str | None:
    return shutil.which("node")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_vendor_digests() -> BlockingFinding | None:
    """Recompute sha256 of every vendored file vs VENDORED_FROM.json.

    Returns a single ``VENDOR_DIGEST_MISMATCH`` blocking finding on the FIRST
    problem (missing manifest, untracked file, missing file, or mismatch), else
    ``None``. This runs before the engine so a tampered engine never executes.
    """
    if not _VENDORED_FROM.exists():
        return BlockingFinding.meta(
            VENDOR_DIGEST_MISMATCH,
            "Vendored engine manifest VENDORED_FROM.json is missing.",
            path=str(_VENDORED_FROM),
        )
    try:
        manifest = json.loads(_VENDORED_FROM.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return BlockingFinding.meta(
            VENDOR_DIGEST_MISMATCH,
            f"VENDORED_FROM.json could not be read/parsed: {exc}",
            path=str(_VENDORED_FROM),
        )
    recorded: dict[str, str] = manifest.get("fileDigests", {})
    if not recorded:
        return BlockingFinding.meta(
            VENDOR_DIGEST_MISMATCH,
            "VENDORED_FROM.json has an empty fileDigests map.",
            path=str(_VENDORED_FROM),
        )

    on_disk = {
        p.relative_to(_VENDOR_ROOT).as_posix(): p
        for p in _VENDOR_ROOT.rglob("*")
        if p.is_file() and p.name != _MANIFEST_NAME
    }

    # Untracked files would dodge the digest check entirely.
    untracked = sorted(set(on_disk) - set(recorded))
    if untracked:
        return BlockingFinding.meta(
            VENDOR_DIGEST_MISMATCH,
            f"Untracked vendored file(s) not in manifest: {', '.join(untracked)}",
            path=untracked[0],
        )

    for rel, expected in sorted(recorded.items()):
        path = on_disk.get(rel)
        if path is None:
            return BlockingFinding.meta(
                VENDOR_DIGEST_MISMATCH,
                f"Vendored file recorded in manifest is missing on disk: {rel}",
                path=rel,
            )
        if _sha256(path) != expected:
            return BlockingFinding.meta(
                VENDOR_DIGEST_MISMATCH,
                f"Vendored file digest mismatch (tamper): {rel}",
                path=rel,
            )
    return None


@lru_cache(maxsize=1)
def recognized_schema_ids() -> frozenset[str] | None:
    """Introspect the engine's RECOGNIZED_SCIENTIFIC_SCHEMA_IDS via Node.

    Returns the recognized set, or ``None`` if Node is unavailable / the
    introspection failed (the caller treats ``None`` as ENGINE_UNAVAILABLE, i.e.
    it cannot prove recognized-ness, so it fails closed). Cached for the process.
    """
    node = _node_executable()
    if node is None or not _INDEX_MJS.exists():
        return None
    script = (
        "import { RECOGNIZED_SCIENTIFIC_SCHEMA_IDS } from "
        f"{json.dumps(_INDEX_MJS.as_posix())};"
        "process.stdout.write(JSON.stringify([...RECOGNIZED_SCIENTIFIC_SCHEMA_IDS]));"
    )
    try:
        proc = subprocess.run(
            [node, "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            env=_subprocess_env(),
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        ids = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
        return None
    return frozenset(ids)


def _subprocess_env() -> dict[str, str]:
    """A minimal, predictable environment for the Node subprocess.

    We pass PATH through (so ``node`` resolves) but otherwise keep it lean; the
    engine reads nothing from env. This avoids inheriting surprising state.
    """
    env: dict[str, str] = {}
    for key in ("PATH", "HOME", "NODE_OPTIONS_DISABLED"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def validate_object(payload: dict[str, Any]) -> PolicyResult:
    """Validate one projected spine object, fail-closed.

    Order of guards (each a hard block, evaluated before trusting the engine):
      1. vendored-file digest integrity (VENDOR_DIGEST_MISMATCH);
      2. node present + engine introspectable (ENGINE_UNAVAILABLE);
      3. payload.schemaId in the recognized set (UNRECOGNIZED_SPINE_SCHEMA_ID);
      4. subprocess healthy + stdout parses (ENGINE_UNAVAILABLE);
      5. only then: trust the engine's {valid, failures}.
    """
    findings: list[BlockingFinding] = []

    # 1. Digest integrity FIRST — never run a tampered engine.
    digest_finding = verify_vendor_digests()
    if digest_finding is not None:
        return PolicyResult(valid=False, findings=(digest_finding,))

    # 2. Node + engine introspection.
    node = _node_executable()
    if node is None:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    "Node executable not found; cannot run the spine policy engine.",
                ),
            ),
        )
    if not _RUN_POLICY_CLI.exists():
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    f"Vendored run-policy CLI missing: {_RUN_POLICY_CLI}",
                    path=str(_RUN_POLICY_CLI),
                ),
            ),
        )

    recognized = recognized_schema_ids()
    if recognized is None:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    "Could not introspect the engine's recognized schemaId set.",
                ),
            ),
        )

    # 3. Recognized-id guard — closes the engine's silent valid:true no-op for
    #    unknown ids. Done in Python (not trusting the engine) so an unrecognized
    #    id can never sail through as a pass.
    schema_id = payload.get("schemaId")
    if not isinstance(schema_id, str) or schema_id not in recognized:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    UNRECOGNIZED_SPINE_SCHEMA_ID,
                    f"Projected object schemaId is not recognized by the engine: {schema_id!r}",
                    path="$.schemaId",
                    schemaId=schema_id,
                ),
            ),
        )

    # 4. Run the engine.
    try:
        serialized = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    f"Projected object is not JSON-serializable: {exc}",
                ),
            ),
        )
    encoded = serialized.encode("utf-8")
    if len(encoded) > _MAX_INPUT_BYTES:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    f"Projected object exceeds the {_MAX_INPUT_BYTES}-byte input cap.",
                ),
            ),
        )

    try:
        proc = subprocess.run(
            [node, str(_RUN_POLICY_CLI)],
            input=encoded,
            capture_output=True,
            timeout=_TIMEOUT_SECONDS,
            env=_subprocess_env(),
        )
    except subprocess.TimeoutExpired:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    f"Spine policy engine timed out after {_TIMEOUT_SECONDS}s.",
                ),
            ),
        )
    except OSError as exc:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    f"Spine policy engine could not be launched: {exc}",
                ),
            ),
        )

    if proc.returncode != 0:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    f"Spine policy engine exited non-zero ({proc.returncode}).",
                ),
            ),
        )

    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    if not stdout:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    "Spine policy engine produced empty stdout.",
                ),
            ),
        )
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    "Spine policy engine stdout was not valid JSON.",
                ),
            ),
        )

    # 5. Defensive envelope checks before trusting the verdict.
    if not isinstance(result, dict) or "valid" not in result:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    "Spine policy engine returned a malformed result envelope.",
                ),
            ),
        )

    raw_failures = result.get("failures", [])
    if not isinstance(raw_failures, list):
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    "Spine policy engine returned a malformed failures list.",
                ),
            ),
        )

    for item in raw_failures:
        if not isinstance(item, dict):
            findings.append(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    "Spine policy engine returned a malformed failure entry.",
                )
            )
            continue
        findings.append(
            BlockingFinding(
                code=str(item.get("code", "UNKNOWN_SPINE_CODE")),
                message=str(item.get("message", "")),
                path=str(item.get("path", "$")),
                origin="scientific",
                context={"schemaId": schema_id},
            )
        )

    engine_valid = result.get("valid") is True
    # valid is True ONLY when the engine said true AND we recorded no findings.
    valid = engine_valid and not findings
    return PolicyResult(valid=valid, findings=tuple(findings))


_BUNDLE_RUNNER = (
    "import {{ validateScientificBundlePolicy }} from {index};"
    "import {{ readFileSync }} from 'node:fs';"
    "const inp = JSON.parse(readFileSync(0, 'utf8'));"
    "const manifest = JSON.parse(readFileSync({manifest}, 'utf8'));"
    "const r = validateScientificBundlePolicy(inp.payloads, inp.bundlePolicyType,"
    " {{ schemaManifest: manifest }});"
    "process.stdout.write(JSON.stringify({{ valid: r.valid === true,"
    " failures: Array.isArray(r.failures) ? r.failures : [] }}));"
)


def validate_bundle(
    payloads: list[dict[str, Any]], bundle_policy_type: str
) -> PolicyResult:
    """Validate a BUNDLE of projected spine objects under a bundle policy type.

    This runs the vendored engine's ``validateScientificBundlePolicy`` over the
    EMITTED bundle so the bundle-level invariants (SEMANTIC_LOSS_EVENT_REQUIRED,
    SEMANTIC_LOSS_MUST_CONSTRAIN, ONTOLOGY_PROTECTIONS_MUST_BE_LINKED,
    NONCLAIM_BOUNDARY_MUST_PROTECT, ...) actually FIRE — previously the gate ran
    only per-object policy, so these bundle codes were advertised-but-uninvoked
    (a dead arm). Same fail-closed guards as ``validate_object``: vendored-file
    digest integrity, node presence, recognized schemaId for every member, and a
    healthy subprocess are checked before any ``valid:true`` is trusted.
    """
    # 1. Digest integrity FIRST.
    digest_finding = verify_vendor_digests()
    if digest_finding is not None:
        return PolicyResult(valid=False, findings=(digest_finding,))

    # 2. Node + engine present.
    node = _node_executable()
    if node is None or not _INDEX_MJS.exists() or not _SCHEMA_MANIFEST.exists():
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    "Node / vendored engine / schema manifest unavailable; cannot "
                    "run the bundle policy.",
                ),
            ),
        )

    # 3. Every member's schemaId must be recognized (no silent no-op member).
    recognized = recognized_schema_ids()
    if recognized is None:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    "Could not introspect the engine's recognized schemaId set.",
                ),
            ),
        )
    for member in payloads:
        sid = member.get("schemaId")
        if not isinstance(sid, str) or sid not in recognized:
            return PolicyResult(
                valid=False,
                findings=(
                    BlockingFinding.meta(
                        UNRECOGNIZED_SPINE_SCHEMA_ID,
                        f"Bundle member schemaId is not recognized: {sid!r}",
                        path="$.schemaId",
                        schemaId=sid,
                    ),
                ),
            )

    # 4. Run the bundle policy via an inline module (the vendored run-policy CLI is
    #    single-object only; we import the byte-pinned index.mjs, never a new file
    #    in the digest-checked vendor tree).
    script = _BUNDLE_RUNNER.format(
        index=json.dumps(_INDEX_MJS.as_posix()),
        manifest=json.dumps(_SCHEMA_MANIFEST.as_posix()),
    )
    try:
        serialized = json.dumps(
            {"payloads": payloads, "bundlePolicyType": bundle_policy_type},
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE, f"Bundle not JSON-serializable: {exc}"
                ),
            ),
        )
    if len(serialized) > _MAX_INPUT_BYTES:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    f"Projected bundle exceeds the {_MAX_INPUT_BYTES}-byte input cap.",
                ),
            ),
        )
    try:
        proc = subprocess.run(
            [node, "--input-type=module", "-e", script],
            input=serialized,
            capture_output=True,
            timeout=_TIMEOUT_SECONDS,
            env=_subprocess_env(),
        )
    except subprocess.TimeoutExpired:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE, "Spine bundle policy timed out."
                ),
            ),
        )
    except OSError as exc:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE, f"Spine bundle policy could not launch: {exc}"
                ),
            ),
        )
    if proc.returncode != 0:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE,
                    f"Spine bundle policy exited non-zero ({proc.returncode}).",
                ),
            ),
        )
    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    if not stdout:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE, "Spine bundle policy produced empty stdout."
                ),
            ),
        )
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE, "Spine bundle policy stdout was not JSON."
                ),
            ),
        )
    if not isinstance(result, dict) or "valid" not in result:
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE, "Spine bundle policy returned a malformed envelope."
                ),
            ),
        )
    raw_failures = result.get("failures", [])
    if not isinstance(raw_failures, list):
        return PolicyResult(
            valid=False,
            findings=(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE, "Spine bundle policy returned a malformed failures list."
                ),
            ),
        )
    findings: list[BlockingFinding] = []
    for item in raw_failures:
        if not isinstance(item, dict):
            findings.append(
                BlockingFinding.meta(
                    ENGINE_UNAVAILABLE, "Spine bundle policy returned a malformed failure entry."
                )
            )
            continue
        findings.append(
            BlockingFinding(
                code=str(item.get("code", "UNKNOWN_SPINE_CODE")),
                message=str(item.get("message", "")),
                path=str(item.get("path", "$")),
                origin="scientific",
                context={"bundlePolicyType": bundle_policy_type},
            )
        )
    valid = result.get("valid") is True and not findings
    return PolicyResult(valid=valid, findings=tuple(findings))
