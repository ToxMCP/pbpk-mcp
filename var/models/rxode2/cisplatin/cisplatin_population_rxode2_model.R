suppressPackageStartupMessages(library(rxode2))

`%||%` <- function(lhs, rhs) {
  if (is.null(lhs) || length(lhs) == 0) {
    return(rhs)
  }
  lhs
}

.scalar_text <- function(value) {
  if (is.null(value) || length(value) == 0) {
    return(NULL)
  }
  candidate <- as.character(unlist(value, use.names = FALSE)[[1]])
  if (is.na(candidate) || !nzchar(candidate)) {
    return(NULL)
  }
  candidate
}

.text_values <- function(value) {
  if (is.null(value) || length(value) == 0) {
    return(character())
  }
  candidates <- as.character(unlist(value, use.names = FALSE))
  candidates <- candidates[!is.na(candidates) & nzchar(candidates)]
  unique(candidates)
}

.request_section <- function(value, scalar_key = NULL) {
  if (is.null(value) || length(value) == 0) {
    return(list())
  }
  if (is.list(value)) {
    return(value)
  }
  if (is.null(scalar_key)) {
    return(list())
  }
  stats::setNames(list(value), scalar_key)
}

.normalize_context_use <- function(value) {
  candidate <- tolower(.scalar_text(value) %||% "")
  if (!nzchar(candidate)) {
    return(NULL)
  }
  if (candidate %in% c("research", "research-only", "exploratory", "method-development")) {
    return("research-only")
  }
  candidate
}

pbpk_model_metadata <- function() {
  list(
    name = "Cisplatin population kidney model",
    modelVersion = "2026-03-17-rxode2",
    createdBy = "Codex",
    backend = "rxode2"
  )
}

.parameter_provenance_for_category <- function(category) {
  switch(
    as.character(category %||% ""),
    Physiology = list(
      provenance_status = "partially-declared",
      sourceTable = "pbpk_parameter_catalog",
      sourceType = "adult-human-physiology-default",
      source = "Workspace adult physiology defaults for MCP demonstration",
      evidenceType = "literature-informed default",
      rationale = "Provides the adult baseline physiology used for deterministic and bounded population simulations.",
      notes = "Specific literature citations are not yet bundled in this example module."
    ),
    Binding = list(
      provenance_status = "partially-declared",
      sourceTable = "pbpk_parameter_catalog",
      sourceType = "compound-property-default",
      source = "Workspace cisplatin binding defaults",
      evidenceType = "literature-informed default",
      rationale = "Represents example cisplatin blood and plasma binding assumptions for research-use scenarios."
    ),
    Renal = list(
      provenance_status = "partially-declared",
      sourceTable = "pbpk_parameter_catalog",
      sourceType = "renal-physiology-default",
      source = "Workspace renal physiology defaults",
      evidenceType = "literature-informed default",
      rationale = "Captures the renal filtration and urine-flow settings exposed through the MCP contract."
    ),
    Transport = list(
      provenance_status = "partially-declared",
      sourceTable = "pbpk_parameter_catalog",
      sourceType = "transport-calibration-parameter",
      source = "Workspace cisplatin transporter calibration defaults",
      evidenceType = "mechanistic calibration default",
      rationale = "Represents OCT2 and MATE transport parameters exposed for exploratory mechanistic studies."
    ),
    Partition = list(
      provenance_status = "partially-declared",
      sourceTable = "pbpk_parameter_catalog",
      sourceType = "partition-coefficient-default",
      source = "Workspace tissue partition defaults",
      evidenceType = "model-assumption default",
      rationale = "Provides the tissue partition parameters exposed by the example MCP model."
    ),
    Dose = list(
      provenance_status = "declared",
      sourceTable = "pbpk_parameter_catalog",
      sourceType = "study-design-input",
      source = "User-editable dosing inputs",
      evidenceType = "scenario definition",
      rationale = "Defines the dosing scenario rather than an estimated physiological property."
    ),
    Simulation = list(
      provenance_status = "declared",
      sourceTable = "pbpk_parameter_catalog",
      sourceType = "runtime-configuration",
      source = "User-editable simulation controls",
      evidenceType = "execution setting",
      rationale = "Controls solver horizon and output sampling for the MCP execution path."
    ),
    list(
      provenance_status = "unreported",
      sourceTable = "pbpk_parameter_catalog"
    )
  )
}

pbpk_parameter_catalog <- function() {
  base_catalog <- list(
    list(path = "Physiology|BodyWeight", display_name = "Body weight", unit = "kg", category = "Physiology", is_editable = TRUE),
    list(path = "Binding|UnboundFractionPlasma", display_name = "Unbound fraction in plasma", unit = "unitless", category = "Binding", is_editable = TRUE),
    list(path = "Binding|BloodPlasmaRatio", display_name = "Blood to plasma ratio", unit = "unitless", category = "Binding", is_editable = TRUE),
    list(path = "Filtration|GFRPerKg", display_name = "Glomerular filtration rate per kg", unit = "L/h/kg", category = "Renal", is_editable = TRUE),
    list(path = "Renal|UrineFlowRate", display_name = "Urine flow rate", unit = "L/h", category = "Renal", is_editable = TRUE),
    list(path = "Transport|OCT2ScalingFactor", display_name = "OCT2 scaling factor", unit = "unitless", category = "Transport", is_editable = TRUE),
    list(path = "Transport|OCT2ActivityFraction", display_name = "OCT2 activity fraction", unit = "unitless", category = "Transport", is_editable = TRUE),
    list(path = "Transport|OCT2Vmax", display_name = "OCT2 Vmax", unit = "pmol/mg/min", category = "Transport", is_editable = TRUE),
    list(path = "Transport|OCT2Km", display_name = "OCT2 Km", unit = "umol/L", category = "Transport", is_editable = TRUE),
    list(path = "Transport|MATEScalingFactor", display_name = "MATE scaling factor", unit = "unitless", category = "Transport", is_editable = TRUE),
    list(path = "Partition|Fat", display_name = "Fat partition coefficient", unit = "unitless", category = "Partition", is_editable = TRUE),
    list(path = "Partition|Slow", display_name = "Slow tissue partition coefficient", unit = "unitless", category = "Partition", is_editable = TRUE),
    list(path = "Partition|Rich", display_name = "Rich tissue partition coefficient", unit = "unitless", category = "Partition", is_editable = TRUE),
    list(path = "Partition|Kidney", display_name = "Kidney partition coefficient", unit = "unitless", category = "Partition", is_editable = TRUE),
    list(path = "Dose|BodySurfaceArea", display_name = "Body surface area", unit = "m2", category = "Dose", is_editable = TRUE),
    list(path = "Dose|DosePerSquareMeter", display_name = "Dose per square meter", unit = "mg/m2", category = "Dose", is_editable = TRUE),
    list(path = "Dose|InfusionDuration", display_name = "Infusion duration", unit = "h", category = "Dose", is_editable = TRUE),
    list(path = "Simulation|EndTime", display_name = "Simulation end time", unit = "h", category = "Simulation", is_editable = TRUE),
    list(path = "Simulation|SamplingStep", display_name = "Sampling step", unit = "h", category = "Simulation", is_editable = TRUE)
  )

  lapply(base_catalog, function(entry) {
    utils::modifyList(entry, .parameter_provenance_for_category(entry$category))
  })
}

pbpk_default_parameters <- function() {
  list(
    "Physiology|BodyWeight" = 70,
    "Binding|UnboundFractionPlasma" = 0.8,
    "Binding|BloodPlasmaRatio" = 2.15,
    "Filtration|GFRPerKg" = 0.1071,
    "Renal|UrineFlowRate" = 0.083,
    "Transport|OCT2ScalingFactor" = 35,
    "Transport|OCT2ActivityFraction" = 1,
    "Transport|OCT2Vmax" = 13.7,
    "Transport|OCT2Km" = 11.4,
    "Transport|MATEScalingFactor" = 0.06,
    "Partition|Fat" = 0.0605,
    "Partition|Slow" = 0.2512,
    "Partition|Rich" = 0.2678,
    "Partition|Kidney" = 0.2698,
    "Dose|BodySurfaceArea" = 1.78,
    "Dose|DosePerSquareMeter" = 80,
    "Dose|InfusionDuration" = 1,
    "Simulation|EndTime" = 48,
    "Simulation|SamplingStep" = 0.1
  )
}

pbpk_parameter_table <- function(parameters = NULL, parameter_catalog = NULL, ...) {
  defaults <- pbpk_default_parameters()
  resolved_parameters <- .coerce_parameters(parameters %||% defaults)
  catalog <- parameter_catalog %||% pbpk_parameter_catalog()
  bounds <- .validation_parameter_bounds()

  rows <- lapply(catalog, function(entry) {
    path <- .scalar_text(entry$path)
    if (is.null(path) || !nzchar(path)) {
      return(NULL)
    }
    bound <- bounds[[path]]
    utils::modifyList(
      entry,
      list(
        value = as.numeric(resolved_parameters[[path]] %||% defaults[[path]] %||% NA_real_),
        default_value = as.numeric(defaults[[path]] %||% NA_real_),
        runtime_bound_lower = if (is.null(bound)) NULL else bound$lower,
        runtime_bound_upper = if (is.null(bound)) NULL else bound$upper,
        runtime_bound_unit = if (is.null(bound)) NULL else bound$unit
      )
    )
  })

  Filter(Negate(is.null), rows)
}

pbpk_performance_evidence <- function(...) {
  list(
    list(
      id = "deterministic-runtime-smoke",
      kind = "runtime-smoke-test",
      status = "passed",
      targetOutput = "Plasma|Cisplatin|Concentration",
      dataset = "embedded-runtime-smoke",
      acceptanceCriterion = "Deterministic simulation executes and returns finite concentration-time output.",
      evidenceLevel = "runtime-only",
      notes = "Confirms executable integrity only; does not constitute external predictive validation."
    ),
    list(
      id = "population-runtime-smoke",
      kind = "runtime-smoke-test",
      status = "passed",
      targetOutput = "Plasma|Cisplatin|Concentration",
      dataset = "embedded-runtime-smoke",
      acceptanceCriterion = "Population simulation executes and returns bounded aggregate outputs.",
      evidenceLevel = "runtime-only",
      notes = "Supports workflow robustness, not regulatory-grade predictivity."
    )
  )
}

.cisplatin_lookup <- local({
  mapping <- list(
    "Physiology|BodyWeight" = "BW",
    "Binding|UnboundFractionPlasma" = "Fup",
    "Binding|BloodPlasmaRatio" = "BPR",
    "Filtration|GFRPerKg" = "GFR_per_kg",
    "Renal|UrineFlowRate" = "kURINE",
    "Transport|OCT2ScalingFactor" = "SFOCT",
    "Transport|OCT2ActivityFraction" = "PEROCT",
    "Transport|OCT2Vmax" = "VmaxOCTc",
    "Transport|OCT2Km" = "KmOCT",
    "Transport|MATEScalingFactor" = "SFMATE",
    "Partition|Fat" = "PF",
    "Partition|Slow" = "PS",
    "Partition|Rich" = "PR",
    "Partition|Kidney" = "PRK",
    "Dose|BodySurfaceArea" = "BSA",
    "Dose|DosePerSquareMeter" = "DoseMgPerM2",
    "Dose|InfusionDuration" = "InfusionDuration",
    "Simulation|EndTime" = "SimulationEnd",
    "Simulation|SamplingStep" = "SamplingStep"
  )
  function() mapping
})

.coerce_parameters <- function(parameters) {
  defaults <- pbpk_default_parameters()
  if (is.null(parameters) || length(parameters) == 0) {
    parameters <- defaults
  }

  merged <- defaults
  for (name in names(parameters)) {
    merged[[name]] <- as.numeric(parameters[[name]])
  }
  merged
}

.rxode_parameters <- function(parameters) {
  merged <- .coerce_parameters(parameters)
  lookup <- .cisplatin_lookup()
  values <- lapply(names(lookup), function(path) {
    as.numeric(merged[[path]])
  })
  names(values) <- unname(unlist(lookup, use.names = FALSE))
  unlist(values, use.names = TRUE)
}

.initial_states <- function() {
  c(
    AB = 0,
    AF = 0,
    AS = 0,
    AR = 0,
    AKB = 0,
    AFIL = 0,
    ARK = 0,
    APT = 0,
    AUR = 0,
    AOCT = 0,
    AMATE = 0,
    GF = 0,
    VUR = 1e-6
  )
}

.dose_umol <- function(parameters, molecular_weight = 300.5) {
  merged <- .coerce_parameters(parameters)
  total_mg <- merged[["Dose|DosePerSquareMeter"]] * merged[["Dose|BodySurfaceArea"]]
  ((total_mg * 1e-3) / molecular_weight) * 1e6
}

.simulation_grid <- function(parameters) {
  merged <- .coerce_parameters(parameters)
  seq(
    0,
    as.numeric(merged[["Simulation|EndTime"]]),
    by = as.numeric(merged[["Simulation|SamplingStep"]])
  )
}

.derived_geometry <- function(parameter_vector) {
  bw <- as.numeric(parameter_vector[["BW"]])
  list(
    VB = 0.0771 * bw,
    VKB = 0.18 * 0.0044 * bw,
    VRK = 0.21 * 0.0044 * bw,
    VPT = 0.28 * 0.0044 * bw,
    VFIL = 0.33 * 0.0044 * bw
  )
}

.cisplatin_model <- local({
  model <- NULL
  function() {
    if (!is.null(model)) {
      return(model)
    }
    model <<- rxode2({
      QFC = 0.05
      QSC = 0.27
      QRC = 0.49
      QKBC = 0.19

      VBC = 0.0771
      VFC = 0.2142
      VSC = 0.58
      VRC = 0.1243
      VKBC = 0.18 * 0.0044
      VRKC = 0.21 * 0.0044
      VPTC = 0.28 * 0.0044
      VFILC = 0.33 * 0.0044
      VTKC = 0.0044

      QC = 15 * (BW^0.74)
      QF = QFC * QC
      QS = QSC * QC
      QR = QRC * QC
      QKB = QKBC * QC

      VB = VBC * BW
      VF = VFC * BW
      VS = VSC * BW
      VR = VRC * BW
      VKB = VKBC * BW
      VRK = VRKC * BW
      VPT = VPTC * BW
      VFIL = VFILC * BW
      VTK = VTKC * BW

      CB = AB / VB
      CP = (CB / BPR) * Fup
      CF = AF / VF
      CS = AS / VS
      CR = AR / VR
      CKB = AKB / VKB
      CRK = ARK / VRK
      CPT = APT / VPT
      CFIL = AFIL / VFIL

      CVF = CF / PF
      CVS = CS / PS
      CVR = CR / PR
      CVRK = CRK / PRK

      GFR = GFR_per_kg * BW
      MK = VTKC * BW * 1000
      PTC = 6e7
      PTPROTEIN = 2.0e-9
      MPT = MK * PTC * PTPROTEIN

      VmaxOCT = (VmaxOCTc / 1e6) * 60 * MPT * 1000 * SFOCT * PEROCT
      CLMATE = (VmaxOCTc / KmOCT) * 60 * MPT * 5 * SFMATE / 1000

      rate_GF = CKB * GFR * (Fup / BPR)
      rate_OCT = (VmaxOCT * (CKB * (Fup / BPR))) / (KmOCT + (CKB * (Fup / BPR)))
      rate_MATE = CLMATE * CPT

      d/dt(GF) = rate_GF
      d/dt(AF) = QF * (CB - CVF)
      d/dt(AS) = QS * (CB - CVS)
      d/dt(AR) = QR * (CB - CVR)
      d/dt(AB) = (QF * CVF + QS * CVS + QR * CVR + QKB * CVRK) - CB * (QF + QS + QR + QKB)
      d/dt(AOCT) = rate_OCT
      d/dt(AMATE) = rate_MATE
      d/dt(AKB) = QKB * CB - (QKB * CKB) - rate_GF - rate_OCT
      d/dt(ARK) = QKB * (CKB - CVRK)
      d/dt(APT) = rate_OCT - rate_MATE
      d/dt(AUR) = CFIL * kURINE
      d/dt(VUR) = kURINE
      d/dt(AFIL) = rate_GF + rate_MATE - (CFIL * kURINE)
    })
    model
  }
})

.run_single <- function(parameters) {
  parameter_vector <- .rxode_parameters(parameters)
  events <- rxode2::eventTable(amount.units = "umol", time.units = "h")
  events$add.sampling(.simulation_grid(parameters))
  events$add.dosing(
    dose = .dose_umol(parameters),
    dosing.to = "AB",
    dur = as.numeric(.coerce_parameters(parameters)[["Dose|InfusionDuration"]])
  )

  solved <- rxode2::rxSolve(
    .cisplatin_model(),
    params = parameter_vector,
    events = events,
    inits = .initial_states()
  )
  as.data.frame(solved)
}

.append_derived_outputs <- function(df, parameter_vector) {
  geom <- .derived_geometry(parameter_vector)
  df$`Plasma|Cisplatin|Concentration` <- (df$AB / geom$VB / parameter_vector[["BPR"]]) * parameter_vector[["Fup"]]
  df$`Kidney|Blood|Cisplatin|Concentration` <- df$AKB / geom$VKB
  df$`Kidney|ProximalTubule|Cisplatin|Concentration` <- df$APT / geom$VPT
  df$`Kidney|Filtrate|Cisplatin|Concentration` <- df$AFIL / geom$VFIL
  df$`Urine|Cisplatin|Amount` <- df$AUR
  df
}

.default_output_paths <- function() {
  c(
    "Plasma|Cisplatin|Concentration",
    "Kidney|Blood|Cisplatin|Concentration",
    "Kidney|ProximalTubule|Cisplatin|Concentration",
    "Kidney|Filtrate|Cisplatin|Concentration",
    "Urine|Cisplatin|Amount"
  )
}

.supported_sampling_modes <- function() {
  c("bounded-normal")
}

.population_variability_paths <- function() {
  c(
    "Physiology|BodyWeight",
    "Binding|UnboundFractionPlasma",
    "Filtration|GFRPerKg",
    "Transport|OCT2ActivityFraction",
    "Transport|MATEScalingFactor"
  )
}

.model_assumptions <- function() {
  c(
    "Adult human physiology is represented through fixed structural geometry with bounded parameter variability.",
    "Intravenous infusion into the blood compartment is the supported dosing route.",
    "Renal handling is represented through glomerular filtration, aggregate OCT2 uptake, and aggregate apical efflux terms.",
    "Model outputs are currently focused on plasma and kidney compartments plus cumulative urine amount."
  )
}

.unsupported_uses <- function() {
  c(
    "Cross-species extrapolation",
    "Pediatric physiology",
    "Pregnancy physiology",
    "Non-intravenous dosing regimens",
    "Regulatory decision support without additional qualification evidence"
  )
}

.missing_qualification_evidence <- function() {
  c(
    "No formal external qualification package is attached to the MCP runtime.",
    "No encoded local or global sensitivity analysis is currently shipped with the model contract.",
    "No automated mass-balance or unit-regression suite is enforced at load time.",
    "No external peer-review or prior regulatory use record is declared in metadata."
  )
}

.validation_parameter_bounds <- function() {
  list(
    "Physiology|BodyWeight" = list(lower = 35, upper = 140, unit = "kg"),
    "Binding|UnboundFractionPlasma" = list(lower = 0.05, upper = 1, unit = "unitless"),
    "Binding|BloodPlasmaRatio" = list(lower = 0.5, upper = 5, unit = "unitless"),
    "Filtration|GFRPerKg" = list(lower = 0.02, upper = 0.3, unit = "L/h/kg"),
    "Renal|UrineFlowRate" = list(lower = 0.001, upper = 1, unit = "L/h"),
    "Transport|OCT2ScalingFactor" = list(lower = 0.01, upper = 200, unit = "unitless"),
    "Transport|OCT2ActivityFraction" = list(lower = 0.05, upper = 2, unit = "unitless"),
    "Transport|OCT2Vmax" = list(lower = 0.1, upper = 1000, unit = "pmol/mg/min"),
    "Transport|OCT2Km" = list(lower = 0.1, upper = 1000, unit = "umol/L"),
    "Transport|MATEScalingFactor" = list(lower = 0.001, upper = 2, unit = "unitless"),
    "Partition|Fat" = list(lower = 0.01, upper = 10, unit = "unitless"),
    "Partition|Slow" = list(lower = 0.01, upper = 10, unit = "unitless"),
    "Partition|Rich" = list(lower = 0.01, upper = 10, unit = "unitless"),
    "Partition|Kidney" = list(lower = 0.01, upper = 10, unit = "unitless"),
    "Dose|BodySurfaceArea" = list(lower = 0.5, upper = 3.5, unit = "m2"),
    "Dose|DosePerSquareMeter" = list(lower = 1, upper = 200, unit = "mg/m2"),
    "Dose|InfusionDuration" = list(lower = 0.05, upper = 24, unit = "h"),
    "Simulation|EndTime" = list(lower = 0.5, upper = 720, unit = "h"),
    "Simulation|SamplingStep" = list(lower = 0.01, upper = 24, unit = "h")
  )
}

.make_validation_issue <- function(code, message, field = NULL, severity = "error") {
  list(
    code = code,
    message = message,
    field = field,
    severity = severity
  )
}

pbpk_supported_outputs <- function() {
  .default_output_paths()
}

pbpk_model_profile <- function() {
  bounds <- .validation_parameter_bounds()
  bound_entries <- lapply(names(bounds), function(path) {
    c(list(path = path), bounds[[path]])
  })

  list(
    contextOfUse = list(
      scientificPurpose = "Mechanistic adult human cisplatin kidney PBPK exploration for deterministic and bounded population simulations.",
      decisionContext = "Research and method-development use for adult human cisplatin renal exposure questions.",
      regulatoryUse = "research-only",
      acceptableUncertainty = "Not formally specified in the current MCP package.",
      confidenceLevelRequired = "Fit-for-purpose research confidence; not yet qualified for regulatory reliance.",
      repurposingAllowed = FALSE,
      supportedQuestions = c(
        "Relative impact of renal filtration and transport changes on plasma and kidney exposure.",
        "Exploratory bounded population variability for adult-like cisplatin cohorts."
      ),
      unsupportedQuestions = c(
        "Regulatory decision support without additional qualification evidence.",
        "Route-to-route extrapolation beyond intravenous infusion.",
        "Cross-species, pediatric, or pregnancy extrapolation."
      )
    ),
    applicabilityDomain = list(
      type = "declared-with-runtime-guardrails",
      qualificationLevel = "research-use",
      status = "partially-characterized",
      compounds = c("cisplatin"),
      species = c("human"),
      lifeStage = c("adult"),
      routes = c("iv-infusion"),
      outputs = pbpk_supported_outputs(),
      tissues = c("plasma", "kidney blood", "proximal tubule", "filtrate", "urine"),
      parameterBounds = bound_entries,
      assumptions = .model_assumptions(),
      exclusions = .unsupported_uses(),
      summary = paste(
        "Adult human cisplatin kidney PBPK model for intravenous infusion scenarios,",
        "with MCP-enforced runtime guardrails and research-use qualification only."
      )
    ),
    modelPerformance = list(
      status = "limited-internal-evaluation",
      targetOutputs = pbpk_supported_outputs(),
      goodnessOfFit = list(
        status = "not-bundled",
        summary = "No bundled observed-versus-predicted dataset or formal goodness-of-fit metrics are attached to this MCP example."
      ),
      predictiveChecks = list(
        status = "face-validity-and-smoke-tests-only",
        summary = "Current evidence is limited to runtime smoke tests and qualitative plausibility checks within the declared adult IV cisplatin scope."
      ),
      evaluationData = list(
        status = "not-bundled",
        summary = "No external calibration or verification datasets are packaged in the current MCP example."
      ),
      missingEvidence = c(
        "Observed-versus-predicted comparisons for key plasma and kidney outputs",
        "Formal goodness-of-fit metrics and acceptance criteria",
        "External or prospective predictive evaluation datasets"
      ),
      summary = paste(
        "The model is executable and bounded for research use,",
        "but it does not yet carry a formal predictive-performance dossier suitable for regulatory reliance."
      )
    ),
    parameterProvenance = list(
      status = "partially-declared",
      sourceTable = "pbpk_parameter_catalog / pbpk_parameter_table",
      coverage = "Named runtime parameters exposed through the MCP contract",
      declaredParameterCount = length(pbpk_default_parameters()),
      provenanceMethod = "Category-level provenance annotations with current values, defaults, and runtime bounds",
      missingEvidence = c(
        "Parameter-by-parameter literature citations and study conditions",
        "Formal parameter-identifiability analysis"
      ),
      summary = paste(
        "The MCP contract exposes a structured parameter table with current values, defaults, runtime bounds,",
        "and category-level provenance annotations for each exposed parameter."
      )
    ),
    uncertainty = list(
      status = "partially-characterized",
      variabilityApproach = list(
        supported = TRUE,
        method = "bounded-normal sampling",
        variedParameters = .population_variability_paths(),
        notes = c(
          "Population sampling clips draws into declared runtime bounds.",
          "Sampling bounds are implementation guardrails, not posterior uncertainty distributions."
        )
      ),
      sensitivityAnalysis = list(
        status = "not-encoded",
        summary = "No formal local or global sensitivity analysis metadata is bundled with the MCP contract."
      ),
      residualUncertainty = c(
        "Transport and partition terms are represented as aggregate parameters.",
        "Guardrail bounds should not be interpreted as a validated extrapolation envelope."
      ),
      missingEvidence = .missing_qualification_evidence()
    ),
    implementationVerification = list(
      status = "basic-internal-checks",
      codeAvailability = "workspace-source",
      solver = "rxode2::rxSolve",
      verifiedChecks = c(
        "R syntax validation",
        "Deterministic simulation smoke test",
        "Population simulation smoke test",
        "Parameter path normalization",
        "Runtime guardrail enforcement"
      ),
      missingChecks = c(
        "Formal mass-balance regression tests",
        "Flow and volume consistency assertions",
        "Solver qualification matrix",
        "Automated unit regression suite"
      ),
      notes = c(
        "Implementation verification currently relies on smoke tests and code inspection.",
        "A full qualification package is not yet attached to this model runtime."
      )
    ),
    peerReview = list(
      status = "not-reported",
      priorRegulatoryUse = FALSE,
      revisionStatus = "active-development",
      notes = c(
        "No external peer review or prior regulatory use record is declared in this MCP model profile."
      )
    ),
    profileSource = list(
      type = "module-self-declared",
      path = "cisplatin_population_rxode2_model.R",
      sourceToolHint = "rxode2",
      summary = "Scientific profile is declared within the MCP-ready rxode2 model module in the workspace."
    )
  )
}

pbpk_capabilities <- function() {
  profile <- pbpk_model_profile()
  list(
    backend = "rxode2",
    deterministicSimulation = TRUE,
    populationSimulation = TRUE,
    parameterEditing = TRUE,
    validationHook = TRUE,
    scientificProfile = TRUE,
    supportedOutputs = pbpk_supported_outputs(),
    supportedSampling = .supported_sampling_modes(),
    tags = c("cisplatin", "renal", "population", "adult"),
    applicabilityDomain = profile$applicabilityDomain
  )
}

pbpk_validate_request <- function(request = list(), parameters = NULL, stage = NULL, ...) {
  profile <- pbpk_model_profile()
  context_of_use <- profile$contextOfUse %||% list()
  domain_profile <- profile$applicabilityDomain %||% list()
  resolved_parameters <- .coerce_parameters(parameters %||% pbpk_default_parameters())
  bounds <- .validation_parameter_bounds()
  errors <- list()
  warnings <- list()

  add_error <- function(code, message, field = NULL) {
    errors[[length(errors) + 1]] <<- .make_validation_issue(code, message, field, "error")
  }

  add_warning <- function(code, message, field = NULL) {
    warnings[[length(warnings) + 1]] <<- .make_validation_issue(code, message, field, "warning")
  }

  for (path in names(bounds)) {
    value <- as.numeric(resolved_parameters[[path]])
    bound <- bounds[[path]]
    if (!is.finite(value)) {
      add_error("invalid_parameter_value", sprintf("Parameter '%s' must be numeric", path), path)
      next
    }
    if (value < bound$lower || value > bound$upper) {
      add_error(
        "parameter_out_of_bounds",
        sprintf(
          "Value %.4g is outside the supported range %.4g..%.4g %s",
          value,
          bound$lower,
          bound$upper,
          bound$unit
        ),
        path
      )
    }
  }

  if (resolved_parameters[["Simulation|SamplingStep"]] >= resolved_parameters[["Simulation|EndTime"]]) {
    add_error(
      "invalid_sampling_window",
      "Sampling step must be smaller than the simulation end time",
      "Simulation|SamplingStep"
    )
  }

  requested_outputs <- .requested_output_paths(request$outputs %||% list())
  unsupported_outputs <- setdiff(requested_outputs, pbpk_supported_outputs())
  for (path in unsupported_outputs) {
    add_error(
      "unsupported_output",
      sprintf("Output '%s' is not supported by this model", path),
      path
    )
  }

  cohort <- request$cohort %||% list()
  if (!is.null(cohort$size)) {
    size <- suppressWarnings(as.integer(cohort$size))
    if (is.na(size) || size < 1 || size > 200) {
      add_error(
        "cohort_size_out_of_bounds",
        sprintf("Population size must be between 1 and 200; received '%s'", as.character(cohort$size)),
        "cohort.size"
      )
    }
  }

  sampling <- as.character(cohort$sampling %||% NA_character_)
  if (!is.na(sampling) && nzchar(sampling) && !sampling %in% .supported_sampling_modes()) {
    add_error(
      "unsupported_sampling",
      sprintf(
        "Sampling mode '%s' is not supported; expected one of: %s",
        sampling,
        paste(.supported_sampling_modes(), collapse = ", ")
      ),
      "cohort.sampling"
    )
  }

  for (covariate in cohort$covariates %||% list()) {
    path <- as.character(covariate$parameterPath %||% covariate$path %||% NA_character_)
    if (is.na(path) || !nzchar(path)) {
      add_error("covariate_path_missing", "Each covariate must declare a parameter path", "cohort.covariates")
      next
    }
    if (!path %in% names(resolved_parameters)) {
      add_error(
        "unknown_covariate_path",
        sprintf("Covariate path '%s' is not a known model parameter", path),
        path
      )
      next
    }

    bound <- bounds[[path]] %||% NULL
    if (!is.null(covariate$value)) {
      value <- suppressWarnings(as.numeric(covariate$value))
      if (is.na(value)) {
        add_error("invalid_covariate_value", sprintf("Covariate '%s' must be numeric", path), path)
      } else if (!is.null(bound) && (value < bound$lower || value > bound$upper)) {
        add_error(
          "covariate_value_out_of_bounds",
          sprintf(
            "Covariate value %.4g is outside the supported range %.4g..%.4g %s",
            value,
            bound$lower,
            bound$upper,
            bound$unit
          ),
          path
        )
      }
    }

    if (!is.null(covariate$mean)) {
      mean_value <- suppressWarnings(as.numeric(covariate$mean))
      if (is.na(mean_value)) {
        add_error("invalid_covariate_mean", sprintf("Covariate mean for '%s' must be numeric", path), path)
      }

      lower <- suppressWarnings(as.numeric(covariate$lower %||% NA_real_))
      upper <- suppressWarnings(as.numeric(covariate$upper %||% NA_real_))
      if (!is.na(lower) && !is.na(upper) && lower > upper) {
        add_error(
          "covariate_bounds_invalid",
          sprintf("Covariate bounds for '%s' must satisfy lower <= upper", path),
          path
        )
      }

      if (!is.null(bound)) {
        if (!is.na(mean_value) && (mean_value < bound$lower || mean_value > bound$upper)) {
          add_error(
            "covariate_mean_out_of_bounds",
            sprintf(
              "Covariate mean %.4g is outside the supported range %.4g..%.4g %s",
              mean_value,
              bound$lower,
              bound$upper,
              bound$unit
            ),
            path
          )
        }
        if (!is.na(lower) && lower < bound$lower) {
          add_error(
            "covariate_lower_out_of_bounds",
            sprintf("Covariate lower bound %.4g is below the supported minimum %.4g %s", lower, bound$lower, bound$unit),
            path
          )
        }
        if (!is.na(upper) && upper > bound$upper) {
          add_error(
            "covariate_upper_out_of_bounds",
            sprintf("Covariate upper bound %.4g is above the supported maximum %.4g %s", upper, bound$upper, bound$unit),
            path
          )
        }
      }
    }
  }

  requested_domain <- .request_section(
    request$applicabilityDomain %||% request$applicability %||% request$domain
  )
  requested_species <- .text_values(requested_domain$species %||% request$species)
  supported_species <- tolower(.text_values(domain_profile$species))
  for (species in requested_species) {
    if (length(supported_species) > 0 && !tolower(species) %in% supported_species) {
      add_error(
        "unsupported_species",
        sprintf("Species '%s' is outside the declared applicability domain", species),
        "species"
      )
    }
  }

  requested_life_stage <- .text_values(requested_domain$lifeStage %||% request$lifeStage %||% request$life_stage)
  supported_life_stage <- tolower(.text_values(domain_profile$lifeStage))
  for (life_stage in requested_life_stage) {
    if (length(supported_life_stage) > 0 && !tolower(life_stage) %in% supported_life_stage) {
      add_error(
        "unsupported_life_stage",
        sprintf("Life stage '%s' is outside the declared applicability domain", life_stage),
        "lifeStage"
      )
    }
  }

  requested_routes <- .text_values(requested_domain$routes %||% requested_domain$route %||% request$routes %||% request$route)
  supported_routes <- tolower(.text_values(domain_profile$routes))
  for (route in requested_routes) {
    if (length(supported_routes) > 0 && !tolower(route) %in% supported_routes) {
      add_error(
        "unsupported_route",
        sprintf("Route '%s' is outside the declared applicability domain", route),
        "route"
      )
    }
  }

  requested_compounds <- .text_values(requested_domain$compounds %||% requested_domain$compound %||% request$compound)
  supported_compounds <- tolower(.text_values(domain_profile$compounds))
  for (compound in requested_compounds) {
    if (length(supported_compounds) > 0 && !tolower(compound) %in% supported_compounds) {
      add_error(
        "unsupported_compound",
        sprintf("Compound '%s' is outside the declared applicability domain", compound),
        "compound"
      )
    }
  }

  requested_context <- .request_section(
    request$contextOfUse %||% request$context_of_use,
    scalar_key = "regulatoryUse"
  )
  requested_use <- .normalize_context_use(
    requested_context$regulatoryUse %||% requested_context$intendedUse %||%
      request$regulatoryUse %||% request$intendedUse
  )
  declared_use <- .normalize_context_use(context_of_use$regulatoryUse)
  if (!is.null(requested_use) && !is.null(declared_use) && requested_use != declared_use) {
    add_error(
      "context_of_use_mismatch",
      sprintf(
        "Requested context of use '%s' is outside the declared model context '%s'",
        requested_use,
        declared_use
      ),
      "contextOfUse.regulatoryUse"
    )
  }

  if (identical(stage, "load_simulation")) {
    add_warning(
      "runtime_guardrails_only",
      "Applicability checks currently reflect runtime guardrails for this implementation, not external scientific qualification."
    )
    add_warning(
      "research_use_only",
      "Declared context of use is research-only; regulatory or cross-domain use requires additional qualification evidence."
    )
  }

  list(
    ok = length(errors) == 0,
    summary = if (length(errors) == 0) {
      "Request is within the declared runtime guardrails and research-use context"
    } else {
      "Request is outside the declared runtime guardrails or context of use"
    },
    errors = errors,
    warnings = warnings,
    domain = domain_profile,
    assessment = list(
      decision = if (length(errors) == 0) "within-declared-guardrails" else "outside-declared-guardrails",
      guardrailType = domain_profile$type %||% "unspecified",
      qualificationLevel = domain_profile$qualificationLevel %||% "unreported",
      declaredContextOfUse = declared_use %||% "unreported",
      missingEvidence = .missing_qualification_evidence()
    )
  )
}

.requested_output_paths <- function(outputs) {
  candidates <- character()
  if (!is.null(outputs) && length(outputs) > 0) {
    time_series <- outputs$time_series %||% outputs$timeSeries %||% list()
    for (item in time_series) {
      candidates <- c(
        candidates,
        as.character(item$path %||% item$parameter %||% item$output %||% NA_character_)
      )
    }
  }
  candidates <- candidates[nzchar(candidates)]
  unique(candidates %||% .default_output_paths())
}

.series_from_dataframe <- function(df, output_paths) {
  available_units <- list(
    "Plasma|Cisplatin|Concentration" = "umol/L",
    "Kidney|Blood|Cisplatin|Concentration" = "umol/L",
    "Kidney|ProximalTubule|Cisplatin|Concentration" = "umol/L",
    "Kidney|Filtrate|Cisplatin|Concentration" = "umol/L",
    "Urine|Cisplatin|Amount" = "umol"
  )
  raw_series <- lapply(output_paths, function(path) {
    if (!path %in% names(df)) {
      return(NULL)
    }
    list(
      parameter = path,
      unit = available_units[[path]] %||% "unitless",
      values = lapply(seq_len(nrow(df)), function(index) {
        list(
          time = as.numeric(df$time[[index]]),
          value = as.numeric(df[[path]][[index]])
        )
      })
    )
  })
  Filter(Negate(is.null), raw_series)
}

.trapezoid_auc <- function(times, values) {
  total <- 0
  if (length(times) <= 1) {
    return(total)
  }
  for (index in 2:length(times)) {
    delta <- times[[index]] - times[[index - 1]]
    if (delta < 0) {
      next
    }
    total <- total + (delta * (values[[index]] + values[[index - 1]]) / 2)
  }
  total
}

.safe_sd <- function(values) {
  if (length(values) <= 1) {
    return(0)
  }
  as.numeric(stats::sd(values))
}

.bounded_normal <- function(mean_value, sd_value, lower, upper) {
  value <- stats::rnorm(1, mean = mean_value, sd = sd_value)
  min(max(value, lower), upper)
}

.sample_subject_parameters <- function(parameters, cohort) {
  parameters <- .coerce_parameters(parameters)
  size <- as.integer(cohort$size %||% 1)
  if (size < 1) {
    stop("Population size must be at least 1", call. = FALSE)
  }
  if (size > 200) {
    stop("Population size above 200 is not supported by the rxode2 bridge", call. = FALSE)
  }

  seed <- cohort$seed %||% NULL
  if (!is.null(seed)) {
    set.seed(as.integer(seed))
  }

  subjects <- vector("list", length = size)
  bounds <- .validation_parameter_bounds()
  for (index in seq_len(size)) {
    subject <- parameters
    subject[["Physiology|BodyWeight"]] <- .bounded_normal(
      parameters[["Physiology|BodyWeight"]],
      parameters[["Physiology|BodyWeight"]] * 0.15,
      bounds[["Physiology|BodyWeight"]]$lower,
      bounds[["Physiology|BodyWeight"]]$upper
    )
    subject[["Binding|UnboundFractionPlasma"]] <- .bounded_normal(
      parameters[["Binding|UnboundFractionPlasma"]],
      0.08,
      bounds[["Binding|UnboundFractionPlasma"]]$lower,
      bounds[["Binding|UnboundFractionPlasma"]]$upper
    )
    subject[["Filtration|GFRPerKg"]] <- .bounded_normal(
      parameters[["Filtration|GFRPerKg"]],
      parameters[["Filtration|GFRPerKg"]] * 0.1,
      bounds[["Filtration|GFRPerKg"]]$lower,
      bounds[["Filtration|GFRPerKg"]]$upper
    )
    subject[["Transport|OCT2ActivityFraction"]] <- .bounded_normal(
      parameters[["Transport|OCT2ActivityFraction"]],
      0.15,
      bounds[["Transport|OCT2ActivityFraction"]]$lower,
      bounds[["Transport|OCT2ActivityFraction"]]$upper
    )
    subject[["Transport|MATEScalingFactor"]] <- .bounded_normal(
      parameters[["Transport|MATEScalingFactor"]],
      max(parameters[["Transport|MATEScalingFactor"]] * 0.2, 0.01),
      bounds[["Transport|MATEScalingFactor"]]$lower,
      bounds[["Transport|MATEScalingFactor"]]$upper
    )

    covariates <- cohort$covariates %||% list()
    for (covariate in covariates) {
      path <- as.character(covariate$parameterPath %||% covariate$path %||% NA_character_)
      if (!nzchar(path) || !path %in% names(subject)) {
        next
      }
      if (!is.null(covariate$value)) {
        subject[[path]] <- as.numeric(covariate$value)
      } else if (!is.null(covariate$mean)) {
        mean_value <- as.numeric(covariate$mean)
        sd_value <- as.numeric(covariate$sd %||% max(abs(mean_value) * as.numeric(covariate$cv %||% 0.1), 1e-6))
        lower <- as.numeric(covariate$lower %||% 0)
        upper <- as.numeric(covariate$upper %||% max(mean_value + (4 * sd_value), lower))
        subject[[path]] <- .bounded_normal(mean_value, sd_value, lower, upper)
      }
    }

    subjects[[index]] <- subject
  }

  subjects
}

pbpk_run_simulation <- function(parameters, simulation_id = NULL, run_id = NULL, request = list()) {
  output_paths <- .requested_output_paths(request$outputs %||% list())
  resolved_parameters <- .coerce_parameters(parameters)
  solved <- .run_single(resolved_parameters)
  solved <- .append_derived_outputs(solved, .rxode_parameters(resolved_parameters))

  list(
    metadata = list(
      engine = "rxode2",
      sourceModel = "cisplatin_population_rxode2_model.R",
      requestedOutputs = output_paths
    ),
    series = .series_from_dataframe(solved, output_paths)
  )
}

pbpk_run_population <- function(parameters, cohort = list(), outputs = list(), simulation_id = NULL, request = list()) {
  output_paths <- .requested_output_paths(outputs)
  subjects <- .sample_subject_parameters(parameters, cohort)
  metrics <- vector("list", length(subjects))
  subject_series <- vector("list", length(subjects))

  for (index in seq_along(subjects)) {
    solved <- .run_single(subjects[[index]])
    solved <- .append_derived_outputs(solved, .rxode_parameters(subjects[[index]]))

    plasma <- solved$`Plasma|Cisplatin|Concentration`
    times <- solved$time
    cmax <- max(plasma)
    tmax <- times[[which.max(plasma)]]
    auc <- .trapezoid_auc(times, plasma)
    metrics[[index]] <- list(cmax = cmax, tmax = tmax, auc = auc)

    outputs_payload <- lapply(output_paths, function(path) {
      solved[[path]]
    })
    names(outputs_payload) <- output_paths

    subject_series[[index]] <- list(
      subjectId = index,
      time = as.numeric(times),
      outputs = outputs_payload
    )
  }

  cmax_values <- vapply(metrics, function(item) item$cmax, numeric(1))
  tmax_values <- vapply(metrics, function(item) item$tmax, numeric(1))
  auc_values <- vapply(metrics, function(item) item$auc, numeric(1))

  chunk_size <- 25L
  chunk_count <- ceiling(length(subject_series) / chunk_size)
  chunks <- vector("list", chunk_count)

  for (chunk_index in seq_len(chunk_count)) {
    start_index <- ((chunk_index - 1L) * chunk_size) + 1L
    end_index <- min(length(subject_series), chunk_index * chunk_size)
    chunk_subjects <- subject_series[start_index:end_index]
    first_subject <- chunk_subjects[[1]]
    preview_path <- output_paths[[1]]
    chunks[[chunk_index]] <- list(
      chunkId = sprintf("subjects-%03d-%03d", start_index, end_index),
      subjectRange = c(start_index, end_index),
      timeRange = c(0, max(first_subject$time)),
      preview = list(
        output = preview_path,
        subjectId = first_subject$subjectId,
        time = first_subject$time[1:min(5, length(first_subject$time))],
        value = first_subject$outputs[[preview_path]][1:min(5, length(first_subject$outputs[[preview_path]]))]
      ),
      payload = list(
        outputs = output_paths,
        subjects = chunk_subjects
      )
    )
  }

  list(
    aggregates = list(
      meanCmax = mean(cmax_values),
      sdCmax = .safe_sd(cmax_values),
      meanTmax = mean(tmax_values),
      meanAUC = mean(auc_values),
      sdAUC = .safe_sd(auc_values)
    ),
    metadata = list(
      engine = "rxode2",
      sourceModel = "cisplatin_population_rxode2_model.R",
      cohortSize = length(subject_series),
      storedOutputs = output_paths
    ),
    chunks = chunks
  )
}
