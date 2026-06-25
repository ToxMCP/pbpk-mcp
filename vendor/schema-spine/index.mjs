// Vendored public entry for @ngra-ai/toxmcp-schema-spine (Track-B pilot).
//
// VENDORED COPY — do not edit by hand. Synced from ToxMCP/toxmcp-schema-spine
// at the gitSha pinned in VENDORED_FROM.json. The vendor:verify step recomputes
// the sha256 of every file here against VENDORED_FROM.json and hard-fails on any
// mismatch, so this engine is digest-pinned and tamper-evident.
//
// Re-exports the policy enforcement (anti-overclaim / AI-provenance / human-
// review invariants) plus the recognized-input introspection the fail-closed
// bridge needs to reject inputs the engine does not actually reason about (an
// unrecognized schemaId otherwise returns {valid:true} — a silent no-op).
//
// NOTE: the upstream index.mjs imports from "./scripts/policy-validator.mjs";
// the vendored layout is flat, so this copy imports from "./policy-validator.mjs".
export {
  validateScientificObjectPolicy,
  validateScientificBundlePolicy,
  isUsableHumanReview,
  RECOGNIZED_SCIENTIFIC_SCHEMA_IDS,
  RECOGNIZED_BUNDLE_POLICY_TYPE_LIST,
  isRecognizedScientificSchemaId,
  isRecognizedBundlePolicyType,
} from "./policy-validator.mjs";
