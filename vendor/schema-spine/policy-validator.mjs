import { createHash } from "node:crypto";

// =============================================================================
// ToxMCP / NGRA.ai scientific-policy validator.
//
// ENFORCEMENT MODEL (read this before "strengthening" the free-text scanners):
//   The ROBUST, adversarially-tested controls are STRUCTURAL and operate on
//   typed/enumerated fields and machine tokens, NOT on free prose:
//     - claim-class escalation ladder (CLAIM_TRANSITION_*, no upward/lateral
//       pre-authorization into causal_support/adversity/risk/regulatory_translation),
//     - ClaimRecord high-stakes review gating (HIGH_CLAIM_*),
//     - downstream-use / accepted-claim AUTHORIZATION tokens, normalized
//       (NFKD + combining-strip + cross-script homoglyph fold + invisible-char
//       strip + separator fold) and backstopped by a residual-non-ASCII-LETTER
//       check so an UNMAPPED homoglyph still cannot launder a machine token,
//     - review/provenance, waiver-substance, public-repo, and digest/manifest checks.
//
//   The free-text overclaim scanners (FREE_TEXT_OVERCLAIM / *_OVERCLAIM /
//   PROTECTION_RECORD_FREE_TEXT_OVERCLAIM / AI_RECORD_FREE_TEXT_OVERCLAIM) are
//   BEST-EFFORT DEFENSE-IN-DEPTH against lazy/unintentional overclaims in human
//   prose. They are NOT — and a regex lexicon CANNOT be — robust against a
//   determined adversary writing natural language. ACCEPTED, DOCUMENTED residuals
//   (verified across 5 adversarial rounds; do NOT chase them with more regex —
//   it trades one false-positive/negative for another):
//     1. Pure paraphrase with no lexicon token ("will not cause any harm").
//     2. Negation-by-proximity: a comma-less benign negation within ~24 chars
//        of an assertion ("not dangerous it is safe") may suppress detection;
//        clause punctuation (. , ; :) and distance close the common forms.
//     3. Intra-word ASCII spacing ("s a f e") / unmapped narrative homoglyph /
//        multi-word phrase separator-joined in TRUE prose (kept un-folded so
//        "fail_safe"/"read-across" are not false-positived).
//     4. CONFUSABLE_MAP is a curated subset, not the full Unicode TR39 table;
//        narrative homoglyph coverage is best-effort (auth tokens are not).
//     5. A legitimate exotic-but-unmapped non-ASCII LETTER in an auth-token id
//        (e.g. Greek omega) trips the residual backstop — use ASCII ids.
//   In every residual case a class-level overclaim is still bounded by the
//   STRUCTURAL invariants above; only the advisory prose signal is weaker.
//   CONTRACT: callers MUST schema-validate (every schema is additionalProperties:
//   false) BEFORE policy validation — records under undeclared keys are out of scope.
// =============================================================================

const PUBLIC_CHANNELS = new Set(["public_preview", "public_release"]);
const AI_ASSISTED_STATES = new Set(["assisted", "generated", "adjudication_support"]);
const HIGH_CLAIM_CLASSES = new Set(["causal_support", "adversity", "internal_dose", "risk", "regulatory_translation"]);
const ONTOLOGY_BLOCKED_TARGETS = new Set(["causal_support", "adversity", "risk", "regulatory_translation"]);
// Escalation-blocked TARGET classes: an upward transition into any of these
// cannot be pre-authorized as allowed/allowed_with_review (see claimTransitionPolicy).
// internal_dose is deliberately excluded — exposure -> internal_dose is a
// legitimate dosimetry transition that the exposure pipeline depends on.
const ESCALATION_BLOCKED_TARGET_CLASSES = new Set(["causal_support", "adversity", "risk", "regulatory_translation"]);
const BIOACTIVITY_POD_ALIASES = new Set(["bioactivity_pod_mcp", "bioactivity-pod-mcp", "bioactivity_pod"]);
const WOE_ALIASES = new Set(["woe_ngra_synthesis_mcp", "woe-ngra-synthesis-mcp", "woe_mcp", "woe-mcp"]);
const IATA_ALIASES = new Set(["iata_mcp", "iata-mcp"]);
const EXPOSURE_ALIASES = new Set(["exposure_scenario_mcp", "exposure-scenario-mcp", "dietary_mcp", "dietary-mcp", "fate_mcp", "fate-mcp"]);
const PBK_ALIASES = new Set(["httk_ivive_engine", "httk-ivive-engine", "pbpk_mcp", "pbpk-mcp", "pbpk_previous", "pbpk-previous"]);
const IVIVE_BER_ALIASES = new Set(["ivive_ber_mcp", "ivive-ber-mcp"]);
const POPULATION_VARIABILITY_ALIASES = new Set(["population_variability_mcp", "population-variability-mcp", "population_variability_susceptibility_mcp", "population-variability-susceptibility-mcp", "population_variability_susceptibility", "population-variability-susceptibility"]);
const HIGH_READ_ACROSS_TARGETS = new Set(["mechanistic_support", "causal_support", "adversity", "risk", "regulatory_translation"]);
const POD_READY_STATUSES = new Set(["fit_for_prioritization", "risk_assessment_ready", "regulatory_submission_ready"]);
// Regulatory-TRANSLATION downstream uses a non-risk record (bioactivity PoD,
// internal exposure, population) must not authorize. Shared so the gates can't
// drift apart (round-5 widened only the ClaimRecord gate, leaving these narrow
// — a plain-ASCII "adi_derivation" passed a clean PoD). NOTE: PoD-TYPE tokens
// (noael/loael/bmd) are intentionally excluded here — those are points of
// departure, not risk translations.
const REGULATORY_TRANSLATION_USES = "tolerable daily intake|derived no effect level|margin of exposure|health[- ]?based guidance|guidance value|threshold of toxicological concern|safe dose|safe level|permitted daily exposure|occupational exposure limit|market authoriz|\\b(adi|rfd|tdi|dnel|oel|hbgv|pde|mrl|ttc)\\b";
const POD_BLOCKED_DOWNSTREAM_USE_PATTERN = new RegExp("risk|regulatory|safe|safety|advers|legal|compliance|acceptable daily intake|reference dose|" + REGULATORY_TRANSLATION_USES, "i");
const INTERNAL_EXPOSURE_BLOCKED_DOWNSTREAM_USE_PATTERN = new RegExp("risk|regulatory|safe|safety|legal|compliance|acceptable daily intake|reference dose|" + REGULATORY_TRANSLATION_USES, "i");
const INTERNAL_EXPOSURE_BLOCKED_HANDOFF_CLAIM_PATTERN = new RegExp("risk|regulatory|safe|safety|legal|compliance|acceptable daily intake|reference dose|validated pbpk|externally validated pbpk|qualified pbpk|" + REGULATORY_TRANSLATION_USES, "i");
const INTERNAL_EXPOSURE_BLOCKED_TARGET_CLAIM_CLASSES = new Set(["causal_support", "adversity", "risk", "regulatory_translation"]);
const POPULATION_BLOCKED_DOWNSTREAM_USE_PATTERN = new RegExp("individual|personal|person[-_ ]?specific|risk|regulatory|safe|safety|legal|compliance|diagnostic|deterministic|vulnerable[-_ ]?population[-_ ]?oracle|" + REGULATORY_TRANSLATION_USES, "i");
const POPULATION_BLOCKED_TARGET_CLAIM_CLASSES = new Set(["causal_support", "adversity", "risk", "regulatory_translation"]);
const SENSITIVE_SOCIAL_DESCRIPTOR_CLASSES = new Set(["race", "ethnicity", "ancestry", "nationality", "geography", "socioeconomic"]);
const RELEASE_GRADE_SIGNATURE_ALGORITHMS = new Set(["sha256_ed25519", "sha256_sigstore"]);
const RECOGNIZED_BUNDLE_POLICY_TYPES = new Set([
  "ontology_aop_context_handoff",
  "bioactivity_pod_woe_iata_handoff",
  "exposure_internal_exposure_ber_handoff",
  "population_variability_susceptibility_handoff",
  "control_plane_release_readiness"
]);
const CONTROL_PLANE_OVERCLAIM_PATTERN = /\b(certificate of analysis|regulatory acceptance|regulatory approval|regulatorily acceptable|approved for regulatory|fit for regulatory submission|cleared for market|market authorization|authorized for market|final safety conclusion|final safety clearance|safe for use|scientific validation|scientifically validated|world[- ]?class|10\/10|risk[- ]?free)\b/i;
// Negation scope is intra-sentence ([^.]{0,120}, not .{0,120}); a negation in a
// PRIOR sentence ("We do not market this. This server is scientifically
// validated.") no longer launders an overclaim in the next sentence.
const CONTROL_PLANE_NEGATION_PATTERN = /\b(not|no|without|prohibit(?:ed|s)?|excluded|cannot|must not|does not|do not|not evidence of|not a|not an)\b[^.,;:]{0,24}\b(certificate of analysis|regulatory acceptance|regulatory approval|regulatorily acceptable|approved for regulatory|fit for regulatory submission|cleared for market|market authorization|authorized for market|final safety conclusion|final safety clearance|safe for use|scientific validation|scientifically validated|world[- ]?class|10\/10|risk[- ]?free)\b/i;
const PROHIBITION_KEYWORD_GROUPS = [
  [/causal/i],
  [/ker/i, /key event relationship/i],
  [/advers/i],
  [/risk/i],
  [/regulatory/i]
];
const CLAIM_CLASS_RANK = new Map([
  ["not_assessed", 0],
  ["identity", 1],
  ["context_only", 1],
  ["association", 2],
  ["bioactivity", 3],
  ["mechanistic_support", 4],
  ["exposure", 4],
  ["causal_support", 5],
  ["internal_dose", 5],
  ["adversity", 6],
  ["risk", 7],
  ["regulatory_translation", 7]
]);
const ONTOLOGY_ALIASES = new Set(["annotation_ontology_mcp", "ontology_mcp", "ontology-mcp"]);
const AOP_ALIASES = new Set(["aop_mcp", "aop-mcp"]);
const SCHEMA_IDS = {
  aiModelUseRecord: "https://schemas.ngra.ai/toxmcp/AiModelUseRecord.v1.schema.json",
  assessmentRun: "https://schemas.ngra.ai/toxmcp/AssessmentRun.v1.schema.json",
  humanReviewRecord: "https://schemas.ngra.ai/toxmcp/HumanReviewRecord.v1.schema.json",
  releaseVisibilityPolicy: "https://schemas.ngra.ai/toxmcp/ReleaseVisibilityPolicy.v1.schema.json",
  claimRecord: "https://schemas.ngra.ai/toxmcp/ClaimRecord.v1.schema.json",
  evidenceAnchor: "https://schemas.ngra.ai/toxmcp/EvidenceAnchor.v1.schema.json",
  reviewState: "https://schemas.ngra.ai/toxmcp/ReviewState.v1.schema.json",
  claimTransitionPolicy: "https://schemas.ngra.ai/toxmcp/ClaimTransitionPolicy.v1.schema.json",
  handoffEnvelope: "https://schemas.ngra.ai/toxmcp/HandoffEnvelope.v1.schema.json",
  toxMcpObject: "https://schemas.ngra.ai/toxmcp/ToxMcpObject.v1.schema.json",
  uncertaintyRecord: "https://schemas.ngra.ai/toxmcp/UncertaintyRecord.v1.schema.json",
  semanticLossEvent: "https://schemas.ngra.ai/toxmcp/SemanticLossEvent.v1.schema.json",
  confidenceCeiling: "https://schemas.ngra.ai/toxmcp/ConfidenceCeiling.v1.schema.json",
  nonClaimBoundary: "https://schemas.ngra.ai/toxmcp/NonClaimBoundary.v1.schema.json",
  applicabilityBoundary: "https://schemas.ngra.ai/toxmcp/ApplicabilityBoundary.v1.schema.json",
  evidenceAdmissibility: "https://schemas.ngra.ai/toxmcp/EvidenceAdmissibility.v1.schema.json",
  assayStudyQuality: "https://schemas.ngra.ai/toxmcp/AssayStudyQuality.v1.schema.json",
  replicateDesign: "https://schemas.ngra.ai/toxmcp/ReplicateDesign.v1.schema.json",
  concentrationResponseDesign: "https://schemas.ngra.ai/toxmcp/ConcentrationResponseDesign.v1.schema.json",
  bioactivityObservation: "https://schemas.ngra.ai/toxmcp/BioactivityObservation.v1.schema.json",
  pointOfDepartureRecord: "https://schemas.ngra.ai/toxmcp/PointOfDepartureRecord.v1.schema.json",
  bioactivityPodReadiness: "https://schemas.ngra.ai/toxmcp/BioactivityPodReadiness.v1.schema.json",
  readAcrossJustification: "https://schemas.ngra.ai/toxmcp/ReadAcrossJustification.v1.schema.json",
  weightOfEvidenceEvaluation: "https://schemas.ngra.ai/toxmcp/WeightOfEvidenceEvaluation.v1.schema.json",
  iataStrategyDecision: "https://schemas.ngra.ai/toxmcp/IataStrategyDecision.v1.schema.json",
  exposureScenarioContext: "https://schemas.ngra.ai/toxmcp/ExposureScenarioContext.v1.schema.json",
  routeDoseEstimate: "https://schemas.ngra.ai/toxmcp/RouteDoseEstimate.v1.schema.json",
  tkParameterProvenance: "https://schemas.ngra.ai/toxmcp/TKParameterProvenance.v1.schema.json",
  freeConcentrationCorrection: "https://schemas.ngra.ai/toxmcp/FreeConcentrationCorrection.v1.schema.json",
  internalExposureSummary: "https://schemas.ngra.ai/toxmcp/InternalExposureSummary.v1.schema.json",
  comparabilityQualification: "https://schemas.ngra.ai/toxmcp/ComparabilityQualification.v1.schema.json",
  reverseDosimetryRecord: "https://schemas.ngra.ai/toxmcp/ReverseDosimetryRecord.v1.schema.json",
  bioactivityExposureRatioRecord: "https://schemas.ngra.ai/toxmcp/BioactivityExposureRatioRecord.v1.schema.json",
  populationProfile: "https://schemas.ngra.ai/toxmcp/PopulationProfile.v1.schema.json",
  sensitiveDescriptorPolicy: "https://schemas.ngra.ai/toxmcp/SensitiveDescriptorPolicy.v1.schema.json",
  subgroupDefinition: "https://schemas.ngra.ai/toxmcp/SubgroupDefinition.v1.schema.json",
  variabilityDimension: "https://schemas.ngra.ai/toxmcp/VariabilityDimension.v1.schema.json",
  modifierEvidenceLane: "https://schemas.ngra.ai/toxmcp/ModifierEvidenceLane.v1.schema.json",
  subgroupComparison: "https://schemas.ngra.ai/toxmcp/SubgroupComparison.v1.schema.json",
  susceptibilitySummary: "https://schemas.ngra.ai/toxmcp/SusceptibilitySummary.v1.schema.json",
  subgroupReviewPacket: "https://schemas.ngra.ai/toxmcp/SubgroupReviewPacket.v1.schema.json",
  transportCapability: "https://schemas.ngra.ai/toxmcp/TransportCapability.v1.schema.json",
  schemaSignature: "https://schemas.ngra.ai/toxmcp/SchemaSignature.v1.schema.json",
  validationEvidenceBundle: "https://schemas.ngra.ai/toxmcp/ValidationEvidenceBundle.v1.schema.json",
  auditEventChain: "https://schemas.ngra.ai/toxmcp/AuditEventChain.v1.schema.json",
  spineReleaseReadinessEvidenceOverlay: "https://schemas.ngra.ai/toxmcp/SpineReleaseReadinessEvidenceOverlay.v1.schema.json",
  spineBenchmarkSuiteEvidenceOverlay: "https://schemas.ngra.ai/toxmcp/SpineBenchmarkSuiteEvidenceOverlay.v1.schema.json",
  spineBenchmarkRunEvidenceOverlay: "https://schemas.ngra.ai/toxmcp/SpineBenchmarkRunEvidenceOverlay.v1.schema.json"
};

// --- Public consumer API: recognized-input introspection (for fail-closed bridges) ---
// A consumer (e.g. the ToxMCP Hub Node bridge) MUST NOT treat a bare {valid:true}
// from validateScientificObjectPolicy as a safe pass: an UNRECOGNIZED or missing
// schemaId, a non-object, or an empty object all return {valid:true} simply because
// no rule matched — not because the input was vetted. These exports let a consumer
// gate fail-closed on inputs this policy engine does not actually reason about, and
// keep the recognized-id list single-source-of-truth (no duplication downstream).
export const RECOGNIZED_SCIENTIFIC_SCHEMA_IDS = Object.freeze(
  Object.values(SCHEMA_IDS).slice().sort()
);
export const RECOGNIZED_BUNDLE_POLICY_TYPE_LIST = Object.freeze(
  [...RECOGNIZED_BUNDLE_POLICY_TYPES].slice().sort()
);
export function isRecognizedScientificSchemaId(schemaId) {
  return typeof schemaId === "string" && RECOGNIZED_SCIENTIFIC_SCHEMA_IDS.includes(schemaId);
}
export function isRecognizedBundlePolicyType(bundlePolicyType) {
  return RECOGNIZED_BUNDLE_POLICY_TYPES.has(bundlePolicyType);
}

function failure(code, message, path = "$") {
  return { code, message, path };
}

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function sha256Stable(value) {
  return `sha256:${createHash("sha256").update(stableStringify(value)).digest("hex")}`;
}

function auditEventHash(event) {
  const { eventHash, ...eventWithoutHash } = event;
  return sha256Stable(eventWithoutHash);
}

// Cross-script homoglyph fold (letters from other scripts that render like
// Latin). NFKD/NFKC does NOT fold these — they are distinct scripts, not
// compatibility equivalents — so e.g. a Cyrillic "а" (U+0430) or a Latin
// small-capital "ꜱ" (U+A731) reads as Latin to a human/consumer while dodging an
// ASCII regex. Built from code points so no confusable glyphs live in the source.
// This is a CURATED subset, not the full Unicode TR39 confusables table; the
// residual risk is handled structurally for the high-value case: AUTHORIZATION
// tokens get a residual-non-ASCII check (anyForbidden) so an UNMAPPED homoglyph
// still cannot launder a machine token. Narrative homoglyph coverage is
// best-effort (the structural claim-class invariants are the real backstop).
const CONFUSABLE_ENTRIES = [
  // Cyrillic
  [0x0430, "a"], [0x0435, "e"], [0x043e, "o"], [0x0440, "p"], [0x0441, "c"], [0x0443, "y"], [0x0445, "x"], [0x0455, "s"], [0x0456, "i"], [0x0458, "j"], [0x0432, "b"], [0x043a, "k"], [0x043c, "m"], [0x043d, "h"], [0x0442, "t"], [0x04bb, "h"], [0x0501, "d"], [0x04cf, "l"], [0x0454, "e"], [0x04ab, "c"], [0x049b, "k"],
  [0x0410, "a"], [0x0412, "b"], [0x0415, "e"], [0x041a, "k"], [0x041c, "m"], [0x041d, "h"], [0x041e, "o"], [0x0420, "p"], [0x0421, "c"], [0x0422, "t"], [0x0423, "y"], [0x0425, "x"], [0x0405, "s"], [0x0406, "i"], [0x0408, "j"],
  // Greek
  [0x03b1, "a"], [0x03b2, "b"], [0x03b5, "e"], [0x03b9, "i"], [0x03ba, "k"], [0x03bd, "v"], [0x03bf, "o"], [0x03c1, "p"], [0x03c4, "t"], [0x03c5, "u"], [0x03c7, "x"], [0x03f2, "c"], [0x03bc, "u"],
  [0x0391, "a"], [0x0392, "b"], [0x0395, "e"], [0x0397, "h"], [0x0399, "i"], [0x039a, "k"], [0x039c, "m"], [0x039d, "n"], [0x039f, "o"], [0x03a1, "p"], [0x03a4, "t"], [0x03a5, "y"], [0x03a7, "x"], [0x0396, "z"],
  // IPA / Latin Extended letterforms
  [0x0251, "a"], [0x0261, "g"], [0x0269, "i"], [0x026a, "i"], [0x0280, "r"], [0x0282, "s"], [0x0288, "t"], [0x028b, "v"], [0x028f, "y"], [0x0274, "n"], [0x0271, "m"], [0x017f, "s"], [0x0142, "l"], [0x0192, "f"], [0x0131, "i"],
  // Latin small-capital (Phonetic Extensions) + Latin Extended-D
  [0x1d00, "a"], [0x1d04, "c"], [0x1d07, "e"], [0x1d0a, "j"], [0x1d0b, "k"], [0x1d0d, "m"], [0x1d0f, "o"], [0x1d18, "p"], [0x1d1b, "t"], [0x1d1c, "u"], [0x1d20, "v"], [0x1d21, "w"], [0x1d22, "z"], [0xa730, "f"], [0xa731, "s"],
  // Armenian / letterlike symbols
  [0x0585, "o"], [0x0578, "n"], [0x212a, "k"], [0x212e, "e"], [0x2113, "l"]
];
const CONFUSABLE_MAP = Object.fromEntries(CONFUSABLE_ENTRIES.map(([code, ascii]) => [String.fromCharCode(code), ascii]));
const CONFUSABLE_PATTERN = new RegExp(`[${CONFUSABLE_ENTRIES.map(([code]) => String.fromCharCode(code)).join("")}]`, "g");
// Invisible / format characters to neutralize. Stripping the whole \p{Cf} class
// is allowlist-free and future-proof — it subsumes U+200B-200D ZW*, U+2060 word
// joiner AND its invisible-math siblings U+2061-2064, U+200E/200F bidi marks,
// U+00AD soft hyphen, U+FEFF BOM — plus the Hangul/Mongolian filler letters
// (category Lo, not Cf) which also render as nothing. None are legitimate inside
// a toxicology token or phrase.
const ZERO_WIDTH_PATTERN = new RegExp(`[\\p{Cf}${[0x115f, 0x1160, 0x3164, 0xffa0, 0x180e].map((code) => String.fromCharCode(code)).join("")}]`, "gu");

function normForms(value) {
  // NFKD (fold fullwidth / math-alphanumeric / NBSP-family / precomposed) -> drop
  // combining marks -> fold cross-script homoglyphs to Latin.
  const base = value.normalize("NFKD").replace(/\p{M}+/gu, "").replace(CONFUSABLE_PATTERN, (ch) => CONFUSABLE_MAP[ch]);
  // TWO boundary treatments of invisible chars, BOTH scanned: DELETING them
  // repairs an intra-word split ("sa<ZWSP>fe" -> "safe"); REPLACING them with a
  // space preserves an inter-word boundary ("reference<WJ>dose" -> "reference
  // dose"). Only WHITESPACE is collapsed here — underscores/hyphens are NOT
  // word-split in narrative ("fail_safe"/"read-across" must stay single tokens);
  // separator folding is applied ONLY to authorization tokens (see authTokenForms).
  const deleted = base.replace(ZERO_WIDTH_PATTERN, "").replace(/\s+/gu, " ").trim();
  const spaced = base.replace(ZERO_WIDTH_PATTERN, " ").replace(/\s+/gu, " ").trim();
  return deleted === spaced ? [deleted] : [deleted, spaced];
}

// Authorization-token forms: like normForms but ALSO fold separators (underscore,
// hyphen, and the Unicode dash family) to spaces, so snake/kebab machine tokens
// match the spaced lexicon ("adi_derivation" -> "adi derivation",
// "reference<en-dash>dose" -> "reference dose"). Used ONLY for the machine
// authorization arrays (allowedDownstreamUses / acceptedClaims / overlap) — NOT
// for narrative, where "fail_safe" must stay one word.
function authTokenForms(value) {
  return [...new Set(normForms(value).map((form) => form.replace(/[-_‐-―−⁃]+/gu, " ").replace(/\s+/g, " ").trim()))];
}

function normalizeForScan(value) {
  // Primary (zero-width-deleted) narrative canonical form; also the basis for the
  // residual-non-ASCII-letter authorization-token check (hasResidualNonAsciiLetter).
  return normForms(value)[0];
}

// Union of narrative + separator-folded token forms — for ENTITY / RATIONALE
// fields (evidenceAnchor.targetEntity, IATA rationale, model-identity strings,
// control-plane manifest text) where a separator-joined token like
// "regulatory_decision" must read as the phrase, yet the field is not a pure
// machine token. TRUE prose fields (knownLimitations etc.) keep normForms only,
// so "fail_safe"/"read-across" are not word-split there.
function bothForms(value) {
  return [...new Set([...normForms(value), ...authTokenForms(value)])];
}

function matchesForbiddenAnyForm(pattern, value) {
  return typeof value === "string" && bothForms(value).some((form) => pattern.test(form));
}

// ---- Overclaim lexicons + negation-aware matching ------------------------
// Shared negation lead. Excludes bare "no" (intrinsic to "poses no hazard"/"no
// toxicological concern", so it would let one phrase's "no" suppress a different
// phrase); genuine "no X" negations use the multi-word triggers, and
// conservative hazard framings ("far from", "anything but", "too uncertain to",
// "rules out") are included so honest disclosure is never mistaken for overclaim.
const NEGATION_LEAD = "not|without|cannot|can ?not|could not|never|nor|insufficient|fails? to|lacks?|isn'?t|aren'?t|wasn'?t|does ?n'?t|do ?n'?t|did ?n'?t|no claim|no assertion|no evidence|no support|no basis|unable to|far from|anything but|by no means|hardly|rules? out|ruling out|nothing shows|too uncertain to|stops? short of|precludes?";

function compileOverclaim(inner, wordBoundary = true) {
  const phrase = wordBoundary ? `\\b(?:${inner})\\b` : `(?:${inner})`;
  // Negation must ABUT the phrase: same clause (breaks on . , ; :) AND within a
  // short window. A wider window let a benign leading negation ("We did not
  // identify any data gaps, and the chemical is safe") launder a real overclaim
  // (round-10 finding); a clause-scoped adjacency keeps the honest-disclosure
  // fixes ("cannot be considered safe", "far from harmless") while closing it.
  return { overclaim: new RegExp(phrase, "i"), negated: new RegExp(`\\b(?:${NEGATION_LEAD})\\b[^.,;:]{0,24}${phrase}`, "i") };
}
// An overclaim counts only when ASSERTED — the lexicon matches in some
// normalization form with NO same-sentence negation preceding it (so honest
// "cannot be considered safe" / "far from harmless" passes). Scans both forms.
function isAssertedOverclaim(compiled, value) {
  return typeof value === "string" && normForms(value).some((form) => compiled.overclaim.test(form) && !compiled.negated.test(form));
}
// As isAssertedOverclaim, but over the separator-folded TOKEN forms — for machine
// authorization tokens (e.g. handoff acceptedClaims) where "safe_for_regulatory_use"
// must be read as the phrase "safe for regulatory use".
function isAssertedOverclaimToken(compiled, value) {
  return typeof value === "string" && authTokenForms(value).some((form) => compiled.overclaim.test(form) && !compiled.negated.test(form));
}

// GENERAL narrative lexicon (AiModelUseRecord / ToxMcpObject / ClaimRecord.claimText
// FREE_TEXT / Handoff acceptedClaims). Bare "causal"/"causes"/"adverse outcome"
// are OMITTED (honest "loses causal specificity" must pass; class-level causal/
// adversity overclaims are governed by the structural claim-class invariants).
const GENERAL_OVERCLAIM = compileOverclaim("safe|regulatorily acceptable|regulatory acceptance|legally compliant|individual risk|poses no hazard|harmless|fit for unrestricted use|no toxicological concern");
// Protection-record assertive safety phrases (ConfidenceCeiling/Uncertainty/SemanticLoss).
const PROTECTION_OVERCLAIM = compileOverclaim("is safe|are safe|deemed safe|considered safe|poses no hazard|harmless|fit for unrestricted use|unrestricted use|no toxicological concern");
// ClaimRecord.claimText assertion lexicons (substring matching preserved for
// "authoriz"/"permitted"; negation-aware so honest "this is not safe" is clean).
const ABSOLUTE_OVERCLAIM = compileOverclaim("safe|regulatorily acceptable|regulatory acceptance|legally compliant|approved|accepted|legally sufficient");
const REGULATORY_TRANSLATION_OVERCLAIM = compileOverclaim("compliant|accepted|approved|legally sufficient|authoriz|permitted|registered|cleared for market", false);
const CONTEXT_ONLY_OVERCLAIM = compileOverclaim("causal|causes|adverse|safe|risk", false);
// High-stakes ClaimRecord downstream-use gate — PoD-pattern breadth PLUS the
// regulatory-derivation lexicon (ADI/RfD/TDI/MRL/PDE/NOAEL/LOAEL/BMD/OEL/HBGV/
// TTC/market-authorization/margin-of-exposure/derivation/decision).
const HIGH_STAKES_DOWNSTREAM_USE_PATTERN = /risk|regulat|safety|safe|legal|complian|advers|causal|reference dose|acceptable daily intake|margin of exposure|market authoriz|guidance value|exposure limit|permitted daily exposure|threshold of toxicological concern|derivation|decision|\b(adi|rfd|tdi|mrl|pde|oel|noael|loael|bmd|bmdl|hbgv|ttc)\b/i;

function matchesForbidden(pattern, value) {
  // Narrative single-value match: scan BOTH normalization forms (NOT separator-folded).
  return typeof value === "string" && normForms(value).some((form) => pattern.test(form));
}

// A machine authorization/identifier token should be ASCII. A residual non-ASCII
// LETTER surviving normalization is an UNMAPPED homoglyph (the attack), flagged
// without enumerating glyphs. Non-letter typography (en-dash/degree/fraction) is
// NOT flagged; narrative is never subject to this check (it legitimately carries
// non-ASCII such as α-tocopherol / µg).
function hasResidualNonAsciiLetter(value) {
  return typeof value === "string" && /\p{L}/u.test(normalizeForScan(value).replace(/[\x00-\x7f]/g, ""));
}

function anyForbidden(values, pattern) {
  // Authorization-token arrays: separator-folded token forms + the residual-letter backstop.
  return Array.isArray(values) && values.some((value) =>
    (typeof value === "string" && authTokenForms(value).some((form) => pattern.test(form))) || hasResidualNonAsciiLetter(value));
}

function containsAnyOverclaimText(value) {
  if (typeof value === "string") {
    return isAssertedOverclaim(GENERAL_OVERCLAIM, value);
  }
  if (Array.isArray(value)) {
    return value.some(containsAnyOverclaimText);
  }
  if (value && typeof value === "object") {
    return Object.values(value).some(containsAnyOverclaimText);
  }
  return false;
}

function containsIataDecisionOverclaimText(value) {
  if (typeof value === "string") {
    return bothForms(value).some((form) => /\b(safe level|safe dose|safe exposure|safe threshold|acceptable exposure|acceptable exposure threshold|acceptable daily intake|reference dose|no risk|risk[- ]?free|regulatory decision|regulatory conclusion|final safety conclusion|legally sufficient|compliance threshold|acceptable for compliance|regulatory compliance)\b/i.test(form));
  }
  if (Array.isArray(value)) {
    return value.some(containsIataDecisionOverclaimText);
  }
  if (value && typeof value === "object") {
    return Object.values(value).some(containsIataDecisionOverclaimText);
  }
  return false;
}

function containsModelIdentityValidationOverclaim(value) {
  if (typeof value === "string") {
    return bothForms(value).some((form) =>
      /\b(model identity|model name|provider|codex|gpt|claude|gemini)\b.{0,80}\b(proves|guarantees|establishes|counts as|is sufficient for)\b.{0,80}\b(validation|scientific adequacy|regulatory acceptance)\b/i.test(form) ||
      /\bvalidated because\b.{0,80}\b(model|provider|codex|gpt|claude|gemini)\b/i.test(form));
  }
  if (Array.isArray(value)) {
    return value.some(containsModelIdentityValidationOverclaim);
  }
  if (value && typeof value === "object") {
    return Object.values(value).some(containsModelIdentityValidationOverclaim);
  }
  return false;
}

function hasBlockingReviewDecision(review) {
  return review.decision === "unknown_with_blocker" || review.decision === "rejected" || review.conflictDeclaration === "unknown_with_blocker";
}

function containsKeyword(values, pattern) {
  return values.some((value) => pattern.test(value));
}

function hasAllProhibitionKeywords(values) {
  return PROHIBITION_KEYWORD_GROUPS.every((group) => group.some((pattern) => containsKeyword(values, pattern)));
}

function hasInternalExposureProhibitionKeywords(values) {
  return [
    /risk/i,
    /regulatory/i,
    /safe|safety/i,
    /validated pbpk|externally validated pbpk|qualified pbpk|internal[-_ ]?dose without pbk/i
  ].every((pattern) => containsKeyword(values, pattern));
}

function hasPopulationProhibitionKeywords(values) {
  return [
    /individual|personal|person[-_ ]?specific/i,
    /risk/i,
    /regulatory/i,
    /safe|safety/i,
    /sensitive|proxy|demographic/i
  ].every((pattern) => containsKeyword(values, pattern));
}

function containsControlPlaneOverclaim(value) {
  if (typeof value === "string") {
    return bothForms(value).some((form) => CONTROL_PLANE_OVERCLAIM_PATTERN.test(form) && !CONTROL_PLANE_NEGATION_PATTERN.test(form));
  }
  if (Array.isArray(value)) {
    return value.some(containsControlPlaneOverclaim);
  }
  if (value && typeof value === "object") {
    return Object.values(value).some(containsControlPlaneOverclaim);
  }
  return false;
}

// Keys whose VALUES are identifiers, references, digests, or deliberate
// enumerations of forbidden concepts (prohibition/caveat lists). They are
// validated structurally elsewhere and must NOT be overclaim-scanned: a correct
// protective record must NAME the claims it forbids, and a hyphenated
// class-bearing id (e.g. "claim-causal-support-001") would otherwise
// false-positive. Every OTHER string leaf — all narrative/assertion text — is
// scanned, so an overclaim cannot be smuggled into a not-yet-enumerated field.
const OVERCLAIM_SCAN_EXEMPT_KEYS = new Set([
  "schemaId",
  "prohibitedClaims",
  "prohibitedDownstreamUses",
  "requiredCaveats",
  "acceptedClaims",
  "rejectedClaims",
  "allowedDownstreamUses",
  "blockers",
  // excludedUses enumerates the uses an artifact deliberately does NOT support
  // (e.g. "regulatory acceptance", "autonomous scientific validation"). Like the
  // prohibition lists above, it must NAME forbidden concepts as NEGATIVE claims,
  // so it is exempt; every other narrative field (intendedUse, claimBoundaries,
  // limitations, unresolvedRisks, ...) is still deep-scanned.
  "excludedUses"
]);

function isOverclaimScanExemptKey(key) {
  if (key === null) {
    return false;
  }
  return OVERCLAIM_SCAN_EXEMPT_KEYS.has(key) || /(Id|Ids|Ref|Refs|Digest|Digests)$/.test(key);
}

// Deep narrative overclaim scan: walks EVERY string leaf of an object except
// exempt (identifier/reference/prohibition) keys. Applies the bare-keyword
// scanner (safe/causal/adverse/individual-risk) AND the negation-aware
// control-plane scanner. Replaces the original hand-picked field allowlist,
// which an attacker stepped around by moving the overclaim one field over.
function containsDeepOverclaim(value, key = null) {
  if (isOverclaimScanExemptKey(key)) {
    return false;
  }
  if (typeof value === "string") {
    return containsAnyOverclaimText(value) || containsControlPlaneOverclaim(value);
  }
  if (Array.isArray(value)) {
    return value.some((item) => containsDeepOverclaim(item, key));
  }
  if (value && typeof value === "object") {
    return Object.entries(value).some(([childKey, childValue]) => containsDeepOverclaim(childValue, childKey));
  }
  return false;
}

// Protection records (ConfidenceCeiling/UncertaintyRecord/SemanticLossEvent)
// legitimately use words like "causal"/"adverse" in explanatory narrative
// (e.g. "loses ... causal specificity"), so the bare-keyword scanner would
// false-positive on correct protective text. Scan their narrative with the
// negation-aware control-plane scanner PLUS the assertive safety/no-risk
// phrases ("is safe", "poses no hazard", "harmless", "fit for unrestricted
// use") — those do not occur in legitimate protective description, so they are
// matched without negation suppression.
function containsDeepControlPlaneOverclaim(value, key = null) {
  if (isOverclaimScanExemptKey(key)) {
    return false;
  }
  if (typeof value === "string") {
    return containsControlPlaneOverclaim(value) || isAssertedOverclaim(PROTECTION_OVERCLAIM, value);
  }
  if (Array.isArray(value)) {
    return value.some((item) => containsDeepControlPlaneOverclaim(item, key));
  }
  if (value && typeof value === "object") {
    return Object.entries(value).some(([childKey, childValue]) => containsDeepControlPlaneOverclaim(childValue, childKey));
  }
  return false;
}

function hasSubstantiveWaiver(waiver) {
  return Boolean(waiver) && typeof waiver === "object" && !Array.isArray(waiver) &&
    ["waiverId", "reason", "approvedBy", "approvedAt"].every((field) => typeof waiver[field] === "string" && waiver[field].trim().length > 0);
}

function usesSensitiveSocialDescriptor(payload) {
  return (payload.descriptorClasses ?? []).some((descriptorClass) => SENSITIVE_SOCIAL_DESCRIPTOR_CLASSES.has(descriptorClass));
}

function isConstrainedPopulationUncertainty(payload) {
  return payload.propagationRule === "cap_confidence" || payload.propagationRule === "review_required" || payload.propagationRule === "block_claim";
}

function isConstrainedPopulationCeiling(payload) {
  return payload.maxSupportLevel !== "strong" && payload.maxActionability !== "decision_support";
}

function normalizeMcpName(name) {
  return name.trim().toLowerCase().replace(/\s+/g, "_");
}

function isOntologyAopHandoff(payload) {
  return ONTOLOGY_ALIASES.has(normalizeMcpName(payload.producer)) && AOP_ALIASES.has(normalizeMcpName(payload.consumer));
}

function isBioactivityPodWoeHandoff(payload) {
  return BIOACTIVITY_POD_ALIASES.has(normalizeMcpName(payload.producer)) && WOE_ALIASES.has(normalizeMcpName(payload.consumer));
}

function isWoeIataHandoff(payload) {
  return WOE_ALIASES.has(normalizeMcpName(payload.producer)) && IATA_ALIASES.has(normalizeMcpName(payload.consumer));
}

function isExposurePbkHandoff(payload) {
  return EXPOSURE_ALIASES.has(normalizeMcpName(payload.producer)) && PBK_ALIASES.has(normalizeMcpName(payload.consumer));
}

function isPbkIviveBerHandoff(payload) {
  return PBK_ALIASES.has(normalizeMcpName(payload.producer)) && IVIVE_BER_ALIASES.has(normalizeMcpName(payload.consumer));
}

function isExposureInternalExposureBerHandoff(payload) {
  return isExposurePbkHandoff(payload) || isPbkIviveBerHandoff(payload);
}

function isPopulationVariabilityHandoff(payload) {
  return POPULATION_VARIABILITY_ALIASES.has(normalizeMcpName(payload.producer)) && (WOE_ALIASES.has(normalizeMcpName(payload.consumer)) || IATA_ALIASES.has(normalizeMcpName(payload.consumer)));
}

function getProtectionId(payload) {
  if (payload.schemaId === SCHEMA_IDS.uncertaintyRecord) {
    return payload.uncertaintyId;
  }
  if (payload.schemaId === SCHEMA_IDS.semanticLossEvent) {
    return payload.semanticLossEventId;
  }
  if (payload.schemaId === SCHEMA_IDS.confidenceCeiling) {
    return payload.confidenceCeilingId;
  }
  if (payload.schemaId === SCHEMA_IDS.nonClaimBoundary) {
    return payload.boundaryId;
  }
  return null;
}

function getObjectId(payload) {
  if (payload.schemaId === SCHEMA_IDS.assayStudyQuality) return payload.assayStudyQualityId;
  if (payload.schemaId === SCHEMA_IDS.replicateDesign) return payload.replicateDesignId;
  if (payload.schemaId === SCHEMA_IDS.concentrationResponseDesign) return payload.concentrationResponseDesignId;
  if (payload.schemaId === SCHEMA_IDS.bioactivityObservation) return payload.bioactivityObservationId;
  if (payload.schemaId === SCHEMA_IDS.pointOfDepartureRecord) return payload.podId;
  if (payload.schemaId === SCHEMA_IDS.bioactivityPodReadiness) return payload.bioactivityPodReadinessId;
  if (payload.schemaId === SCHEMA_IDS.readAcrossJustification) return payload.readAcrossJustificationId;
  if (payload.schemaId === SCHEMA_IDS.weightOfEvidenceEvaluation) return payload.woeEvaluationId;
  if (payload.schemaId === SCHEMA_IDS.iataStrategyDecision) return payload.iataStrategyDecisionId;
  if (payload.schemaId === SCHEMA_IDS.exposureScenarioContext) return payload.exposureScenarioContextId;
  if (payload.schemaId === SCHEMA_IDS.routeDoseEstimate) return payload.routeDoseEstimateId;
  if (payload.schemaId === SCHEMA_IDS.tkParameterProvenance) return payload.tkParameterProvenanceId;
  if (payload.schemaId === SCHEMA_IDS.freeConcentrationCorrection) return payload.freeConcentrationCorrectionId;
  if (payload.schemaId === SCHEMA_IDS.internalExposureSummary) return payload.internalExposureSummaryId;
  if (payload.schemaId === SCHEMA_IDS.comparabilityQualification) return payload.comparabilityQualificationId;
  if (payload.schemaId === SCHEMA_IDS.reverseDosimetryRecord) return payload.reverseDosimetryRecordId;
  if (payload.schemaId === SCHEMA_IDS.bioactivityExposureRatioRecord) return payload.bioactivityExposureRatioRecordId;
  if (payload.schemaId === SCHEMA_IDS.populationProfile) return payload.populationProfileId;
  if (payload.schemaId === SCHEMA_IDS.sensitiveDescriptorPolicy) return payload.sensitiveDescriptorPolicyId;
  if (payload.schemaId === SCHEMA_IDS.subgroupDefinition) return payload.subgroupDefinitionId;
  if (payload.schemaId === SCHEMA_IDS.variabilityDimension) return payload.variabilityDimensionId;
  if (payload.schemaId === SCHEMA_IDS.modifierEvidenceLane) return payload.modifierEvidenceLaneId;
  if (payload.schemaId === SCHEMA_IDS.subgroupComparison) return payload.subgroupComparisonId;
  if (payload.schemaId === SCHEMA_IDS.susceptibilitySummary) return payload.susceptibilitySummaryId;
  if (payload.schemaId === SCHEMA_IDS.subgroupReviewPacket) return payload.subgroupReviewPacketId;
  if (payload.schemaId === SCHEMA_IDS.transportCapability) return payload.transportCapabilityId;
  if (payload.schemaId === SCHEMA_IDS.schemaSignature) return payload.signatureId;
  if (payload.schemaId === SCHEMA_IDS.validationEvidenceBundle) return payload.validationEvidenceBundleId;
  if (payload.schemaId === SCHEMA_IDS.auditEventChain) return payload.auditEventChainId;
  if (payload.schemaId === SCHEMA_IDS.spineReleaseReadinessEvidenceOverlay) return payload.overlayId;
  if (payload.schemaId === SCHEMA_IDS.spineBenchmarkSuiteEvidenceOverlay) return payload.overlayId;
  if (payload.schemaId === SCHEMA_IDS.spineBenchmarkRunEvidenceOverlay) return payload.overlayId;
  if (payload.schemaId === SCHEMA_IDS.releaseVisibilityPolicy) return payload.releasePolicyId;
  if (payload.schemaId === SCHEMA_IDS.evidenceAdmissibility) return payload.admissibilityId;
  if (payload.schemaId === SCHEMA_IDS.applicabilityBoundary) return payload.applicabilityId;
  if (payload.schemaId === SCHEMA_IDS.handoffEnvelope) return payload.handoffId;
  return getProtectionId(payload);
}

function isReleaseUsableValidationEvidence(payload) {
  return payload.evidenceStatus === "complete" && payload.integrityStatus === "verified" && ["reproducible", "partially_reproducible"].includes(payload.reproducibilityStatus);
}

function isPublicReleaseUsableValidationEvidence(payload) {
  return isReleaseUsableValidationEvidence(payload) && payload.licenseClearance === "cleared" && payload.dataRightsClearance === "cleared";
}

function isReleaseUsableSignature(payload) {
  return payload.verificationStatus === "verified" && payload.canonicalizationAlgorithm !== "not_assessed" && RELEASE_GRADE_SIGNATURE_ALGORITHMS.has(payload.signatureAlgorithm);
}

function isPublicReleaseUsableSignature(payload) {
  return isReleaseUsableSignature(payload) && payload.trustScope === "public_release";
}

function hasSubstantiveRefs(refs) {
  return refs.some((ref) => !/^(none|not[-_ ]?assessed|unknown|missing|null)$/i.test(ref));
}

function hasDomainExpertReview(records) {
  return records.some((record) =>
    isUsableHumanReview(record) &&
    ["toxicologist", "risk_assessor", "regulatory_expert"].includes(record.reviewerRole) &&
    ["adjudication", "final_signoff"].includes(record.reviewStage)
  );
}

function assessmentProducesBioactivityPod(payload) {
  const outputRefs = payload.outputObjectRefs ?? [];
  const outputSchemaRefs = payload.modelUseRecords.flatMap((record) => record.structuredOutputSchemaRefs ?? []);
  const nestedOutputRefs = payload.modelUseRecords.flatMap((record) => record.outputObjectRefs ?? []);
  return [...outputRefs, ...outputSchemaRefs, ...nestedOutputRefs].some((ref) =>
    matchesForbidden(/pod|point[-_ ]?of[-_ ]?departure|bioactivity|PointOfDepartureRecord|BioactivityObservation|BioactivityPodReadiness/i, ref)
  );
}

export function isUsableHumanReview(review) {
  // A waiver DEFERS review; it is not a usable review. Only an accepted or
  // corrected decision counts as review that actually happened. (Hardening:
  // previously "waived" was accepted here, letting a waiver launder as review.)
  return !hasBlockingReviewDecision(review) && (review.decision === "accepted" || review.decision === "corrected");
}

function addNestedFailures(failures, nestedResult, prefix) {
  for (const nestedFailure of nestedResult.failures) {
    failures.push({
      ...nestedFailure,
      path: `${prefix}${nestedFailure.path.slice(1)}`
    });
  }
}

function dedupeFailures(failures) {
  const seen = new Set();
  return failures.filter((item) => {
    const key = item.code;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

export function validateScientificObjectPolicy(payload, options = {}) {
  const failures = [];
  const manifestEntries = options.schemaManifest?.entries ?? [];
  const manifestById = new Map(manifestEntries.map((entry) => [entry.schemaId, entry]));

  if (payload.schemaId === SCHEMA_IDS.assessmentRun) {
    payload.modelUseRecords.forEach((record, index) => {
      const nestedResult = validateScientificObjectPolicy(record, options);
      addNestedFailures(failures, nestedResult, `$.modelUseRecords[${index}]`);
    });

    payload.humanReviewRecords.forEach((record, index) => {
      const nestedResult = validateScientificObjectPolicy(record, options);
      addNestedFailures(failures, nestedResult, `$.humanReviewRecords[${index}]`);
    });

    if (AI_ASSISTED_STATES.has(payload.aiUse) && payload.modelUseRecords.length === 0) {
      failures.push(failure("AI_MODEL_IDENTITY_REQUIRED", "AI-assisted assessments require at least one model-use record.", "$.modelUseRecords"));
    }

    if (payload.publicReleaseEligible && payload.aiUse === "unknown_with_blocker") {
      failures.push(failure("AI_UNKNOWN_WITH_PUBLIC_RELEASE", "Unknown AI use blocks public scientific release.", "$.aiUse"));
    }

    if (payload.aiUse === "none" && payload.modelUseRecords.length > 0) {
      failures.push(failure("AI_USE_NONE_WITH_MODEL_TRACE", "aiUse cannot be none when model-use records are present.", "$.modelUseRecords"));
    }

    if (payload.publicReleaseEligible && AI_ASSISTED_STATES.has(payload.aiUse) && payload.humanReviewRecords.length === 0) {
      failures.push(failure("HUMAN_REVIEW_REQUIRED_FOR_PUBLIC_AI_ASSESSMENT", "Public AI-assisted scientific assessments require human review.", "$.humanReviewRecords"));
    }

    if (payload.publicReleaseEligible && AI_ASSISTED_STATES.has(payload.aiUse) && payload.humanReviewRecords.length > 0 && !payload.humanReviewRecords.some(isUsableHumanReview)) {
      failures.push(failure("USABLE_HUMAN_REVIEW_REQUIRED", "Public AI-assisted assessments require at least one usable human review decision.", "$.humanReviewRecords"));
    }

    // Fire for ALL AI_ASSISTED_STATES (assisted / generated / adjudication_support),
    // not just "generated": relabelling a public PoD-producing run "assisted"
    // previously dodged the toxicologist/risk-assessor/regulatory-expert gate.
    if (payload.publicReleaseEligible && AI_ASSISTED_STATES.has(payload.aiUse) && assessmentProducesBioactivityPod(payload) && !hasDomainExpertReview(payload.humanReviewRecords)) {
      failures.push(failure("AI_GENERATED_POD_REQUIRES_DOMAIN_REVIEW", "AI-assisted or AI-generated bioactivity/PoD outputs require toxicologist, risk-assessor, or regulatory-expert review before public release.", "$.humanReviewRecords"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.aiModelUseRecord) {
    if (payload.publicReleaseEligible && payload.provider === "unknown_with_blocker") {
      failures.push(failure("AI_UNKNOWN_WITH_PUBLIC_RELEASE", "Unknown model provider blocks public release.", "$.provider"));
    }

    if (payload.rawPromptRetentionPolicy === "redacted_with_digest" && !payload.promptTemplateDigest) {
      failures.push(failure("PROMPT_REDACTION_DIGEST_REQUIRED", "Prompt redaction requires a stable digest.", "$.promptTemplateDigest"));
    }

    if (
      containsModelIdentityValidationOverclaim(payload.knownLimitations) ||
      containsModelIdentityValidationOverclaim(payload.assessmentRole) ||
      containsModelIdentityValidationOverclaim(payload.knownNondeterminism)
    ) {
      failures.push(failure("MODEL_IDENTITY_IS_NOT_VALIDATION", "Model identity is provenance and cannot be marketed as scientific validation.", "$.knownLimitations"));
    }

    // INVARIANT: deep-scan EVERY narrative string leaf (excluding identifiers/
    // references/digests), not a hand-picked field list. The earlier hardening
    // added knownNondeterminism beside knownLimitations, but the same overclaim
    // string still passed verbatim in modelName, modelVersionOrSnapshot,
    // endpointOrRuntime, deploymentRegion, etc. — the allowlist just moved the
    // goalposts one field over.
    if (containsDeepOverclaim(payload)) {
      failures.push(failure("AI_RECORD_FREE_TEXT_OVERCLAIM", "AI model-use free-text fields cannot carry scientific or regulatory overclaims.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.humanReviewRecord) {
    if (hasBlockingReviewDecision(payload)) {
      failures.push(failure("HUMAN_REVIEW_BLOCKED", "Human review is not usable when the decision, conflict declaration, or reviewer state is blocked.", "$.decision"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.releaseVisibilityPolicy) {
    // INVARIANT: a public repository on disk is itself a public-exposure event,
    // independent of the declared channel or the publicReleaseEligible flag.
    // Previously every gate keyed on publicReleaseEligible OR a public channel,
    // so repoVisibility="public" with publicReleaseEligible=false on an internal
    // channel sailed through with secrets unscanned and license uncleared. The
    // ToxMcpManifest path already enforces this for public repos; the dedicated
    // release-gating object must too. (Same codes as the channel gate, so the
    // dedupe merges them when both branches apply.)
    if (payload.repoVisibility === "public") {
      if (payload.licenseClearance !== "cleared") {
        failures.push(failure("PUBLIC_RELEASE_LICENSE_CLEARANCE_REQUIRED", "Public repository visibility requires license clearance.", "$.licenseClearance"));
      }
      if (payload.dataRightsClearance !== "cleared") {
        failures.push(failure("PUBLIC_RELEASE_DATA_RIGHTS_CLEARANCE_REQUIRED", "Public repository visibility requires data-rights clearance.", "$.dataRightsClearance"));
      }
      if (payload.secretsScan !== "passed") {
        failures.push(failure("PUBLIC_RELEASE_SECRETS_SCAN_REQUIRED", "Public repository visibility requires a passing secrets scan.", "$.secretsScan"));
      }
      if (payload.publicReleaseApproval !== "approved") {
        failures.push(failure("PUBLIC_RELEASE_APPROVAL_REQUIRED", "Public repository visibility requires explicit public-release approval.", "$.publicReleaseApproval"));
      }
    }

    if (payload.publicReleaseEligible && !PUBLIC_CHANNELS.has(payload.intendedReleaseChannel)) {
      failures.push(failure("PUBLIC_ELIGIBLE_REQUIRES_PUBLIC_CHANNEL", "Objects marked public-release eligible must use a public release channel.", "$.intendedReleaseChannel"));
    }

    if (payload.publicReleaseEligible && payload.repoVisibility !== "public") {
      failures.push(failure("PUBLIC_RELEASE_REPO_VISIBILITY_REQUIRED", "Public-release eligible objects require public repo visibility after explicit clearance.", "$.repoVisibility"));
    }

    if (PUBLIC_CHANNELS.has(payload.intendedReleaseChannel)) {
      if (payload.repoVisibility !== "public") {
        failures.push(failure("PUBLIC_RELEASE_REPO_VISIBILITY_REQUIRED", "Public releases require public repo visibility after explicit clearance.", "$.repoVisibility"));
      }
      if (payload.licenseClearance !== "cleared") {
        failures.push(failure("PUBLIC_RELEASE_LICENSE_CLEARANCE_REQUIRED", "Public releases require license clearance.", "$.licenseClearance"));
      }
      if (payload.dataRightsClearance !== "cleared") {
        failures.push(failure("PUBLIC_RELEASE_DATA_RIGHTS_CLEARANCE_REQUIRED", "Public releases require data-rights clearance.", "$.dataRightsClearance"));
      }
      if (payload.secretsScan !== "passed") {
        failures.push(failure("PUBLIC_RELEASE_SECRETS_SCAN_REQUIRED", "Public releases require a passing secrets scan.", "$.secretsScan"));
      }
      if (payload.publicReleaseApproval !== "approved") {
        failures.push(failure("PUBLIC_RELEASE_APPROVAL_REQUIRED", "Public releases require explicit approval.", "$.publicReleaseApproval"));
      }
    }
  }

  if (payload.schemaId === SCHEMA_IDS.claimRecord) {
    if (containsAnyOverclaimText(payload.claimText)) {
      failures.push(failure("FREE_TEXT_OVERCLAIM", "Claim text cannot carry hidden scientific or regulatory overclaims.", "$.claimText"));
    }

    if (isAssertedOverclaim(ABSOLUTE_OVERCLAIM, payload.claimText)) {
      failures.push(failure("ABSOLUTE_OR_REGULATORY_OVERCLAIM", "Claim text cannot assert safety, legal sufficiency, approval, or regulatory acceptance.", "$.claimText"));
    }

    if (payload.claimClass === "regulatory_translation" && isAssertedOverclaim(REGULATORY_TRANSLATION_OVERCLAIM, payload.claimText)) {
      failures.push(failure("REGULATORY_TRANSLATION_OVERCLAIM", "Regulatory translation cannot claim legal sufficiency or acceptance.", "$.claimText"));
    }

    if (payload.claimClass === "context_only" && isAssertedOverclaim(CONTEXT_ONLY_OVERCLAIM, payload.claimText)) {
      failures.push(failure("CONTEXT_ONLY_OVERCLAIM", "Context-only claims cannot assert causality, adversity, safety, or risk.", "$.claimText"));
    }

    if (payload.claimClass === "context_only" && (payload.supportLevel === "moderate" || payload.supportLevel === "strong" || payload.actionability === "decision_support")) {
      failures.push(failure("ONTOLOGY_CONFIDENCE_CEILING_EXCEEDED", "Ontology context-only claims cannot exceed weak support or become decision support without downstream review.", "$.supportLevel"));
    }

    if (payload.claimClass === "context_only" && anyForbidden(payload.allowedDownstreamUses, /risk|regulatory|causal|advers|ker|key event relationship/i)) {
      failures.push(failure("CONTEXT_ONLY_BAD_DOWNSTREAM_USE", "Context-only claims cannot authorize risk, regulatory, causal, KER, or adversity downstream uses.", "$.allowedDownstreamUses"));
    }

    if (payload.claimClass === "context_only" && !hasAllProhibitionKeywords(payload.prohibitedDownstreamUses)) {
      failures.push(failure("CONTEXT_ONLY_PROHIBITIONS_REQUIRED", "Context-only claims must explicitly prohibit causal, KER, adversity, risk, and regulatory downstream claims.", "$.prohibitedDownstreamUses"));
    }

    // INVARIANT: high-stakes claim classes (causal_support, adversity,
    // internal_dose, risk, regulatory_translation) need a human review pathway,
    // and cannot be strong / decision-support / authorize risk- or
    // regulatory-grade downstream use unless review has ACTUALLY occurred
    // (human_reviewed or adjudicated). A bare "strong, decision_support risk
    // claim authorizing regulatory_submission with requiredReviewState
    // not_assessed" previously passed with zero failures, standalone and inside
    // every bundle (bundle validators never re-inspect arbitrary ClaimRecords).
    if (HIGH_CLAIM_CLASSES.has(payload.claimClass)) {
      const reviewPathwayPresent = ["human_review_required", "human_reviewed", "adjudicated"].includes(payload.requiredReviewState);
      const reviewActuallyDone = ["human_reviewed", "adjudicated"].includes(payload.requiredReviewState);
      const authorizesHighStakesUse = anyForbidden(payload.allowedDownstreamUses, HIGH_STAKES_DOWNSTREAM_USE_PATTERN);
      if (payload.requiredReviewState !== "blocked" && !reviewPathwayPresent) {
        failures.push(failure("HIGH_CLAIM_REQUIRES_REVIEW", "High-stakes claim classes require a human review pathway (human_review_required, human_reviewed, or adjudicated).", "$.requiredReviewState"));
      }
      if ((payload.supportLevel === "strong" || payload.actionability === "decision_support" || authorizesHighStakesUse) && !reviewActuallyDone) {
        failures.push(failure("HIGH_CLAIM_STRONG_SUPPORT_REQUIRES_REVIEW", "High-stakes claims cannot be strong, decision-support, or authorize risk/regulatory downstream use unless human review has actually occurred (human_reviewed or adjudicated).", "$.supportLevel"));
      }
    }
  }

  if (payload.schemaId === SCHEMA_IDS.evidenceAnchor) {
    if (payload.evidenceClass === "aop" && payload.role === "context" && (payload.supportDirection !== "context_only" || matchesForbiddenAnyForm(/ker|key event relationship|causal/i, payload.targetEntity))) {
      failures.push(failure("AOP_CONTEXT_NOT_KER_EVIDENCE", "AOP context handoff cannot be treated as KER truth or primary causal evidence.", "$.targetEntity"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.reviewState) {
    if (payload.publicationReadiness === "ready" && payload.blockers.length > 0) {
      failures.push(failure("READY_WITH_BLOCKERS", "Publication readiness cannot be ready while blockers remain.", "$.blockers"));
    }

    if (payload.publicationReadiness === "ready" && payload.machineReview !== "passed") {
      failures.push(failure("READY_WITH_FAILED_MACHINE_REVIEW", "Publication readiness cannot be ready unless machine review passed.", "$.machineReview"));
    }

    if (payload.publicationReadiness === "ready" && payload.humanReview === "required") {
      failures.push(failure("READY_WITH_PENDING_HUMAN_REVIEW", "Publication readiness cannot be ready while human review is still required.", "$.humanReview"));
    }

    // Hardening: "ready" cannot be reached by skipping review. Only a completed
    // review, or a formally documented waiver, qualifies — not_required/failed
    // (and waived without a waiver) cannot publish.
    if (payload.publicationReadiness === "ready" && (payload.humanReview === "not_required" || payload.humanReview === "failed")) {
      failures.push(failure("READY_WITHOUT_HUMAN_REVIEW", "Publication readiness cannot be ready unless human review is completed or formally waived with a documented waiver.", "$.humanReview"));
    }

    // Presence is not enough — an empty/hollow waiver {} previously laundered a
    // "ready" publication that skipped human review. Require waiver substance.
    if (payload.humanReview === "waived" && !hasSubstantiveWaiver(payload.waiver)) {
      failures.push(failure("HUMAN_REVIEW_WAIVED_WITHOUT_WAIVER", "A waived human review requires a documented waiver with a non-empty waiverId, reason, approver, and approval timestamp.", "$.waiver"));
    }

    if (payload.publicationReadiness === "ready" && payload.adjudication === "blocked") {
      failures.push(failure("READY_WITH_BLOCKED_ADJUDICATION", "Publication readiness cannot be ready when adjudication is blocked.", "$.adjudication"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.claimTransitionPolicy) {
    const sourceRank = CLAIM_CLASS_RANK.get(payload.sourceClaimClass) ?? 0;
    const targetRank = CLAIM_CLASS_RANK.get(payload.targetClaimClass) ?? 0;
    if ((payload.transitionStatus === "allowed" || payload.transitionStatus === "allowed_with_review") && (payload.sourceClaimClass === "context_only" || payload.sourceClaimClass === "association") && payload.targetClaimClass === "causal_support") {
      failures.push(failure("SEMANTIC_MAPPING_NOT_CAUSALITY", "Semantic/context mappings cannot be promoted directly to causal support.", "$.targetClaimClass"));
    }

    if ((payload.transitionStatus === "allowed" || payload.transitionStatus === "allowed_with_review") && payload.sourceClaimClass === "bioactivity" && payload.targetClaimClass === "adversity") {
      failures.push(failure("BIOACTIVITY_NOT_ADVERSITY", "Bioactivity cannot be promoted directly to adversity without WoE review.", "$.targetClaimClass"));
    }

    if ((payload.transitionStatus === "allowed" || payload.transitionStatus === "allowed_with_review") && payload.sourceClaimClass === "context_only" && payload.targetClaimClass === "risk") {
      failures.push(failure("CONTEXT_ONLY_NOT_RISK", "Context-only evidence cannot become a risk claim.", "$.targetClaimClass"));
    }

    if ((payload.transitionStatus === "allowed" || payload.transitionStatus === "allowed_with_review") && payload.sourceClaimClass === "context_only" && ONTOLOGY_BLOCKED_TARGETS.has(payload.targetClaimClass)) {
      failures.push(failure("ONTOLOGY_CONTEXT_TARGET_BLOCKED", "Ontology context-only transitions cannot target causal support, adversity, risk, or regulatory translation.", "$.targetClaimClass"));
    }

    if (payload.transitionStatus === "allowed" && targetRank > sourceRank + 1) {
      failures.push(failure("CLAIM_TRANSITION_ESCALATION_REQUIRES_REVIEW", "Large claim-class escalation cannot be marked allowed without review.", "$.transitionStatus"));
    }

    // INVARIANT (replaces the earlier ">2 ranks" heuristic, which let +1/+2
    // escalations into high-stakes classes through): an UPWARD transition whose
    // target is a high-stakes class (causal_support, adversity, risk,
    // regulatory_translation) cannot be pre-authorized as allowed or
    // allowed_with_review. requiredReviewState is only an asserted label, never
    // reconciled against a real HumanReviewRecord at policy time, so "with
    // review" gives no actual protection here; such escalations must be earned
    // per-claim (evidence + human review) and the policy must mark them blocked.
    // internal_dose is intentionally NOT a blocked target (exposure ->
    // internal_dose is a legitimate dosimetry step). targetRank >= sourceRank
    // catches upward AND same-rank lateral moves (e.g. internal_dose ->
    // causal_support, risk -> regulatory_translation) while still permitting a
    // genuine de-escalation. This single rule subsumes the named guards above
    // and — because HandoffEnvelope.downstreamUsePolicy is nested-validated —
    // also closes generic (non-aliased) handoff laundering.
    if ((payload.transitionStatus === "allowed" || payload.transitionStatus === "allowed_with_review") && ESCALATION_BLOCKED_TARGET_CLASSES.has(payload.targetClaimClass) && targetRank >= sourceRank) {
      failures.push(failure("CLAIM_TRANSITION_ESCALATION_TOO_LARGE", "An upward or lateral transition into a high-stakes claim class (causal support, adversity, risk, regulatory translation) cannot be pre-authorized as allowed or allowed_with_review; mark it blocked and earn the escalation per-claim with evidence and human review.", "$.transitionStatus"));
    }

    if ((payload.transitionStatus === "allowed" || payload.transitionStatus === "allowed_with_review") && HIGH_CLAIM_CLASSES.has(payload.targetClaimClass) && payload.requiredEvidenceRefs.length === 0) {
      failures.push(failure("CLAIM_TRANSITION_EVIDENCE_REQUIRED", "High-impact claim transitions require evidence references.", "$.requiredEvidenceRefs"));
    }

    if (payload.transitionStatus === "allowed_with_review" && !["human_review_required", "human_reviewed", "adjudicated"].includes(payload.requiredReviewState)) {
      failures.push(failure("CLAIM_TRANSITION_REVIEW_STATE_REQUIRED", "Allowed-with-review transitions must require or record human/adjudicated review.", "$.requiredReviewState"));
    }
  }

  // INVARIANT: protection records (ConfidenceCeiling/UncertaintyRecord/
  // SemanticLossEvent) previously had NO single-object policy checks, so an
  // overclaim could ride in their narrative fields (reason/consequence/driver/
  // description) while the record still looked structurally protective. Those
  // fields legitimately use words like "causal"/"adverse" in explanation (e.g.
  // "loses causal specificity"), so they are scanned with the negation-aware
  // control-plane scanner only — it flags unambiguous safety/regulatory/
  // certificate overclaims without false-positiving on protective description.
  if (
    payload.schemaId === SCHEMA_IDS.confidenceCeiling ||
    payload.schemaId === SCHEMA_IDS.uncertaintyRecord ||
    payload.schemaId === SCHEMA_IDS.semanticLossEvent
  ) {
    if (containsDeepControlPlaneOverclaim(payload)) {
      failures.push(failure("PROTECTION_RECORD_FREE_TEXT_OVERCLAIM", "Protection-record narrative fields cannot carry safety, regulatory, or certification overclaims.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.assayStudyQuality) {
    if (payload.handoffEligibility !== "blocked" && ["failed", "missing", "not_assessed"].includes(payload.controlStatus)) {
      failures.push(failure("CONTROL_FAILURE_BLOCKS_HANDOFF", "Assay handoff requires documented passing controls.", "$.controlStatus"));
    }

    if (payload.handoffEligibility !== "blocked" && ["failed", "missing", "not_assessed"].includes(payload.acceptanceCriteriaStatus)) {
      failures.push(failure("ASSAY_STUDY_QUALITY_REQUIRED", "Assay handoff requires passed acceptance criteria.", "$.acceptanceCriteriaStatus"));
    }

    if (payload.handoffEligibility !== "blocked" && payload.assayInterferenceStatus === "unbounded") {
      failures.push(failure("ASSAY_INTERFERENCE_NOT_BOUND", "Unbounded assay interference blocks scientific handoff.", "$.assayInterferenceStatus"));
    }

    if (payload.handoffEligibility !== "blocked" && payload.batchOrPlateEffectStatus === "unresolved") {
      failures.push(failure("BATCH_EFFECT_NOT_BOUND", "Unresolved batch or plate effects cannot be treated as handoff-ready.", "$.batchOrPlateEffectStatus"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.replicateDesign) {
    if (payload.biologicalReplicateCount < 2) {
      failures.push(failure("BIOLOGICAL_REPLICATE_COUNT_REQUIRED", "Bioactivity evidence requires explicit biological replicate support.", "$.biologicalReplicateCount"));
    }

    if (payload.pseudoreplicationRisk === "possible" || payload.pseudoreplicationRisk === "likely" || payload.pseudoreplicationRisk === "not_assessed") {
      failures.push(failure("PSEUDOREPLICATION_INFLATES_SUPPORT", "Possible or unassessed pseudoreplication cannot inflate support.", "$.pseudoreplicationRisk"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.concentrationResponseDesign) {
    if (payload.podEligibility === "pod_ready" && payload.concentrationLevels < 4) {
      failures.push(failure("INSUFFICIENT_CONCENTRATION_RESPONSE", "PoD-ready concentration response requires at least four concentration levels.", "$.concentrationLevels"));
    }

    if (payload.podEligibility === "pod_ready" && (payload.concentrationBasis === "unknown_with_blocker" || payload.concentrationBasis === "not_assessed")) {
      failures.push(failure("CONCENTRATION_BASIS_MISMATCH", "PoD-ready concentration response requires a usable concentration basis.", "$.concentrationBasis"));
    }

    if (payload.podEligibility === "pod_ready" && ["failed", "missing", "not_assessed"].includes(payload.controlStatus)) {
      failures.push(failure("CONTROL_FAILURE_BLOCKS_HANDOFF", "PoD-ready concentration response requires passing controls.", "$.controlStatus"));
    }

    if (payload.podEligibility === "pod_ready" && (payload.cytotoxicityConfounding === "possible" || payload.cytotoxicityConfounding === "likely" || payload.cytotoxicityConfounding === "not_assessed")) {
      failures.push(failure("CYTOTOXICITY_CONFOUNDS_POD", "Possible, likely, or unassessed cytotoxicity confounding blocks PoD readiness.", "$.cytotoxicityConfounding"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.bioactivityObservation) {
    if (payload.fitReadiness === "pod_ready" && payload.concentrationAxis.concentrationLevels < 4) {
      failures.push(failure("INSUFFICIENT_CONCENTRATION_RESPONSE", "PoD-ready bioactivity observations require at least four concentration levels.", "$.concentrationAxis.concentrationLevels"));
    }

    if (payload.fitReadiness === "pod_ready" && (payload.replicateSummary.biologicalReplicates < 2 || payload.replicateSummary.plateOrBatchCount < 1)) {
      failures.push(failure("BIOLOGICAL_REPLICATE_COUNT_REQUIRED", "PoD-ready bioactivity observations require biological replicate and batch/plate support.", "$.replicateSummary"));
    }

    if (payload.fitReadiness === "pod_ready" && Object.values(payload.controls).some((status) => status === "failed" || status === "missing")) {
      failures.push(failure("CONTROL_FAILURE_BLOCKS_HANDOFF", "PoD-ready bioactivity observations require usable controls.", "$.controls"));
    }

    if (payload.fitReadiness === "pod_ready" && payload.batchEffectAssessment === "unresolved") {
      failures.push(failure("BATCH_EFFECT_NOT_BOUND", "Unresolved batch effects block PoD-ready bioactivity handoff.", "$.batchEffectAssessment"));
    }

    if (payload.fitReadiness === "pod_ready" && (payload.cytotoxicityConfounding === "possible" || payload.cytotoxicityConfounding === "likely" || payload.cytotoxicityConfounding === "not_assessed")) {
      failures.push(failure("CYTOTOXICITY_CONFOUNDS_POD", "Possible, likely, or unassessed cytotoxicity confounding blocks PoD-ready bioactivity handoff.", "$.cytotoxicityConfounding"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.pointOfDepartureRecord) {
    const podIsReady = POD_READY_STATUSES.has(payload.qualificationStatus) || payload.actionability === "decision_support";
    const podIsActionable = payload.qualificationStatus !== "blocked" && payload.qualificationStatus !== "not_assessed" && payload.qualificationStatus !== "exploratory" && payload.actionability !== "none";
    if (podIsReady && (!payload.fitDiagnostics.modelConverged || payload.fitDiagnostics.goodnessOfFit !== "acceptable" || payload.fitDiagnostics.residualPattern === "problematic")) {
      failures.push(failure("POD_MODEL_DIAGNOSTICS_REQUIRED", "Ready PoD records require acceptable model convergence, goodness of fit, and residual diagnostics.", "$.fitDiagnostics"));
    }

    if ((payload.derivationMethod === "heuristic_screening" || payload.uncertaintyQuantification === "heuristic_bracket") && (payload.podType === "BMDL" || payload.podType === "BMDU")) {
      failures.push(failure("HEURISTIC_INTERVAL_MISLABELED", "Heuristic brackets cannot be labeled as BMDL/BMDU intervals.", "$.podType"));
    }

    if (podIsActionable && (payload.applicabilityDomainStatus === "outside" || payload.applicabilityDomainStatus === "unknown_with_blocker")) {
      failures.push(failure("POD_OUTSIDE_APPLICABILITY_DOMAIN", "PoD records cannot be actionable outside the declared applicability domain.", "$.applicabilityDomainStatus"));
    }

    if (podIsActionable && !payload.applicabilityDomainStatus) {
      failures.push(failure("POD_APPLICABILITY_STATUS_REQUIRED", "Actionable PoD records require structured applicability-domain status.", "$.applicabilityDomainStatus"));
    }

    if (payload.qualificationStatus === "risk_assessment_ready" || payload.qualificationStatus === "regulatory_submission_ready" || anyForbidden(payload.allowedDownstreamUses, POD_BLOCKED_DOWNSTREAM_USE_PATTERN)) {
      failures.push(failure("BIOACTIVITY_POD_NOT_RISK_OR_REGULATORY_READY", "Bioactivity PoD records cannot declare risk/regulatory readiness or authorize risk/regulatory downstream use.", "$.allowedDownstreamUses"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.bioactivityPodReadiness) {
    if ((payload.readinessStatus === "eligible" || payload.readinessStatus === "conditional") && payload.blockers.length > 0) {
      failures.push(failure("POD_READINESS_WITH_BLOCKERS", "PoD readiness cannot be eligible or conditional while blockers remain.", "$.blockers"));
    }

    if ((payload.readinessStatus === "eligible" || payload.readinessStatus === "conditional") && !hasSubstantiveRefs(payload.confidenceCeilingRefs)) {
      failures.push(failure("POD_READINESS_REQUIRES_CONFIDENCE_CEILING", "PoD readiness requires linked confidence ceilings.", "$.confidenceCeilingRefs"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.readAcrossJustification) {
    const highReadAcrossClaim = HIGH_READ_ACROSS_TARGETS.has(payload.targetClaimClass) || payload.supportLevel === "moderate" || payload.supportLevel === "strong" || payload.actionability === "decision_support";
    if (payload.hypothesisType === "structural_similarity_only" && highReadAcrossClaim) {
      failures.push(failure("STRUCTURAL_SIMILARITY_ONLY_OVERCLAIM", "Structural similarity alone cannot support high read-across claims.", "$.hypothesisType"));
      failures.push(failure("READ_ACROSS_WITHOUT_ANALOG_JUSTIFICATION", "Read-across requires analog, mechanistic, metabolic, or empirical-category justification.", "$.similarityBasis"));
    }

    if (highReadAcrossClaim && !hasSubstantiveRefs(payload.uncertaintyRefs)) {
      failures.push(failure("CATEGORY_CLAIM_UNCERTAINTY_REQUIRED", "Read-across/category claims require explicit uncertainty propagation.", "$.uncertaintyRefs"));
    }

    if (payload.analogAdequacy !== "adequate_with_limitations" && payload.actionability !== "none") {
      failures.push(failure("READ_ACROSS_ANALOG_OUTSIDE_DOMAIN", "Read-across with inadequate, unknown, or unassessed analog adequacy cannot be actionable.", "$.analogAdequacy"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.weightOfEvidenceEvaluation) {
    const supportInflated = payload.conclusionSupportLevel === "moderate" || payload.conclusionSupportLevel === "strong" || payload.actionability === "decision_support";
    if ((payload.evidenceDependenceAssessment === "dependent" || payload.evidenceDependenceAssessment === "partially_dependent") && supportInflated) {
      failures.push(failure("WOE_DEPENDENCY_INFLATION", "Dependent evidence cannot inflate WoE support or actionability.", "$.evidenceDependenceAssessment"));
    }

    if (payload.conflictStatus === "unresolved_conflict" && (supportInflated || !hasSubstantiveRefs(payload.confidenceCeilingRefs))) {
      failures.push(failure("UNRESOLVED_CONFLICT_REQUIRES_CEILING", "Unresolved conflict requires confidence ceilings and cannot support inflated conclusions.", "$.conflictStatus"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.iataStrategyDecision) {
    if (!payload.evidenceBundleRefs.some((ref) => /woe|weight[-_ ]?of[-_ ]?evidence/i.test(ref))) {
      failures.push(failure("IATA_INPUT_WITHOUT_WOE_SUMMARY", "IATA strategy decisions require a WoE summary or bundle reference.", "$.evidenceBundleRefs"));
    }

    if (containsIataDecisionOverclaimText(payload)) {
      failures.push(failure("IATA_NOT_REGULATORY_DECISION", "IATA strategy decisions must not become hidden regulatory or final safety decisions.", "$"));
      failures.push(failure("ABSOLUTE_OR_REGULATORY_OVERCLAIM", "IATA free text cannot assert safe levels, no-risk conclusions, or regulatory sufficiency.", "$"));
    }

    if (matchesForbidden(/probability|confidence|risk/i, payload.proportionalityRationale) && matchesForbidden(/utility score/i, payload.proportionalityRationale)) {
      failures.push(failure("UTILITY_SCORE_NOT_PROBABILITY", "IATA utility scores must not be described as probabilities, confidence, or risk.", "$.proportionalityRationale"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.exposureScenarioContext) {
    if (payload.route === "not_assessed" || !hasSubstantiveRefs(payload.uncertaintyRefs)) {
      failures.push(failure("EXPOSURE_SCENARIO_CONTEXT_REQUIRED", "Exposure scenarios require assessed route and explicit uncertainty references.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.routeDoseEstimate) {
    if (anyForbidden(payload.allowedDownstreamUses, /internal[-_ ]?dose|css|cmax|auc|pbpk[-_ ]?result|risk|regulatory/i)) {
      failures.push(failure("EXTERNAL_EXPOSURE_NOT_INTERNAL_DOSE", "Route-dose estimates are external exposure records and cannot authorize internal-dose, risk, or regulatory claims.", "$.allowedDownstreamUses"));
    }

    if (!hasSubstantiveRefs(payload.uncertaintyRefs) || !hasSubstantiveRefs(payload.confidenceCeilingRefs)) {
      failures.push(failure("EXPOSURE_UNCERTAINTY_AND_CEILING_REQUIRED", "Route-dose estimates require uncertainty and confidence ceiling references.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.tkParameterProvenance) {
    if (!hasSubstantiveRefs(payload.uncertaintyRefs)) {
      failures.push(failure("TK_PARAMETER_UNCERTAINTY_REQUIRED", "TK parameter provenance requires explicit uncertainty records.", "$.uncertaintyRefs"));
    }

    if (hasSubstantiveRefs(payload.uncertaintyRefs) && (payload.sourceType === "default" || payload.sourceType === "qsar" || payload.sourceType === "expert_judgment")) {
      if (!payload.uncertaintyRefs.some((ref) => /uncertainty/i.test(ref))) {
        failures.push(failure("TK_PARAMETER_UNCERTAINTY_REQUIRED", "Default, QSAR, or expert-judgment TK parameters require explicit uncertainty records.", "$.uncertaintyRefs"));
      }
    }

    if (payload.sourceType === "unknown_with_blocker" || payload.sourceType === "not_assessed") {
      failures.push(failure("TK_PARAMETER_PROVENANCE_BLOCKED", "Unknown or unassessed TK parameter provenance blocks internal-exposure use.", "$.sourceType"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.freeConcentrationCorrection) {
    const assumptionValues = [
      payload.proteinBindingAssumption,
      payload.lipidBindingAssumption,
      payload.plasticSorptionAssumption,
      payload.headspaceVolatilizationAssumption
    ];
    if (assumptionValues.some((value) => value === "not_assessed" || value === "unknown_with_blocker")) {
      failures.push(failure("FREE_CONCENTRATION_ASSUMPTIONS_REQUIRED", "Free concentration correction must explicitly assess protein, lipid, plastic sorption, and headspace assumptions.", "$"));
    }

    if (!hasSubstantiveRefs(payload.uncertaintyRefs) || !hasSubstantiveRefs(payload.confidenceCeilingRefs)) {
      failures.push(failure("FREE_CONCENTRATION_UNCERTAINTY_AND_CEILING_REQUIRED", "Free concentration correction requires explicit uncertainty and confidence ceiling references.", "$"));
    }

    if (payload.domainWarnings.length > 0 && !hasSubstantiveRefs(payload.confidenceCeilingRefs)) {
      failures.push(failure("FREE_CONCENTRATION_WARNING_REQUIRES_CEILING", "Free concentration domain warnings require confidence ceilings.", "$.confidenceCeilingRefs"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.internalExposureSummary) {
    if ((payload.pbkTier === "httk_screening" || payload.pbkTier === "generic_pbk") && (payload.modelQualificationStatus === "externally_validated" || anyForbidden(payload.allowedDownstreamUses, /risk|regulatory|decision/i))) {
      failures.push(failure("HTTK_SCREENING_NOT_PBPK", "HTTK/generic PBK screening outputs cannot be represented as externally validated PBPK or risk/regulatory decision support.", "$.pbkTier"));
    }

    if (payload.bindingBasis === "not_assessed" || payload.bindingBasis === "unknown_with_blocker" || payload.matrix === "not_assessed" || payload.matrix === "unknown_with_blocker" || payload.route === "not_assessed") {
      failures.push(failure("INTERNAL_EXPOSURE_BASIS_REQUIRED", "Internal exposure requires assessed route, matrix, and binding basis.", "$"));
    }

    if (!hasSubstantiveRefs(payload.parameterProvenanceRefs) || !hasSubstantiveRefs(payload.uncertaintyRefs) || !hasSubstantiveRefs(payload.confidenceCeilingRefs)) {
      failures.push(failure("INTERNAL_EXPOSURE_UNCERTAINTY_REQUIRED", "Internal exposure requires parameter provenance, uncertainty, and confidence ceiling references.", "$"));
    }

    if (anyForbidden(payload.allowedDownstreamUses, INTERNAL_EXPOSURE_BLOCKED_DOWNSTREAM_USE_PATTERN)) {
      failures.push(failure("INTERNAL_EXPOSURE_NOT_RISK_OR_REGULATORY_READY", "Internal exposure summaries cannot authorize risk/regulatory downstream uses.", "$.allowedDownstreamUses"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.comparabilityQualification) {
    const matchFields = [
      payload.routeMatch,
      payload.timeBasisMatch,
      payload.matrixMatch,
      payload.bindingBasisMatch,
      payload.populationMatch,
      payload.compartmentMatch
    ];
    const hasMismatch = matchFields.some((value) => value === "mismatch" || value === "unknown_with_blocker" || value === "not_assessed");
    if ((payload.qualificationStatus === "comparable" || payload.qualificationStatus === "comparable_with_limitations") && hasMismatch) {
      failures.push(failure("COMPARABILITY_ACCEPTED_WITH_MISMATCH", "Comparability cannot be accepted when route, time, matrix, binding, population, or compartment is mismatched or unassessed.", "$"));
    }

    if (hasMismatch && payload.mismatchReasons.length === 0) {
      failures.push(failure("COMPARABILITY_MISMATCH_REASONS_REQUIRED", "Comparability mismatches require explicit mismatch reasons.", "$.mismatchReasons"));
    }

    if (!hasSubstantiveRefs(payload.uncertaintyRefs) || !hasSubstantiveRefs(payload.confidenceCeilingRefs)) {
      failures.push(failure("COMPARABILITY_UNCERTAINTY_AND_CEILING_REQUIRED", "Comparability qualification requires explicit uncertainty and confidence ceiling references.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.reverseDosimetryRecord) {
    if (payload.method === "biomonitoring_inference" && payload.qualificationStatus !== "review_required" && payload.qualificationStatus !== "blocked") {
      failures.push(failure("BIOMONITORING_REVERSE_REQUIRES_REVIEW", "Biomonitoring reverse inference requires review or PBPK deferral before use.", "$.qualificationStatus"));
    }

    if (anyForbidden(payload.allowedDownstreamUses, INTERNAL_EXPOSURE_BLOCKED_DOWNSTREAM_USE_PATTERN)) {
      failures.push(failure("REVERSE_DOSIMETRY_NOT_RISK_OR_REGULATORY", "Reverse dosimetry records cannot authorize risk/regulatory downstream uses.", "$.allowedDownstreamUses"));
    }

    if (!hasSubstantiveRefs(payload.uncertaintyRefs) || !hasSubstantiveRefs(payload.confidenceCeilingRefs)) {
      failures.push(failure("REVERSE_DOSIMETRY_UNCERTAINTY_AND_CEILING_REQUIRED", "Reverse dosimetry records require explicit uncertainty and confidence ceiling references.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.bioactivityExposureRatioRecord) {
    if (!hasSubstantiveRefs(payload.uncertaintyRefs) || !hasSubstantiveRefs(payload.confidenceCeilingRefs)) {
      failures.push(failure("BER_UNCERTAINTY_AND_CEILING_REQUIRED", "BER records require explicit uncertainty and confidence ceilings.", "$"));
    }

    if (payload.interpretationClass !== "screening_context" && payload.interpretationClass !== "prioritization_context" && payload.interpretationClass !== "requires_review") {
      failures.push(failure("BER_REQUIRES_COMPARABILITY", "BER interpretation requires comparable or limited comparable inputs.", "$.interpretationClass"));
    }

    if (anyForbidden(payload.allowedDownstreamUses, INTERNAL_EXPOSURE_BLOCKED_DOWNSTREAM_USE_PATTERN)) {
      failures.push(failure("BER_NOT_RISK_OR_REGULATORY", "BER records cannot authorize risk/regulatory downstream uses.", "$.allowedDownstreamUses"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.populationProfile) {
    if (payload.samplingOrModelBasis === "not_assessed" || payload.samplingOrModelBasis === "unknown_with_blocker" || payload.representativeness === "not_assessed" || payload.representativeness === "unknown_with_blocker") {
      failures.push(failure("POPULATION_PROFILE_BASIS_REQUIRED", "Population profiles require assessed sampling/model basis and representativeness.", "$"));
    }

    if (!hasSubstantiveRefs(payload.uncertaintyRefs)) {
      failures.push(failure("POPULATION_UNCERTAINTY_REQUIRED", "Population profiles require explicit uncertainty references.", "$.uncertaintyRefs"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.sensitiveDescriptorPolicy) {
    if (payload.useStatus === "not_used" && payload.allowedRole !== "none") {
      failures.push(failure("SENSITIVE_DESCRIPTOR_POLICY_CONTRADICTION", "Sensitive descriptor policy cannot allow a role when descriptors are not used.", "$.allowedRole"));
    }

    if (usesSensitiveSocialDescriptor(payload) && (payload.useStatus === "used_with_biological_rationale" || payload.allowedRole === "effect_modifier_with_review")) {
      failures.push(failure("SENSITIVE_DESCRIPTOR_PROXY_MISUSE", "Social or demographic descriptors cannot be treated as biological effect modifiers.", "$"));
    }

    if (payload.useStatus === "used_as_context" && !payload.requiresHumanReview) {
      failures.push(failure("SENSITIVE_DESCRIPTOR_REQUIRES_REVIEW", "Sensitive descriptor context requires human review.", "$.requiresHumanReview"));
    }

    if (!hasPopulationProhibitionKeywords(payload.prohibitedClaims)) {
      failures.push(failure("SENSITIVE_DESCRIPTOR_PROHIBITIONS_REQUIRED", "Sensitive descriptor policy must prohibit individual, risk, regulatory, safety, and proxy-biology claims.", "$.prohibitedClaims"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.subgroupDefinition) {
    if (payload.subgroupGranularity === "individual") {
      failures.push(failure("INDIVIDUAL_RISK_CLAIM_BLOCKED", "Population variability records cannot define individual-level prediction targets.", "$.subgroupGranularity"));
    }

    if (payload.descriptorBasis === "unknown_with_blocker" || payload.descriptorBasis === "not_assessed") {
      failures.push(failure("SUBGROUP_DESCRIPTOR_BASIS_REQUIRED", "Subgroup definitions require an assessed descriptor basis.", "$.descriptorBasis"));
    }

    if (!hasSubstantiveRefs(payload.uncertaintyRefs)) {
      failures.push(failure("POPULATION_UNCERTAINTY_REQUIRED", "Subgroup definitions require explicit uncertainty references.", "$.uncertaintyRefs"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.variabilityDimension) {
    if (payload.dimensionType === "sensitive_descriptor" && payload.actionability !== "none" && payload.actionability !== "requires_review") {
      failures.push(failure("SENSITIVE_DESCRIPTOR_PROXY_MISUSE", "Sensitive descriptors cannot become actionable variability dimensions.", "$.dimensionType"));
    }

    if (payload.actionability === "decision_support") {
      failures.push(failure("POPULATION_VARIABILITY_NOT_DECISION_SUPPORT", "Population variability dimensions cannot become autonomous decision support.", "$.actionability"));
    }

    if (!hasSubstantiveRefs(payload.uncertaintyRefs) || !hasSubstantiveRefs(payload.confidenceCeilingRefs)) {
      failures.push(failure("POPULATION_UNCERTAINTY_AND_CEILING_REQUIRED", "Variability dimensions require uncertainty and confidence ceiling references.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.modifierEvidenceLane) {
    if (payload.laneType === "sensitive_descriptor_context" && (payload.evidenceStrength === "moderate" || payload.evidenceStrength === "strong")) {
      failures.push(failure("SENSITIVE_DESCRIPTOR_PROXY_MISUSE", "Sensitive descriptor context cannot provide moderate or strong biological evidence.", "$.evidenceStrength"));
    }

    if ((payload.dependenceAssessment === "dependent" || payload.dependenceAssessment === "partially_dependent") && (payload.evidenceStrength === "moderate" || payload.evidenceStrength === "strong")) {
      failures.push(failure("POPULATION_EVIDENCE_DEPENDENCY_INFLATION", "Dependent population evidence cannot inflate support.", "$.dependenceAssessment"));
    }

    if (anyForbidden(payload.allowedDownstreamUses, POPULATION_BLOCKED_DOWNSTREAM_USE_PATTERN)) {
      failures.push(failure("POPULATION_VARIABILITY_NOT_RISK_OR_REGULATORY_READY", "Modifier evidence lanes cannot authorize individual, risk, safety, or regulatory downstream uses.", "$.allowedDownstreamUses"));
    }

    if (!hasSubstantiveRefs(payload.uncertaintyRefs) || !hasSubstantiveRefs(payload.confidenceCeilingRefs)) {
      failures.push(failure("POPULATION_UNCERTAINTY_AND_CEILING_REQUIRED", "Modifier evidence lanes require uncertainty and confidence ceiling references.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.subgroupComparison) {
    if ((payload.comparatorConsistency === "mismatch" || payload.comparatorConsistency === "unknown_with_blocker" || payload.comparatorConsistency === "not_assessed") && (payload.effectMagnitudeBand === "moderate" || payload.effectMagnitudeBand === "high")) {
      failures.push(failure("SUBGROUP_COMPARATOR_MISMATCH", "Mismatched or unassessed comparators cannot support moderate/high subgroup effect interpretation.", "$.comparatorConsistency"));
    }

    if (!hasSubstantiveRefs(payload.uncertaintyRefs) || !hasSubstantiveRefs(payload.confidenceCeilingRefs)) {
      failures.push(failure("POPULATION_UNCERTAINTY_AND_CEILING_REQUIRED", "Subgroup comparisons require uncertainty and confidence ceiling references.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.susceptibilitySummary) {
    if (anyForbidden(payload.allowedDownstreamUses, POPULATION_BLOCKED_DOWNSTREAM_USE_PATTERN)) {
      failures.push(failure("POPULATION_VARIABILITY_NOT_RISK_OR_REGULATORY_READY", "Susceptibility summaries cannot authorize individual, risk, safety, or regulatory downstream uses.", "$.allowedDownstreamUses"));
    }

    if (payload.actionability === "decision_support" || payload.supportLevel === "strong") {
      failures.push(failure("POPULATION_VARIABILITY_NOT_DECISION_SUPPORT", "Susceptibility summaries cannot claim strong support or autonomous decision support in this slice.", "$"));
    }

    if (payload.conclusionClass === "susceptibility_signal" && !["human_review_required", "human_reviewed", "adjudicated"].includes(payload.requiredReviewState)) {
      failures.push(failure("SUBGROUP_SUSCEPTIBILITY_REQUIRES_REVIEW", "Susceptibility signals require human review or adjudication state.", "$.requiredReviewState"));
    }

    if (!hasSubstantiveRefs(payload.uncertaintyRefs) || !hasSubstantiveRefs(payload.confidenceCeilingRefs) || !hasSubstantiveRefs(payload.nonClaimBoundaryRefs)) {
      failures.push(failure("POPULATION_PROTECTIONS_REQUIRED", "Susceptibility summaries require uncertainty, confidence ceiling, and non-claim boundary references.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.subgroupReviewPacket) {
    if (payload.handoffEligibility === "eligible_with_limitations" && !["human_reviewed", "adjudicated"].includes(payload.reviewStatus)) {
      failures.push(failure("SUBGROUP_REVIEW_PACKET_REQUIRES_HUMAN_REVIEW", "Eligible subgroup review packets require human review or adjudication.", "$.reviewStatus"));
    }

    if (anyForbidden(payload.allowedDownstreamUses, POPULATION_BLOCKED_DOWNSTREAM_USE_PATTERN)) {
      failures.push(failure("POPULATION_VARIABILITY_NOT_RISK_OR_REGULATORY_READY", "Subgroup review packets cannot authorize individual, risk, safety, or regulatory downstream uses.", "$.allowedDownstreamUses"));
    }

    if (!hasSubstantiveRefs(payload.uncertaintyRefs) || !hasSubstantiveRefs(payload.confidenceCeilingRefs) || !hasSubstantiveRefs(payload.nonClaimBoundaryRefs)) {
      failures.push(failure("POPULATION_PROTECTIONS_REQUIRED", "Subgroup review packets require uncertainty, confidence ceiling, and non-claim boundary references.", "$"));
    }
  }

  // Spine control-plane EVIDENCE OVERLAYS (reference a Hub-owned manifest/report/
  // benchmark by digest; carry only net-new scientific evidence + non-claim guards;
  // see docs/adr/0001). The const non-claim guards are schema-enforced; here we
  // additionally forbid control-plane overclaims in their narrative. Scan EVERY
  // narrative string leaf (containsDeepControlPlaneOverclaim, which exempts
  // id/ref/digest keys), NOT a hand-picked field allowlist — an allowlist just
  // moves the goalposts one field over (e.g. an overclaim in unresolvedRisks),
  // which is the exact anti-pattern this engine's invariant forbids.
  if (payload.schemaId === SCHEMA_IDS.spineReleaseReadinessEvidenceOverlay) {
    if (containsDeepControlPlaneOverclaim(payload)) {
      failures.push(failure("CONTROL_PLANE_RELEASE_OVERCLAIM", "Release-readiness evidence overlays cannot become certificates, safety conclusions, regulatory acceptance, scientific validation, or marketing grades.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.spineBenchmarkSuiteEvidenceOverlay) {
    if (containsDeepControlPlaneOverclaim(payload)) {
      failures.push(failure("CONTROL_PLANE_RELEASE_OVERCLAIM", "Benchmark-suite evidence overlays cannot carry control-plane safety, regulatory, or marketing overclaims.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.spineBenchmarkRunEvidenceOverlay) {
    if (containsDeepControlPlaneOverclaim(payload)) {
      failures.push(failure("CONTROL_PLANE_RELEASE_OVERCLAIM", "Benchmark-run evidence overlays cannot carry control-plane safety, regulatory, or marketing overclaims.", "$"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.transportCapability) {
    if (payload.transport === "stdio" && payload.endpoint.kind !== "stdio_command") {
      failures.push(failure("TRANSPORT_ENDPOINT_KIND_MISMATCH", "stdio transport requires a stdio command endpoint.", "$.endpoint.kind"));
    }

    if (payload.transport === "streamable_http" && payload.endpoint.kind !== "http_url") {
      failures.push(failure("TRANSPORT_ENDPOINT_KIND_MISMATCH", "Streamable HTTP transport requires an HTTP URL endpoint.", "$.endpoint.kind"));
    }

    if (payload.transport === "stdio" && payload.deploymentScope === "public") {
      failures.push(failure("STDIO_NOT_PUBLIC_REMOTE_TRANSPORT", "stdio is a local transport and cannot be declared as a public remote transport.", "$.deploymentScope"));
    }

    if (payload.transport === "sse" && payload.releaseQualified) {
      failures.push(failure("SSE_TRANSPORT_NOT_RELEASE_QUALIFIED", "Deprecated HTTP+SSE transport cannot be marked release-qualified.", "$.releaseQualified"));
    }

    if (payload.transport === "custom" && payload.releaseQualified) {
      failures.push(failure("CUSTOM_TRANSPORT_NOT_RELEASE_QUALIFIED", "Custom transports require separate qualification before release readiness.", "$.releaseQualified"));
    }

    if (payload.transport === "streamable_http" && payload.releaseQualified) {
      const methods = new Set(payload.endpoint.methods ?? []);
      const secretsMissing = (payload.auth.scheme === "api_key" || payload.auth.scheme === "custom") && !payload.auth.secretsInEnv;
      const conformanceMissing =
        payload.supportStatus !== "supported" ||
        payload.endpoint.kind !== "http_url" ||
        !methods.has("POST") ||
        !methods.has("GET") ||
        !["stateless", "stateful"].includes(payload.sessionMode) ||
        payload.auth.status !== "implemented" ||
        payload.auth.scheme === "none" ||
        payload.auth.scheme === "not_assessed" ||
        !payload.auth.tokenAudienceValidated ||
        secretsMissing ||
        payload.originProtection.status !== "enabled" ||
        !payload.originProtection.originValidation ||
        !payload.originProtection.dnsRebindingProtection ||
        payload.rateLimitPolicy.status !== "enforced" ||
        payload.structuredOutputSupport !== "supported" ||
        payload.toolAnnotationsSupport !== "supported";
      if (conformanceMissing) {
        failures.push(failure("STREAMABLE_HTTP_RELEASE_CONFORMANCE_REQUIRED", "Release-qualified Streamable HTTP requires supported POST/GET endpoint, auth, origin/DNS-rebinding protection, rate limits, structured outputs, and tool annotations.", "$"));
      }
    }
  }

  if (payload.schemaId === SCHEMA_IDS.schemaSignature) {
    if ((payload.trustScope === "public_release" || payload.releaseBlocking) && payload.verificationStatus !== "verified") {
      failures.push(failure("SCHEMA_SIGNATURE_VERIFICATION_REQUIRED", "Release-blocking or public-release schema signatures must be verified.", "$.verificationStatus"));
    }

    if (payload.trustScope === "public_release" && !RELEASE_GRADE_SIGNATURE_ALGORITHMS.has(payload.signatureAlgorithm)) {
      failures.push(failure("SCHEMA_SIGNATURE_ALGORITHM_REQUIRED", "Public-release signatures require a release-grade signing algorithm, not a digest-only record.", "$.signatureAlgorithm"));
    }

    if ((payload.trustScope === "public_release" || payload.releaseBlocking) && payload.canonicalizationAlgorithm === "not_assessed") {
      failures.push(failure("SCHEMA_CANONICALIZATION_REQUIRED", "Release-blocking signatures require an assessed canonicalization algorithm.", "$.canonicalizationAlgorithm"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.validationEvidenceBundle) {
    if (payload.evidenceStatus === "complete" && payload.integrityStatus !== "verified") {
      failures.push(failure("VALIDATION_EVIDENCE_COMPLETE_REQUIRES_VERIFICATION", "Complete validation evidence requires verified integrity.", "$.integrityStatus"));
    }

    if (payload.evidenceStatus === "complete" && !["reproducible", "partially_reproducible"].includes(payload.reproducibilityStatus)) {
      failures.push(failure("VALIDATION_EVIDENCE_REPRODUCIBILITY_REQUIRED", "Complete validation evidence requires reproducible or partially reproducible status.", "$.reproducibilityStatus"));
    }

    if (payload.evidenceStatus === "complete" && payload.artifactRefs.length === 0) {
      failures.push(failure("VALIDATION_EVIDENCE_ARTIFACTS_REQUIRED", "Complete validation evidence requires retained or digest-linked artifacts.", "$.artifactRefs"));
    }
  }

  if (payload.schemaId === SCHEMA_IDS.auditEventChain) {
    if (payload.eventCount !== payload.events.length) {
      failures.push(failure("AUDIT_CHAIN_EVENT_COUNT_MISMATCH", "Audit event count must match the number of events.", "$.eventCount"));
    }

    if (payload.events[0]?.previousHash !== null) {
      failures.push(failure("AUDIT_CHAIN_ROOT_PREVIOUS_HASH_REQUIRED", "The first audit event must have null previousHash.", "$.events[0].previousHash"));
    }

    if (payload.events.length > 0 && payload.rootHash !== payload.events[0].eventHash) {
      failures.push(failure("AUDIT_CHAIN_ROOT_HASH_MISMATCH", "Audit root hash must equal the first event hash.", "$.rootHash"));
    }

    if (payload.events.length > 0 && payload.tipHash !== payload.events[payload.events.length - 1].eventHash) {
      failures.push(failure("AUDIT_CHAIN_TIP_HASH_MISMATCH", "Audit tip hash must equal the last event hash.", "$.tipHash"));
    }

    for (let index = 1; index < payload.events.length; index += 1) {
      if (payload.events[index].previousHash !== payload.events[index - 1].eventHash) {
        failures.push(failure("AUDIT_CHAIN_LINKAGE_BROKEN", "Each audit event previousHash must equal the preceding event hash.", `$.events[${index}].previousHash`));
      }
    }

    payload.events.forEach((event, index) => {
      if (event.eventHash !== auditEventHash(event)) {
        failures.push(failure("AUDIT_CHAIN_EVENT_HASH_MISMATCH", "Audit event hashes must be computed from canonical event content.", `$.events[${index}].eventHash`));
      }
    });
  }

  if (payload.schemaId === SCHEMA_IDS.handoffEnvelope) {
    if (manifestEntries.length === 0) {
      failures.push(failure("SCHEMA_MANIFEST_REQUIRED", "Handoff pin validation requires a schema manifest.", "$.schemaPins"));
    } else {
      payload.schemaPins.forEach((pin, index) => {
        const manifestEntry = manifestById.get(pin.schemaId);
        if (!manifestEntry) {
          failures.push(failure("SCHEMA_PIN_UNKNOWN_SCHEMA", "Handoff schema pins must reference schemas in the local manifest.", `$.schemaPins[${index}].schemaId`));
        } else if (pin.schemaDigest !== `sha256:${manifestEntry.digest}`) {
          failures.push(failure("SCHEMA_PIN_DIGEST_MISMATCH", "Handoff schema pin digest must match the local schema manifest.", `$.schemaPins[${index}].schemaDigest`));
        }
      });
    }

    const accepted = new Set(payload.acceptedClaims);
    const overlap = payload.rejectedClaims.filter((claim) => accepted.has(claim));
    if (overlap.length > 0) {
      failures.push(failure("HANDOFF_CLAIM_BOTH_ACCEPTED_AND_REJECTED", "A handoff cannot accept and reject the same claim.", "$.acceptedClaims"));
    }

    if (isOntologyAopHandoff(payload) && anyForbidden(overlap, /causal|causality/i)) {
      failures.push(failure("AOP_HANDOFF_ACCEPTS_REJECTED_CAUSALITY", "Ontology to AOP handoff cannot accept a causal claim it also rejected.", "$.acceptedClaims"));
    }

    if (isOntologyAopHandoff(payload) && payload.compatibility === "accepted") {
      failures.push(failure("ONTOLOGY_HANDOFF_REQUIRES_LIMITATIONS", "Provisional Ontology to AOP handoffs must be accepted with limitations.", "$.compatibility"));
    }

    if ((isBioactivityPodWoeHandoff(payload) || isWoeIataHandoff(payload)) && payload.compatibility === "accepted") {
      failures.push(failure("BIOACTIVITY_POD_HANDOFF_REQUIRES_LIMITATIONS", "Bioactivity/PoD/WoE/IATA handoffs must preserve limitations until externally qualified.", "$.compatibility"));
    }

    if (isExposureInternalExposureBerHandoff(payload)) {
      if (payload.compatibility === "accepted") {
        failures.push(failure("INTERNAL_EXPOSURE_HANDOFF_REQUIRES_LIMITATIONS", "Exposure/PBK/IVIVE-BER handoffs must preserve limitations until externally qualified.", "$.compatibility"));
      }

      if (anyForbidden(payload.acceptedClaims, INTERNAL_EXPOSURE_BLOCKED_HANDOFF_CLAIM_PATTERN)) {
        failures.push(failure("INTERNAL_EXPOSURE_HANDOFF_BLOCKED_CLAIM", "Exposure/PBK/IVIVE-BER handoffs cannot accept risk, safety, regulatory, or validated-PBPK claims.", "$.acceptedClaims"));
      }

      if ((payload.downstreamUsePolicy.transitionStatus === "allowed" || payload.downstreamUsePolicy.transitionStatus === "allowed_with_review") && INTERNAL_EXPOSURE_BLOCKED_TARGET_CLAIM_CLASSES.has(payload.downstreamUsePolicy.targetClaimClass)) {
        failures.push(failure("INTERNAL_EXPOSURE_HANDOFF_BLOCKED_TRANSITION", "Exposure/PBK/IVIVE-BER handoffs cannot authorize direct adversity, risk, or regulatory claim transitions.", "$.downstreamUsePolicy.targetClaimClass"));
      }
    }

    if (isPopulationVariabilityHandoff(payload)) {
      if (payload.compatibility === "accepted") {
        failures.push(failure("POPULATION_HANDOFF_REQUIRES_LIMITATIONS", "Population variability handoffs must preserve limitations and review requirements.", "$.compatibility"));
      }

      if (anyForbidden(payload.acceptedClaims, POPULATION_BLOCKED_DOWNSTREAM_USE_PATTERN)) {
        failures.push(failure("POPULATION_HANDOFF_BLOCKED_CLAIM", "Population variability handoffs cannot accept individual, risk, safety, regulatory, or oracle claims.", "$.acceptedClaims"));
      }

      if ((payload.downstreamUsePolicy.transitionStatus === "allowed" || payload.downstreamUsePolicy.transitionStatus === "allowed_with_review") && POPULATION_BLOCKED_TARGET_CLAIM_CLASSES.has(payload.downstreamUsePolicy.targetClaimClass)) {
        failures.push(failure("POPULATION_HANDOFF_BLOCKED_TRANSITION", "Population variability handoffs cannot authorize direct adversity, risk, or regulatory claim transitions.", "$.downstreamUsePolicy.targetClaimClass"));
      }
    }

    // acceptedClaims normally holds claim-id REFERENCES; scan EVERY entry for an
    // overclaim or a residual exotic glyph (a separator-joined assertion like
    // "safe_for_regulatory_use" dodged the earlier whitespace-only heuristic).
    // Legit id refs like "claim-causal-support-001" do not match the general
    // lexicon (bare causal/adverse/risk are no longer in it) and are pure ASCII,
    // so they pass cleanly.
    if ((payload.acceptedClaims ?? []).some((claim) => isAssertedOverclaimToken(GENERAL_OVERCLAIM, claim) || hasResidualNonAsciiLetter(claim))) {
      failures.push(failure("HANDOFF_ACCEPTED_CLAIM_OVERCLAIM", "Handoff acceptedClaims must reference claim records, not assert scientific or regulatory conclusions.", "$.acceptedClaims"));
    }

    const nestedResult = validateScientificObjectPolicy(payload.downstreamUsePolicy, options);
    addNestedFailures(failures, nestedResult, "$.downstreamUsePolicy");
  }

  if (payload.schemaId === SCHEMA_IDS.toxMcpObject) {
    const manifestEntry = manifestById.get(payload.schemaId);
    if (!manifestEntry) {
      failures.push(failure("SCHEMA_MANIFEST_REQUIRED", "ToxMcpObject policy validation requires a schema manifest.", "$.schemaDigest"));
    } else if (payload.schemaDigest !== `sha256:${manifestEntry.digest}`) {
      failures.push(failure("SCHEMA_DIGEST_MISMATCH", "Object schema digest does not match schema manifest.", "$.schemaDigest"));
    }

    if (payload.migrationStatus === "unknown_major_blocked") {
      failures.push(failure("UNKNOWN_MAJOR_SCHEMA_VERSION", "Unknown major schema versions must be blocked.", "$.migrationStatus"));
    }

    // Deep-scan ALL narrative leaves (not only limitations/knownDataGaps),
    // matching the AiModelUseRecord treatment — ToxMcpObject is the generic
    // envelope most fleet outputs wrap in.
    if (containsDeepOverclaim(payload)) {
      failures.push(failure("FREE_TEXT_OVERCLAIM", "Free text cannot carry hidden scientific or regulatory overclaims.", "$"));
    }

    // Re-validate the declared nested governed records the envelope embeds
    // (previously never re-checked): a ready-with-blockers ReviewState or a
    // non-protective NonClaimBoundary could otherwise hide inside a
    // clean-looking wrapper. (Records under SCHEMA-UNDECLARED keys cannot exist
    // in schema-valid input — every schema is additionalProperties:false — so
    // callers MUST schema-validate before policy-validation.)
    if (payload.reviewState && typeof payload.reviewState === "object") {
      addNestedFailures(failures, validateScientificObjectPolicy(payload.reviewState, options), "$.reviewState");
    }
    (payload.nonClaimBoundaries ?? []).forEach((boundary, index) => {
      if (boundary && typeof boundary === "object") {
        addNestedFailures(failures, validateScientificObjectPolicy(boundary, options), `$.nonClaimBoundaries[${index}]`);
      }
    });
  }

  const dedupedFailures = dedupeFailures(failures);
  return { valid: dedupedFailures.length === 0, failures: dedupedFailures };
}

export function validateScientificBundlePolicy(payloads, bundlePolicyType, options = {}) {
  const failures = [];

  payloads.forEach((payload, index) => {
    const nestedResult = validateScientificObjectPolicy(payload, options);
    addNestedFailures(failures, nestedResult, `$[${index}]`);
  });

  if (!RECOGNIZED_BUNDLE_POLICY_TYPES.has(bundlePolicyType)) {
    failures.push(failure("UNKNOWN_BUNDLE_POLICY_TYPE", "Bundle policy type must be recognized so bundle-specific checks cannot silently no-op.", "$"));
  }

  if (bundlePolicyType === "ontology_aop_context_handoff") {
    const semanticUncertainties = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.uncertaintyRecord && payload.uncertaintyClass === "semantic_mapping");
    const nonClaimBoundaries = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.nonClaimBoundary);
    const confidenceCeilings = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.confidenceCeiling && payload.ceilingType === "semantic_loss");
    const semanticLossEvents = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.semanticLossEvent && (payload.lossType === "ontology_alignment" || payload.lossType === "handoff"));
    const ontologyHandoffs = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.handoffEnvelope && isOntologyAopHandoff(payload));
    const limitedOntologyHandoffs = ontologyHandoffs.filter((payload) => payload.compatibility === "accepted_with_limitations");
    const linkedProtectionIds = new Set(ontologyHandoffs.flatMap((payload) => payload.objectRefs));

    const isConstrainedSemanticUncertainty = (payload) => payload.propagationRule === "cap_confidence" || payload.propagationRule === "review_required";
    const isProtectiveNonClaimBoundary = (payload) => payload.reviewerRequirement !== "none" && payload.autonomousUseProhibition === true && hasAllProhibitionKeywords(payload.prohibitedClaims);
    const isProtectiveConfidenceCeiling = (payload) => (payload.maxSupportLevel === "not_assessed" || payload.maxSupportLevel === "context_only" || payload.maxSupportLevel === "weak") && (payload.maxActionability === "none" || payload.maxActionability === "screening" || payload.maxActionability === "prioritization" || payload.maxActionability === "requires_review");
    const isProtectiveSemanticLoss = (payload) => payload.downstreamImpact === "cap_confidence" || payload.downstreamImpact === "review_required" || payload.downstreamImpact === "block_claim";

    const allProtectionIds = [
      ...semanticUncertainties,
      ...nonClaimBoundaries,
      ...confidenceCeilings,
      ...semanticLossEvents
    ].map(getProtectionId).filter(Boolean);
    const allProtectionsLinked = allProtectionIds.length > 0 && allProtectionIds.every((id) => linkedProtectionIds.has(id));

    if (semanticUncertainties.length === 0) {
      failures.push(failure("SEMANTIC_MAPPING_UNCERTAINTY_REQUIRED", "Ontology/AOP context handoff requires semantic-mapping uncertainty.", "$"));
    } else if (!semanticUncertainties.every(isConstrainedSemanticUncertainty)) {
      failures.push(failure("SEMANTIC_MAPPING_UNCERTAINTY_MUST_CONSTRAIN", "Semantic-mapping uncertainty must cap confidence or require review.", "$"));
    }
    if (nonClaimBoundaries.length === 0) {
      failures.push(failure("NONCLAIM_BOUNDARY_REQUIRED", "Ontology/AOP context handoff requires explicit non-claim boundaries.", "$"));
    } else if (!nonClaimBoundaries.every(isProtectiveNonClaimBoundary)) {
      failures.push(failure("NONCLAIM_BOUNDARY_MUST_PROTECT", "Ontology/AOP non-claim boundary must require review, prohibit autonomous use, and block causal/KER/adversity/risk/regulatory claims.", "$"));
    }
    if (confidenceCeilings.length === 0) {
      failures.push(failure("ONTOLOGY_CONFIDENCE_CEILING_REQUIRED", "Ontology/AOP context handoff requires a semantic-loss confidence ceiling.", "$"));
    } else if (!confidenceCeilings.every(isProtectiveConfidenceCeiling)) {
      failures.push(failure("ONTOLOGY_CONFIDENCE_CEILING_MUST_CONSTRAIN", "Ontology/AOP confidence ceiling must cap support and actionability.", "$"));
    }
    if (semanticLossEvents.length === 0) {
      failures.push(failure("SEMANTIC_LOSS_EVENT_REQUIRED", "Ontology/AOP context handoff requires a semantic-loss event.", "$"));
    } else if (!semanticLossEvents.every(isProtectiveSemanticLoss)) {
      failures.push(failure("SEMANTIC_LOSS_MUST_CONSTRAIN", "Ontology/AOP semantic loss must require review, cap confidence, or block claims.", "$"));
    }
    if (limitedOntologyHandoffs.length === 0) {
      failures.push(failure("ONTOLOGY_HANDOFF_REQUIRES_LIMITATIONS", "Ontology/AOP bundle requires an accepted-with-limitations handoff.", "$"));
    }
    if (ontologyHandoffs.length > 0 && !allProtectionsLinked) {
      failures.push(failure("ONTOLOGY_PROTECTIONS_MUST_BE_LINKED", "Ontology/AOP handoff objectRefs must link all protection records used by the bundle.", "$"));
    }
  }

  if (bundlePolicyType === "bioactivity_pod_woe_iata_handoff") {
    const assayQualityRecords = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.assayStudyQuality);
    const replicateDesigns = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.replicateDesign);
    const concentrationResponseDesigns = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.concentrationResponseDesign);
    const bioactivityObservations = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.bioactivityObservation);
    const podRecords = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.pointOfDepartureRecord);
    const podReadinessRecords = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.bioactivityPodReadiness);
    const applicabilityBoundaries = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.applicabilityBoundary);
    const evidenceAdmissibilityRecords = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.evidenceAdmissibility);
    const uncertainties = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.uncertaintyRecord);
    const confidenceCeilings = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.confidenceCeiling);
    const nonClaimBoundaries = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.nonClaimBoundary);
    const woeEvaluations = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.weightOfEvidenceEvaluation);
    const iataStrategyDecisions = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.iataStrategyDecision);
    const handoffs = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.handoffEnvelope && (isBioactivityPodWoeHandoff(payload) || isWoeIataHandoff(payload)));

    const objectIds = new Set(payloads.map(getObjectId).filter(Boolean));
    const bioactivityIds = new Set(bioactivityObservations.map((payload) => payload.bioactivityObservationId));
    const podIds = new Set(podRecords.map((payload) => payload.podId));
    const woeIds = new Set(woeEvaluations.map((payload) => payload.woeEvaluationId));
    const linkedRefs = new Set(handoffs.flatMap((payload) => payload.objectRefs));
    const admissibleEvidenceRefs = new Set(
      evidenceAdmissibilityRecords
        .filter((payload) => payload.status === "admitted" || payload.status === "advisory")
        .map((payload) => payload.evidenceRef ?? payload.admissibilityId)
    );
    const protectionIds = [
      ...applicabilityBoundaries,
      ...evidenceAdmissibilityRecords,
      ...uncertainties,
      ...confidenceCeilings,
      ...nonClaimBoundaries,
      ...podReadinessRecords
    ].map(getObjectId).filter(Boolean);
    const primaryIds = [
      ...assayQualityRecords,
      ...replicateDesigns,
      ...concentrationResponseDesigns,
      ...bioactivityObservations,
      ...podRecords,
      ...woeEvaluations,
      ...iataStrategyDecisions
    ].map(getObjectId).filter(Boolean);

    if (assayQualityRecords.length === 0) {
      failures.push(failure("ASSAY_STUDY_QUALITY_REQUIRED", "Bioactivity/PoD handoff requires assay study quality records.", "$"));
    }
    if (replicateDesigns.length === 0) {
      failures.push(failure("BIOLOGICAL_REPLICATE_COUNT_REQUIRED", "Bioactivity/PoD handoff requires replicate design records.", "$"));
    }
    if (concentrationResponseDesigns.length === 0) {
      failures.push(failure("INSUFFICIENT_CONCENTRATION_RESPONSE", "Bioactivity/PoD handoff requires concentration-response design records.", "$"));
    }
    if (bioactivityObservations.length === 0) {
      failures.push(failure("BIOACTIVITY_OBSERVATION_REQUIRED", "Bioactivity/PoD handoff requires bioactivity observation records.", "$"));
    }
    if (podRecords.length === 0) {
      failures.push(failure("POINT_OF_DEPARTURE_REQUIRED", "Bioactivity/PoD handoff requires point-of-departure records.", "$"));
    }
    if (podReadinessRecords.length === 0) {
      failures.push(failure("BIOACTIVITY_POD_READINESS_REQUIRED", "Bioactivity/PoD handoff requires PoD readiness records.", "$"));
    }
    if (applicabilityBoundaries.length === 0) {
      failures.push(failure("APPLICABILITY_BOUNDARY_REQUIRED", "Bioactivity/PoD handoff requires applicability boundaries.", "$"));
    }
    if (evidenceAdmissibilityRecords.length === 0) {
      failures.push(failure("EVIDENCE_ADMITTED_WITHOUT_ADMISSIBILITY", "Bioactivity/PoD/WoE handoff requires evidence admissibility records.", "$"));
    }
    if (uncertainties.length === 0) {
      failures.push(failure("CATEGORY_CLAIM_UNCERTAINTY_REQUIRED", "Bioactivity/PoD/WoE handoff requires explicit uncertainty records.", "$"));
    }
    if (confidenceCeilings.length === 0) {
      failures.push(failure("UNRESOLVED_CONFLICT_REQUIRES_CEILING", "Bioactivity/PoD/WoE handoff requires confidence ceilings.", "$"));
    }
    if (nonClaimBoundaries.length === 0) {
      failures.push(failure("NONCLAIM_BOUNDARY_REQUIRED", "Bioactivity/PoD/WoE/IATA handoff requires non-claim boundaries.", "$"));
    }
    if (woeEvaluations.length === 0) {
      failures.push(failure("WEIGHT_OF_EVIDENCE_SUMMARY_REQUIRED", "IATA handoff requires WoE evaluation.", "$"));
    }
    if (iataStrategyDecisions.length === 0) {
      failures.push(failure("IATA_INPUT_WITHOUT_WOE_SUMMARY", "Bioactivity/PoD/WoE handoff requires IATA strategy input or decision record.", "$"));
    }
    if (handoffs.length === 0) {
      failures.push(failure("HANDOFF_REQUIRED", "Bioactivity/PoD/WoE/IATA bundle requires version-pinned handoff envelopes.", "$"));
    }

    for (const pod of podRecords) {
      if (!pod.sourceBioactivityRefs.every((ref) => bioactivityIds.has(ref))) {
        failures.push(failure("POD_SOURCE_MODALITY_OVERWRITE", "PoD source bioactivity references must resolve to bioactivity observations in the bundle.", "$"));
      }
    }

    for (const readiness of podReadinessRecords) {
      if (!podIds.has(readiness.podRef) || !readiness.bioactivityObservationRefs.every((ref) => bioactivityIds.has(ref)) || !readiness.requiredRecordRefs.every((ref) => objectIds.has(ref))) {
        failures.push(failure("BIOACTIVITY_POD_READINESS_MISSING_REQUIRED_RECORD", "PoD readiness records must link to the PoD, bioactivity observations, and required quality records in the bundle.", "$"));
      }
    }

    for (const woe of woeEvaluations) {
      const missingAdmissibility = woe.evidenceRefs.filter((ref) => !admissibleEvidenceRefs.has(ref));
      if (missingAdmissibility.length > 0) {
        failures.push(failure("EVIDENCE_ADMITTED_WITHOUT_ADMISSIBILITY", "Every WoE evidence reference must have an admissibility record.", "$"));
      }

      if (woe.conclusionClaimClass === "risk" || woe.conclusionClaimClass === "regulatory_translation" || woe.conclusionClaimClass === "adversity") {
        failures.push(failure("BIOACTIVITY_WOE_NOT_RISK_OR_ADVERSITY", "Bioactivity/PoD WoE slice cannot conclude adversity, risk, or regulatory translation.", "$"));
      }
    }

    for (const iata of iataStrategyDecisions) {
      if (!iata.evidenceBundleRefs.some((ref) => woeIds.has(ref))) {
        failures.push(failure("IATA_INPUT_WITHOUT_WOE_SUMMARY", "IATA strategy decisions must reference the bundled WoE evaluation.", "$"));
      }
    }

    const outsideOrBlockedDomain = applicabilityBoundaries.some((payload) =>
      payload.domainMatch === "outside" ||
      payload.domainMatch === "unknown_with_blocker" ||
      !payload.domainMatch ||
      (payload.domainMatch !== "inside" && payload.outsideDomainAction === "block")
    );
    const actionablePod = podRecords.some((payload) =>
      payload.qualificationStatus !== "blocked" &&
      payload.qualificationStatus !== "not_assessed" &&
      payload.qualificationStatus !== "exploratory" &&
      payload.actionability !== "none"
    ) || podReadinessRecords.some((payload) => payload.readinessStatus === "eligible" || payload.readinessStatus === "conditional");
    if (outsideOrBlockedDomain && actionablePod) {
      failures.push(failure("POD_OUTSIDE_APPLICABILITY_DOMAIN", "PoD outputs cannot be actionable outside the declared applicability domain.", "$"));
    }

    if (handoffs.length > 0 && protectionIds.some((id) => !linkedRefs.has(id))) {
      failures.push(failure("BIOACTIVITY_POD_PROTECTIONS_MUST_BE_LINKED", "Bioactivity/PoD handoff objectRefs must link applicability, admissibility, uncertainty, confidence ceiling, readiness, and non-claim records.", "$"));
    }

    if (handoffs.length > 0 && primaryIds.some((id) => !linkedRefs.has(id))) {
      failures.push(failure("BIOACTIVITY_POD_PRIMARY_RECORDS_MUST_BE_LINKED", "Bioactivity/PoD handoff objectRefs must link assay quality, replicate design, concentration response, bioactivity, PoD, WoE, and IATA records.", "$"));
    }
  }

  if (bundlePolicyType === "exposure_internal_exposure_ber_handoff") {
    const exposureScenarios = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.exposureScenarioContext);
    const routeDoseEstimates = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.routeDoseEstimate);
    const tkParameterRecords = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.tkParameterProvenance);
    const freeCorrections = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.freeConcentrationCorrection);
    const internalExposureSummaries = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.internalExposureSummary);
    const comparabilityQualifications = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.comparabilityQualification);
    const reverseDosimetryRecords = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.reverseDosimetryRecord);
    const berRecords = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.bioactivityExposureRatioRecord);
    const uncertainties = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.uncertaintyRecord);
    const confidenceCeilings = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.confidenceCeiling);
    const nonClaimBoundaries = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.nonClaimBoundary);
    const allHandoffs = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.handoffEnvelope);
    const handoffs = allHandoffs.filter(isExposureInternalExposureBerHandoff);

    const objectIds = new Set(payloads.map(getObjectId).filter(Boolean));
    const exposureScenarioIds = new Set(exposureScenarios.map((payload) => payload.exposureScenarioContextId));
    const routeDoseIds = new Set(routeDoseEstimates.map((payload) => payload.routeDoseEstimateId));
    const internalExposureIds = new Set(internalExposureSummaries.map((payload) => payload.internalExposureSummaryId));
    const comparabilityIds = new Set(comparabilityQualifications.map((payload) => payload.comparabilityQualificationId));
    const uncertaintyIds = new Set(uncertainties.map((payload) => payload.uncertaintyId));
    const confidenceCeilingIds = new Set(confidenceCeilings.map((payload) => payload.confidenceCeilingId));
    const linkedRefs = new Set(handoffs.flatMap((payload) => payload.objectRefs));
    const requiredLinkedIds = [
      ...exposureScenarios,
      ...routeDoseEstimates,
      ...tkParameterRecords,
      ...freeCorrections,
      ...internalExposureSummaries,
      ...comparabilityQualifications,
      ...reverseDosimetryRecords,
      ...berRecords,
      ...uncertainties,
      ...confidenceCeilings,
      ...nonClaimBoundaries
    ].map(getObjectId).filter(Boolean);
    const sliceObjectIds = new Set(requiredLinkedIds);
    const offAliasTouchingHandoffs = allHandoffs.filter((payload) =>
      !isExposureInternalExposureBerHandoff(payload) &&
      payload.objectRefs.some((ref) => sliceObjectIds.has(ref))
    );
    const allDomainObjectsWithUncertainty = [
      ...exposureScenarios,
      ...routeDoseEstimates,
      ...tkParameterRecords,
      ...freeCorrections,
      ...internalExposureSummaries,
      ...comparabilityQualifications,
      ...reverseDosimetryRecords,
      ...berRecords
    ];
    const allDomainObjectsWithConfidenceCeilings = [
      ...routeDoseEstimates,
      ...freeCorrections,
      ...internalExposureSummaries,
      ...comparabilityQualifications,
      ...reverseDosimetryRecords,
      ...berRecords
    ];
    const unresolvedUncertaintyRefs = allDomainObjectsWithUncertainty.flatMap((payload) =>
      (payload.uncertaintyRefs ?? []).filter((ref) => hasSubstantiveRefs([ref]) && !uncertaintyIds.has(ref))
    );
    const unresolvedConfidenceCeilingRefs = allDomainObjectsWithConfidenceCeilings.flatMap((payload) =>
      (payload.confidenceCeilingRefs ?? []).filter((ref) => hasSubstantiveRefs([ref]) && !confidenceCeilingIds.has(ref))
    );
    const unresolvedCeilingTriggerRefs = confidenceCeilings.flatMap((payload) =>
      payload.triggerRefs.filter((ref) => hasSubstantiveRefs([ref]) && !uncertaintyIds.has(ref))
    );
    const isConstrainedInternalExposureUncertainty = (payload) =>
      payload.propagationRule === "cap_confidence" ||
      payload.propagationRule === "review_required" ||
      payload.propagationRule === "block_claim";
    const isConstrainedInternalExposureCeiling = (payload) =>
      payload.maxSupportLevel !== "strong" && payload.maxActionability !== "decision_support";

    if (exposureScenarios.length === 0) {
      failures.push(failure("EXPOSURE_SCENARIO_CONTEXT_REQUIRED", "Exposure/Internal exposure bundle requires an exposure scenario context.", "$"));
    }
    if (routeDoseEstimates.length === 0) {
      failures.push(failure("ROUTE_DOSE_ESTIMATE_REQUIRED", "Exposure/Internal exposure bundle requires external route-dose estimates.", "$"));
    }
    if (tkParameterRecords.length === 0) {
      failures.push(failure("TK_PARAMETER_PROVENANCE_REQUIRED", "Exposure/Internal exposure bundle requires TK parameter provenance.", "$"));
    }
    if (freeCorrections.length === 0) {
      failures.push(failure("FREE_CONCENTRATION_CORRECTION_REQUIRED", "Exposure/Internal exposure bundle requires free concentration correction or an explicit record of assumptions.", "$"));
    }
    if (internalExposureSummaries.length === 0) {
      failures.push(failure("INTERNAL_EXPOSURE_SUMMARY_REQUIRED", "Exposure/Internal exposure bundle requires internal exposure summaries.", "$"));
    }
    if (comparabilityQualifications.length === 0) {
      failures.push(failure("COMPARABILITY_QUALIFICATION_REQUIRED", "BER handoff requires comparability qualification.", "$"));
    }
    if (berRecords.length === 0) {
      failures.push(failure("BER_RECORD_REQUIRED", "Exposure/Internal exposure bundle requires a BER record.", "$"));
    }
    if (uncertainties.length === 0) {
      failures.push(failure("INTERNAL_EXPOSURE_UNCERTAINTY_REQUIRED", "Exposure/Internal exposure bundle requires uncertainty records.", "$"));
    }
    if (confidenceCeilings.length === 0) {
      failures.push(failure("BER_UNCERTAINTY_AND_CEILING_REQUIRED", "Exposure/Internal exposure bundle requires confidence ceilings.", "$"));
    }
    if (nonClaimBoundaries.length === 0) {
      failures.push(failure("NONCLAIM_BOUNDARY_REQUIRED", "Exposure/Internal exposure bundle requires non-claim boundaries.", "$"));
    } else if (!nonClaimBoundaries.every((payload) => payload.reviewerRequirement !== "none" && payload.autonomousUseProhibition === true && hasInternalExposureProhibitionKeywords(payload.prohibitedClaims))) {
      failures.push(failure("INTERNAL_EXPOSURE_NONCLAIM_BOUNDARY_MUST_PROTECT", "Exposure/Internal exposure non-claim boundaries must require review, prohibit autonomous use, and block risk, safety, regulatory, and validated-PBPK claims.", "$"));
    }
    if (handoffs.length === 0) {
      failures.push(failure("HANDOFF_REQUIRED", "Exposure/Internal exposure bundle requires version-pinned handoff envelopes.", "$"));
    }
    if (uncertainties.length > 0 && !uncertainties.every(isConstrainedInternalExposureUncertainty)) {
      failures.push(failure("INTERNAL_EXPOSURE_UNCERTAINTY_MUST_CONSTRAIN", "Exposure/Internal exposure uncertainty records must cap confidence, require review, or block claims.", "$"));
    }
    if (confidenceCeilings.length > 0 && !confidenceCeilings.every(isConstrainedInternalExposureCeiling)) {
      failures.push(failure("INTERNAL_EXPOSURE_CONFIDENCE_CEILING_MUST_CONSTRAIN", "Exposure/Internal exposure confidence ceilings cannot permit strong support or decision support.", "$"));
    }
    if (unresolvedUncertaintyRefs.length > 0 || unresolvedCeilingTriggerRefs.length > 0) {
      failures.push(failure("EXPOSURE_UNCERTAINTY_REFS_MUST_RESOLVE", "Exposure/Internal exposure uncertainty and ceiling trigger refs must resolve to bundled UncertaintyRecord ids.", "$"));
    }
    if (unresolvedConfidenceCeilingRefs.length > 0) {
      failures.push(failure("EXPOSURE_CONFIDENCE_CEILING_REFS_MUST_RESOLVE", "Exposure/Internal exposure confidence ceiling refs must resolve to bundled ConfidenceCeiling ids.", "$"));
    }
    if (offAliasTouchingHandoffs.some((payload) => payload.compatibility === "accepted")) {
      failures.push(failure("INTERNAL_EXPOSURE_HANDOFF_REQUIRES_LIMITATIONS", "Any handoff touching Exposure/PBK/IVIVE-BER records must preserve limitations until externally qualified.", "$"));
    }
    if (offAliasTouchingHandoffs.some((payload) => anyForbidden(payload.acceptedClaims, INTERNAL_EXPOSURE_BLOCKED_HANDOFF_CLAIM_PATTERN))) {
      failures.push(failure("INTERNAL_EXPOSURE_HANDOFF_BLOCKED_CLAIM", "Any handoff touching Exposure/PBK/IVIVE-BER records cannot accept risk, safety, regulatory, or validated-PBPK claims.", "$"));
    }
    if (offAliasTouchingHandoffs.some((payload) => (payload.downstreamUsePolicy.transitionStatus === "allowed" || payload.downstreamUsePolicy.transitionStatus === "allowed_with_review") && INTERNAL_EXPOSURE_BLOCKED_TARGET_CLAIM_CLASSES.has(payload.downstreamUsePolicy.targetClaimClass))) {
      failures.push(failure("INTERNAL_EXPOSURE_HANDOFF_BLOCKED_TRANSITION", "Any handoff touching Exposure/PBK/IVIVE-BER records cannot authorize direct adversity, risk, or regulatory claim transitions.", "$"));
    }

    for (const routeDose of routeDoseEstimates) {
      if (!exposureScenarioIds.has(routeDose.exposureScenarioContextRef)) {
        failures.push(failure("ROUTE_DOSE_SCENARIO_REF_REQUIRED", "Route-dose estimates must reference an exposure scenario in the bundle.", "$"));
      }
    }

    for (const internalExposure of internalExposureSummaries) {
      if (!internalExposure.sourceExposureRefs.every((ref) => routeDoseIds.has(ref))) {
        failures.push(failure("INTERNAL_EXPOSURE_SOURCE_REF_REQUIRED", "Internal exposure summaries must reference route-dose estimates in the bundle.", "$"));
      }
      if (!internalExposure.parameterProvenanceRefs.every((ref) => objectIds.has(ref))) {
        failures.push(failure("INTERNAL_EXPOSURE_PARAMETER_REF_REQUIRED", "Internal exposure summaries must reference bundled TK parameter provenance.", "$"));
      }
    }

    for (const comparability of comparabilityQualifications) {
      const matchFields = [
        comparability.routeMatch,
        comparability.timeBasisMatch,
        comparability.matrixMatch,
        comparability.bindingBasisMatch,
        comparability.populationMatch,
        comparability.compartmentMatch
      ];
      const hasMismatch = matchFields.some((value) => value === "mismatch" || value === "unknown_with_blocker" || value === "not_assessed");
      if (!internalExposureIds.has(comparability.internalExposureRef)) {
        failures.push(failure("COMPARABILITY_INTERNAL_EXPOSURE_REF_REQUIRED", "Comparability qualification must reference bundled internal exposure.", "$"));
      }
      if (hasMismatch) {
        failures.push(failure("COMPARABILITY_MISMATCH_BLOCKS_BER", "BER cannot proceed from mismatched or unassessed comparability.", "$"));
      }
    }

    for (const ber of berRecords) {
      if (!internalExposureIds.has(ber.internalExposureRef) || !comparabilityIds.has(ber.comparabilityQualificationRef)) {
        failures.push(failure("BER_REQUIRES_COMPARABILITY", "BER records must reference bundled internal exposure and comparability qualification.", "$"));
      }
    }

    if (handoffs.length > 0 && requiredLinkedIds.some((id) => !linkedRefs.has(id))) {
      failures.push(failure("INTERNAL_EXPOSURE_RECORDS_MUST_BE_LINKED", "Exposure/PBK/IVIVE-BER handoff objectRefs must link scenario, route dose, TK parameters, free correction, internal exposure, comparability, BER, uncertainty, confidence ceiling, and non-claim records.", "$"));
    }
  }

  if (bundlePolicyType === "population_variability_susceptibility_handoff") {
    const populationProfiles = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.populationProfile);
    const sensitiveDescriptorPolicies = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.sensitiveDescriptorPolicy);
    const subgroupDefinitions = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.subgroupDefinition);
    const variabilityDimensions = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.variabilityDimension);
    const modifierEvidenceLanes = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.modifierEvidenceLane);
    const subgroupComparisons = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.subgroupComparison);
    const susceptibilitySummaries = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.susceptibilitySummary);
    const subgroupReviewPackets = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.subgroupReviewPacket);
    const uncertainties = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.uncertaintyRecord);
    const confidenceCeilings = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.confidenceCeiling);
    const nonClaimBoundaries = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.nonClaimBoundary);
    const allHandoffs = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.handoffEnvelope);
    const handoffs = allHandoffs.filter(isPopulationVariabilityHandoff);

    const objectIds = new Set(payloads.map(getObjectId).filter(Boolean));
    const populationProfileIds = new Set(populationProfiles.map((payload) => payload.populationProfileId));
    const sensitivePolicyIds = new Set(sensitiveDescriptorPolicies.map((payload) => payload.sensitiveDescriptorPolicyId));
    const subgroupIds = new Set(subgroupDefinitions.map((payload) => payload.subgroupDefinitionId));
    const dimensionIds = new Set(variabilityDimensions.map((payload) => payload.variabilityDimensionId));
    const laneIds = new Set(modifierEvidenceLanes.map((payload) => payload.modifierEvidenceLaneId));
    const comparisonIds = new Set(subgroupComparisons.map((payload) => payload.subgroupComparisonId));
    const summaryIds = new Set(susceptibilitySummaries.map((payload) => payload.susceptibilitySummaryId));
    const uncertaintyIds = new Set(uncertainties.map((payload) => payload.uncertaintyId));
    const confidenceCeilingIds = new Set(confidenceCeilings.map((payload) => payload.confidenceCeilingId));
    const nonClaimBoundaryIds = new Set(nonClaimBoundaries.map((payload) => payload.boundaryId));
    const linkedRefs = new Set(handoffs.flatMap((payload) => payload.objectRefs));
    const requiredLinkedIds = [
      ...populationProfiles,
      ...sensitiveDescriptorPolicies,
      ...subgroupDefinitions,
      ...variabilityDimensions,
      ...modifierEvidenceLanes,
      ...subgroupComparisons,
      ...susceptibilitySummaries,
      ...subgroupReviewPackets,
      ...uncertainties,
      ...confidenceCeilings,
      ...nonClaimBoundaries
    ].map(getObjectId).filter(Boolean);
    const sliceObjectIds = new Set(requiredLinkedIds);
    const offAliasTouchingHandoffs = allHandoffs.filter((payload) =>
      !isPopulationVariabilityHandoff(payload) &&
      payload.objectRefs.some((ref) => sliceObjectIds.has(ref))
    );

    const allDomainObjectsWithUncertainty = [
      ...populationProfiles,
      ...subgroupDefinitions,
      ...variabilityDimensions,
      ...modifierEvidenceLanes,
      ...subgroupComparisons,
      ...susceptibilitySummaries,
      ...subgroupReviewPackets
    ];
    const allDomainObjectsWithConfidenceCeilings = [
      ...variabilityDimensions,
      ...modifierEvidenceLanes,
      ...subgroupComparisons,
      ...susceptibilitySummaries,
      ...subgroupReviewPackets
    ];
    const allDomainObjectsWithNonClaimBoundaries = [
      ...susceptibilitySummaries,
      ...subgroupReviewPackets
    ];
    const unresolvedUncertaintyRefs = allDomainObjectsWithUncertainty.flatMap((payload) =>
      (payload.uncertaintyRefs ?? []).filter((ref) => hasSubstantiveRefs([ref]) && !uncertaintyIds.has(ref))
    );
    const unresolvedConfidenceCeilingRefs = allDomainObjectsWithConfidenceCeilings.flatMap((payload) =>
      (payload.confidenceCeilingRefs ?? []).filter((ref) => hasSubstantiveRefs([ref]) && !confidenceCeilingIds.has(ref))
    );
    const unresolvedNonClaimBoundaryRefs = allDomainObjectsWithNonClaimBoundaries.flatMap((payload) =>
      (payload.nonClaimBoundaryRefs ?? []).filter((ref) => hasSubstantiveRefs([ref]) && !nonClaimBoundaryIds.has(ref))
    );
    const unresolvedCeilingTriggerRefs = confidenceCeilings.flatMap((payload) =>
      payload.triggerRefs.filter((ref) => hasSubstantiveRefs([ref]) && !uncertaintyIds.has(ref))
    );

    if (populationProfiles.length === 0) {
      failures.push(failure("POPULATION_PROFILE_REQUIRED", "Population variability handoff requires population profiles.", "$"));
    }
    if (sensitiveDescriptorPolicies.length === 0) {
      failures.push(failure("SENSITIVE_DESCRIPTOR_POLICY_REQUIRED", "Population variability handoff requires sensitive descriptor policy records.", "$"));
    }
    if (subgroupDefinitions.length === 0) {
      failures.push(failure("SUBGROUP_DEFINITION_REQUIRED", "Population variability handoff requires subgroup definitions.", "$"));
    }
    if (variabilityDimensions.length === 0) {
      failures.push(failure("VARIABILITY_DIMENSION_REQUIRED", "Population variability handoff requires variability dimensions.", "$"));
    }
    if (modifierEvidenceLanes.length === 0) {
      failures.push(failure("MODIFIER_EVIDENCE_LANE_REQUIRED", "Population variability handoff requires modifier evidence lanes.", "$"));
    }
    if (subgroupComparisons.length === 0) {
      failures.push(failure("SUBGROUP_COMPARISON_REQUIRED", "Population variability handoff requires subgroup comparisons.", "$"));
    }
    if (susceptibilitySummaries.length === 0) {
      failures.push(failure("SUSCEPTIBILITY_SUMMARY_REQUIRED", "Population variability handoff requires susceptibility summaries.", "$"));
    }
    if (subgroupReviewPackets.length === 0) {
      failures.push(failure("SUBGROUP_REVIEW_PACKET_REQUIRED", "Population variability handoff requires subgroup review packets.", "$"));
    }
    if (uncertainties.length === 0) {
      failures.push(failure("POPULATION_UNCERTAINTY_REQUIRED", "Population variability handoff requires uncertainty records.", "$"));
    }
    if (confidenceCeilings.length === 0) {
      failures.push(failure("POPULATION_CONFIDENCE_CEILING_REQUIRED", "Population variability handoff requires confidence ceilings.", "$"));
    }
    if (nonClaimBoundaries.length === 0) {
      failures.push(failure("NONCLAIM_BOUNDARY_REQUIRED", "Population variability handoff requires non-claim boundaries.", "$"));
    } else if (!nonClaimBoundaries.every((payload) => payload.reviewerRequirement !== "none" && payload.autonomousUseProhibition === true && hasPopulationProhibitionKeywords(payload.prohibitedClaims))) {
      failures.push(failure("POPULATION_NONCLAIM_BOUNDARY_MUST_PROTECT", "Population non-claim boundaries must require review, prohibit autonomous use, and block individual, risk, safety, regulatory, and proxy-biology claims.", "$"));
    }
    if (handoffs.length === 0) {
      failures.push(failure("HANDOFF_REQUIRED", "Population variability bundle requires version-pinned handoff envelopes.", "$"));
    }
    if (uncertainties.length > 0 && !uncertainties.every(isConstrainedPopulationUncertainty)) {
      failures.push(failure("POPULATION_UNCERTAINTY_MUST_CONSTRAIN", "Population variability uncertainty records must cap confidence, require review, or block claims.", "$"));
    }
    if (confidenceCeilings.length > 0 && !confidenceCeilings.every(isConstrainedPopulationCeiling)) {
      failures.push(failure("POPULATION_CONFIDENCE_CEILING_MUST_CONSTRAIN", "Population variability confidence ceilings cannot permit strong support or decision support.", "$"));
    }
    if (unresolvedUncertaintyRefs.length > 0 || unresolvedCeilingTriggerRefs.length > 0) {
      failures.push(failure("POPULATION_UNCERTAINTY_REFS_MUST_RESOLVE", "Population variability uncertainty and ceiling trigger refs must resolve to bundled UncertaintyRecord ids.", "$"));
    }
    if (unresolvedConfidenceCeilingRefs.length > 0) {
      failures.push(failure("POPULATION_CONFIDENCE_CEILING_REFS_MUST_RESOLVE", "Population variability confidence ceiling refs must resolve to bundled ConfidenceCeiling ids.", "$"));
    }
    if (unresolvedNonClaimBoundaryRefs.length > 0) {
      failures.push(failure("POPULATION_NONCLAIM_REFS_MUST_RESOLVE", "Population variability non-claim boundary refs must resolve to bundled NonClaimBoundary ids.", "$"));
    }
    if (offAliasTouchingHandoffs.some((payload) => payload.compatibility === "accepted")) {
      failures.push(failure("POPULATION_HANDOFF_REQUIRES_LIMITATIONS", "Any handoff touching population variability records must preserve limitations.", "$"));
    }
    if (offAliasTouchingHandoffs.some((payload) => anyForbidden(payload.acceptedClaims, POPULATION_BLOCKED_DOWNSTREAM_USE_PATTERN))) {
      failures.push(failure("POPULATION_HANDOFF_BLOCKED_CLAIM", "Any handoff touching population variability records cannot accept individual, risk, safety, regulatory, or oracle claims.", "$"));
    }
    if (offAliasTouchingHandoffs.some((payload) => (payload.downstreamUsePolicy.transitionStatus === "allowed" || payload.downstreamUsePolicy.transitionStatus === "allowed_with_review") && POPULATION_BLOCKED_TARGET_CLAIM_CLASSES.has(payload.downstreamUsePolicy.targetClaimClass))) {
      failures.push(failure("POPULATION_HANDOFF_BLOCKED_TRANSITION", "Any handoff touching population variability records cannot authorize direct adversity, risk, or regulatory claim transitions.", "$"));
    }

    for (const subgroup of subgroupDefinitions) {
      if (!populationProfileIds.has(subgroup.populationProfileRef) || !populationProfileIds.has(subgroup.comparatorPopulationRef)) {
        failures.push(failure("SUBGROUP_POPULATION_REF_REQUIRED", "Subgroup definitions must reference bundled population profiles.", "$"));
      }
      if (!sensitivePolicyIds.has(subgroup.sensitiveDescriptorPolicyRef)) {
        failures.push(failure("SENSITIVE_DESCRIPTOR_POLICY_REQUIRED", "Subgroup definitions must reference a bundled sensitive descriptor policy.", "$"));
      }
    }

    for (const dimension of variabilityDimensions) {
      if (!subgroupIds.has(dimension.subgroupRef)) {
        failures.push(failure("VARIABILITY_DIMENSION_SUBGROUP_REF_REQUIRED", "Variability dimensions must reference bundled subgroup definitions.", "$"));
      }
      if (!dimension.evidenceLaneRefs.every((ref) => laneIds.has(ref))) {
        failures.push(failure("VARIABILITY_DIMENSION_EVIDENCE_REF_REQUIRED", "Variability dimensions must reference bundled modifier evidence lanes.", "$"));
      }
    }

    for (const comparison of subgroupComparisons) {
      if (!subgroupIds.has(comparison.subgroupRef) || !populationProfileIds.has(comparison.referencePopulationRef) || !populationProfileIds.has(comparison.comparatorPopulationRef)) {
        failures.push(failure("SUBGROUP_COMPARISON_REF_REQUIRED", "Subgroup comparisons must reference bundled subgroup and population profile records.", "$"));
      }
    }

    for (const summary of susceptibilitySummaries) {
      if (!subgroupIds.has(summary.subgroupRef) || !summary.comparisonRefs.every((ref) => comparisonIds.has(ref))) {
        failures.push(failure("SUSCEPTIBILITY_SUMMARY_REF_REQUIRED", "Susceptibility summaries must reference bundled subgroup and comparison records.", "$"));
      }
      if (!summary.dominantDriverRefs.every((ref) => dimensionIds.has(ref) || laneIds.has(ref))) {
        failures.push(failure("SUSCEPTIBILITY_DRIVER_REF_REQUIRED", "Susceptibility summaries must reference bundled variability dimensions or modifier lanes as dominant drivers.", "$"));
      }
    }

    for (const packet of subgroupReviewPackets) {
      const packetRefsResolve =
        packet.populationProfileRefs.every((ref) => populationProfileIds.has(ref)) &&
        packet.subgroupDefinitionRefs.every((ref) => subgroupIds.has(ref)) &&
        packet.sensitiveDescriptorPolicyRefs.every((ref) => sensitivePolicyIds.has(ref)) &&
        packet.variabilityDimensionRefs.every((ref) => dimensionIds.has(ref)) &&
        packet.modifierEvidenceLaneRefs.every((ref) => laneIds.has(ref)) &&
        packet.comparisonRefs.every((ref) => comparisonIds.has(ref)) &&
        packet.susceptibilitySummaryRefs.every((ref) => summaryIds.has(ref));
      if (!packetRefsResolve) {
        failures.push(failure("SUBGROUP_REVIEW_PACKET_REFS_REQUIRED", "Subgroup review packets must reference bundled population, subgroup, policy, dimension, lane, comparison, and summary records.", "$"));
      }
    }

    if (handoffs.length > 0 && requiredLinkedIds.some((id) => !linkedRefs.has(id))) {
      failures.push(failure("POPULATION_RECORDS_MUST_BE_LINKED", "Population variability handoff objectRefs must link profile, subgroup, policy, dimension, evidence lane, comparison, summary, review packet, uncertainty, confidence ceiling, and non-claim records.", "$"));
    }
  }

  if (bundlePolicyType === "control_plane_release_readiness") {
    // LEAN SPINE EVIDENCE BUNDLE (post-reconciliation, ADR-0001). The Hub owns the
    // executable release flow (manifest/benchmark/release-report + go/no-go gating);
    // this bundle validates the SPINE evidence package layered over it: the
    // evidence overlays (which reference the Hub artifacts by digest) + the net-new
    // evidence artifacts, that spine-side refs resolve, single-MCP coherence, and
    // the non-claim / human-review / public-visibility gating. It does NOT re-model
    // the Hub's benchmark cross-validation or readiness decision.
    const overlays = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.spineReleaseReadinessEvidenceOverlay);
    const suiteOverlays = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.spineBenchmarkSuiteEvidenceOverlay);
    const runOverlays = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.spineBenchmarkRunEvidenceOverlay);
    const transports = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.transportCapability);
    const signatures = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.schemaSignature);
    const validationBundles = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.validationEvidenceBundle);
    const auditChains = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.auditEventChain);
    const releasePolicies = payloads.filter((payload) => payload.schemaId === SCHEMA_IDS.releaseVisibilityPolicy);

    const signatureIds = new Set(signatures.map((payload) => payload.signatureId));
    const validationIds = new Set(validationBundles.map((payload) => payload.validationEvidenceBundleId));
    const auditChainIds = new Set(auditChains.map((payload) => payload.auditEventChainId));
    const releasePolicyIds = new Set(releasePolicies.map((payload) => payload.releasePolicyId));
    const suiteOverlayIds = new Set(suiteOverlays.map((payload) => payload.overlayId));
    const refsResolve = (refs, idSet) => refs.every((ref) => idSet.has(ref));

    if (overlays.length === 0) {
      failures.push(failure("RELEASE_READINESS_EVIDENCE_OVERLAY_REQUIRED", "Control-plane release-readiness evidence bundles require a release-readiness evidence overlay.", "$"));
    }
    if (transports.length === 0) {
      failures.push(failure("TRANSPORT_CAPABILITY_REQUIRED", "Control-plane release-readiness evidence bundles require transport capability records.", "$"));
    }
    if (signatures.length === 0) {
      failures.push(failure("SCHEMA_SIGNATURE_REQUIRED", "Control-plane release-readiness evidence bundles require schema signature records.", "$"));
    }
    if (validationBundles.length === 0) {
      failures.push(failure("VALIDATION_EVIDENCE_BUNDLE_REQUIRED", "Control-plane release-readiness evidence bundles require validation evidence bundles.", "$"));
    }
    if (auditChains.length === 0) {
      failures.push(failure("AUDIT_EVENT_CHAIN_REQUIRED", "Control-plane release-readiness evidence bundles require audit event chains.", "$"));
    }
    if (releasePolicies.length === 0) {
      failures.push(failure("RELEASE_VISIBILITY_POLICY_REQUIRED", "Control-plane release-readiness evidence bundles require release visibility policies.", "$"));
    }

    // Single target MCP across all evidence overlays.
    const overlayMcpIds = new Set([...overlays, ...suiteOverlays, ...runOverlays].map((payload) => payload.mcpId));
    if (overlayMcpIds.size > 1) {
      failures.push(failure("CONTROL_PLANE_SINGLE_MCP_REQUIRED", "All evidence overlays in a release-readiness evidence bundle must target the same MCP.", "$"));
    }

    // Spine-side ref resolution (NOT the Hub's executable refs).
    for (const overlay of overlays) {
      if (!(refsResolve(overlay.validationEvidenceBundleRefs, validationIds) && refsResolve(overlay.schemaSignatureRefs, signatureIds) && refsResolve(overlay.auditEventChainRefs, auditChainIds))) {
        failures.push(failure("RELEASE_EVIDENCE_OVERLAY_REFS_MUST_RESOLVE", "Release-readiness evidence overlay refs must resolve to bundled validation evidence, schema signature, and audit event chain records.", "$"));
      }
      if (!releasePolicyIds.has(overlay.releaseVisibilityPolicyRef)) {
        failures.push(failure("RELEASE_VISIBILITY_POLICY_REF_REQUIRED", "Release-readiness evidence overlays must reference a bundled release visibility policy.", "$.releaseVisibilityPolicyRef"));
      }
    }
    for (const runOverlay of runOverlays) {
      if (!suiteOverlayIds.has(runOverlay.benchmarkSuiteOverlayRef)) {
        failures.push(failure("BENCHMARK_RUN_OVERLAY_SUITE_REF_REQUIRED", "Benchmark-run evidence overlays must reference a bundled benchmark-suite evidence overlay.", "$.benchmarkSuiteOverlayRef"));
      }
      if (!auditChainIds.has(runOverlay.auditEventChainRef)) {
        failures.push(failure("BENCHMARK_RUN_OVERLAY_AUDIT_REF_REQUIRED", "Benchmark-run evidence overlays must reference a bundled audit event chain.", "$.auditEventChainRef"));
      }
    }

    // Public-release intent gating (spine evidence side; the Hub owns the go/no-go).
    if (overlays.some((overlay) => PUBLIC_CHANNELS.has(overlay.releaseChannel))) {
      const hasPublicReleasePolicy = releasePolicies.some((policy) =>
        policy.publicReleaseEligible &&
        PUBLIC_CHANNELS.has(policy.intendedReleaseChannel) &&
        policy.repoVisibility === "public" &&
        policy.licenseClearance === "cleared" &&
        policy.dataRightsClearance === "cleared" &&
        policy.secretsScan === "passed" &&
        policy.publicReleaseApproval === "approved"
      );
      if (!hasPublicReleasePolicy) {
        failures.push(failure("CONTROL_PLANE_PUBLIC_RELEASE_REQUIRES_VISIBILITY_CLEARANCE", "Public release intent requires explicit public release visibility, license, data-rights, secrets-scan, and approval clearance.", "$"));
      }

      if (!transports.some((transport) => transport.transport === "streamable_http" && transport.deploymentScope === "public" && transport.releaseQualified)) {
        failures.push(failure("CONTROL_PLANE_PUBLIC_RELEASE_REQUIRES_STREAMABLE_HTTP", "Public ngra.ai release intent requires a public release-qualified Streamable HTTP transport.", "$"));
      }

      const publicOverlays = overlays.filter((overlay) => PUBLIC_CHANNELS.has(overlay.releaseChannel));
      if (publicOverlays.some((overlay) => !["completed", "waived"].includes(overlay.requiredHumanReviewStatus))) {
        failures.push(failure("CONTROL_PLANE_PUBLIC_RELEASE_REQUIRES_HUMAN_REVIEW", "Public-release evidence overlays require completed or formally waived human review.", "$"));
      }

      const publicValidationRefs = new Set(publicOverlays.flatMap((overlay) => overlay.validationEvidenceBundleRefs));
      const publicSignatureRefs = new Set(publicOverlays.flatMap((overlay) => overlay.schemaSignatureRefs));
      const publicValidationBundles = validationBundles.filter((validationBundle) => publicValidationRefs.has(validationBundle.validationEvidenceBundleId));
      const publicSignatures = signatures.filter((signature) => publicSignatureRefs.has(signature.signatureId));

      if (publicValidationBundles.length === 0 || !publicValidationBundles.every(isPublicReleaseUsableValidationEvidence)) {
        failures.push(failure("CONTROL_PLANE_PUBLIC_RELEASE_REQUIRES_CLEARED_VALIDATION_EVIDENCE", "Public-ready evidence overlays require complete validation evidence with cleared license and data-rights status.", "$"));
      }

      if (publicSignatures.length === 0 || !publicSignatures.every(isPublicReleaseUsableSignature)) {
        failures.push(failure("CONTROL_PLANE_PUBLIC_RELEASE_REQUIRES_PUBLIC_SIGNATURES", "Public-ready evidence overlays require verified public-release scoped schema signatures.", "$"));
      }
    }
  }

  const dedupedFailures = dedupeFailures(failures);
  return { valid: dedupedFailures.length === 0, failures: dedupedFailures };
}
