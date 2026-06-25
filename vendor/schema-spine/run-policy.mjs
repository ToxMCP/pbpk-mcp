#!/usr/bin/env node
// run-policy.mjs — single-object policy CLI for the Track-B scientific-invariants gate.
//
// Contract (kept deliberately tiny so the Python bridge can reason about every
// failure mode):
//   stdin  : exactly one JSON object (a projected spine object)
//   stdout : one JSON object  {"valid": <bool>, "failures": [{code,message,path}, ...]}
//   exit   : 0 always when stdout was written (the *bridge* decides blocking;
//            a non-zero exit is treated by the bridge as ENGINE_UNAVAILABLE)
//
// This CLI does NOT itself decide pass/fail policy or interpret recognized-ness;
// it is a thin, deterministic wrapper around validateScientificObjectPolicy from
// the vendored, digest-pinned engine. The fail-closed semantics (unrecognized
// schemaId, digest mismatch, timeouts, empty/garbled stdout) all live in the
// Python bridge (src/ivive_ber_mcp/governance/spine_bridge.py).

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { validateScientificObjectPolicy } from "./index.mjs";

const here = dirname(fileURLToPath(import.meta.url));

function readStdin() {
  // fd 0; read synchronously to keep the wrapper trivially deterministic.
  try {
    return readFileSync(0, "utf8");
  } catch {
    return "";
  }
}

function main() {
  const raw = readStdin();
  if (!raw || raw.trim() === "") {
    // Empty stdin is a usage error, not a valid:true. Emit a parse-failure shape
    // and exit non-zero so the bridge maps it to ENGINE_UNAVAILABLE / parse error.
    process.stdout.write(
      JSON.stringify({ valid: false, error: "EMPTY_STDIN" }) + "\n",
    );
    process.exit(2);
  }

  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (err) {
    process.stdout.write(
      JSON.stringify({ valid: false, error: "STDIN_NOT_JSON", detail: String(err && err.message) }) + "\n",
    );
    process.exit(3);
  }

  // Load the vendored digest manifest so manifest-aware invariants can run.
  let schemaManifest;
  try {
    schemaManifest = JSON.parse(
      readFileSync(join(here, "schema-manifest.json"), "utf8"),
    );
  } catch {
    schemaManifest = undefined;
  }

  const result = validateScientificObjectPolicy(payload, { schemaManifest });
  // Normalize to the documented shape.
  const out = {
    valid: result.valid === true,
    failures: Array.isArray(result.failures) ? result.failures : [],
  };
  process.stdout.write(JSON.stringify(out) + "\n");
  process.exit(0);
}

main();
