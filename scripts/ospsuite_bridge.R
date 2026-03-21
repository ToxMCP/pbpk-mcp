suppressPackageStartupMessages(library(jsonlite))

`%||%` <- function(lhs, rhs) {
  if (is.null(lhs) || length(lhs) == 0) {
    return(rhs)
  }
  lhs
}

now_utc <- function() {
  format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC")
}

safe_chr <- function(value, default = NULL) {
  if (is.null(value) || length(value) == 0) {
    return(default)
  }
  candidate <- as.character(value[[1]])
  if (is.na(candidate) || identical(candidate, "NA")) {
    return(default)
  }
  candidate
}

safe_num <- function(value, default = NULL) {
  if (is.null(value) || length(value) == 0) {
    return(default)
  }
  candidate <- suppressWarnings(as.numeric(value[[1]]))
  if (is.na(candidate)) {
    return(default)
  }
  candidate
}

safe_lgl <- function(value, default = FALSE) {
  if (is.null(value) || length(value) == 0) {
    return(default)
  }
  candidate <- suppressWarnings(as.logical(value[[1]]))
  if (is.na(candidate)) {
    return(default)
  }
  candidate
}

emit_json <- function(payload) {
  cat(toJSON(payload, auto_unbox = TRUE, null = "null", digits = NA), "\n")
  flush(stdout())
}

emit_error <- function(code, message, details = NULL) {
  emit_json(list(error = list(code = code, message = message, details = details)))
}

ensure_ospsuite <- local({
  loaded <- FALSE
  function() {
    if (loaded) {
      return(invisible(TRUE))
    }
    if (!requireNamespace("ospsuite", quietly = TRUE)) {
      stop("The ospsuite package is required for .pkml simulations", call. = FALSE)
    }
    suppressPackageStartupMessages(library(ospsuite))
    loaded <<- TRUE
    invisible(TRUE)
  }
})

simulations <- new.env(parent = emptyenv())
results_store <- new.env(parent = emptyenv())
population_results_store <- new.env(parent = emptyenv())

simulation_record <- function(simulation_id) {
  if (!exists(simulation_id, envir = simulations, inherits = FALSE)) {
    stop(sprintf("Simulation '%s' not loaded", simulation_id), call. = FALSE)
  }
  get(simulation_id, envir = simulations, inherits = FALSE)
}

result_record <- function(results_id) {
  if (!exists(results_id, envir = results_store, inherits = FALSE)) {
    stop(sprintf("Results '%s' not found", results_id), call. = FALSE)
  }
  get(results_id, envir = results_store, inherits = FALSE)
}

population_result_record <- function(results_id) {
  if (!exists(results_id, envir = population_results_store, inherits = FALSE)) {
    stop(sprintf("Population results '%s' not found", results_id), call. = FALSE)
  }
  get(results_id, envir = population_results_store, inherits = FALSE)
}

parameter_payload <- function(parameter) {
  list(
    path = safe_chr(parameter$path),
    value = safe_num(parameter$value, 0),
    unit = safe_chr(parameter$displayUnit) %||% safe_chr(parameter$unit) %||% "unitless",
    display_name = safe_chr(parameter$name),
    last_updated_at = now_utc(),
    source = "ospsuite"
  )
}

parameter_summary_payload <- function(parameter) {
  list(
    path = safe_chr(parameter$path),
    display_name = safe_chr(parameter$name),
    unit = safe_chr(parameter$displayUnit) %||% safe_chr(parameter$unit),
    category = NULL,
    is_editable = TRUE
  )
}

ospsuite_output_selection_count <- function(simulation) {
  outputs <- tryCatch(
    simulation$outputSelections$get("OutputsAsArray"),
    error = function(...) list()
  )
  length(outputs %||% list())
}

ospsuite_output_priority <- function(path) {
  normalized <- tolower(path %||% "")
  patterns <- c(
    "plasma (peripheral venous blood)",
    "whole blood (peripheral venous blood)",
    "plasma unbound (peripheral venous blood)",
    "peripheralvenousblood",
    "venousblood",
    "arterialblood",
    "plasma unbound",
    "whole blood",
    "blood cells",
    "tissue",
    "interstitial unbound",
    "intracellular unbound",
    "fraction excreted to urine",
    "fraction excreted to bile",
    "fraction excreted to feces"
  )

  for (index in seq_along(patterns)) {
    if (grepl(patterns[[index]], normalized, fixed = TRUE)) {
      return(index)
    }
  }

  length(patterns) + 1
}

ospsuite_observer_output_candidates <- function(simulation) {
  quantity_paths <- tryCatch(getAllQuantityPathsIn(simulation), error = function(...) character())
  candidates <- character()

  for (path in quantity_paths) {
    quantity <- getQuantity(path, simulation, stopIfNotFound = FALSE)
    if (is.null(quantity)) {
      next
    }

    quantity_type <- safe_chr(quantity$quantityType) %||%
      safe_chr(quantity$get("QuantityTypeAsString"), "")
    if (!nzchar(quantity_type) || !grepl("Observer", quantity_type, fixed = TRUE)) {
      next
    }

    candidates <- c(candidates, safe_chr(path))
  }

  unique(candidates[nzchar(candidates)])
}

ensure_ospsuite_output_selections <- function(simulation, max_outputs = 24L) {
  existing_count <- ospsuite_output_selection_count(simulation)
  if (existing_count > 0) {
    return(list(
      mode = "declared",
      selectedCount = existing_count,
      autoSelectedCount = 0L,
      candidateCount = existing_count,
      selectedPaths = list()
    ))
  }

  observer_paths <- ospsuite_observer_output_candidates(simulation)
  if (length(observer_paths) == 0) {
    return(list(
      mode = "empty",
      selectedCount = 0L,
      autoSelectedCount = 0L,
      candidateCount = 0L,
      selectedPaths = list()
    ))
  }

  ranked_paths <- observer_paths[order(
    vapply(observer_paths, ospsuite_output_priority, numeric(1)),
    nchar(observer_paths),
    observer_paths
  )]
  selected_paths <- utils::head(ranked_paths, max(1L, as.integer(max_outputs)))
  added_paths <- list()

  for (path in selected_paths) {
    quantity <- getQuantity(path, simulation, stopIfNotFound = FALSE)
    if (is.null(quantity)) {
      next
    }
    simulation$outputSelections$addQuantity(quantity)
    added_paths[[length(added_paths) + 1]] <- path
  }

  auto_selected_count <- length(added_paths)
  if (auto_selected_count == 0) {
    return(list(
      mode = "empty",
      selectedCount = 0L,
      autoSelectedCount = 0L,
      candidateCount = length(observer_paths),
      selectedPaths = list()
    ))
  }

  list(
    mode = "observer-fallback",
    selectedCount = ospsuite_output_selection_count(simulation),
    autoSelectedCount = auto_selected_count,
    candidateCount = length(observer_paths),
    selectedPaths = added_paths
  )
}

ospsuite_output_selection_warnings <- function(selection_info) {
  mode <- safe_chr(selection_info$mode, "declared")
  if (identical(mode, "observer-fallback")) {
    return(list(list(
      code = "ospsuite_auto_output_selection",
      message = sprintf(
        paste(
          "Model declared no OutputSelections;",
          "auto-selected %d observer quantities from %d candidates for runtime execution"
        ),
        safe_num(selection_info$autoSelectedCount, 0),
        safe_num(selection_info$candidateCount, 0)
      ),
      field = "OutputSelections",
      severity = "warning"
    )))
  }

  if (identical(mode, "empty")) {
    return(list(list(
      code = "ospsuite_missing_output_selection",
      message = paste(
        "Model declared no OutputSelections and no observer-backed fallback",
        "could be generated for runtime execution"
      ),
      field = "OutputSelections",
      severity = "warning"
    )))
  }

  list()
}

series_from_results <- function(simulation_results) {
  result_type <- safe_chr(simulation_results$type)
  result_count <- safe_num(simulation_results$count, 0)
  if (result_count <= 0 || identical(result_type, "OSPSuite.Core.Domain.Data.NullSimulationResults")) {
    stop(
      paste(
        "Simulation produced no results.",
        "The model may require explicit output selections or may be incompatible with the current runtime."
      ),
      call. = FALSE
    )
  }

  df <- simulationResultsToDataFrame(simulation_results)
  paths <- unique(df$paths)
  lapply(paths, function(path) {
    rows <- df[df$paths == path, , drop = FALSE]
    values <- lapply(seq_len(nrow(rows)), function(index) {
      list(
        time = as.numeric(rows$Time[[index]]),
        value = as.numeric(rows$simulationValues[[index]])
      )
    })
    list(
      parameter = as.character(path),
      unit = safe_chr(rows$unit, "dimensionless"),
      values = values
    )
  })
}

detect_backend <- function(file_path) {
  extension <- tolower(tools::file_ext(file_path))
  if (extension == "pkml") {
    return("ospsuite")
  }
  if (extension == "r") {
    return("rxode2")
  }
  stop(
    sprintf("Unsupported simulation extension '.%s'; expected .pkml or .R", extension),
    call. = FALSE
  )
}

normalize_parameter_catalog <- function(parameters, catalog) {
  normalized <- list()
  if (!is.null(catalog) && length(catalog) > 0) {
    for (entry in catalog) {
      if (!is.list(entry)) {
        next
      }
      path <- safe_chr(entry$path)
      if (is.null(path) || !nzchar(path)) {
        next
      }
      normalized_entry <- entry
      normalized_entry$path <- path
      normalized_entry$display_name <- safe_chr(entry$display_name) %||% safe_chr(entry$displayName) %||% path
      normalized_entry$unit <- safe_chr(entry$unit, "unitless")
      normalized_entry$category <- safe_chr(entry$category)
      normalized_entry$is_editable <- isTRUE(entry$is_editable %||% entry$isEditable %||% TRUE)
      normalized_entry$provenance_status <- safe_chr(entry$provenance_status) %||%
        safe_chr(entry$provenanceStatus) %||%
        if (length(normalize_text_values(list(
          entry$source,
          entry$sourceType,
          entry$sourceCitation,
          entry$sourceTable,
          entry$evidenceType,
          entry$rationale,
          entry$distribution,
          entry$mean,
          entry$sd,
          entry$standardDeviation,
          entry$experimentalConditions,
          entry$testConditions,
          entry$studyConditions,
          entry$motivation
        ))) > 0) {
          "declared"
        } else {
          "unreported"
        }
      normalized[[path]] <- normalized_entry
    }
  }

  for (path in names(parameters)) {
    if (is.null(normalized[[path]])) {
      normalized[[path]] <- list(
        path = path,
        display_name = path,
        unit = "unitless",
        category = NULL,
        is_editable = TRUE,
        provenance_status = "unreported"
      )
    }
  }

  normalized
}

normalize_validation_issues <- function(entries, default_severity) {
  normalized <- list()
  for (entry in entries %||% list()) {
    if (is.character(entry) || is.numeric(entry) || is.logical(entry)) {
      message <- safe_chr(entry)
      if (is.null(message) || !nzchar(message)) {
        next
      }
      normalized[[length(normalized) + 1]] <- list(
        code = NULL,
        message = message,
        field = NULL,
        severity = default_severity
      )
      next
    }

    if (!is.list(entry)) {
      next
    }

    message <- safe_chr(entry$message) %||% safe_chr(entry$msg) %||% safe_chr(entry$text)
    if (is.null(message) || !nzchar(message)) {
      next
    }

    normalized[[length(normalized) + 1]] <- list(
      code = safe_chr(entry$code),
      message = message,
      field = safe_chr(entry$field) %||% safe_chr(entry$path),
      severity = safe_chr(entry$severity, default_severity)
    )
  }

  normalized
}

normalize_validation_payload <- function(payload) {
  if (is.null(payload)) {
    return(list(ok = TRUE, summary = NULL, errors = list(), warnings = list(), domain = NULL, assessment = NULL))
  }

  if (!is.list(payload)) {
    stop("Validation hooks must return a list payload", call. = FALSE)
  }

  errors <- normalize_validation_issues(payload$errors, "error")
  warnings <- normalize_validation_issues(payload$warnings, "warning")
  ok <- safe_lgl(payload$ok, length(errors) == 0)

  list(
    ok = isTRUE(ok) && length(errors) == 0,
    summary = safe_chr(payload$summary),
    errors = errors,
    warnings = warnings,
    domain = payload$domain %||% payload$applicabilityDomain %||% NULL,
    assessment = if (is.null(payload$assessment)) NULL else payload$assessment
  )
}

format_validation_messages <- function(validation) {
  issues <- c(validation$errors %||% list(), validation$warnings %||% list())
  messages <- vapply(issues, function(entry) {
    field <- safe_chr(entry$field)
    message <- safe_chr(entry$message, "validation issue")
    if (is.null(field) || !nzchar(field)) {
      return(message)
    }
    sprintf("%s: %s", field, message)
  }, character(1))
  messages[nzchar(messages)]
}

call_module_hook <- function(module_env, function_name, args = list()) {
  if (!exists(function_name, envir = module_env, inherits = FALSE)) {
    return(NULL)
  }

  hook <- get(function_name, envir = module_env, inherits = FALSE)
  if (!is.function(hook)) {
    stop(sprintf("Model hook '%s' must be a function", function_name), call. = FALSE)
  }

  formal_names <- names(formals(hook)) %||% character()
  if (!("..." %in% formal_names)) {
    args <- args[names(args) %in% formal_names]
  }

  do.call(hook, args)
}

default_model_profile <- function(backend, file_path, applicability_domain = NULL) {
  model_name <- basename(file_path %||% backend)
  runtime_version <- safe_chr(R.version$version.string)
  software_name <- switch(
    backend,
    ospsuite = "ospsuite",
    rxode2 = "rxode2",
    backend
  )
  software_version <- tryCatch(
    as.character(utils::packageVersion(software_name)),
    error = function(...) NULL
  )
  list(
    contextOfUse = list(
      status = "unreported",
      summary = sprintf("No context-of-use metadata is declared for '%s'", model_name)
    ),
    applicabilityDomain = applicability_domain %||% list(
      type = "unreported",
      summary = sprintf("No model-specific applicability domain is declared for '%s'", model_name)
    ),
    modelPerformance = list(
      status = "unreported",
      summary = sprintf("No model-performance or predictivity metadata is declared for '%s'", model_name)
    ),
    parameterProvenance = list(
      status = "unreported",
      summary = sprintf("No parameter-provenance metadata is declared for '%s'", model_name)
    ),
    uncertainty = list(
      status = "unreported",
      summary = sprintf("No uncertainty or sensitivity metadata is declared for '%s'", model_name)
    ),
    implementationVerification = list(
      status = "unreported",
      summary = sprintf("No implementation-verification metadata is declared for '%s'", model_name)
    ),
    platformQualification = list(
      status = "runtime-platform-documented",
      softwareName = software_name,
      softwareVersion = software_version,
      runtime = "R",
      runtimeVersion = runtime_version,
      qualificationBasis = paste(
        "The MCP bridge records the execution software and runtime version,",
        "but no formal software-platform qualification dossier is attached by default."
      ),
      missingEvidence = list(
        "Formal software/platform qualification dossier",
        "Documented software validation or acceptance criteria"
      ),
      summary = sprintf(
        "The MCP bridge records runtime platform details for '%s', but this should not be treated as formal software qualification evidence.",
        model_name
      )
    ),
    peerReview = list(
      status = "unreported",
      summary = sprintf("No peer-review or prior-use metadata is declared for '%s'", model_name)
    ),
    profileSource = list(
      type = "unreported",
      summary = sprintf("No profile-source metadata is declared for '%s'", model_name)
    )
  )
}

normalize_profile_section <- function(value, default, scalar_field = "summary") {
  merged <- default %||% list()
  if (is.null(value)) {
    return(merged)
  }

  if (is.list(value)) {
    for (name in names(value)) {
      merged[[name]] <- value[[name]]
    }
    return(merged)
  }

  scalar <- safe_chr(value)
  if (is.null(scalar) || !nzchar(scalar)) {
    return(merged)
  }
  merged[[scalar_field]] <- scalar
  merged
}

normalize_model_profile <- function(payload, backend, file_path, applicability_domain = NULL) {
  defaults <- default_model_profile(backend, file_path, applicability_domain)
  if (is.null(payload)) {
    return(defaults)
  }
  if (!is.list(payload)) {
    stop("pbpk_model_profile() must return a list", call. = FALSE)
  }

  merged <- defaults
  normalized_sections <- c(
    "contextOfUse",
    "applicabilityDomain",
    "modelPerformance",
    "parameterProvenance",
    "uncertainty",
    "implementationVerification",
    "platformQualification",
    "peerReview",
    "profileSource"
  )

  for (name in setdiff(names(payload), normalized_sections)) {
    merged[[name]] <- payload[[name]]
  }

  for (name in normalized_sections) {
    if (identical(name, "peerReview")) {
      merged[[name]] <- normalize_peer_review_section(payload[[name]], defaults[[name]])
    } else if (identical(name, "modelPerformance")) {
      merged[[name]] <- normalize_model_performance_section(payload[[name]], defaults[[name]])
    } else {
      merged[[name]] <- normalize_profile_section(payload[[name]], defaults[[name]])
    }
  }

  merged
}

normalize_text_values <- function(value) {
  if (is.null(value) || length(value) == 0) {
    return(character())
  }

  if (is.list(value)) {
    values <- unlist(lapply(value, normalize_text_values), use.names = FALSE)
    values <- trimws(as.character(values %||% character()))
    return(unique(values[nzchar(values)]))
  }

  candidate <- safe_chr(value)
  if (is.null(candidate) || !nzchar(candidate)) {
    return(character())
  }

  unique(trimws(candidate))
}

coerce_request_section <- function(value, scalar_key = NULL) {
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

first_text_value <- function(value) {
  values <- normalize_text_values(value)
  if (length(values) == 0) {
    return(NULL)
  }
  values[[1]]
}

selection_triplet <- function(requested = NULL, declared = NULL) {
  list(
    requested = requested,
    declared = declared,
    effective = requested %||% declared
  )
}

normalize_context_token <- function(value) {
  candidate <- safe_chr(value)
  if (is.null(candidate) || !nzchar(candidate)) {
    return(NULL)
  }

  normalized <- tolower(gsub("[^a-z0-9]+", "-", trimws(candidate)))
  normalized <- gsub("(^-+|-+$)", "", normalized)
  if (!nzchar(normalized)) {
    return(NULL)
  }
  normalized
}

is_unreported_token <- function(value) {
  token <- normalize_context_token(value)
  if (is.null(token)) {
    return(TRUE)
  }

  token %in% c(
    "unreported",
    "undeclared",
    "undeclared-in-transfer-file",
    "not-reported",
    "unknown",
    "unspecified",
    "not-assessed"
  )
}

is_missing_evidence_token <- function(value) {
  token <- normalize_context_token(value)
  if (is.null(token)) {
    return(TRUE)
  }

  token %in% c(
    "unreported",
    "undeclared",
    "undeclared-in-transfer-file",
    "not-reported",
    "unknown",
    "unspecified",
    "not-assessed",
    "not-bundled",
    "not-available",
    "not-encoded",
    "not-included",
    "not-collected",
    "not-attached",
    "not-qualified"
  )
}

is_limited_evidence_token <- function(value) {
  token <- normalize_context_token(value)
  if (is.null(token)) {
    return(FALSE)
  }

  token %in% c(
    "limited-internal-evaluation",
    "smoke-only",
    "face-validity-and-smoke-tests-only",
    "qualitative-only",
    "runtime-only",
    "runtime-smoke-test-only",
    "example-only",
    "illustrative-only"
  )
}

performance_evidence_rows_from_profile <- function(performance) {
  evidence_rows <- performance$evidence %||% performance$evidenceRows %||% performance$evidenceTable
  if (is.list(evidence_rows) && length(evidence_rows) > 0) {
    return(evidence_rows)
  }

  rows <- list()
  goodness <- exact_list_field(performance, "goodnessOfFit")
  predictive <- exact_list_field(performance, "predictiveChecks")
  evaluation <- exact_list_field(performance, "evaluationData")
  if (!is.list(goodness)) goodness <- list()
  if (!is.list(predictive)) predictive <- list()
  if (!is.list(evaluation)) evaluation <- list()

  metrics <- exact_list_field(goodness, "metrics") %||% list()
  for (index in seq_along(metrics)) {
    entry <- metrics[[index]]
    if (is.character(entry) || is.numeric(entry) || is.logical(entry)) {
      rows[[length(rows) + 1]] <- list(
        id = sprintf("goodness-of-fit-metric-%03d", index),
        kind = "goodness-of-fit-metric",
        metric = safe_chr(entry),
        status = safe_chr(exact_list_field(goodness, "status"), "declared")
      )
    } else if (is.list(entry)) {
      rows[[length(rows) + 1]] <- utils::modifyList(
        list(
          id = sprintf("goodness-of-fit-metric-%03d", index),
          kind = "goodness-of-fit-metric",
          status = safe_chr(exact_list_field(goodness, "status"), "declared")
        ),
        entry
      )
    }
  }

  goodness_datasets <- normalize_text_values(exact_list_field(goodness, "datasets"))
  if (length(goodness_datasets) > 0) {
    for (index in seq_along(goodness_datasets)) {
      dataset <- goodness_datasets[[index]]
      rows[[length(rows) + 1]] <- list(
        id = sprintf("goodness-of-fit-dataset-%03d", length(rows) + 1),
        kind = "goodness-of-fit-dataset",
        dataset = dataset,
        status = safe_chr(exact_list_field(goodness, "status"), "declared"),
        acceptanceCriterion = performance_acceptance_criterion_at(goodness, index)
      )
    }
  }

  predictive_datasets <- normalize_text_values(exact_list_field(predictive, "datasets"))
  if (length(predictive_datasets) > 0) {
    for (index in seq_along(predictive_datasets)) {
      dataset <- predictive_datasets[[index]]
      rows[[length(rows) + 1]] <- list(
        id = sprintf("predictive-check-dataset-%03d", length(rows) + 1),
        kind = "predictive-dataset",
        dataset = dataset,
        status = safe_chr(exact_list_field(predictive, "status"), "declared"),
        acceptanceCriterion = performance_acceptance_criterion_at(predictive, index)
      )
    }
  }

  append_dataset_record_rows <- function(section, kind, default_status) {
    dataset_records <- performance_section_dataset_records(section)
    if (!is.list(dataset_records) || length(dataset_records) == 0) {
      return(invisible(NULL))
    }

    for (index in seq_along(dataset_records)) {
      entry <- dataset_records[[index]]
      if (!is.list(entry)) {
        next
      }
      dataset <- safe_chr(entry$dataset) %||%
        safe_chr(entry$datasetId) %||%
        safe_chr(entry$id) %||%
        safe_chr(entry$name)
      rows[[length(rows) + 1]] <<- utils::modifyList(
        list(
          id = sprintf("%s-%03d", kind, length(rows) + 1),
          kind = kind,
          dataset = dataset,
          status = default_status,
          acceptanceCriterion = safe_chr(entry$acceptanceCriterion) %||%
            performance_acceptance_criterion_at(section, index)
        ),
        entry
      )
    }
  }

  append_dataset_record_rows(
    goodness,
    "goodness-of-fit-dataset",
    safe_chr(exact_list_field(goodness, "status"), "declared")
  )
  append_dataset_record_rows(
    predictive,
    "predictive-dataset",
    safe_chr(exact_list_field(predictive, "status"), "declared")
  )
  append_dataset_record_rows(
    evaluation,
    "predictive-dataset",
    safe_chr(exact_list_field(evaluation, "status"), "declared")
  )

  rows
}

uncertainty_evidence_rows_from_profile <- function(uncertainty) {
  evidence_rows <- uncertainty$evidence %||% uncertainty$evidenceRows %||% uncertainty$evidenceTable
  if (is.list(evidence_rows) && length(evidence_rows) > 0) {
    return(evidence_rows)
  }

  rows <- list()
  variability <- uncertainty$variabilityApproach %||% list()
  variability_method <- safe_chr(variability$method)
  variability_parameters <- normalize_text_values(
    variability$variedParameters %||% variability$parameters
  )
  variability_notes <- normalize_text_values(variability$notes %||% variability$summary)
  if ((!is.null(variability_method) && nzchar(variability_method)) ||
      length(variability_parameters) > 0 ||
      length(variability_notes) > 0) {
    rows[[length(rows) + 1]] <- list(
      id = "variability-approach",
      kind = "variability-approach",
      status = safe_chr(uncertainty$status, "declared"),
      method = variability_method,
      variedParameters = as.list(variability_parameters),
      notes = as.list(variability_notes)
    )
  }

  sensitivity <- uncertainty$sensitivityAnalysis %||% list()
  sensitivity_status <- safe_chr(sensitivity$status)
  sensitivity_summary <- safe_chr(sensitivity$summary)
  sensitivity_method <- safe_chr(sensitivity$method)
  if ((!is.null(sensitivity_status) && !is_unreported_token(sensitivity_status)) ||
      (!is.null(sensitivity_summary) && nzchar(sensitivity_summary)) ||
      (!is.null(sensitivity_method) && nzchar(sensitivity_method))) {
    rows[[length(rows) + 1]] <- list(
      id = "sensitivity-analysis",
      kind = "sensitivity-analysis",
      status = safe_chr(sensitivity$status, safe_chr(uncertainty$status, "declared")),
      method = sensitivity_method,
      summary = sensitivity_summary
    )
  }

  residuals <- normalize_text_values(uncertainty$residualUncertainty)
  for (index in seq_along(residuals)) {
    rows[[length(rows) + 1]] <- list(
      id = sprintf("residual-uncertainty-%03d", index),
      kind = "residual-uncertainty",
      status = safe_chr(uncertainty$status, "declared"),
      summary = residuals[[index]]
    )
  }

  rows
}

implementation_verification_rows_from_profile <- function(verification) {
  evidence_rows <- verification$evidence %||% verification$evidenceRows %||% verification$evidenceTable
  if (is.list(evidence_rows) && length(evidence_rows) > 0) {
    return(evidence_rows)
  }

  rows <- list()
  verified_checks <- normalize_text_values(verification$verifiedChecks)
  for (index in seq_along(verified_checks)) {
    rows[[length(rows) + 1]] <- list(
      id = sprintf("verified-check-%03d", index),
      kind = "verified-check",
      status = safe_chr(verification$status, "declared"),
      checkName = verified_checks[[index]],
      solver = safe_chr(verification$solver),
      runtime = safe_chr(verification$runtime)
    )
  }

  if (length(rows) == 0) {
    summary <- safe_chr(verification$summary)
    if (!is.null(summary) && nzchar(summary)) {
      rows[[length(rows) + 1]] <- list(
        id = "implementation-verification-summary",
        kind = "implementation-verification-summary",
        status = safe_chr(verification$status, "declared"),
        summary = summary,
        solver = safe_chr(verification$solver),
        runtime = safe_chr(verification$runtime)
      )
    }
  }

  rows
}

platform_qualification_rows_from_profile <- function(platform_qualification) {
  evidence_rows <- platform_qualification$evidence %||%
    platform_qualification$evidenceRows %||%
    platform_qualification$evidenceTable
  if (is.list(evidence_rows) && length(evidence_rows) > 0) {
    return(evidence_rows)
  }

  rows <- list()
  if (length(normalize_text_values(list(
    platform_qualification$softwareName,
    platform_qualification$softwareVersion,
    platform_qualification$runtime,
    platform_qualification$runtimeVersion,
    platform_qualification$qualificationBasis,
    platform_qualification$summary
  ))) > 0) {
    rows[[length(rows) + 1]] <- list(
      id = "software-platform-record",
      kind = "software-platform-record",
      status = safe_chr(platform_qualification$status, "declared"),
      summary = safe_chr(platform_qualification$summary),
      softwareName = safe_chr(platform_qualification$softwareName),
      softwareVersion = safe_chr(platform_qualification$softwareVersion),
      runtime = safe_chr(platform_qualification$runtime),
      runtimeVersion = safe_chr(platform_qualification$runtimeVersion),
      qualificationBasis = safe_chr(platform_qualification$qualificationBasis)
    )
  }

  rows
}

performance_metric_count <- function(performance) {
  goodness <- exact_list_field(performance, "goodnessOfFit")
  if (!is.list(goodness)) {
    goodness <- list()
  }
  metrics <- exact_list_field(goodness, "metrics") %||% list()
  if (is.null(metrics)) {
    return(0L)
  }
  if (is.list(metrics)) {
    return(length(metrics))
  }
  length(normalize_text_values(metrics))
}

performance_dataset_count <- function(performance) {
  summary <- performance_traceability_summary(performance)
  as.integer(
    summary$goodnessOfFitDatasetCount +
      summary$goodnessOfFitDatasetRecordCount +
      summary$predictiveDatasetCount +
      summary$predictiveDatasetRecordCount +
      summary$evaluationDatasetCount +
      summary$evaluationDatasetRecordCount
  )
}

performance_evidence_count <- function(performance) {
  explicit_count <- safe_num(performance$evidenceCount, 0)
  if (is.finite(explicit_count) && explicit_count > 0) {
    return(as.integer(explicit_count))
  }
  as.integer(length(performance_evidence_rows_from_profile(performance)))
}

uncertainty_evidence_count <- function(uncertainty) {
  explicit_count <- safe_num(uncertainty$evidenceCount, 0)
  if (is.finite(explicit_count) && explicit_count > 0) {
    return(as.integer(explicit_count))
  }
  as.integer(length(uncertainty_evidence_rows_from_profile(uncertainty)))
}

implementation_verification_count <- function(verification) {
  explicit_count <- safe_num(verification$evidenceCount, 0)
  if (is.finite(explicit_count) && explicit_count > 0) {
    return(as.integer(explicit_count))
  }
  as.integer(length(implementation_verification_rows_from_profile(verification)))
}

platform_qualification_count <- function(platform_qualification) {
  explicit_count <- safe_num(platform_qualification$evidenceCount, 0)
  if (is.finite(explicit_count) && explicit_count > 0) {
    return(as.integer(explicit_count))
  }
  as.integer(length(platform_qualification_rows_from_profile(platform_qualification)))
}

merge_validation_issues <- function(existing, additions) {
  merged <- existing %||% list()
  seen <- character()

  if (length(merged) > 0) {
    seen <- vapply(merged, function(entry) {
      paste(
        safe_chr(entry$code, ""),
        safe_chr(entry$field, ""),
        safe_chr(entry$message, ""),
        safe_chr(entry$severity, ""),
        sep = "|"
      )
    }, character(1))
  }

  for (entry in additions %||% list()) {
    key <- paste(
      safe_chr(entry$code, ""),
      safe_chr(entry$field, ""),
      safe_chr(entry$message, ""),
      safe_chr(entry$severity, ""),
      sep = "|"
    )
    if (key %in% seen) {
      next
    }
    merged[[length(merged) + 1]] <- entry
    seen <- c(seen, key)
  }

  merged
}

append_missing_evidence <- function(target, entry) {
  messages <- normalize_text_values(entry)
  merged <- unique(c(normalize_text_values(target), messages))
  as.list(merged)
}

oecd_dimension_status <- function(present_fields, missing_fields) {
  present_count <- length(unique(normalize_text_values(present_fields)))
  missing_count <- length(unique(normalize_text_values(missing_fields)))

  if (present_count == 0) {
    return("missing")
  }
  if (missing_count == 0) {
    return("declared")
  }
  "partial"
}

oecd_dimension <- function(id, label, present_fields = character(), missing_fields = character(), summary = NULL) {
  list(
    id = id,
    label = label,
    status = oecd_dimension_status(present_fields, missing_fields),
    declaredFields = as.list(unique(normalize_text_values(present_fields))),
    missingFields = as.list(unique(normalize_text_values(missing_fields))),
    summary = summary
  )
}

profile_oecd_checklist <- function(profile, capabilities = list()) {
  context <- profile$contextOfUse %||% list()
  context_present <- character()
  context_missing <- character()
  for (field in c("scientificPurpose", "decisionContext", "regulatoryUse")) {
    if (length(normalize_text_values(context[[field]])) > 0 && !is_unreported_token(context[[field]])) {
      context_present <- c(context_present, field)
    } else {
      context_missing <- c(context_missing, field)
    }
  }

  domain <- profile$applicabilityDomain %||% list()
  domain_present <- character()
  domain_missing <- character()
  for (field in c("type", "qualificationLevel", "species", "routes")) {
    if (length(normalize_text_values(domain[[field]])) > 0 && !is_unreported_token(domain[[field]])) {
      domain_present <- c(domain_present, field)
    } else {
      domain_missing <- c(domain_missing, field)
    }
  }

  performance <- profile$modelPerformance %||% list()
  performance_traceability <- performance_traceability_summary(performance)
  performance_present <- character()
  performance_missing <- character()
  metric_count <- performance_metric_count(performance)
  dataset_count <- performance_dataset_count(performance)
  evidence_count <- performance_evidence_count(performance)
  goodness <- exact_list_field(performance, "goodnessOfFit") %||% list()
  predictive <- exact_list_field(performance, "predictiveChecks") %||% list()
  if (!is_missing_evidence_token(performance$status)) {
    performance_present <- c(performance_present, "status")
  } else {
    performance_missing <- c(performance_missing, "status")
  }
  if (!is_missing_evidence_token(exact_list_field(goodness, "status")) &&
      (
        metric_count > 0 ||
          performance_traceability$goodnessOfFitDatasetCount > 0 ||
          performance_traceability$goodnessOfFitDatasetRecordCount > 0 ||
          evidence_count > 0
      )) {
    performance_present <- c(performance_present, "goodnessOfFit")
  } else {
    performance_missing <- c(performance_missing, "goodnessOfFit")
  }
  if (!is_missing_evidence_token(exact_list_field(predictive, "status")) &&
      (
        performance_traceability$predictiveDatasetCount > 0 ||
          performance_traceability$predictiveDatasetRecordCount > 0 ||
          performance_traceability$evaluationDatasetCount > 0 ||
          performance_traceability$evaluationDatasetRecordCount > 0 ||
          evidence_count > 0
      )) {
    performance_present <- c(performance_present, "predictiveChecks")
  } else {
    performance_missing <- c(performance_missing, "predictiveChecks")
  }
  if (performance_traceability$acceptanceCriterionCount > 0) {
    performance_present <- c(performance_present, "acceptanceCriteria")
  } else {
    performance_missing <- c(performance_missing, "acceptanceCriteria")
  }
  if (length(normalize_text_values(performance$targetOutputs)) > 0) {
    performance_present <- c(performance_present, "targetOutputs")
  } else {
    performance_missing <- c(performance_missing, "targetOutputs")
  }
  if (is_limited_evidence_token(performance$status) ||
      is_limited_evidence_token(exact_list_field(predictive, "status"))) {
    performance_missing <- c(performance_missing, "externalPredictivityEvidence")
  }

  provenance <- profile$parameterProvenance %||% list()
  provenance_present <- character()
  provenance_missing <- character()
  declared_parameter_count <- safe_num(provenance$declaredParameterCount, 0)
  if (!is_unreported_token(provenance$status)) {
    provenance_present <- c(provenance_present, "status")
  } else {
    provenance_missing <- c(provenance_missing, "status")
  }
  if (length(normalize_text_values(provenance$sourceTable %||% provenance$source)) > 0) {
    provenance_present <- c(provenance_present, "sourceTable")
  } else {
    provenance_missing <- c(provenance_missing, "sourceTable")
  }
  if (length(normalize_text_values(provenance$coverage)) > 0 ||
      (is.finite(declared_parameter_count) && declared_parameter_count > 0)) {
    provenance_present <- c(provenance_present, "coverage")
  } else {
    provenance_missing <- c(provenance_missing, "coverage")
  }
  if (length(normalize_text_values(provenance$provenanceMethod %||% provenance$evidenceTypes)) > 0) {
    provenance_present <- c(provenance_present, "provenanceMethod")
  } else {
    provenance_missing <- c(provenance_missing, "provenanceMethod")
  }

  uncertainty <- profile$uncertainty %||% list()
  uncertainty_present <- character()
  uncertainty_missing <- character()
  uncertainty_row_count <- uncertainty_evidence_count(uncertainty)
  if (!is_unreported_token(uncertainty$status)) {
    uncertainty_present <- c(uncertainty_present, "status")
  } else {
    uncertainty_missing <- c(uncertainty_missing, "status")
  }
  sensitivity_status <- uncertainty$sensitivityAnalysis$status %||% NULL
  if (!is_unreported_token(sensitivity_status) || length(normalize_text_values(uncertainty$variabilityApproach$method)) > 0) {
    uncertainty_present <- c(uncertainty_present, "sensitivityAnalysis")
  } else {
    uncertainty_missing <- c(uncertainty_missing, "sensitivityAnalysis")
  }
  if (length(normalize_text_values(uncertainty$residualUncertainty)) > 0) {
    uncertainty_present <- c(uncertainty_present, "residualUncertainty")
  } else {
    uncertainty_missing <- c(uncertainty_missing, "residualUncertainty")
  }
  if (uncertainty_row_count > 0) {
    uncertainty_present <- c(uncertainty_present, "evidenceRows")
  } else {
    uncertainty_missing <- c(uncertainty_missing, "evidenceRows")
  }

  verification <- profile$implementationVerification %||% list()
  verification_present <- character()
  verification_missing <- character()
  verification_row_count <- implementation_verification_count(verification)
  if (!is_unreported_token(verification$status)) {
    verification_present <- c(verification_present, "status")
  } else {
    verification_missing <- c(verification_missing, "status")
  }
  if (length(normalize_text_values(verification$verifiedChecks)) > 0) {
    verification_present <- c(verification_present, "verifiedChecks")
  } else {
    verification_missing <- c(verification_missing, "verifiedChecks")
  }
  if (length(normalize_text_values(verification$solver)) > 0 || length(normalize_text_values(verification$runtime)) > 0) {
    verification_present <- c(verification_present, "runtimeOrSolver")
  } else {
    verification_missing <- c(verification_missing, "runtimeOrSolver")
  }
  if (verification_row_count > 0) {
    verification_present <- c(verification_present, "evidenceRows")
  } else {
    verification_missing <- c(verification_missing, "evidenceRows")
  }

  platform <- profile$platformQualification %||% list()
  platform_present <- character()
  platform_missing <- character()
  platform_row_count <- platform_qualification_count(platform)
  if (!is_unreported_token(platform$status)) {
    platform_present <- c(platform_present, "status")
  } else {
    platform_missing <- c(platform_missing, "status")
  }
  if (length(normalize_text_values(platform$softwareName %||% platform$softwareVersion)) > 0) {
    platform_present <- c(platform_present, "softwareIdentity")
  } else {
    platform_missing <- c(platform_missing, "softwareIdentity")
  }
  if (length(normalize_text_values(platform$runtime)) > 0 ||
      length(normalize_text_values(platform$runtimeVersion)) > 0) {
    platform_present <- c(platform_present, "runtimeEnvironment")
  } else {
    platform_missing <- c(platform_missing, "runtimeEnvironment")
  }
  if (length(normalize_text_values(platform$qualificationBasis)) > 0) {
    platform_present <- c(platform_present, "qualificationBasis")
  } else {
    platform_missing <- c(platform_missing, "qualificationBasis")
  }
  if (platform_row_count > 0) {
    platform_present <- c(platform_present, "evidenceRows")
  } else {
    platform_missing <- c(platform_missing, "evidenceRows")
  }

  review <- profile$peerReview %||% list()
  review_coverage <- peer_review_coverage_summary(review)
  review_present <- character()
  review_missing <- character()
  if (!is_unreported_token(review$status)) {
    review_present <- c(review_present, "status")
  } else {
    review_missing <- c(review_missing, "status")
  }
  if (review_coverage$reviewRecordCount > 0) {
    review_present <- c(review_present, "reviewRecords")
  } else {
    review_missing <- c(review_missing, "reviewRecords")
  }
  if (review_coverage$priorUseCount > 0) {
    review_present <- c(review_present, "priorRegulatoryUse")
  } else {
    review_missing <- c(review_missing, "priorRegulatoryUse")
  }
  if (review_coverage$revisionEntryCount > 0) {
    review_present <- c(review_present, "revisionHistory")
  } else {
    review_missing <- c(review_missing, "revisionHistory")
  }
  if (length(normalize_text_values(review$revisionStatus)) > 0) {
    review_present <- c(review_present, "revisionStatus")
  } else {
    review_missing <- c(review_missing, "revisionStatus")
  }

  source <- profile$profileSource %||% list()
  traceability_present <- character()
  traceability_missing <- character()
  if (isTRUE(capabilities$scientificProfile)) {
    traceability_present <- c(traceability_present, "scientificProfile")
  } else {
    traceability_missing <- c(traceability_missing, "scientificProfile")
  }
  if (!is_unreported_token(source$type)) {
    traceability_present <- c(traceability_present, "profileSource.type")
  } else {
    traceability_missing <- c(traceability_missing, "profileSource.type")
  }
  if (length(normalize_text_values(source$path)) > 0 ||
      length(normalize_text_values(source$sourceToolHint)) > 0 ||
      !identical(safe_chr(source$type), "bridge-default")) {
    traceability_present <- c(traceability_present, "traceabilityDetail")
  } else {
    traceability_missing <- c(traceability_missing, "traceabilityDetail")
  }

  list(
    contextOfUse = oecd_dimension(
      "contextOfUse",
      "Context of use",
      present_fields = context_present,
      missing_fields = context_missing,
      summary = safe_chr(context$summary, "Problem formulation and intended use metadata")
    ),
    applicabilityDomain = oecd_dimension(
      "applicabilityDomain",
      "Applicability domain",
      present_fields = domain_present,
      missing_fields = domain_missing,
      summary = safe_chr(domain$summary, "Declared domain, species, route, and qualification metadata")
    ),
    modelPerformanceAndPredictivity = oecd_dimension(
      "modelPerformanceAndPredictivity",
      "Model performance and predictivity",
      present_fields = performance_present,
      missing_fields = performance_missing,
      summary = safe_chr(performance$summary, "Goodness-of-fit, predictive checks, and performance metadata")
    ),
    parameterizationAndProvenance = oecd_dimension(
      "parameterizationAndProvenance",
      "Parameterization and provenance",
      present_fields = provenance_present,
      missing_fields = provenance_missing,
      summary = safe_chr(provenance$summary, "Parameter tables, sources, and provenance traceability")
    ),
    uncertaintyAndSensitivity = oecd_dimension(
      "uncertaintyAndSensitivity",
      "Uncertainty and sensitivity",
      present_fields = uncertainty_present,
      missing_fields = uncertainty_missing,
      summary = safe_chr(uncertainty$summary, "Uncertainty, variability, and sensitivity characterization")
    ),
    implementationVerification = oecd_dimension(
      "implementationVerification",
      "Implementation verification",
      present_fields = verification_present,
      missing_fields = verification_missing,
      summary = safe_chr(verification$summary, "Code, solver, and internal verification evidence")
    ),
    softwarePlatformQualification = oecd_dimension(
      "softwarePlatformQualification",
      "Software/platform qualification",
      present_fields = platform_present,
      missing_fields = platform_missing,
      summary = safe_chr(
        platform$summary,
        "Software-platform identity, versioning, and qualification-basis metadata"
      )
    ),
    peerReviewAndPriorUse = oecd_dimension(
      "peerReviewAndPriorUse",
      "Peer review and prior use",
      present_fields = review_present,
      missing_fields = review_missing,
      summary = safe_chr(review$summary, "External review, revision status, and prior-use traceability")
    ),
    reportingAndTraceability = oecd_dimension(
      "reportingAndTraceability",
      "Reporting and traceability",
      present_fields = traceability_present,
      missing_fields = traceability_missing,
      summary = safe_chr(source$summary, "Profile source and traceability metadata")
    )
  )
}

profile_oecd_checklist_score <- function(checklist) {
  entries <- checklist %||% list()
  if (length(entries) == 0) {
    return(0)
  }

  total <- 0
  for (entry in entries) {
    status <- safe_chr(entry$status, "missing")
    total <- total + switch(
      status,
      declared = 1,
      partial = 0.5,
      missing = 0,
      0
    )
  }
  total / length(entries)
}

collect_text_values <- function(...) {
  values <- unlist(lapply(list(...), normalize_text_values), use.names = FALSE)
  values <- trimws(as.character(values %||% character()))
  unique(values[nzchar(values)])
}

exact_list_field <- function(value, name) {
  if (!is.list(value) || is.null(names(value)) || !(name %in% names(value))) {
    return(NULL)
  }
  value[[name]]
}

record_entry_count <- function(value) {
  if (is.null(value) || length(value) == 0) {
    return(0L)
  }

  if (is.logical(value) && length(value) == 1 && !isTRUE(value)) {
    return(0L)
  }

  if (is.list(value)) {
    if (!is.null(names(value))) {
      return(as.integer(length(normalize_text_values(value)) > 0))
    }

    return(as.integer(sum(vapply(value, function(entry) {
      if (is.logical(entry) && length(entry) == 1 && !isTRUE(entry)) {
        return(FALSE)
      }
      length(normalize_text_values(entry)) > 0
    }, logical(1)))))
  }

  as.integer(length(normalize_text_values(value)) > 0)
}

peer_review_coverage_summary <- function(review) {
  review_records <- exact_list_field(review, "reviewRecords") %||%
    exact_list_field(review, "reviews") %||%
    exact_list_field(review, "peerReviewRecords") %||%
    exact_list_field(review, "reviewHistory")
  prior_use <- exact_list_field(review, "priorRegulatoryUse") %||%
    exact_list_field(review, "priorUse") %||%
    exact_list_field(review, "priorApplications") %||%
    exact_list_field(review, "priorUseHistory")
  revision_history <- exact_list_field(review, "revisionHistory") %||%
    exact_list_field(review, "changeHistory") %||%
    exact_list_field(review, "versionHistory") %||%
    exact_list_field(review, "revisions")

  review_record_count <- record_entry_count(review_records)
  if (review_record_count == 0 &&
      length(collect_text_values(
      review$reviewType,
      review$reviewOutcome,
      review$reviewDate,
      review$reviewer,
      review$reviewBody
      )) > 0) {
    review_record_count <- 1L
  }

  list(
    reviewRecordCount = as.integer(review_record_count),
    priorUseCount = as.integer(record_entry_count(prior_use)),
    revisionEntryCount = as.integer(record_entry_count(revision_history)),
    hasRevisionStatus = length(normalize_text_values(
      exact_list_field(review, "revisionStatus") %||%
        exact_list_field(review, "changeStatus") %||%
        exact_list_field(review, "versionStatus")
    )) > 0
  )
}

normalize_peer_review_section <- function(value, default) {
  merged <- normalize_profile_section(value, default)
  raw <- if (is.list(value)) value else list()

  review_records <- exact_list_field(raw, "reviewRecords") %||%
    exact_list_field(raw, "reviews") %||%
    exact_list_field(raw, "peerReviewRecords") %||%
    exact_list_field(raw, "reviewHistory")
  if (!is.null(review_records) && is.null(exact_list_field(merged, "reviewRecords"))) {
    merged$reviewRecords <- review_records
  }

  prior_use <- exact_list_field(raw, "priorRegulatoryUse") %||%
    exact_list_field(raw, "priorUse") %||%
    exact_list_field(raw, "priorApplications") %||%
    exact_list_field(raw, "priorUseHistory")
  if (!is.null(prior_use) && is.null(exact_list_field(merged, "priorRegulatoryUse"))) {
    merged$priorRegulatoryUse <- prior_use
  }

  revision_history <- exact_list_field(raw, "revisionHistory") %||%
    exact_list_field(raw, "changeHistory") %||%
    exact_list_field(raw, "versionHistory") %||%
    exact_list_field(raw, "revisions")
  if (!is.null(revision_history) && is.null(exact_list_field(merged, "revisionHistory"))) {
    merged$revisionHistory <- revision_history
  }

  if (length(normalize_text_values(exact_list_field(merged, "revisionStatus"))) == 0) {
    merged$revisionStatus <- safe_chr(exact_list_field(raw, "changeStatus")) %||%
      safe_chr(exact_list_field(raw, "versionStatus"))
  }
  if (length(normalize_text_values(exact_list_field(merged, "summary"))) == 0) {
    merged$summary <- safe_chr(exact_list_field(raw, "reviewSummary"))
  }

  coverage <- peer_review_coverage_summary(merged)
  merged$coverage <- coverage
  merged$reviewRecordCount <- coverage$reviewRecordCount
  merged$priorUseCount <- coverage$priorUseCount
  merged$revisionEntryCount <- coverage$revisionEntryCount

  merged
}

performance_section_dataset_records <- function(section) {
  exact_list_field(section, "datasetRecords") %||%
    exact_list_field(section, "records") %||%
    exact_list_field(section, "benchmarkDatasets") %||%
    exact_list_field(section, "benchmarkRecords")
}

performance_section_dataset_names <- function(section) {
  normalize_text_values(
    exact_list_field(section, "datasets") %||%
      exact_list_field(section, "datasetIds") %||%
      exact_list_field(section, "datasetNames")
  )
}

performance_section_acceptance_criteria <- function(section) {
  normalize_text_values(
    exact_list_field(section, "acceptanceCriteria") %||%
      exact_list_field(section, "acceptanceCriterion") %||%
      exact_list_field(section, "criteria")
  )
}

performance_acceptance_criteria_values <- function(performance, rows = list()) {
  section_values <- unique(c(
    normalize_text_values(exact_list_field(performance, "acceptanceCriteria")),
    performance_section_acceptance_criteria(exact_list_field(performance, "goodnessOfFit") %||% list()),
    performance_section_acceptance_criteria(exact_list_field(performance, "predictiveChecks") %||% list()),
    performance_section_acceptance_criteria(exact_list_field(performance, "evaluationData") %||% list())
  ))
  row_values <- unique(unlist(lapply(rows %||% list(), function(entry) {
    normalize_text_values(entry$acceptanceCriterion)
  }), use.names = FALSE))
  unique(c(section_values, row_values))
}

performance_traceability_summary <- function(performance, rows = list()) {
  goodness <- exact_list_field(performance, "goodnessOfFit")
  predictive <- exact_list_field(performance, "predictiveChecks")
  evaluation <- exact_list_field(performance, "evaluationData")
  if (!is.list(goodness)) goodness <- list()
  if (!is.list(predictive)) predictive <- list()
  if (!is.list(evaluation)) evaluation <- list()

  acceptance_values <- performance_acceptance_criteria_values(performance, rows)

  list(
    goodnessOfFitMetricCount = as.integer(length(goodness$metrics %||% list())),
    goodnessOfFitDatasetCount = as.integer(length(performance_section_dataset_names(goodness))),
    goodnessOfFitDatasetRecordCount = as.integer(record_entry_count(performance_section_dataset_records(goodness))),
    predictiveDatasetCount = as.integer(length(performance_section_dataset_names(predictive))),
    predictiveDatasetRecordCount = as.integer(record_entry_count(performance_section_dataset_records(predictive))),
    evaluationDatasetCount = as.integer(length(performance_section_dataset_names(evaluation))),
    evaluationDatasetRecordCount = as.integer(record_entry_count(performance_section_dataset_records(evaluation))),
    acceptanceCriterionCount = as.integer(length(acceptance_values)),
    hasExplicitAcceptanceCriteria = length(acceptance_values) > 0
  )
}

performance_acceptance_criterion_at <- function(section, index) {
  values <- performance_section_acceptance_criteria(section)
  if (length(values) == 0) {
    return(NULL)
  }
  if (index <= length(values)) {
    return(values[[index]])
  }
  values[[length(values)]]
}

normalize_model_performance_section <- function(value, default) {
  merged <- normalize_profile_section(value, default)

  for (section_name in c("goodnessOfFit", "predictiveChecks", "evaluationData")) {
    section <- exact_list_field(merged, section_name)
    if (!is.list(section)) {
      next
    }

    if (is.null(exact_list_field(section, "datasetRecords"))) {
      records <- performance_section_dataset_records(section)
      if (!is.null(records)) {
        section$datasetRecords <- records
      }
    }
    if (length(normalize_text_values(exact_list_field(section, "acceptanceCriteria"))) == 0) {
      criteria <- performance_section_acceptance_criteria(section)
      if (length(criteria) > 0) {
        section$acceptanceCriteria <- as.list(criteria)
      }
    }
    merged[[section_name]] <- section
  }

  if (length(normalize_text_values(exact_list_field(merged, "acceptanceCriteria"))) == 0) {
    criteria <- performance_acceptance_criteria_values(merged)
    if (length(criteria) > 0) {
      merged$acceptanceCriteria <- as.list(criteria)
    }
  }

  coverage <- performance_traceability_summary(merged)
  merged$coverage <- coverage
  merged$goodnessOfFitDatasetRecordCount <- coverage$goodnessOfFitDatasetRecordCount
  merged$predictiveDatasetRecordCount <- coverage$predictiveDatasetRecordCount
  merged$evaluationDatasetRecordCount <- coverage$evaluationDatasetRecordCount
  merged$acceptanceCriterionCount <- coverage$acceptanceCriterionCount

  merged
}

aggregate_coverage_status <- function(statuses) {
  normalized <- normalize_text_values(statuses)
  if (length(normalized) == 0) {
    return("missing")
  }
  if (all(normalized == "declared")) {
    return("declared")
  }
  if (all(normalized == "missing")) {
    return("missing")
  }
  "partial"
}

coverage_item <- function(
  id,
  label,
  status = "missing",
  mapped_from = character(),
  missing_elements = character(),
  summary = NULL,
  oecd_reference = NULL,
  question_numbers = integer()
) {
  list(
    id = id,
    label = label,
    status = safe_chr(status, "missing"),
    oecdReference = safe_chr(oecd_reference),
    questionNumbers = as.list(as.integer(question_numbers %||% integer())),
    mappedFrom = as.list(unique(normalize_text_values(mapped_from))),
    missingElements = as.list(unique(normalize_text_values(missing_elements))),
    summary = summary
  )
}

parameter_table_field_present <- function(parameter_table, fields) {
  rows <- parameter_table$rows %||% list()
  for (entry in rows) {
    if (!is.list(entry)) {
      next
    }
    for (field in fields) {
      value <- entry[[field]]
      if (is.null(value) || length(value) == 0) {
        next
      }
      if (is.numeric(value) || is.logical(value)) {
        return(TRUE)
      }
      if (length(normalize_text_values(value)) > 0) {
        return(TRUE)
      }
    }
  }
  FALSE
}

has_passed_verification_check <- function(executable_verification, exact = character(), patterns = character()) {
  checks <- executable_verification$checks %||% list()
  if (length(checks) == 0) {
    return(FALSE)
  }

  for (entry in checks) {
    status <- tolower(safe_chr(entry$status, ""))
    if (!identical(status, "passed")) {
      next
    }
    check_id <- tolower(safe_chr(entry$id, ""))
    if (!nzchar(check_id)) {
      next
    }
    if (length(exact) > 0 && check_id %in% tolower(exact)) {
      return(TRUE)
    }
    if (length(patterns) > 0 && any(vapply(patterns, function(pattern) grepl(pattern, check_id), logical(1)))) {
      return(TRUE)
    }
  }

  FALSE
}

build_oecd_coverage <- function(
  record,
  validation = list(),
  checklist = list(),
  missing_evidence = character(),
  performance_evidence = list(),
  uncertainty_evidence = list(),
  verification_evidence = list(),
  platform_qualification_evidence = list(),
  executable_verification = list(),
  parameter_table = list()
) {
  profile <- record$profile %||% list()
  metadata <- record$metadata %||% list()
  context <- profile$contextOfUse %||% list()
  domain <- profile$applicabilityDomain %||% list()
  performance <- profile$modelPerformance %||% list()
  provenance <- profile$parameterProvenance %||% list()
  uncertainty <- profile$uncertainty %||% list()
  verification <- profile$implementationVerification %||% list()
  platform <- profile$platformQualification %||% list()
  review <- profile$peerReview %||% list()
  source <- profile$profileSource %||% list()

  assumption_values <- collect_text_values(
    profile$assumptions,
    context$assumptions,
    domain$assumptions,
    profile$modelAssumptions
  )
  conceptual_values <- collect_text_values(
    profile$conceptualModel,
    profile$modelStructure,
    profile$graphicalRepresentation,
    profile$conceptualisation,
    profile$conceptualization,
    profile$modeOfAction,
    profile$biologicalBasis
  )
  equation_values <- collect_text_values(
    profile$mathematicalRepresentation,
    profile$theoreticalBasis,
    profile$equations,
    profile$modelEquations
  )
  reference_values <- collect_text_values(
    profile$references,
    profile$publications,
    profile$links,
    profile$backgroundInformation,
    profile$backgroundReferences,
    profile$relatedResources
  )

  developer_present <- character()
  developer_missing <- character()
  if (length(collect_text_values(metadata$createdBy, profile$modelDeveloper$name, profile$developer$name)) > 0) {
    developer_present <- c(developer_present, "developerName")
  } else {
    developer_missing <- c(developer_missing, "developerName")
  }
  if (length(collect_text_values(
    profile$modelDeveloper$contact,
    profile$modelDeveloper$email,
    profile$developer$contact,
    profile$developer$email
  )) > 0) {
    developer_present <- c(developer_present, "contactDetails")
  } else {
    developer_missing <- c(developer_missing, "contactDetails")
  }

  summary_present <- character()
  summary_missing <- character()
  if (length(collect_text_values(
    context$summary,
    domain$summary,
    performance$summary,
    uncertainty$summary,
    verification$summary
  )) > 0) {
    summary_present <- c(summary_present, "developmentAndCharacterisationSummary")
  } else {
    summary_missing <- c(summary_missing, "developmentAndCharacterisationSummary")
  }
  if (length(collect_text_values(validation$summary, validation$assessment$decision)) > 0) {
    summary_present <- c(summary_present, "validationSummary")
  } else {
    summary_missing <- c(summary_missing, "validationSummary")
  }
  if (length(collect_text_values(context$regulatoryUse, domain$qualificationLevel)) > 0) {
    summary_present <- c(summary_present, "regulatoryApplicability")
  } else {
    summary_missing <- c(summary_missing, "regulatoryApplicability")
  }

  step1_present <- character()
  step1_missing <- character()
  for (field in c("scientificPurpose", "decisionContext", "regulatoryUse")) {
    if (length(normalize_text_values(context[[field]])) > 0 && !is_unreported_token(context[[field]])) {
      step1_present <- c(step1_present, field)
    } else {
      step1_missing <- c(step1_missing, field)
    }
  }

  step2_present <- character()
  step2_missing <- character()
  if (length(assumption_values) > 0) {
    step2_present <- c(step2_present, "assumptions")
  } else {
    step2_missing <- c(step2_missing, "assumptions")
  }
  if (length(conceptual_values) > 0) {
    step2_present <- c(step2_present, "conceptualModel")
  } else {
    step2_missing <- c(step2_missing, "conceptualModel")
  }
  if (length(equation_values) > 0) {
    step2_present <- c(step2_present, "mathematicalRepresentation")
  } else {
    step2_missing <- c(step2_missing, "mathematicalRepresentation")
  }

  parameter_table_rows <- safe_num(parameter_table$returnedRows, 0)
  step3_present <- character()
  step3_missing <- character()
  if (!is_unreported_token(provenance$status)) {
    step3_present <- c(step3_present, "parameterProvenance")
  } else {
    step3_missing <- c(step3_missing, "parameterProvenance")
  }
  if (parameter_table_rows > 0) {
    step3_present <- c(step3_present, "parameterTable")
  } else {
    step3_missing <- c(step3_missing, "parameterTable")
  }
  if (parameter_table_field_present(parameter_table, c("source", "sourceType", "sourceCitation", "sourceTable"))) {
    step3_present <- c(step3_present, "parameterSources")
  } else {
    step3_missing <- c(step3_missing, "parameterSources")
  }
  if (parameter_table_field_present(parameter_table, c("distribution", "mean", "sd", "standardDeviation"))) {
    step3_present <- c(step3_present, "parameterDistributions")
  } else {
    step3_missing <- c(step3_missing, "parameterDistributions")
  }

  step4_present <- character()
  step4_missing <- character()
  if (!is_unreported_token(verification$status)) {
    step4_present <- c(step4_present, "implementationVerification")
  } else {
    step4_missing <- c(step4_missing, "implementationVerification")
  }
  if (length(collect_text_values(verification$solver, verification$runtime, platform$runtime, platform$runtimeVersion)) > 0) {
    step4_present <- c(step4_present, "solverAndRuntime")
  } else {
    step4_missing <- c(step4_missing, "solverAndRuntime")
  }
  if (!is_unreported_token(platform$status)) {
    step4_present <- c(step4_present, "platformQualification")
  } else {
    step4_missing <- c(step4_missing, "platformQualification")
  }

  step6_present <- character()
  step6_missing <- character()
  if (!is_unreported_token(source$type)) {
    step6_present <- c(step6_present, "profileSource")
  } else {
    step6_missing <- c(step6_missing, "profileSource")
  }
  if (length(collect_text_values(source$path, source$sourceToolHint, record$file_path)) > 0) {
    step6_present <- c(step6_present, "traceability")
  } else {
    step6_missing <- c(step6_missing, "traceability")
  }
  if (parameter_table_rows > 0) {
    step6_present <- c(step6_present, "parameterTables")
  } else {
    step6_missing <- c(step6_missing, "parameterTables")
  }

  implementation_present <- character()
  implementation_missing <- character()
  if (length(collect_text_values(platform$softwareName, platform$softwareVersion)) > 0) {
    implementation_present <- c(implementation_present, "softwareIdentity")
  } else {
    implementation_missing <- c(implementation_missing, "softwareIdentity")
  }
  if (length(collect_text_values(platform$runtime, platform$runtimeVersion, verification$solver)) > 0) {
    implementation_present <- c(implementation_present, "runtimeAndSolver")
  } else {
    implementation_missing <- c(implementation_missing, "runtimeAndSolver")
  }
  if (safe_num(platform_qualification_evidence$returnedRows, 0) > 0 ||
      length(normalize_text_values(platform$qualificationBasis)) > 0) {
    implementation_present <- c(implementation_present, "softwareVerificationQualification")
  } else {
    implementation_missing <- c(implementation_missing, "softwareVerificationQualification")
  }

  parameter_section_present <- character()
  parameter_section_missing <- character()
  if (parameter_table_rows > 0) {
    parameter_section_present <- c(parameter_section_present, "parameterRows")
  } else {
    parameter_section_missing <- c(parameter_section_missing, "parameterRows")
  }
  if (parameter_table_field_present(parameter_table, c("unit"))) {
    parameter_section_present <- c(parameter_section_present, "units")
  } else {
    parameter_section_missing <- c(parameter_section_missing, "units")
  }
  if (parameter_table_field_present(parameter_table, c("source", "sourceType", "sourceCitation", "sourceTable"))) {
    parameter_section_present <- c(parameter_section_present, "sources")
  } else {
    parameter_section_missing <- c(parameter_section_missing, "sources")
  }
  if (parameter_table_field_present(parameter_table, c("mean", "sd", "standardDeviation", "distribution"))) {
    parameter_section_present <- c(parameter_section_present, "distributions")
  } else {
    parameter_section_missing <- c(parameter_section_missing, "distributions")
  }
  if (parameter_table_field_present(parameter_table, c("experimentalConditions", "testConditions", "rationale", "motivation"))) {
    parameter_section_present <- c(parameter_section_present, "experimentalConditions")
  } else {
    parameter_section_missing <- c(parameter_section_missing, "experimentalConditions")
  }

  reporting_sections <- list(
    nameOfModel = coverage_item(
      "table3.1.A",
      "A. Name of model",
      status = if (length(collect_text_values(metadata$name, record$file_path)) > 0) "declared" else "missing",
      mapped_from = c("report.model.name", "report.model.filePath"),
      missing_elements = if (length(collect_text_values(metadata$name, record$file_path)) > 0) character() else "model identity",
      summary = "Model identity reported in the exported dossier metadata.",
      oecd_reference = "Table 3.1 A"
    ),
    developerAndContactDetails = coverage_item(
      "table3.1.B",
      "B. Model developer and contact details",
      status = oecd_dimension_status(developer_present, developer_missing),
      mapped_from = c("report.model.createdBy", "profile.modelDeveloper", "profile.developer"),
      missing_elements = developer_missing,
      summary = "Developer and contact details are mapped from report metadata or explicit profile developer fields when available.",
      oecd_reference = "Table 3.1 B"
    ),
    summary = coverage_item(
      "table3.1.C",
      "C. Summary of model characterisation, development, validation, and regulatory applicability",
      status = oecd_dimension_status(summary_present, summary_missing),
      mapped_from = c("profile.contextOfUse.summary", "profile.applicabilityDomain.summary", "validation.summary", "validation.assessment.decision"),
      missing_elements = summary_missing,
      summary = "High-level report summary is derived from existing profile summaries and validation context.",
      oecd_reference = "Table 3.1 C"
    ),
    scopeAndPurpose = coverage_item(
      "table3.1.D.step1",
      "D Step 1. Scope and purpose of the model (problem formulation)",
      status = checklist$contextOfUse$status %||% oecd_dimension_status(step1_present, step1_missing),
      mapped_from = c("profile.contextOfUse", "oecdChecklist.contextOfUse"),
      missing_elements = step1_missing,
      summary = "Problem formulation coverage is derived from the declared context-of-use block.",
      oecd_reference = "Table 3.1 D Step 1"
    ),
    modelConceptualisation = coverage_item(
      "table3.1.D.step2",
      "D Step 2. Model conceptualisation (model structure, mathematical representation)",
      status = oecd_dimension_status(step2_present, step2_missing),
      mapped_from = c("profile.assumptions", "profile.conceptualModel", "profile.mathematicalRepresentation", "profile.equations"),
      missing_elements = step2_missing,
      summary = "Conceptualisation coverage is only marked when assumptions, conceptual structure, or equation metadata are explicitly declared.",
      oecd_reference = "Table 3.1 D Step 2"
    ),
    modelParameterisation = coverage_item(
      "table3.1.D.step3",
      "D Step 3. Model parameterisation (parameter estimation and analysis)",
      status = aggregate_coverage_status(c(
        checklist$parameterizationAndProvenance$status,
        oecd_dimension_status(step3_present, step3_missing)
      )),
      mapped_from = c("profile.parameterProvenance", "parameterTable", "oecdChecklist.parameterizationAndProvenance"),
      missing_elements = step3_missing,
      summary = "Parameterisation coverage is derived from parameter provenance metadata and the exported parameter table.",
      oecd_reference = "Table 3.1 D Step 3"
    ),
    computerImplementation = coverage_item(
      "table3.1.D.step4",
      "D Step 4. Computer implementation (solving the equations)",
      status = aggregate_coverage_status(c(
        checklist$implementationVerification$status,
        checklist$softwarePlatformQualification$status,
        oecd_dimension_status(step4_present, step4_missing)
      )),
      mapped_from = c("profile.implementationVerification", "profile.platformQualification", "verificationEvidence", "platformQualificationEvidence"),
      missing_elements = step4_missing,
      summary = "Computer-implementation coverage is derived from solver/runtime metadata, implementation verification, and platform qualification evidence.",
      oecd_reference = "Table 3.1 D Step 4"
    ),
    modelPerformance = coverage_item(
      "table3.1.D.step5",
      "D Step 5. Model Performance",
      status = checklist$modelPerformanceAndPredictivity$status %||% "missing",
      mapped_from = c("profile.modelPerformance", "performanceEvidence", "oecdChecklist.modelPerformanceAndPredictivity"),
      missing_elements = checklist$modelPerformanceAndPredictivity$missingFields %||% list(),
      summary = "Performance coverage is derived from declared fit/predictivity metadata and bundled performance evidence.",
      oecd_reference = "Table 3.1 D Step 5"
    ),
    modelDocumentation = coverage_item(
      "table3.1.D.step6",
      "D Step 6. Model Documentation",
      status = aggregate_coverage_status(c(
        checklist$reportingAndTraceability$status,
        oecd_dimension_status(step6_present, step6_missing)
      )),
      mapped_from = c("profile.profileSource", "parameterTable", "oecdChecklist.reportingAndTraceability"),
      missing_elements = step6_missing,
      summary = "Documentation coverage tracks source traceability, profile origin, and parameter-table inclusion.",
      oecd_reference = "Table 3.1 D Step 6"
    ),
    identificationOfUncertainties = coverage_item(
      "table3.1.E",
      "E. Identification of uncertainties",
      status = checklist$uncertaintyAndSensitivity$status %||% "missing",
      mapped_from = c("profile.uncertainty", "uncertaintyEvidence", "oecdChecklist.uncertaintyAndSensitivity"),
      missing_elements = checklist$uncertaintyAndSensitivity$missingFields %||% list(),
      summary = "Uncertainty coverage is derived from declared uncertainty metadata and bundled evidence rows.",
      oecd_reference = "Table 3.1 E"
    ),
    modelImplementationDetails = coverage_item(
      "table3.1.F",
      "F. Model implementation details",
      status = oecd_dimension_status(implementation_present, implementation_missing),
      mapped_from = c("profile.platformQualification", "profile.implementationVerification", "platformQualificationEvidence", "verificationEvidence"),
      missing_elements = implementation_missing,
      summary = "Implementation-detail coverage tracks software identity, runtime/solver metadata, and software/platform qualification basis.",
      oecd_reference = "Table 3.1 F"
    ),
    peerEngagement = coverage_item(
      "table3.1.G",
      "G. Peer engagement (input/review)",
      status = checklist$peerReviewAndPriorUse$status %||% "missing",
      mapped_from = c("profile.peerReview", "oecdChecklist.peerReviewAndPriorUse"),
      missing_elements = checklist$peerReviewAndPriorUse$missingFields %||% list(),
      summary = "Peer-engagement coverage is derived from structured peer-review and prior-use metadata only.",
      oecd_reference = "Table 3.1 G"
    ),
    parameterTables = coverage_item(
      "table3.1.H",
      "H. Parameter tables",
      status = oecd_dimension_status(parameter_section_present, parameter_section_missing),
      mapped_from = c("parameterTable", "profile.parameterProvenance"),
      missing_elements = parameter_section_missing,
      summary = "Parameter-table coverage is derived from the exported table contents and provenance metadata.",
      oecd_reference = "Table 3.1 H"
    ),
    referencesAndBackgroundInformation = coverage_item(
      "table3.1.references",
      "References and background information",
      status = if (length(reference_values) > 0) "declared" else "missing",
      mapped_from = c("profile.references", "profile.publications", "profile.links"),
      missing_elements = if (length(reference_values) > 0) character() else "explicit publications or resource links",
      summary = "Reference coverage is only marked when explicit publications or external resource links are declared in the scientific profile.",
      oecd_reference = "Table 3.1 References"
    )
  )

  has_unit_check <- has_passed_verification_check(
    executable_verification,
    exact = "parameter-unit-consistency",
    patterns = c("unit-consistency", "unit")
  )
  has_mass_balance_check <- has_passed_verification_check(
    executable_verification,
    exact = "mass-balance",
    patterns = c("mass-balance")
  )
  has_flow_check <- has_passed_verification_check(
    executable_verification,
    patterns = c("flow-consistency", "cardiac")
  )
  has_volume_check <- has_passed_verification_check(
    executable_verification,
    patterns = c("volume-consistency")
  )
  has_solver_check <- has_passed_verification_check(
    executable_verification,
    exact = "solver-stability",
    patterns = c("solver")
  )
  has_integrity_check <- has_passed_verification_check(
    executable_verification,
    patterns = c("deterministic-integrity", "reproducibility", "repeatability")
  )

  uncertainty_rows <- uncertainty_evidence$rows %||% list()
  uncertainty_kinds <- tolower(vapply(uncertainty_rows, function(entry) safe_chr(entry$kind, ""), character(1)))
  uncertainty_methods <- tolower(vapply(uncertainty_rows, function(entry) safe_chr(entry$method, ""), character(1)))
  has_local_sensitivity <- any(grepl("local|one-at-a-time|one at a time|oat", uncertainty_methods)) ||
    any(grepl("local|sensitivity-analysis", uncertainty_kinds))
  has_global_sensitivity <- any(grepl("global|sobol|morris|variance", uncertainty_methods)) ||
    any(grepl("global", uncertainty_kinds))
  has_variability_propagation <- any(grepl("propagation", uncertainty_kinds)) ||
    any(grepl("propagation", uncertainty_methods))

  performance_rows <- performance_evidence$rows %||% list()
  performance_traceability <- performance_traceability_summary(performance, performance_rows)
  performance_has_acceptance <- isTRUE(performance_traceability$hasExplicitAcceptanceCriteria)

  regulatory_present <- character()
  regulatory_missing <- character()
  if (length(collect_text_values(context$scientificPurpose, context$decisionContext, context$regulatoryUse)) > 0) {
    regulatory_present <- c(regulatory_present, "envisagedApplication")
  } else {
    regulatory_missing <- c(regulatory_missing, "envisagedApplication")
  }
  if (length(collect_text_values(domain$qualificationLevel, validation$assessment$decision)) > 0) {
    regulatory_present <- c(regulatory_present, "confidenceForApplication")
  } else {
    regulatory_missing <- c(regulatory_missing, "confidenceForApplication")
  }
  if (length(collect_text_values(context$alternativeAssessmentOptions, validation$assessment$alternativeAssessmentOptions)) > 0) {
    regulatory_present <- c(regulatory_present, "alternativeAssessmentOptions")
  } else {
    regulatory_missing <- c(regulatory_missing, "alternativeAssessmentOptions")
  }

  documentation_status <- aggregate_coverage_status(vapply(
    reporting_sections[c(
      "summary",
      "scopeAndPurpose",
      "modelConceptualisation",
      "modelParameterisation",
      "computerImplementation",
      "modelPerformance",
      "modelDocumentation",
      "identificationOfUncertainties",
      "parameterTables"
    )],
    function(entry) safe_chr(entry$status, "missing"),
    character(1)
  ))

  software_present <- character()
  software_missing <- character()
  if (length(collect_text_values(record$file_path, source$type)) > 0) {
    software_present <- c(software_present, "q4-modelCodeAvailable")
  } else {
    software_missing <- c(software_missing, "q4-modelCodeAvailable")
  }
  if (length(equation_values) > 0) {
    software_present <- c(software_present, "q4-mathematicalRepresentation")
  } else {
    software_missing <- c(software_missing, "q4-mathematicalRepresentation")
  }
  if (has_integrity_check || isTRUE(validation$ok)) {
    software_present <- c(software_present, "q5-codeIntegrityChecks")
  } else {
    software_missing <- c(software_missing, "q5-codeIntegrityChecks")
  }
  if (has_unit_check) {
    software_present <- c(software_present, "q6-unitConsistency")
  } else {
    software_missing <- c(software_missing, "q6-unitConsistency")
  }
  if (has_mass_balance_check) {
    software_present <- c(software_present, "q7-massBalance")
  } else {
    software_missing <- c(software_missing, "q7-massBalance")
  }
  if (has_flow_check) {
    software_present <- c(software_present, "q8-flowBalance")
  } else {
    software_missing <- c(software_missing, "q8-flowBalance")
  }
  if (has_volume_check) {
    software_present <- c(software_present, "q9-volumeBalance")
  } else {
    software_missing <- c(software_missing, "q9-volumeBalance")
  }
  if (length(collect_text_values(verification$solver, platform$qualificationBasis)) > 0) {
    software_present <- c(software_present, "q10-solverIdentity")
  } else {
    software_missing <- c(software_missing, "q10-solverIdentity")
  }
  if (has_solver_check) {
    software_present <- c(software_present, "q11-solverConvergence")
  } else {
    software_missing <- c(software_missing, "q11-solverConvergence")
  }
  if (safe_num(platform_qualification_evidence$returnedRows, 0) > 0 ||
      length(normalize_text_values(platform$qualificationBasis)) > 0) {
    software_present <- c(software_present, "q12-platformQualification")
  } else {
    software_missing <- c(software_missing, "q12-platformQualification")
  }

  biological_present <- character()
  biological_missing <- character()
  if (!is_unreported_token(domain$type)) {
    biological_present <- c(biological_present, "biologicalContext")
  } else {
    biological_missing <- c(biological_missing, "biologicalContext")
  }
  if (length(assumption_values) > 0) {
    biological_present <- c(biological_present, "statedAssumptions")
  } else {
    biological_missing <- c(biological_missing, "statedAssumptions")
  }
  if (!is_unreported_token(provenance$status) || parameter_table_rows > 0) {
    biological_present <- c(biological_present, "parameterJustification")
  } else {
    biological_missing <- c(biological_missing, "parameterJustification")
  }

  input_reliability_present <- character()
  input_reliability_missing <- character()
  if (!is_unreported_token(provenance$status)) {
    input_reliability_present <- c(input_reliability_present, "parameterRelevanceReliability")
  } else {
    input_reliability_missing <- c(input_reliability_missing, "parameterRelevanceReliability")
  }
  if (parameter_table_field_present(parameter_table, c("source", "sourceType", "sourceCitation", "sourceTable"))) {
    input_reliability_present <- c(input_reliability_present, "parameterSources")
  } else {
    input_reliability_missing <- c(input_reliability_missing, "parameterSources")
  }
  if (parameter_table_field_present(parameter_table, c("mean", "sd", "standardDeviation", "distribution"))) {
    input_reliability_present <- c(input_reliability_present, "parameterDistributions")
  } else {
    input_reliability_missing <- c(input_reliability_missing, "parameterDistributions")
  }
  if (parameter_table_field_present(parameter_table, c("experimentalConditions", "testConditions", "rationale", "motivation"))) {
    input_reliability_present <- c(input_reliability_present, "experimentalConditions")
  } else {
    input_reliability_missing <- c(input_reliability_missing, "experimentalConditions")
  }

  uncertainty_present <- character()
  uncertainty_missing <- character()
  if (safe_num(uncertainty_evidence$returnedRows, 0) > 0) {
    uncertainty_present <- c(uncertainty_present, "q17-uncertaintyImpact")
  } else {
    uncertainty_missing <- c(uncertainty_missing, "q17-uncertaintyImpact")
  }
  if (has_local_sensitivity) {
    uncertainty_present <- c(uncertainty_present, "q17-localSensitivity")
  } else {
    uncertainty_missing <- c(uncertainty_missing, "q17-localSensitivity")
  }
  if (has_global_sensitivity) {
    uncertainty_present <- c(uncertainty_present, "q17-globalSensitivity")
  } else {
    uncertainty_missing <- c(uncertainty_missing, "q17-globalSensitivity")
  }
  if (has_variability_propagation) {
    uncertainty_present <- c(uncertainty_present, "q18-influentialParameterConfidence")
  } else {
    uncertainty_missing <- c(uncertainty_missing, "q18-influentialParameterConfidence")
  }

  predictivity_present <- character()
  predictivity_missing <- character()
  if (!is_missing_evidence_token(performance$status) || safe_num(performance_evidence$returnedRows, 0) > 0) {
    predictivity_present <- c(predictivity_present, "performanceMetadata")
  } else {
    predictivity_missing <- c(predictivity_missing, "performanceMetadata")
  }
  if (isTRUE(performance_evidence$supportsObservedVsPredictedEvidence) ||
      isTRUE(performance_evidence$supportsPredictiveDatasetEvidence) ||
      isTRUE(performance_evidence$supportsExternalQualificationEvidence) ||
      performance_traceability$goodnessOfFitDatasetRecordCount > 0 ||
      performance_traceability$predictiveDatasetRecordCount > 0 ||
      performance_traceability$evaluationDatasetRecordCount > 0) {
    predictivity_present <- c(predictivity_present, "predictiveDataset")
  } else {
    predictivity_missing <- c(predictivity_missing, "predictiveDataset")
  }
  if (performance_has_acceptance) {
    predictivity_present <- c(predictivity_present, "acceptanceCriteria")
  } else {
    predictivity_missing <- c(predictivity_missing, "acceptanceCriteria")
  }

  evaluation_sections <- list(
    regulatoryPurpose = coverage_item(
      "table3.2.A.1",
      "A.1 Regulatory Purpose",
      status = oecd_dimension_status(regulatory_present, regulatory_missing),
      mapped_from = c("profile.contextOfUse", "profile.applicabilityDomain.qualificationLevel", "validation.assessment.decision"),
      missing_elements = regulatory_missing,
      summary = "Coverage is descriptive only and does not compare PBPK MCP against alternative assessment options unless those are declared explicitly.",
      oecd_reference = "Table 3.2 A.1",
      question_numbers = c(1L, 2L)
    ),
    documentation = coverage_item(
      "table3.2.A.2",
      "A.2 Documentation",
      status = documentation_status,
      mapped_from = c(
        "profile.contextOfUse",
        "profile.applicabilityDomain",
        "profile.modelPerformance",
        "profile.parameterProvenance",
        "profile.uncertainty",
        "profile.implementationVerification",
        "profile.platformQualification",
        "profile.profileSource",
        "parameterTable"
      ),
      missing_elements = c(
        if (identical(reporting_sections$modelConceptualisation$status, "missing")) "conceptual model or equation metadata" else character(),
        if (identical(reporting_sections$referencesAndBackgroundInformation$status, "missing")) "explicit publications or resource links" else character()
      ),
      summary = "Documentation coverage aggregates the reporting-template sections rather than creating a second independent score.",
      oecd_reference = "Table 3.2 A.2",
      question_numbers = 3L
    ),
    softwareImplementationAndVerification = coverage_item(
      "table3.2.A.3",
      "A.3 Software Implementation and Verification",
      status = oecd_dimension_status(software_present, software_missing),
      mapped_from = c("validation", "verificationEvidence", "executableVerification", "platformQualificationEvidence", "profile.implementationVerification", "profile.platformQualification"),
      missing_elements = software_missing,
      summary = "Coverage is based on available executable checks and declared solver/platform metadata. Missing check categories remain explicit.",
      oecd_reference = "Table 3.2 A.3",
      question_numbers = 4:12
    ),
    peerEngagement = coverage_item(
      "table3.2.A.4",
      "A.4 Peer engagement (input/review)",
      status = checklist$peerReviewAndPriorUse$status %||% "missing",
      mapped_from = c("profile.peerReview", "oecdChecklist.peerReviewAndPriorUse"),
      missing_elements = checklist$peerReviewAndPriorUse$missingFields %||% list(),
      summary = "Coverage is limited to structured peer-review and prior-use metadata declared in the PBPK profile.",
      oecd_reference = "Table 3.2 A.4",
      question_numbers = 13L
    ),
    biologicalBasis = coverage_item(
      "table3.2.B.1",
      "B.1 Biological Basis (Model Structure and Parameters)",
      status = oecd_dimension_status(biological_present, biological_missing),
      mapped_from = c("profile.applicabilityDomain", "profile.assumptions", "profile.parameterProvenance", "parameterTable"),
      missing_elements = biological_missing,
      summary = "Biological-basis coverage is only marked when the profile explicitly provides domain, assumptions, or parameter-justification metadata.",
      oecd_reference = "Table 3.2 B.1",
      question_numbers = 14L
    ),
    theoreticalBasisOfModelEquations = coverage_item(
      "table3.2.B.2",
      "B.2 Theoretical Basis of Model Equations",
      status = if (length(equation_values) > 0) "declared" else "missing",
      mapped_from = c("profile.mathematicalRepresentation", "profile.theoreticalBasis", "profile.equations"),
      missing_elements = if (length(equation_values) > 0) character() else "explicit equation or theoretical-basis metadata",
      summary = "Equation-level theoretical basis is only marked when explicit mathematical-representation metadata is declared.",
      oecd_reference = "Table 3.2 B.2",
      question_numbers = 15L
    ),
    reliabilityOfInputParameters = coverage_item(
      "table3.2.B.3",
      "B.3 Reliability of input parameters",
      status = oecd_dimension_status(input_reliability_present, input_reliability_missing),
      mapped_from = c("profile.parameterProvenance", "parameterTable", "profile.uncertainty"),
      missing_elements = input_reliability_missing,
      summary = "Input-parameter reliability coverage tracks provenance, distributions, and experimental-condition metadata when present.",
      oecd_reference = "Table 3.2 B.3",
      question_numbers = 16L
    ),
    uncertaintyAndSensitivityAnalysis = coverage_item(
      "table3.2.B.4",
      "B.4 Uncertainty and Sensitivity Analysis",
      status = oecd_dimension_status(uncertainty_present, uncertainty_missing),
      mapped_from = c("profile.uncertainty", "uncertaintyEvidence", "ngraObjects.uncertaintySummary"),
      missing_elements = uncertainty_missing,
      summary = "The coverage map distinguishes local sensitivity, global sensitivity, and variability propagation when those are explicitly declared.",
      oecd_reference = "Table 3.2 B.4",
      question_numbers = 17:18
    ),
    goodnessOfFitAndPredictivity = coverage_item(
      "table3.2.B.5",
      "B.5 Goodness-of-Fit and Predictivity",
      status = oecd_dimension_status(predictivity_present, predictivity_missing),
      mapped_from = c("profile.modelPerformance", "performanceEvidence", "oecdChecklist.modelPerformanceAndPredictivity"),
      missing_elements = predictivity_missing,
      summary = "Runtime or internal evidence remains visible here but does not satisfy external predictive-dataset coverage by itself.",
      oecd_reference = "Table 3.2 B.5",
      question_numbers = 19L
    )
  )

  list(
    coverageVersion = "pbpk-oecd-coverage.v1",
    sourceGuidance = "OECD PBK Guidance Tables 3.1 and 3.2",
    affectsChecklistScore = FALSE,
    affectsQualificationState = FALSE,
    summary = "Descriptive coverage map only; this block does not alter oecdChecklistScore or qualificationState.",
    missingEvidence = as.list(unique(normalize_text_values(missing_evidence))),
    reportingTemplate = list(
      table = "Table 3.1",
      sections = reporting_sections
    ),
    evaluationChecklist = list(
      table = "Table 3.2",
      sections = evaluation_sections
    )
  )
}

profile_missing_evidence <- function(profile, capabilities = list()) {
  missing <- character()
  append_missing <- function(message) {
    if (!message %in% missing) {
      missing <<- c(missing, message)
    }
  }

  if (!isTRUE(capabilities$scientificProfile) ||
      identical(safe_chr(profile$profileSource$type), "bridge-default")) {
    append_missing("Model-specific scientific profile")
  }

  context <- profile$contextOfUse %||% list()
  if (is_unreported_token(context$status) && is_unreported_token(context$regulatoryUse)) {
    append_missing("Declared context of use")
  }

  domain <- profile$applicabilityDomain %||% list()
  if (is_unreported_token(domain$type)) {
    append_missing("Declared applicability domain")
  }
  if (is_unreported_token(domain$qualificationLevel)) {
    append_missing("Qualification level for the declared domain")
  }

  performance <- profile$modelPerformance %||% list()
  performance_traceability <- performance_traceability_summary(performance)
  if (is_missing_evidence_token(performance$status)) {
    append_missing("Model performance or predictivity evidence")
  }
  if (performance_metric_count(performance) == 0) {
    append_missing("Formal goodness-of-fit metrics and acceptance criteria")
  }
  if (performance_dataset_count(performance) == 0 && performance_evidence_count(performance) == 0) {
    append_missing("Observed-versus-predicted or predictive evaluation datasets")
  }
  if (performance_traceability$acceptanceCriterionCount == 0) {
    append_missing("Explicit performance acceptance criteria")
  }
  if (performance_dataset_count(performance) > 0 &&
      (
        performance_traceability$goodnessOfFitDatasetRecordCount +
          performance_traceability$predictiveDatasetRecordCount +
          performance_traceability$evaluationDatasetRecordCount
      ) == 0) {
    append_missing("Structured performance dataset records")
  }
  for (item in normalize_text_values(performance$missingEvidence)) {
    append_missing(item)
  }

  provenance <- profile$parameterProvenance %||% list()
  if (is_unreported_token(provenance$status)) {
    append_missing("Parameter provenance table")
  }
  if (length(normalize_text_values(provenance$sourceTable %||% provenance$source)) == 0) {
    append_missing("Parameter provenance source table")
  }
  for (item in normalize_text_values(provenance$missingEvidence)) {
    append_missing(item)
  }

  uncertainty <- profile$uncertainty %||% list()
  if (is_unreported_token(uncertainty$status)) {
    append_missing("Uncertainty and sensitivity characterization")
  }
  if (uncertainty_evidence_count(uncertainty) == 0 &&
      !is_unreported_token(uncertainty$status)) {
    append_missing("Structured uncertainty or sensitivity evidence rows")
  }

  verification <- profile$implementationVerification %||% list()
  if (is_unreported_token(verification$status) ||
      length(verification$verifiedChecks %||% list()) == 0) {
    append_missing("Implementation verification evidence")
  }
  if (implementation_verification_count(verification) == 0 &&
      !is_unreported_token(verification$status)) {
    append_missing("Structured implementation verification evidence rows")
  }
  for (check in normalize_text_values(verification$missingChecks)) {
    append_missing(check)
  }

  platform <- profile$platformQualification %||% list()
  if (is_unreported_token(platform$status)) {
    append_missing("Software/platform qualification record")
  }
  if (length(normalize_text_values(platform$qualificationBasis)) == 0) {
    append_missing("Software/platform qualification basis")
  }
  if (platform_qualification_count(platform) == 0 &&
      !is_unreported_token(platform$status)) {
    append_missing("Structured software/platform qualification evidence rows")
  }
  for (item in normalize_text_values(platform$missingEvidence)) {
    append_missing(item)
  }

  review <- profile$peerReview %||% list()
  if (is_unreported_token(review$status)) {
    append_missing("Peer review or prior use record")
  } else {
    review_coverage <- peer_review_coverage_summary(review)
    if (review_coverage$reviewRecordCount == 0) {
      append_missing("Structured peer-review records")
    }
    if (review_coverage$priorUseCount == 0) {
      append_missing("Prior regulatory or external use traceability")
    }
    if (review_coverage$revisionEntryCount == 0 &&
        !isTRUE(review_coverage$hasRevisionStatus)) {
      append_missing("Revision or change history")
    }
  }
  for (item in normalize_text_values(review$missingEvidence)) {
    append_missing(item)
  }

  unique(missing)
}

profile_oecd_readiness <- function(profile, capabilities = list()) {
  qualification <- normalize_context_token(profile$applicabilityDomain$qualificationLevel)
  profile_source <- safe_chr(profile$profileSource$type)

  if (!isTRUE(capabilities$scientificProfile) || identical(profile_source, "bridge-default")) {
    return(list(level = "runtime-only", confidence = "low"))
  }

  if (qualification %in% c("demo-only", "illustrative-example", "integration-example")) {
    return(list(level = "illustrative-only", confidence = "low"))
  }

  if (qualification %in% c(
    "research-use",
    "research-only",
    "runtime-guardrails",
    "runtime-load-verified"
  )) {
    return(list(level = "research-use", confidence = "medium"))
  }

  if (qualification %in% c(
    "fit-for-purpose",
    "qualified",
    "externally-qualified",
    "regulatory-use",
    "regulatory-qualified"
  )) {
    return(list(level = "fit-for-purpose", confidence = "high"))
  }

  list(level = "structured-but-unqualified", confidence = "low")
}

derive_qualification_state <- function(profile, capabilities = list(), assessment = list()) {
  qualification <- normalize_context_token(profile$applicabilityDomain$qualificationLevel)
  profile_source <- safe_chr(profile$profileSource$type)
  scientific_profile <- isTRUE(capabilities$scientificProfile) &&
    !identical(profile_source, "bridge-default")
  checklist <- assessment$oecdChecklist %||% profile_oecd_checklist(profile, capabilities)
  checklist_score <- safe_num(
    assessment$oecdChecklistScore,
    profile_oecd_checklist_score(checklist)
  )
  missing_evidence <- normalize_text_values(
    assessment$missingEvidence %||% profile_missing_evidence(profile, capabilities)
  )
  missing_count <- length(missing_evidence)
  within_declared_context <- !identical(
    safe_chr(assessment$decision),
    "outside-declared-profile"
  )

  evidence_status <- if (missing_count == 0 && checklist_score >= 1) {
    "complete"
  } else if (missing_count <= 2 && checklist_score >= 0.75) {
    "substantial"
  } else if (checklist_score >= 0.5) {
    "partial"
  } else {
    "minimal"
  }

  if (!scientific_profile) {
    state <- "exploratory"
    label <- "Exploratory"
    summary <- paste(
      "Runtime support is available, but no model-specific scientific profile is declared."
    )
    risk_ready <- FALSE
  } else if (!is.null(qualification) && qualification %in% c(
    "demo-only",
    "illustrative-example",
    "integration-example"
  )) {
    state <- "illustrative-example"
    label <- "Illustrative example"
    summary <- paste(
      "The model is positioned as an example or integration fixture rather than a qualified dossier."
    )
    risk_ready <- FALSE
  } else if (!is.null(qualification) && qualification %in% c(
    "research-use",
    "research-only",
    "runtime-guardrails",
    "runtime-load-verified"
  )) {
    state <- "research-use"
    label <- "Research use"
    summary <- paste(
      "The model declares a research-oriented context of use and should not be treated as regulatory-ready."
    )
    risk_ready <- FALSE
  } else if (!is.null(qualification) && qualification %in% c(
    "fit-for-purpose",
    "qualified",
    "externally-qualified",
    "regulatory-use",
    "regulatory-qualified"
  )) {
    if (within_declared_context && checklist_score >= 0.85 && missing_count <= 1) {
      state <- "qualified-within-context"
      label <- "Qualified within context"
      summary <- paste(
        "The model declares a qualification-oriented context and the attached metadata are",
        "substantially complete for that declared context."
      )
      risk_ready <- TRUE
    } else {
      state <- "regulatory-candidate"
      label <- "Regulatory candidate"
      summary <- paste(
        "The model targets qualification-oriented use, but metadata completeness or request alignment",
        "remain insufficient for a stronger claim."
      )
      risk_ready <- FALSE
    }
  } else if (checklist_score >= 0.75 && scientific_profile) {
    state <- "regulatory-candidate"
    label <- "Regulatory candidate"
    summary <- paste(
      "The model profile is structured enough to mature toward qualification, but the declared",
      "qualification state remains incomplete."
    )
    risk_ready <- FALSE
  } else {
    state <- "research-use"
    label <- "Research use"
    summary <- paste(
      "The model has a scientific profile, but its current declared metadata do not support stronger",
      "qualification claims."
    )
    risk_ready <- FALSE
  }

  list(
    state = state,
    label = label,
    summary = summary,
    qualificationLevel = safe_chr(profile$applicabilityDomain$qualificationLevel, "unreported"),
    profileSource = safe_chr(profile$profileSource$type, "unreported"),
    withinDeclaredContext = within_declared_context,
    scientificProfile = scientific_profile,
    riskAssessmentReady = risk_ready,
    checklistScore = checklist_score,
    missingEvidenceCount = missing_count,
    evidenceStatus = evidence_status
  )
}

profile_assessment_warnings <- function(profile, capabilities = list()) {
  warnings <- list()
  qualification_token <- normalize_context_token(profile$applicabilityDomain$qualificationLevel)

  if (!isTRUE(capabilities$scientificProfile) ||
      identical(safe_chr(profile$profileSource$type), "bridge-default")) {
    warnings[[length(warnings) + 1]] <- list(
      code = "scientific_profile_missing",
      message = paste(
        "This model is runtime-supported, but it does not declare a model-specific",
        "scientific profile with OECD-style context-of-use metadata."
      ),
      field = "profile",
      severity = "warning"
    )
  }

  if (is_missing_evidence_token(profile$modelPerformance$status)) {
    warnings[[length(warnings) + 1]] <- list(
      code = "model_performance_metadata_missing",
      message = "Model-performance or predictivity metadata are not declared for this model.",
      field = "profile.modelPerformance",
      severity = "warning"
    )
  } else if (performance_metric_count(profile$modelPerformance %||% list()) == 0 ||
             (performance_dataset_count(profile$modelPerformance %||% list()) == 0 &&
              performance_evidence_count(profile$modelPerformance %||% list()) == 0) ||
             performance_traceability_summary(profile$modelPerformance %||% list())$acceptanceCriterionCount == 0 ||
             is_limited_evidence_token(profile$modelPerformance$status) ||
             is_limited_evidence_token(
               exact_list_field(profile$modelPerformance %||% list(), "predictiveChecks")$status
             )) {
    warnings[[length(warnings) + 1]] <- list(
      code = "model_performance_evidence_limited",
      message = paste(
        "Model-performance metadata are present, but structured fit, predictive-dataset,",
        "or acceptance-criterion evidence remains limited for qualification-focused use."
      ),
      field = "profile.modelPerformance",
      severity = "warning"
    )
  }

  if (is_unreported_token(profile$parameterProvenance$status)) {
    warnings[[length(warnings) + 1]] <- list(
      code = "parameter_provenance_missing",
      message = "Parameter provenance metadata are not declared for this model.",
      field = "profile.parameterProvenance",
      severity = "warning"
    )
  }

  if (is_unreported_token(profile$uncertainty$status)) {
    warnings[[length(warnings) + 1]] <- list(
      code = "uncertainty_metadata_missing",
      message = "Uncertainty and sensitivity metadata are not declared for this model.",
      field = "profile.uncertainty",
      severity = "warning"
    )
  }

  if (is_unreported_token(profile$platformQualification$status)) {
    warnings[[length(warnings) + 1]] <- list(
      code = "platform_qualification_metadata_missing",
      message = "Software/platform qualification metadata are not declared for this model.",
      field = "profile.platformQualification",
      severity = "warning"
    )
  } else if (length(normalize_text_values(profile$platformQualification$qualificationBasis)) == 0 ||
             platform_qualification_count(profile$platformQualification %||% list()) == 0) {
    warnings[[length(warnings) + 1]] <- list(
      code = "platform_qualification_evidence_limited",
      message = paste(
        "Software/platform metadata are present, but the qualification basis or structured",
        "supporting evidence remains limited."
      ),
      field = "profile.platformQualification",
      severity = "warning"
    )
  }

  if (is_unreported_token(profile$peerReview$status)) {
    warnings[[length(warnings) + 1]] <- list(
      code = "peer_review_metadata_missing",
      message = "Peer-review or prior-use metadata are not declared for this model.",
      field = "profile.peerReview",
      severity = "warning"
    )
  } else {
    review_coverage <- peer_review_coverage_summary(profile$peerReview %||% list())
    if (review_coverage$reviewRecordCount == 0 ||
        review_coverage$priorUseCount == 0 ||
        (review_coverage$revisionEntryCount == 0 &&
         !isTRUE(review_coverage$hasRevisionStatus))) {
      warnings[[length(warnings) + 1]] <- list(
        code = "peer_review_traceability_limited",
        message = paste(
          "Peer-review metadata are present, but structured review records, prior-use traceability,",
          "or revision-history details remain limited."
        ),
        field = "profile.peerReview",
        severity = "warning"
      )
    }
  }

  if (!is.null(qualification_token) && qualification_token %in% c(
    "demo-only",
    "illustrative-example",
    "integration-example"
  )) {
    warnings[[length(warnings) + 1]] <- list(
      code = "qualification_limited",
      message = paste(
        "This model is qualified only as an example or integration fixture,",
        "not as an externally qualified scientific dossier."
      ),
      field = "profile.applicabilityDomain.qualificationLevel",
      severity = "warning"
    )
  }

  warnings
}

with_profile_assessment <- function(validation, profile, capabilities = list()) {
  normalized <- normalize_validation_payload(validation)
  normalized$warnings <- merge_validation_issues(
    normalized$warnings,
    profile_assessment_warnings(profile, capabilities)
  )
  if (is.null(normalized$domain)) {
    normalized$domain <- profile$applicabilityDomain %||% capabilities$applicabilityDomain %||% NULL
  }

  readiness <- profile_oecd_readiness(profile, capabilities)
  checklist <- profile_oecd_checklist(profile, capabilities)
  checklist_score <- profile_oecd_checklist_score(checklist)
  missing_evidence <- profile_missing_evidence(profile, capabilities)
  blocking_issues <- format_validation_messages(list(
    errors = normalized$errors,
    warnings = list()
  ))

  base_assessment <- list(
    decision = if (length(normalized$errors) > 0) {
      "outside-declared-profile"
    } else if (identical(readiness$level, "runtime-only")) {
      "runtime-compatible-only"
    } else {
      "within-declared-profile"
    },
    oecdReadiness = readiness$level,
    confidence = readiness$confidence,
    qualificationLevel = safe_chr(profile$applicabilityDomain$qualificationLevel, "unreported"),
    declaredContextOfUse = safe_chr(profile$contextOfUse$regulatoryUse) %||%
      safe_chr(profile$contextOfUse$status, "unreported"),
    scientificProfile = isTRUE(capabilities$scientificProfile),
    profileSource = safe_chr(profile$profileSource$type, "unreported"),
    oecdChecklist = checklist,
    oecdChecklistScore = checklist_score,
    status = if (length(missing_evidence) == 0) {
      "metadata-complete"
    } else if (length(missing_evidence) <= 2) {
      "metadata-partial"
    } else {
      "metadata-incomplete"
    },
    missingEvidence = as.list(missing_evidence),
    blockingIssues = as.list(blocking_issues)
  )

  existing <- normalized$assessment %||% list()
  merged_assessment <- base_assessment
  for (name in names(existing)) {
    merged_assessment[[name]] <- existing[[name]]
  }
  merged_assessment$missingEvidence <- append_missing_evidence(
    base_assessment$missingEvidence,
    existing$missingEvidence
  )
  merged_assessment$blockingIssues <- append_missing_evidence(
    base_assessment$blockingIssues,
    existing$blockingIssues
  )
  merged_assessment$qualificationState <- derive_qualification_state(
    profile,
    capabilities,
    merged_assessment
  )

  normalized$assessment <- merged_assessment
  normalized
}

profile_request_mismatch_errors <- function(profile, request = list()) {
  requested_domain <- coerce_request_section(
    request$applicabilityDomain %||% request$applicability %||% request$domain
  )
  declared_domain <- profile$applicabilityDomain %||% list()
  errors <- list()

  add_error <- function(code, message, field = NULL) {
    errors[[length(errors) + 1]] <<- list(
      code = code,
      message = message,
      field = field,
      severity = "error"
    )
  }

  compare_values <- function(requested, declared, code, label, field) {
    requested_values <- normalize_text_values(requested)
    declared_values <- tolower(normalize_text_values(declared))
    if (length(requested_values) == 0 || length(declared_values) == 0) {
      return(invisible(NULL))
    }

    for (value in requested_values) {
      if (!tolower(value) %in% declared_values) {
        add_error(code, sprintf("%s '%s' is outside the declared applicability domain", label, value), field)
      }
    }
  }

  compare_values(
    requested_domain$species %||% request$species,
    declared_domain$species,
    "unsupported_species",
    "Species",
    "species"
  )
  compare_values(
    requested_domain$lifeStage %||% request$lifeStage %||% request$life_stage,
    declared_domain$lifeStage,
    "unsupported_life_stage",
    "Life stage",
    "lifeStage"
  )
  compare_values(
    requested_domain$routes %||% requested_domain$route %||% request$routes %||% request$route,
    declared_domain$routes,
    "unsupported_route",
    "Route",
    "route"
  )
  compare_values(
    requested_domain$compounds %||% requested_domain$compound %||% request$compound,
    declared_domain$compounds,
    "unsupported_compound",
    "Compound",
    "compound"
  )

  requested_context <- coerce_request_section(
    request$contextOfUse %||% request$context_of_use,
    scalar_key = "regulatoryUse"
  )
  requested_use <- normalize_context_token(
    requested_context$regulatoryUse %||% requested_context$intendedUse %||%
      request$regulatoryUse %||% request$intendedUse
  )
  declared_use <- normalize_context_token(profile$contextOfUse$regulatoryUse)
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

  errors
}

ospsuite_capabilities <- function(file_path) {
  list(
    backend = "ospsuite",
    deterministicSimulation = TRUE,
    populationSimulation = FALSE,
    parameterEditing = TRUE,
    validationHook = FALSE,
    scientificProfile = FALSE,
    supportedRuntimeFormats = list("pkml"),
    tags = list("ospsuite", "pkml"),
    applicabilityDomain = list(
      type = "unreported",
      summary = sprintf("No model-specific applicability guardrails are declared for '%s'", basename(file_path))
    )
  )
}

infer_ospsuite_origin <- function(file_path) {
  normalized <- tolower(basename(file_path %||% ""))
  if (grepl("mobi", normalized)) {
    return(list(code = "mobi", label = "MoBi"))
  }
  if (grepl("pk[-_ ]?sim", normalized)) {
    return(list(code = "pksim", label = "PK-Sim"))
  }
  list(code = "ospsuite", label = "OSPSuite")
}

ospsuite_profile_sidecar_candidates <- function(file_path) {
  stem <- tools::file_path_sans_ext(file_path)
  unique(c(
    paste0(stem, ".profile.json"),
    paste0(stem, ".pbpk.json"),
    paste0(file_path, ".profile.json")
  ))
}

performance_evidence_sidecar_candidates <- function(file_path) {
  stem <- tools::file_path_sans_ext(file_path)
  unique(c(
    paste0(stem, ".performance.json"),
    paste0(stem, ".performance-evidence.json"),
    paste0(file_path, ".performance.json"),
    paste0(file_path, ".performance-evidence.json")
  ))
}

uncertainty_evidence_sidecar_candidates <- function(file_path) {
  stem <- tools::file_path_sans_ext(file_path)
  unique(c(
    paste0(stem, ".uncertainty.json"),
    paste0(stem, ".uncertainty-evidence.json"),
    paste0(file_path, ".uncertainty.json"),
    paste0(file_path, ".uncertainty-evidence.json")
  ))
}

parameter_table_sidecar_candidates <- function(file_path) {
  stem <- tools::file_path_sans_ext(file_path)
  unique(c(
    paste0(stem, ".parameters.json"),
    paste0(stem, ".parameter-table.json"),
    paste0(file_path, ".parameters.json"),
    paste0(file_path, ".parameter-table.json")
  ))
}

read_json_file <- function(file_path) {
  tryCatch(
    fromJSON(file_path, simplifyVector = FALSE),
    error = function(exc) {
      stop(
        sprintf("Failed to parse JSON file '%s': %s", basename(file_path), exc$message),
        call. = FALSE
      )
    }
  )
}

extract_performance_evidence_rows_payload <- function(payload) {
  candidate <- payload$rows %||%
    payload$performanceEvidence$rows %||%
    payload$evidence

  if (is.list(candidate) && length(candidate) > 0 && is.null(names(candidate))) {
    return(candidate)
  }

  if (is.list(payload) && is.null(names(payload)) && length(payload) > 0) {
    return(payload)
  }

  NULL
}

extract_performance_evidence_metadata <- function(payload) {
  if (!is.list(payload) || is.null(names(payload))) {
    return(NULL)
  }

  metadata <- payload$metadata
  if (is.null(metadata) && is.list(payload$performanceEvidence)) {
    metadata <- payload$performanceEvidence$metadata
  }
  if (!is.list(metadata)) {
    return(NULL)
  }
  metadata
}

extract_uncertainty_evidence_rows_payload <- function(payload) {
  candidate <- payload$rows %||%
    payload$uncertaintyEvidence$rows %||%
    payload$evidence

  if (is.list(candidate) && length(candidate) > 0 && is.null(names(candidate))) {
    return(candidate)
  }

  if (is.list(payload) && is.null(names(payload)) && length(payload) > 0) {
    return(payload)
  }

  NULL
}

extract_uncertainty_evidence_metadata <- function(payload) {
  if (!is.list(payload) || is.null(names(payload))) {
    return(NULL)
  }

  metadata <- payload$metadata
  if (is.null(metadata) && is.list(payload$uncertaintyEvidence)) {
    metadata <- payload$uncertaintyEvidence$metadata
  }
  if (!is.list(metadata)) {
    return(NULL)
  }
  metadata
}

extract_parameter_table_rows_payload <- function(payload) {
  candidate <- payload$rows %||%
    payload$parameterTable$rows %||%
    payload$parameters

  if (is.list(candidate) && length(candidate) > 0 && is.null(names(candidate))) {
    return(candidate)
  }

  if (is.list(payload) && is.null(names(payload)) && length(payload) > 0) {
    return(payload)
  }

  NULL
}

extract_parameter_table_metadata <- function(payload) {
  if (!is.list(payload) || is.null(names(payload))) {
    return(NULL)
  }

  metadata <- payload$metadata
  if (is.null(metadata) && is.list(payload$parameterTable)) {
    metadata <- payload$parameterTable$metadata
  }
  if (!is.list(metadata)) {
    return(NULL)
  }
  metadata
}

performance_evidence_sidecar <- function(file_path) {
  issues <- list()
  for (candidate in performance_evidence_sidecar_candidates(file_path)) {
    if (!file.exists(candidate)) {
      next
    }

    payload <- tryCatch(
      fromJSON(candidate, simplifyVector = FALSE),
      error = function(exc) exc
    )
    if (inherits(payload, "error")) {
      issues[[length(issues) + 1]] <- list(
        code = "performance_sidecar_parse_error",
        message = sprintf(
          "Failed to parse performance evidence sidecar '%s': %s",
          basename(candidate),
          conditionMessage(payload)
        ),
        field = candidate,
        severity = "warning"
      )
      return(list(path = candidate, rows = list(), issues = issues))
    }

    rows <- extract_performance_evidence_rows_payload(payload)
    metadata <- extract_performance_evidence_metadata(payload)
    if (is.null(rows)) {
      issues[[length(issues) + 1]] <- list(
        code = "performance_sidecar_rows_missing",
        message = sprintf(
          "Performance evidence sidecar '%s' must provide 'rows', 'performanceEvidence.rows', or a top-level row array.",
          basename(candidate)
        ),
        field = candidate,
        severity = "warning"
      )
      return(list(path = candidate, rows = list(), metadata = metadata, issues = issues))
    }

    return(list(path = candidate, rows = rows, metadata = metadata, issues = issues))
  }

  list(path = NULL, rows = list(), metadata = NULL, issues = issues)
}

uncertainty_evidence_sidecar <- function(file_path) {
  issues <- list()
  for (candidate in uncertainty_evidence_sidecar_candidates(file_path)) {
    if (!file.exists(candidate)) {
      next
    }

    payload <- tryCatch(
      fromJSON(candidate, simplifyVector = FALSE),
      error = function(exc) exc
    )
    if (inherits(payload, "error")) {
      issues[[length(issues) + 1]] <- list(
        code = "uncertainty_sidecar_parse_error",
        message = sprintf(
          "Failed to parse uncertainty evidence sidecar '%s': %s",
          basename(candidate),
          conditionMessage(payload)
        ),
        field = candidate,
        severity = "warning"
      )
      return(list(path = candidate, rows = list(), metadata = NULL, issues = issues))
    }

    rows <- extract_uncertainty_evidence_rows_payload(payload)
    metadata <- extract_uncertainty_evidence_metadata(payload)
    if (is.null(rows)) {
      issues[[length(issues) + 1]] <- list(
        code = "uncertainty_sidecar_rows_missing",
        message = sprintf(
          "Uncertainty evidence sidecar '%s' must provide 'rows', 'uncertaintyEvidence.rows', or a top-level row array.",
          basename(candidate)
        ),
        field = candidate,
        severity = "warning"
      )
      return(list(path = candidate, rows = list(), metadata = metadata, issues = issues))
    }

    return(list(path = candidate, rows = rows, metadata = metadata, issues = issues))
  }

  list(path = NULL, rows = list(), metadata = NULL, issues = issues)
}

parameter_table_sidecar <- function(file_path) {
  issues <- list()
  for (candidate in parameter_table_sidecar_candidates(file_path)) {
    if (!file.exists(candidate)) {
      next
    }

    payload <- tryCatch(
      fromJSON(candidate, simplifyVector = FALSE),
      error = function(exc) exc
    )
    if (inherits(payload, "error")) {
      issues[[length(issues) + 1]] <- list(
        code = "parameter_table_sidecar_parse_error",
        message = sprintf(
          "Failed to parse parameter-table sidecar '%s': %s",
          basename(candidate),
          conditionMessage(payload)
        ),
        field = candidate,
        severity = "warning"
      )
      return(list(path = candidate, rows = list(), metadata = NULL, issues = issues))
    }

    rows <- extract_parameter_table_rows_payload(payload)
    metadata <- extract_parameter_table_metadata(payload)
    if (is.null(rows)) {
      issues[[length(issues) + 1]] <- list(
        code = "parameter_table_sidecar_rows_missing",
        message = sprintf(
          "Parameter-table sidecar '%s' must provide 'rows', 'parameterTable.rows', or a top-level row array.",
          basename(candidate)
        ),
        field = candidate,
        severity = "warning"
      )
      return(list(path = candidate, rows = list(), metadata = metadata, issues = issues))
    }

    return(list(path = candidate, rows = rows, metadata = metadata, issues = issues))
  }

  list(path = NULL, rows = list(), metadata = NULL, issues = issues)
}

ospsuite_profile_sidecar <- function(file_path) {
  for (candidate in ospsuite_profile_sidecar_candidates(file_path)) {
    if (!file.exists(candidate)) {
      next
    }

    payload <- read_json_file(candidate)
    if (!is.list(payload)) {
      stop(
        sprintf("OSPSuite profile sidecar '%s' must contain a JSON object", basename(candidate)),
        call. = FALSE
      )
    }

    profile_payload <- payload$profile %||% payload
    if (!is.list(profile_payload)) {
      stop(
        sprintf("OSPSuite profile sidecar '%s' must provide a 'profile' object", basename(candidate)),
        call. = FALSE
      )
    }

    return(list(
      path = candidate,
      payload = profile_payload
    ))
  }

  list(path = NULL, payload = NULL)
}

rxode_capabilities <- function(file_path, module_env, parameter_catalog = list()) {
  defaults <- list(
    backend = "rxode2",
    deterministicSimulation = TRUE,
    populationSimulation = exists("pbpk_run_population", envir = module_env, inherits = FALSE),
    parameterEditing = TRUE,
    validationHook = exists("pbpk_validate_request", envir = module_env, inherits = FALSE),
    scientificProfile = exists("pbpk_model_profile", envir = module_env, inherits = FALSE),
    supportedRuntimeFormats = list("r"),
    supportedOutputs = NULL,
    tags = list("rxode2", "custom"),
    applicabilityDomain = NULL
  )

  hook_payload <- call_module_hook(
    module_env,
    "pbpk_capabilities",
    list(file_path = file_path, parameter_catalog = parameter_catalog)
  )

  if (is.null(hook_payload)) {
    return(defaults)
  }
  if (!is.list(hook_payload)) {
    stop("pbpk_capabilities() must return a list", call. = FALSE)
  }

  merged <- defaults
  for (name in names(hook_payload)) {
    merged[[name]] <- hook_payload[[name]]
  }
  merged
}

ospsuite_profile <- function(file_path, capabilities = list()) {
  origin <- infer_ospsuite_origin(file_path)
  sidecar <- ospsuite_profile_sidecar(file_path)
  base_payload <- list(
    contextOfUse = list(
      status = "undeclared-in-transfer-file",
      sourceToolHint = origin$label,
      summary = sprintf(
        "The %s transfer file is executable through the MCP runtime, but no model-specific context-of-use metadata is currently attached.",
        origin$label
      )
    ),
    applicabilityDomain = list(
      type = "pkml-runtime-supported",
      qualificationLevel = "undeclared",
      status = "format-supported",
      sourceToolHint = origin$label,
      summary = sprintf(
        "Model '%s' is loadable as an OSPSuite transfer file, but scientific applicability metadata has not been declared in the current bridge.",
        basename(file_path)
      ),
      notes = list(
        "Runtime support confirms that the pkml file can be loaded by OSPSuite.",
        "Scientific qualification, uncertainty, and peer-review metadata must be supplied separately for regulatory or research claims."
      )
    ),
    uncertainty = list(
      status = "undeclared-in-transfer-file",
      summary = sprintf(
        "No uncertainty or sensitivity metadata is extracted automatically from '%s'.",
        basename(file_path)
      )
    ),
    implementationVerification = list(
      status = "runtime-load-verified",
      runtime = "ospsuite",
      sourceToolHint = origin$label,
      verifiedChecks = list("Transfer file accepted by the OSPSuite runtime"),
      missingChecks = list(
        "Model-specific uncertainty metadata",
        "Model-specific qualification dossier",
        "Peer-review and prior-use declarations"
      )
    ),
    peerReview = list(
      status = "not-reported",
      summary = sprintf(
        "No peer-review or prior-use metadata is attached to '%s' in the current bridge.",
        basename(file_path)
      )
    )
  )

  payload <- base_payload
  if (!is.null(sidecar$payload)) {
    for (name in names(sidecar$payload)) {
      payload[[name]] <- sidecar$payload[[name]]
    }
  }

  profile <- normalize_model_profile(
    payload,
    "ospsuite",
    file_path,
    capabilities$applicabilityDomain %||% NULL
  )
  source_defaults <- list(
    type = if (is.null(sidecar$path)) "bridge-default" else "sidecar",
    path = sidecar$path,
    sourceToolHint = origin$label
  )
  profile$profileSource <- utils::modifyList(
    source_defaults,
    profile$profileSource %||% list()
  )
  if (is_unreported_token(profile$profileSource$type)) {
    profile$profileSource$type <- source_defaults$type
  }
  if (length(normalize_text_values(profile$profileSource$path)) == 0) {
    profile$profileSource$path <- source_defaults$path
  }
  if (length(normalize_text_values(profile$profileSource$sourceToolHint)) == 0) {
    profile$profileSource$sourceToolHint <- source_defaults$sourceToolHint
  }
  profile
}

rxode_profile <- function(file_path, module_env, capabilities = list(), parameter_catalog = list()) {
  hook_payload <- call_module_hook(
    module_env,
    "pbpk_model_profile",
    list(file_path = file_path, parameter_catalog = parameter_catalog, capabilities = capabilities)
  )
  normalize_model_profile(hook_payload, "rxode2", file_path, capabilities$applicabilityDomain %||% NULL)
}

ospsuite_validate_record <- function(record, request = list(), stage = NULL) {
  warnings <- list()
  errors <- list()

  add_warning <- function(code, message, field = NULL) {
    warnings[[length(warnings) + 1]] <<- list(
      code = code,
      message = message,
      field = field,
      severity = "warning"
    )
  }

  add_error <- function(code, message, field = NULL) {
    errors[[length(errors) + 1]] <<- list(
      code = code,
      message = message,
      field = field,
      severity = "error"
    )
  }

  output_mode <- safe_chr(record$capabilities$outputSelectionMode, "declared")
  if (identical(output_mode, "observer-fallback")) {
    add_warning(
      "ospsuite_auto_output_selection",
      sprintf(
        paste(
          "Model declared no OutputSelections;",
          "runtime is using an observer-backed fallback with %d selected outputs"
        ),
        safe_num(record$capabilities$outputSelectionCount, 0)
      ),
      "OutputSelections"
    )
  }

  if (identical(output_mode, "empty") && identical(stage, "run_simulation_sync")) {
    add_error(
      "ospsuite_missing_runtime_outputs",
      paste(
        "Model has no declared OutputSelections and no runtime fallback outputs;",
        "simulation results are unlikely to be available"
      ),
      "OutputSelections"
    )
  }

  errors <- merge_validation_issues(errors, profile_request_mismatch_errors(record$profile, request))
  validation <- list(
    ok = length(errors) == 0,
    summary = if (length(errors) == 0) {
      "Request is consistent with the declared profile and runtime configuration"
    } else {
      "Request is outside the declared profile or runtime configuration"
    },
    errors = errors,
    warnings = warnings,
    domain = record$profile$applicabilityDomain %||% record$capabilities$applicabilityDomain %||% NULL,
    assessment = list(
      decision = if (length(errors) == 0) "within-declared-profile" else "outside-declared-profile"
    )
  )
  with_profile_assessment(validation, record$profile, record$capabilities)
}

rxode_validate_record <- function(record, request = list(), stage = NULL) {
  if (!exists("pbpk_validate_request", envir = record$module_env, inherits = FALSE)) {
    return(with_profile_assessment(list(
      ok = TRUE,
      summary = NULL,
      errors = list(),
      warnings = list(),
      domain = record$profile$applicabilityDomain %||% record$capabilities$applicabilityDomain %||% NULL,
      assessment = NULL
    ), record$profile, record$capabilities))
  }

  raw <- call_module_hook(
    record$module_env,
    "pbpk_validate_request",
    list(
      request = request,
      parameters = record$parameters,
      simulation_id = record$simulation_id,
      simulationId = record$simulation_id,
      metadata = record$metadata,
      parameter_catalog = record$parameter_catalog,
      capabilities = record$capabilities %||% NULL,
      profile = record$profile %||% NULL,
      stage = stage,
      file_path = record$file_path,
      filePath = record$file_path
    )
  )
  normalized <- normalize_validation_payload(raw)
  if (is.null(normalized$domain)) {
    normalized$domain <- record$profile$applicabilityDomain %||% record$capabilities$applicabilityDomain %||% NULL
  }
  with_profile_assessment(normalized, record$profile, record$capabilities)
}

enforce_validation <- function(validation, prefix = "Request rejected") {
  if (isTRUE(validation$ok)) {
    return(invisible(TRUE))
  }

  messages <- format_validation_messages(validation)
  detail <- if (length(messages) > 0) {
    paste(messages, collapse = "; ")
  } else {
    safe_chr(validation$summary, "request is outside the configured guardrails")
  }
  stop(sprintf("%s: %s", prefix, detail), call. = FALSE)
}

rxode_metadata <- function(file_path, module_env) {
  if (exists("pbpk_model_metadata", envir = module_env, inherits = FALSE)) {
    metadata <- module_env$pbpk_model_metadata()
  } else {
    metadata <- list()
  }
  list(
    name = safe_chr(metadata$name, basename(file_path)),
    modelVersion = safe_chr(metadata$modelVersion) %||% safe_chr(metadata$model_version),
    createdBy = safe_chr(metadata$createdBy) %||% safe_chr(metadata$created_by) %||% "rxode2",
    createdAt = safe_chr(metadata$createdAt) %||% now_utc(),
    backend = "rxode2"
  )
}

load_rxode_model <- function(file_path) {
  # Use the regular search path so sourced model modules can resolve functions
  # loaded with library()/require() inside their own script.
  module_env <- new.env(parent = globalenv())
  tryCatch(
    sys.source(file_path, envir = module_env),
    error = function(exc) {
      stop(sprintf("Failed to source rxode2 model '%s': %s", basename(file_path), exc$message), call. = FALSE)
    }
  )

  required_functions <- c("pbpk_default_parameters", "pbpk_run_simulation", "pbpk_run_population")
  missing <- required_functions[!vapply(required_functions, exists, logical(1), envir = module_env, inherits = FALSE)]
  if (length(missing) > 0) {
    stop(
      sprintf(
        "rxode2 model '%s' is missing required functions: %s",
        basename(file_path),
        paste(missing, collapse = ", ")
      ),
      call. = FALSE
    )
  }

  parameters <- as.list(module_env$pbpk_default_parameters())
  if (length(parameters) == 0 || is.null(names(parameters)) || any(!nzchar(names(parameters)))) {
    stop(
      sprintf("rxode2 model '%s' must return a named parameter list", basename(file_path)),
      call. = FALSE
    )
  }
  parameters <- lapply(parameters, function(value) safe_num(value, 0))

  catalog <- NULL
  if (exists("pbpk_parameter_catalog", envir = module_env, inherits = FALSE)) {
    catalog <- module_env$pbpk_parameter_catalog()
  }

  list(
    module_env = module_env,
    parameters = parameters,
    parameter_catalog = normalize_parameter_catalog(parameters, catalog)
  )
}

rxode_parameter_payload <- function(record, path) {
  catalog_entry <- record$parameter_catalog[[path]] %||% list(
    path = path,
    display_name = path,
    unit = "unitless"
  )
  list(
    path = path,
    value = safe_num(record$parameters[[path]], 0),
    unit = safe_chr(catalog_entry$unit, "unitless"),
    display_name = safe_chr(catalog_entry$display_name, path),
    last_updated_at = now_utc(),
    source = "rxode2"
  )
}

normalize_parameter_table_rows <- function(rows, fallback_values = list()) {
  normalized <- list()
  for (entry in rows %||% list()) {
    if (!is.list(entry)) {
      next
    }

    path <- safe_chr(entry$path)
    if (is.null(path) || !nzchar(path)) {
      next
    }

    row <- entry
    row$path <- path
    row$display_name <- safe_chr(entry$display_name) %||% safe_chr(entry$displayName) %||% path
    row$unit <- safe_chr(entry$unit, "unitless")
    row$category <- safe_chr(entry$category)
    row$is_editable <- isTRUE(entry$is_editable %||% entry$isEditable %||% TRUE)

    value <- entry$value
    if (is.null(value) && !is.null(fallback_values[[path]])) {
      value <- fallback_values[[path]]
    }
    row$value <- safe_num(value, 0)
    row$source <- safe_chr(entry$source)
    row$sourceType <- safe_chr(entry$sourceType) %||% safe_chr(entry$source_type)
    row$sourceCitation <- safe_chr(entry$sourceCitation) %||% safe_chr(entry$source_citation)
    row$sourceTable <- safe_chr(entry$sourceTable) %||% safe_chr(entry$source_table)
    row$evidenceType <- safe_chr(entry$evidenceType) %||% safe_chr(entry$evidence_type)
    row$rationale <- safe_chr(entry$rationale) %||% safe_chr(entry$motivation)
    row$motivation <- safe_chr(entry$motivation)
    row$distribution <- safe_chr(entry$distribution) %||%
      safe_chr(entry$distributionType) %||%
      safe_chr(entry$distribution_type)
    if (!is.null(entry$mean)) {
      row$mean <- safe_num(entry$mean, 0)
    }
    if (!is.null(entry$sd)) {
      row$sd <- safe_num(entry$sd, 0)
    } else if (!is.null(entry$standardDeviation)) {
      row$sd <- safe_num(entry$standardDeviation, 0)
    } else if (!is.null(entry$standard_deviation)) {
      row$sd <- safe_num(entry$standard_deviation, 0)
    }
    if (!is.null(entry$lowerBound)) {
      row$lowerBound <- safe_num(entry$lowerBound, 0)
    } else if (!is.null(entry$lower_bound)) {
      row$lowerBound <- safe_num(entry$lower_bound, 0)
    }
    if (!is.null(entry$upperBound)) {
      row$upperBound <- safe_num(entry$upperBound, 0)
    } else if (!is.null(entry$upper_bound)) {
      row$upperBound <- safe_num(entry$upper_bound, 0)
    }
    experimental_conditions <- normalize_text_values(
      entry$experimentalConditions %||%
        entry$testConditions %||%
        entry$studyConditions
    )
    if (length(experimental_conditions) > 0) {
      row$experimentalConditions <- as.list(experimental_conditions)
    }
    notes <- normalize_text_values(entry$notes)
    if (length(notes) > 0) {
      row$notes <- as.list(notes)
    }

    row$provenance_status <- safe_chr(entry$provenance_status) %||%
      safe_chr(entry$provenanceStatus) %||%
      if (length(normalize_text_values(list(
        row$source,
        row$sourceType,
        row$sourceCitation,
        row$sourceTable,
        row$evidenceType,
        row$rationale,
        row$distribution,
        row$mean,
        row$sd,
        row$lowerBound,
        row$upperBound,
        row$experimentalConditions,
        row$notes
      ))) > 0) {
        "declared"
      } else {
        "unreported"
      }

    normalized[[length(normalized) + 1]] <- row
  }

  normalized
}

normalize_performance_evidence_rows <- function(rows) {
  normalized <- list()
  for (index in seq_along(rows %||% list())) {
    entry <- rows[[index]]
    if (!is.list(entry)) {
      next
    }

    row <- entry
    row$id <- safe_chr(entry$id) %||%
      safe_chr(entry$checkId) %||%
      safe_chr(entry$check_id) %||%
      sprintf("evidence-%03d", index)
    row$kind <- safe_chr(entry$kind) %||% safe_chr(entry$type) %||% "unspecified"
    row$status <- safe_chr(entry$status, "unreported")
    row$targetOutput <- safe_chr(entry$targetOutput) %||%
      safe_chr(entry$target_output) %||%
      safe_chr(entry$output)
    row$metric <- safe_chr(entry$metric) %||% safe_chr(entry$metricName) %||% safe_chr(entry$metric_name)
    row$dataset <- safe_chr(entry$dataset) %||% safe_chr(entry$datasetId) %||% safe_chr(entry$study)
    row$acceptanceCriterion <- safe_chr(entry$acceptanceCriterion) %||%
      safe_chr(entry$acceptance_criterion)
    row$evidenceLevel <- safe_chr(entry$evidenceLevel) %||%
      safe_chr(entry$evidence_level)
    row$summary <- safe_chr(entry$summary) %||% safe_chr(entry$description)
    row$qualificationBasis <- safe_chr(entry$qualificationBasis) %||%
      safe_chr(entry$qualification_basis)
    row$dataOrigin <- safe_chr(entry$dataOrigin) %||% safe_chr(entry$data_origin)
    if (!is.null(entry$value)) {
      row$value <- safe_num(entry$value, 0)
    }
    if (!is.null(entry$observedValue)) {
      row$observedValue <- safe_num(entry$observedValue, 0)
    }
    if (!is.null(entry$predictedValue)) {
      row$predictedValue <- safe_num(entry$predictedValue, 0)
    }
    notes <- normalize_text_values(entry$notes)
    if (length(notes) > 0) {
      row$notes <- as.list(notes)
    }

    kind_value <- tolower(safe_chr(row$kind, ""))
    level_value <- tolower(safe_chr(row$evidenceLevel, ""))
    basis_value <- tolower(safe_chr(row$qualificationBasis, ""))

    inferred_class <- safe_chr(entry$evidenceClass) %||% safe_chr(entry$evidence_class)
    if (is.null(inferred_class) || !nzchar(inferred_class)) {
      inferred_class <- if (!is.null(row$observedValue) && !is.null(row$predictedValue)) {
        "observed-vs-predicted"
      } else if (grepl("runtime-smoke|smoke-test|smoke", kind_value) || grepl("runtime-only", level_value)) {
        "runtime-smoke"
      } else if (grepl("external", level_value) || grepl("regulatory|peer-reviewed|qualified", basis_value)) {
        "external-qualification"
      } else if (grepl("predictive", kind_value) || grepl("predictive", level_value)) {
        "predictive-dataset"
      } else if (grepl("goodness-of-fit|fit-metric|observed", kind_value)) {
        "observed-vs-predicted"
      } else if (grepl("internal", level_value) || grepl("reference|baseline|regression", kind_value)) {
        "internal-reference"
      } else {
        "other"
      }
    }
    row$evidenceClass <- inferred_class

    inferred_relevance <- safe_chr(entry$qualificationRelevance) %||%
      safe_chr(entry$qualification_relevance)
    if (is.null(inferred_relevance) || !nzchar(inferred_relevance)) {
      inferred_relevance <- switch(
        inferred_class,
        "runtime-smoke" = "operational-only",
        "internal-reference" = "internal-supporting",
        "observed-vs-predicted" = "predictive-supporting",
        "predictive-dataset" = "predictive-supporting",
        "external-qualification" = "external-supporting",
        "unspecified"
      )
    }
    row$qualificationRelevance <- inferred_relevance

    if (is.null(row$dataOrigin) || !nzchar(row$dataOrigin)) {
      row$dataOrigin <- switch(
        inferred_class,
        "runtime-smoke" = "internal",
        "internal-reference" = "internal",
        "external-qualification" = "external",
        "unspecified"
      )
    }

    normalized[[length(normalized) + 1]] <- row
  }

  normalized
}

named_value_counts <- function(values, expected = NULL) {
  keys <- character(0)
  if (length(expected %||% character(0)) > 0) {
    keys <- unique(c(keys, expected))
  }
  if (length(values %||% character(0)) > 0) {
    keys <- unique(c(keys, values))
  }

  counts <- vector("list", length(keys))
  names(counts) <- keys
  for (key in keys) {
    counts[[key]] <- as.integer(sum(values %||% character(0) == key))
  }
  counts
}

performance_evidence_class_rank <- function(value) {
  normalized <- safe_chr(value, "other")
  switch(
    normalized,
    "none" = 0L,
    "other" = 1L,
    "runtime-smoke" = 2L,
    "internal-reference" = 3L,
    "observed-vs-predicted" = 4L,
    "predictive-dataset" = 5L,
    "external-qualification" = 6L,
    1L
  )
}

performance_evidence_summary <- function(rows) {
  normalized_rows <- rows %||% list()
  classes <- vapply(
    normalized_rows,
    function(entry) safe_chr(entry$evidenceClass, "other"),
    character(1)
  )
  relevance <- vapply(
    normalized_rows,
    function(entry) safe_chr(entry$qualificationRelevance, "unspecified"),
    character(1)
  )

  class_counts <- named_value_counts(
    classes,
    expected = c(
      "runtime-smoke",
      "internal-reference",
      "observed-vs-predicted",
      "predictive-dataset",
      "external-qualification",
      "other"
    )
  )
  relevance_counts <- named_value_counts(
    relevance,
    expected = c(
      "operational-only",
      "internal-supporting",
      "predictive-supporting",
      "external-supporting",
      "unspecified"
    )
  )

  strongest_class <- "none"
  if (length(classes) > 0) {
    ordered_classes <- unique(classes[order(
      vapply(classes, performance_evidence_class_rank, integer(1)),
      decreasing = TRUE
    )])
    strongest_class <- safe_chr(ordered_classes[[1]], "other")
  }

  supports_observed <- as.integer(class_counts[["observed-vs-predicted"]] %||% 0L) > 0
  supports_predictive <- as.integer(class_counts[["predictive-dataset"]] %||% 0L) > 0
  supports_external <- as.integer(class_counts[["external-qualification"]] %||% 0L) > 0
  limited_runtime_internal <- length(normalized_rows) > 0 &&
    !supports_observed &&
    !supports_predictive &&
    !supports_external

  qualification_boundary <- if (length(normalized_rows) == 0) {
    "no-bundled-performance-evidence"
  } else if (limited_runtime_internal) {
    "runtime-or-internal-evidence-only"
  } else if (!supports_external) {
    "predictive-supporting-evidence-without-external-qualification"
  } else {
    "includes-external-qualification-evidence"
  }

  interpretation <- switch(
    qualification_boundary,
    "no-bundled-performance-evidence" =
      "No bundled performance evidence rows were exported for this model/session.",
    "runtime-or-internal-evidence-only" =
      "Bundled performance evidence is limited to runtime smoke or internal reference checks and should not be interpreted as external predictive validation.",
    "predictive-supporting-evidence-without-external-qualification" =
      "Bundled performance evidence includes predictive-supporting rows, but no external qualification package is attached.",
    "includes-external-qualification-evidence" =
      "Bundled performance evidence includes at least one externally oriented qualification row.",
    "Performance evidence classification is present but incomplete."
  )

  list(
    evidenceClassCounts = class_counts,
    qualificationRelevanceCounts = relevance_counts,
    strongestEvidenceClass = strongest_class,
    supportsObservedVsPredictedEvidence = supports_observed,
    supportsPredictiveDatasetEvidence = supports_predictive,
    supportsExternalQualificationEvidence = supports_external,
    limitedToRuntimeOrInternalEvidence = limited_runtime_internal,
    qualificationBoundary = qualification_boundary,
    interpretation = interpretation
  )
}

performance_evidence_row_issues <- function(rows, source = "performanceEvidence") {
  issues <- list()
  append_issue <- function(code, message, field, row_id = NULL) {
    issues[[length(issues) + 1]] <<- list(
      code = code,
      message = message,
      field = field,
      severity = "warning",
      rowId = row_id
    )
  }

  for (index in seq_along(rows %||% list())) {
    row <- rows[[index]]
    if (!is.list(row)) {
      next
    }

    row_id <- safe_chr(row$id, sprintf("row-%03d", index))
    evidence_class <- safe_chr(row$evidenceClass, "other")
    field_prefix <- sprintf("%s.rows[%d]", source, index)

    if (identical(evidence_class, "runtime-smoke") &&
        (is.null(safe_chr(row$acceptanceCriterion)) || !nzchar(safe_chr(row$acceptanceCriterion, "")))) {
      append_issue(
        "performance_row_acceptance_missing",
        "Runtime smoke evidence rows should declare an explicit acceptanceCriterion.",
        paste0(field_prefix, ".acceptanceCriterion"),
        row_id
      )
    }

    if (identical(evidence_class, "observed-vs-predicted")) {
      if (is.null(row$observedValue)) {
        append_issue(
          "performance_row_observed_missing",
          "Observed-versus-predicted rows should include observedValue.",
          paste0(field_prefix, ".observedValue"),
          row_id
        )
      }
      if (is.null(row$predictedValue)) {
        append_issue(
          "performance_row_predicted_missing",
          "Observed-versus-predicted rows should include predictedValue.",
          paste0(field_prefix, ".predictedValue"),
          row_id
        )
      }
      if (is.null(safe_chr(row$dataset)) || !nzchar(safe_chr(row$dataset, ""))) {
        append_issue(
          "performance_row_dataset_missing",
          "Observed-versus-predicted rows should identify the benchmark dataset or study.",
          paste0(field_prefix, ".dataset"),
          row_id
        )
      }
      if (is.null(safe_chr(row$acceptanceCriterion)) || !nzchar(safe_chr(row$acceptanceCriterion, ""))) {
        append_issue(
          "performance_row_acceptance_missing",
          "Observed-versus-predicted rows should declare the comparison acceptanceCriterion.",
          paste0(field_prefix, ".acceptanceCriterion"),
          row_id
        )
      }
    }

    if (identical(evidence_class, "predictive-dataset")) {
      if (is.null(safe_chr(row$dataset)) || !nzchar(safe_chr(row$dataset, ""))) {
        append_issue(
          "performance_row_dataset_missing",
          "Predictive-dataset rows should identify the dataset or benchmark package.",
          paste0(field_prefix, ".dataset"),
          row_id
        )
      }
      if (is.null(safe_chr(row$acceptanceCriterion)) || !nzchar(safe_chr(row$acceptanceCriterion, ""))) {
        append_issue(
          "performance_row_acceptance_missing",
          "Predictive-dataset rows should declare the dataset-level acceptanceCriterion.",
          paste0(field_prefix, ".acceptanceCriterion"),
          row_id
        )
      }
    }

    if (identical(evidence_class, "external-qualification")) {
      if ((is.null(safe_chr(row$dataset)) || !nzchar(safe_chr(row$dataset, ""))) &&
          (is.null(safe_chr(row$qualificationBasis)) || !nzchar(safe_chr(row$qualificationBasis, "")))) {
        append_issue(
          "performance_row_external_basis_missing",
          "External-qualification rows should declare a dataset or qualificationBasis.",
          field_prefix,
          row_id
        )
      }
      if (is.null(safe_chr(row$acceptanceCriterion)) || !nzchar(safe_chr(row$acceptanceCriterion, ""))) {
        append_issue(
          "performance_row_acceptance_missing",
          "External-qualification rows should declare the qualification acceptanceCriterion.",
          paste0(field_prefix, ".acceptanceCriterion"),
          row_id
        )
      }
    }
  }

  issues
}

performance_evidence_metadata_issues <- function(metadata, source = "performanceEvidence.metadata") {
  issues <- list()
  append_issue <- function(code, message, field) {
    issues[[length(issues) + 1]] <<- list(
      code = code,
      message = message,
      field = field,
      severity = "warning"
    )
  }

  if (is.null(safe_chr(metadata$bundleVersion)) || !nzchar(safe_chr(metadata$bundleVersion, ""))) {
    append_issue(
      "performance_bundle_version_missing",
      "Performance evidence bundle metadata should declare bundleVersion.",
      paste0(source, ".bundleVersion")
    )
  }
  if (is.null(safe_chr(metadata$summary)) || !nzchar(safe_chr(metadata$summary, ""))) {
    append_issue(
      "performance_bundle_summary_missing",
      "Performance evidence bundle metadata should declare summary.",
      paste0(source, ".summary")
    )
  }

  issues
}

uncertainty_evidence_row_issues <- function(rows, source = "uncertaintyEvidence") {
  issues <- list()
  append_issue <- function(code, message, field, row_id = NULL) {
    issues[[length(issues) + 1]] <<- list(
      code = code,
      message = message,
      field = field,
      severity = "warning",
      rowId = row_id
    )
  }

  for (index in seq_along(rows %||% list())) {
    row <- rows[[index]]
    if (!is.list(row)) {
      next
    }

    row_id <- safe_chr(row$id, sprintf("row-%03d", index))
    kind <- safe_chr(row$kind, "unspecified")
    field_prefix <- sprintf("%s.rows[%d]", source, index)
    method <- safe_chr(row$method)
    summary <- safe_chr(row$summary)
    metric <- safe_chr(row$metric)
    target_output <- safe_chr(row$targetOutput)
    varied_parameters <- normalize_text_values(row$variedParameters %||% row$parameters)

    if (identical(kind, "variability-approach")) {
      if ((is.null(method) || !nzchar(method)) && (is.null(summary) || !nzchar(summary))) {
        append_issue(
          "uncertainty_row_summary_missing",
          "Variability-approach rows should declare a method or summary.",
          field_prefix,
          row_id
        )
      }
    } else if (kind %in% c("variability-propagation", "sensitivity-analysis")) {
      if ((is.null(method) || !nzchar(method)) && (is.null(summary) || !nzchar(summary))) {
        append_issue(
          "uncertainty_row_summary_missing",
          "Uncertainty rows should declare a method or summary.",
          field_prefix,
          row_id
        )
      }
      if ((is.null(metric) || !nzchar(metric)) &&
          (is.null(target_output) || !nzchar(target_output)) &&
          length(varied_parameters) == 0) {
        append_issue(
          "uncertainty_row_scope_missing",
          "Uncertainty rows should declare a metric, targetOutput, or variedParameters.",
          field_prefix,
          row_id
        )
      }
    } else if (identical(kind, "residual-uncertainty")) {
      if (is.null(summary) || !nzchar(summary)) {
        append_issue(
          "uncertainty_row_summary_missing",
          "Residual-uncertainty rows should declare a summary.",
          paste0(field_prefix, ".summary"),
          row_id
        )
      }
    }
  }

  issues
}

uncertainty_evidence_metadata_issues <- function(metadata, source = "uncertaintyEvidence.metadata") {
  issues <- list()
  append_issue <- function(code, message, field) {
    issues[[length(issues) + 1]] <<- list(
      code = code,
      message = message,
      field = field,
      severity = "warning"
    )
  }

  if (is.null(safe_chr(metadata$bundleVersion)) || !nzchar(safe_chr(metadata$bundleVersion, ""))) {
    append_issue(
      "uncertainty_bundle_version_missing",
      "Uncertainty evidence bundle metadata should declare bundleVersion.",
      paste0(source, ".bundleVersion")
    )
  }
  if (is.null(safe_chr(metadata$summary)) || !nzchar(safe_chr(metadata$summary, ""))) {
    append_issue(
      "uncertainty_bundle_summary_missing",
      "Uncertainty evidence bundle metadata should declare summary.",
      paste0(source, ".summary")
    )
  }

  issues
}

ensure_unique_evidence_row_ids <- function(rows, prefix = "evidence") {
  normalized <- list()
  seen <- list()
  for (index in seq_along(rows %||% list())) {
    row <- rows[[index]]
    if (!is.list(row)) {
      next
    }

    base_id <- safe_chr(row$id, sprintf("%s-%03d", prefix, index))
    duplicate_index <- as.integer(seen[[base_id]] %||% 0L)
    seen[[base_id]] <- duplicate_index + 1L
    if (duplicate_index > 0L) {
      row$id <- sprintf("%s-dup-%02d", base_id, duplicate_index + 1L)
    } else {
      row$id <- base_id
    }
    normalized[[length(normalized) + 1]] <- row
  }
  normalized
}

normalize_supporting_evidence_rows <- function(rows, prefix = "evidence") {
  normalized <- list()
  for (index in seq_along(rows %||% list())) {
    entry <- rows[[index]]
    if (!is.list(entry)) {
      next
    }

    row <- entry
    row$id <- safe_chr(entry$id) %||%
      safe_chr(entry$checkId) %||%
      safe_chr(entry$check_id) %||%
      sprintf("%s-%03d", prefix, index)
    row$kind <- safe_chr(entry$kind) %||% safe_chr(entry$type) %||% prefix
    row$status <- safe_chr(entry$status, "unreported")
    row$summary <- safe_chr(entry$summary) %||% safe_chr(entry$description)
    row$method <- safe_chr(entry$method)
    row$targetOutput <- safe_chr(entry$targetOutput) %||%
      safe_chr(entry$target_output) %||%
      safe_chr(entry$output)
    row$metric <- safe_chr(entry$metric) %||% safe_chr(entry$metricName) %||% safe_chr(entry$metric_name)
    row$dataset <- safe_chr(entry$dataset) %||% safe_chr(entry$datasetId) %||% safe_chr(entry$study)
    row$acceptanceCriterion <- safe_chr(entry$acceptanceCriterion) %||%
      safe_chr(entry$acceptance_criterion)
    row$evidenceLevel <- safe_chr(entry$evidenceLevel) %||%
      safe_chr(entry$evidence_level)
    row$checkName <- safe_chr(entry$checkName) %||% safe_chr(entry$check_name)
    row$solver <- safe_chr(entry$solver)
    row$runtime <- safe_chr(entry$runtime)
    row$runtimeVersion <- safe_chr(entry$runtimeVersion) %||% safe_chr(entry$runtime_version)
    row$softwareName <- safe_chr(entry$softwareName) %||% safe_chr(entry$software)
    row$softwareVersion <- safe_chr(entry$softwareVersion) %||% safe_chr(entry$version)
    row$qualificationBasis <- safe_chr(entry$qualificationBasis) %||%
      safe_chr(entry$qualification_basis)

    varied_parameters <- normalize_text_values(entry$variedParameters %||% entry$parameters)
    if (length(varied_parameters) > 0) {
      row$variedParameters <- as.list(varied_parameters)
    }

    notes <- normalize_text_values(entry$notes)
    if (length(notes) > 0) {
      row$notes <- as.list(notes)
    }

    for (field in c("value", "observedValue", "predictedValue", "lowerBound", "upperBound")) {
      if (!is.null(entry[[field]])) {
        row[[field]] <- safe_num(entry[[field]], 0)
      }
    }

    normalized[[length(normalized) + 1]] <- row
  }

  normalized
}

record_performance_evidence <- function(record, limit = 200L) {
  limit_value <- as.integer(safe_num(limit, 200))
  if (is.na(limit_value) || limit_value < 1) {
    limit_value <- 200L
  }

  collected_rows <- list()
  sources <- character(0)
  performance <- record$profile$modelPerformance %||% list()
  parameter_table <- NULL
  sidecar <- performance_evidence_sidecar(record$file_path)

  if (identical(record$backend, "rxode2") &&
      is.environment(record$module_env) &&
      exists("pbpk_performance_evidence", envir = record$module_env, inherits = FALSE)) {
    parameter_table <- record_parameter_table(record, limit = 5000L)
    raw_rows <- call_module_hook(
      record$module_env,
      "pbpk_performance_evidence",
      list(
        parameters = record$parameters,
        parameter_catalog = record$parameter_catalog,
        parameterCatalog = record$parameter_catalog,
        parameter_table = parameter_table,
        parameterTable = parameter_table,
        simulation_id = record$simulation_id,
        simulationId = record$simulation_id,
        metadata = record$metadata,
        capabilities = record$capabilities,
        profile = record$profile,
        file_path = record$file_path,
        filePath = record$file_path
      )
    )
    if (is.list(raw_rows) && length(raw_rows) > 0) {
      collected_rows <- c(collected_rows, raw_rows)
      sources <- c(sources, "pbpk_performance_evidence")
    }
  }

  profile_rows <- performance_evidence_rows_from_profile(performance)
  if (is.list(profile_rows) && length(profile_rows) > 0) {
    collected_rows <- c(collected_rows, profile_rows)
    sources <- c(sources, "profile-modelPerformance")
  }
  if (is.list(sidecar$rows) && length(sidecar$rows) > 0) {
    collected_rows <- c(collected_rows, sidecar$rows)
    sources <- c(sources, "performance-evidence-sidecar")
  }

  if (length(sources) == 0) {
    sources <- "profile-modelPerformance"
  }

  rows <- normalize_performance_evidence_rows(collected_rows)
  rows <- ensure_unique_evidence_row_ids(rows, prefix = "performance-evidence")
  summary <- performance_evidence_summary(rows)
  traceability <- performance_traceability_summary(performance, rows)
  metadata_issues <- if (!is.null(sidecar$path)) {
    performance_evidence_metadata_issues(sidecar$metadata, source = "performanceEvidence.bundleMetadata")
  } else {
    list()
  }
  quality_issues <- performance_evidence_row_issues(rows)
  total_rows <- length(rows)
  if (total_rows > limit_value) {
    rows <- rows[seq_len(limit_value)]
  }

  utils::modifyList(summary, list(
    traceability = traceability,
    source = if (length(unique(sources)) == 1) unique(sources)[[1]] else "combined",
    sources = as.list(unique(sources)),
    sidecarPath = sidecar$path,
    bundleMetadata = sidecar$metadata,
    issues = c(sidecar$issues %||% list(), metadata_issues, quality_issues),
    issueCount = length(c(sidecar$issues %||% list(), metadata_issues, quality_issues)),
    included = TRUE,
    limit = limit_value,
    totalRows = total_rows,
    returnedRows = length(rows),
    truncated = total_rows > limit_value,
    rows = rows
  ))
}

merge_parameter_table_rows <- function(primary_rows, supplemental_rows) {
  merged <- list()
  row_order <- character()

  add_or_merge <- function(entry) {
    path <- safe_chr(entry$path)
    if (is.null(path) || !nzchar(path)) {
      return(NULL)
    }
    if (!(path %in% row_order)) {
      row_order <<- c(row_order, path)
    }
    existing <- merged[[path]] %||% list()
    merged[[path]] <<- utils::modifyList(existing, entry)
  }

  for (entry in primary_rows %||% list()) {
    add_or_merge(entry)
  }
  for (entry in supplemental_rows %||% list()) {
    add_or_merge(entry)
  }

  unname(merged[row_order])
}

parameter_table_metadata_issues <- function(metadata, source = "parameterTable.bundleMetadata") {
  issues <- list()
  metadata_dict <- metadata %||% list()

  if (is.null(safe_chr(metadata_dict$bundleVersion)) || !nzchar(safe_chr(metadata_dict$bundleVersion, ""))) {
    issues[[length(issues) + 1]] <- list(
      code = "parameter_table_bundle_version_missing",
      message = "Parameter-table bundle metadata should declare bundleVersion.",
      field = sprintf("%s.bundleVersion", source),
      severity = "warning"
    )
  }
  if (is.null(safe_chr(metadata_dict$summary)) || !nzchar(safe_chr(metadata_dict$summary, ""))) {
    issues[[length(issues) + 1]] <- list(
      code = "parameter_table_bundle_summary_missing",
      message = "Parameter-table bundle metadata should declare summary.",
      field = sprintf("%s.summary", source),
      severity = "warning"
    )
  }
  issues
}

parameter_table_row_issues <- function(rows, source = "parameterTable.rows") {
  issues <- list()

  for (index in seq_along(rows %||% list())) {
    row <- rows[[index]]
    if (!is.list(row)) {
      next
    }

    row_id <- safe_chr(row$path, sprintf("row-%03d", index))
    row_field_prefix <- sprintf("%s[%d]", source, index)
    provenance_present <- !identical(safe_chr(row$provenance_status, "unreported"), "unreported") ||
      length(normalize_text_values(list(
        row$source,
        row$sourceType,
        row$sourceCitation,
        row$sourceTable,
        row$evidenceType,
        row$rationale,
        row$distribution,
        row$mean,
        row$sd,
        row$lowerBound,
        row$upperBound,
        row$experimentalConditions
      ))) > 0

    if (provenance_present &&
        length(normalize_text_values(list(row$source, row$sourceCitation, row$sourceTable))) == 0) {
      issues[[length(issues) + 1]] <- list(
        code = "parameter_row_source_missing",
        message = sprintf(
          "Parameter row '%s' declares provenance metadata but does not identify a source, citation, or source table.",
          row_id
        ),
        field = row_field_prefix,
        severity = "warning"
      )
    }

    if (length(normalize_text_values(row$distribution)) > 0 &&
        is.null(row$mean) &&
        is.null(row$sd) &&
        is.null(row$lowerBound) &&
        is.null(row$upperBound)) {
      issues[[length(issues) + 1]] <- list(
        code = "parameter_row_distribution_details_missing",
        message = sprintf(
          "Parameter row '%s' declares a distribution but does not provide supporting statistics or bounds.",
          row_id
        ),
        field = sprintf("%s.distribution", row_field_prefix),
        severity = "warning"
      )
    }

    source_type_token <- normalize_context_token(row$sourceType)
    evidence_type_token <- normalize_context_token(row$evidenceType)
    experimental_source <- (!is.null(source_type_token) &&
      grepl("in-vitro|in-vivo|in-silico|experimental|study|guideline", source_type_token)) ||
      (!is.null(evidence_type_token) &&
      grepl("experimental|study|literature", evidence_type_token))

    if (experimental_source &&
        length(normalize_text_values(list(row$experimentalConditions, row$rationale, row$motivation))) == 0) {
      issues[[length(issues) + 1]] <- list(
        code = "parameter_row_conditions_missing",
        message = sprintf(
          "Parameter row '%s' looks experimental or study-derived but does not declare study conditions or rationale.",
          row_id
        ),
        field = row_field_prefix,
        severity = "warning"
      )
    }
  }

  issues
}

parameter_table_coverage_summary <- function(rows) {
  entries <- rows %||% list()
  count_rows <- function(predicate) {
    as.integer(sum(vapply(entries, predicate, logical(1))))
  }

  list(
    rowCount = as.integer(length(entries)),
    rowsWithUnits = count_rows(function(entry) length(normalize_text_values(entry$unit)) > 0),
    rowsWithSources = count_rows(function(entry) {
      length(normalize_text_values(list(entry$source, entry$sourceCitation, entry$sourceTable))) > 0
    }),
    rowsWithSourceCitations = count_rows(function(entry) length(normalize_text_values(entry$sourceCitation)) > 0),
    rowsWithDistributions = count_rows(function(entry) {
      length(normalize_text_values(entry$distribution)) > 0 ||
        !is.null(entry$mean) ||
        !is.null(entry$sd) ||
        !is.null(entry$lowerBound) ||
        !is.null(entry$upperBound)
    }),
    rowsWithExperimentalConditions = count_rows(function(entry) {
      length(normalize_text_values(entry$experimentalConditions)) > 0
    }),
    rowsWithRationale = count_rows(function(entry) {
      length(normalize_text_values(list(entry$rationale, entry$motivation))) > 0
    })
  )
}

record_parameter_table <- function(record, pattern = NULL, limit = 200L) {
  pattern_value <- safe_chr(pattern)
  limit_value <- as.integer(safe_num(limit, 200))
  if (is.na(limit_value) || limit_value < 1) {
    limit_value <- 200L
  }

  raw_rows <- NULL
  sources <- character(0)
  source <- "runtime-parameter-enumeration"
  fallback_values <- record$parameters %||% list()
  sidecar <- parameter_table_sidecar(record$file_path)

  if (identical(record$backend, "rxode2") &&
      is.environment(record$module_env) &&
      exists("pbpk_parameter_table", envir = record$module_env, inherits = FALSE)) {
    raw_rows <- call_module_hook(
      record$module_env,
      "pbpk_parameter_table",
      list(
        parameters = record$parameters,
        parameter_catalog = record$parameter_catalog,
        simulation_id = record$simulation_id,
        simulationId = record$simulation_id,
        metadata = record$metadata,
        capabilities = record$capabilities,
        profile = record$profile,
        file_path = record$file_path,
        filePath = record$file_path
      )
    )
    source <- "pbpk_parameter_table"
    sources <- c(sources, "pbpk_parameter_table")
  } else if (length(record$parameter_catalog %||% list()) > 0) {
    raw_rows <- unname(record$parameter_catalog)
    source <- "parameter_catalog"
    sources <- c(sources, "parameter_catalog")
  } else if (identical(record$backend, "ospsuite")) {
    ensure_ospsuite()
    paths <- getAllParameterPathsIn(record$simulation)
    raw_rows <- lapply(paths, function(path) {
      parameter <- getParameter(path = path, container = record$simulation)
      row <- parameter_payload(parameter)
      row$category <- NULL
      row$is_editable <- TRUE
      row$provenance_status <- "unreported"
      row
    })
    source <- "ospsuite-runtime"
    sources <- c(sources, "ospsuite-runtime")
  } else {
    raw_rows <- lapply(names(fallback_values), function(path) {
      list(
        path = path,
        display_name = path,
        unit = "unitless",
        value = fallback_values[[path]],
        category = NULL,
        is_editable = TRUE,
        provenance_status = "unreported"
      )
    })
    sources <- c(sources, "runtime-parameter-enumeration")
  }

  rows <- normalize_parameter_table_rows(raw_rows, fallback_values)
  if (is.list(sidecar$rows) && length(sidecar$rows) > 0) {
    sidecar_rows <- normalize_parameter_table_rows(sidecar$rows, fallback_values)
    rows <- merge_parameter_table_rows(rows, sidecar_rows)
    sources <- c(sources, "parameter-table-sidecar")
  }
  if (length(sources) == 0) {
    sources <- source
  }
  total_rows <- length(rows)

  if (!is.null(pattern_value) && nzchar(pattern_value)) {
    rows <- Filter(function(entry) {
      isTRUE(grepl(glob2rx(pattern_value), safe_chr(entry$path, "")))
    }, rows)
  }
  matched_rows <- length(rows)
  coverage <- parameter_table_coverage_summary(rows)
  metadata_issues <- if (!is.null(sidecar$path)) {
    parameter_table_metadata_issues(sidecar$metadata, source = "parameterTable.bundleMetadata")
  } else {
    list()
  }
  quality_issues <- parameter_table_row_issues(rows)

  if (matched_rows > limit_value) {
    rows <- rows[seq_len(limit_value)]
  }

  list(
    source = if (length(unique(sources)) == 1) unique(sources)[[1]] else "combined",
    sources = as.list(unique(sources)),
    included = TRUE,
    pattern = pattern_value,
    limit = limit_value,
    totalRows = total_rows,
    matchedRows = matched_rows,
    returnedRows = length(rows),
    truncated = matched_rows > limit_value,
    sidecarPath = sidecar$path,
    bundleMetadata = sidecar$metadata,
    issues = c(sidecar$issues %||% list(), metadata_issues, quality_issues),
    issueCount = length(c(sidecar$issues %||% list(), metadata_issues, quality_issues)),
    coverage = coverage,
    rows = rows
  )
}

record_uncertainty_evidence <- function(record, limit = 200L) {
  limit_value <- as.integer(safe_num(limit, 200))
  if (is.na(limit_value) || limit_value < 1) {
    limit_value <- 200L
  }

  collected_rows <- list()
  sources <- character(0)
  uncertainty <- record$profile$uncertainty %||% list()
  parameter_table <- NULL
  sidecar <- uncertainty_evidence_sidecar(record$file_path)

  if (identical(record$backend, "rxode2") &&
      is.environment(record$module_env) &&
      exists("pbpk_uncertainty_evidence", envir = record$module_env, inherits = FALSE)) {
    parameter_table <- record_parameter_table(record, limit = 5000L)
    raw_rows <- call_module_hook(
      record$module_env,
      "pbpk_uncertainty_evidence",
      list(
        parameters = record$parameters,
        parameter_catalog = record$parameter_catalog,
        parameterCatalog = record$parameter_catalog,
        parameter_table = parameter_table,
        parameterTable = parameter_table,
        simulation_id = record$simulation_id,
        simulationId = record$simulation_id,
        metadata = record$metadata,
        capabilities = record$capabilities,
        profile = record$profile,
        file_path = record$file_path,
        filePath = record$file_path
      )
    )
    if (is.list(raw_rows) && length(raw_rows) > 0) {
      collected_rows <- c(collected_rows, raw_rows)
      sources <- c(sources, "pbpk_uncertainty_evidence")
    }
  }

  profile_rows <- uncertainty_evidence_rows_from_profile(uncertainty)
  if (is.list(profile_rows) && length(profile_rows) > 0) {
    collected_rows <- c(collected_rows, profile_rows)
    sources <- c(sources, "profile-uncertainty")
  }
  if (is.list(sidecar$rows) && length(sidecar$rows) > 0) {
    collected_rows <- c(collected_rows, sidecar$rows)
    sources <- c(sources, "uncertainty-evidence-sidecar")
  }
  if (length(sources) == 0) {
    sources <- "profile-uncertainty"
  }

  rows <- normalize_supporting_evidence_rows(collected_rows, prefix = "uncertainty")
  rows <- ensure_unique_evidence_row_ids(rows, prefix = "uncertainty-evidence")
  metadata_issues <- if (!is.null(sidecar$path)) {
    uncertainty_evidence_metadata_issues(sidecar$metadata, source = "uncertaintyEvidence.bundleMetadata")
  } else {
    list()
  }
  quality_issues <- uncertainty_evidence_row_issues(rows)
  total_rows <- length(rows)
  if (total_rows > limit_value) {
    rows <- rows[seq_len(limit_value)]
  }

  list(
    source = if (length(unique(sources)) == 1) unique(sources)[[1]] else "combined",
    sources = as.list(unique(sources)),
    sidecarPath = sidecar$path,
    bundleMetadata = sidecar$metadata,
    issues = c(sidecar$issues %||% list(), metadata_issues, quality_issues),
    issueCount = length(c(sidecar$issues %||% list(), metadata_issues, quality_issues)),
    included = TRUE,
    limit = limit_value,
    totalRows = total_rows,
    returnedRows = length(rows),
    truncated = total_rows > limit_value,
    rows = rows
  )
}

record_verification_evidence <- function(record, limit = 200L) {
  limit_value <- as.integer(safe_num(limit, 200))
  if (is.na(limit_value) || limit_value < 1) {
    limit_value <- 200L
  }

  raw_rows <- NULL
  source <- "profile-implementationVerification"
  verification <- record$profile$implementationVerification %||% list()
  parameter_table <- NULL

  if (identical(record$backend, "rxode2") &&
      is.environment(record$module_env) &&
      exists("pbpk_verification_evidence", envir = record$module_env, inherits = FALSE)) {
    parameter_table <- record_parameter_table(record, limit = 5000L)
    raw_rows <- call_module_hook(
      record$module_env,
      "pbpk_verification_evidence",
      list(
        parameters = record$parameters,
        parameter_catalog = record$parameter_catalog,
        parameterCatalog = record$parameter_catalog,
        parameter_table = parameter_table,
        parameterTable = parameter_table,
        simulation_id = record$simulation_id,
        simulationId = record$simulation_id,
        metadata = record$metadata,
        capabilities = record$capabilities,
        profile = record$profile,
        file_path = record$file_path,
        filePath = record$file_path
      )
    )
    source <- "pbpk_verification_evidence"
  } else {
    raw_rows <- implementation_verification_rows_from_profile(verification)
  }

  rows <- normalize_supporting_evidence_rows(raw_rows, prefix = "verification")
  total_rows <- length(rows)
  if (total_rows > limit_value) {
    rows <- rows[seq_len(limit_value)]
  }

  list(
    source = source,
    included = TRUE,
    limit = limit_value,
    totalRows = total_rows,
    returnedRows = length(rows),
    truncated = total_rows > limit_value,
    rows = rows
  )
}

record_platform_qualification_evidence <- function(record, limit = 200L) {
  limit_value <- as.integer(safe_num(limit, 200))
  if (is.na(limit_value) || limit_value < 1) {
    limit_value <- 200L
  }

  raw_rows <- NULL
  source <- "profile-platformQualification"
  platform_qualification <- record$profile$platformQualification %||% list()
  parameter_table <- NULL

  if (identical(record$backend, "rxode2") &&
      is.environment(record$module_env) &&
      exists("pbpk_platform_qualification_evidence", envir = record$module_env, inherits = FALSE)) {
    parameter_table <- record_parameter_table(record, limit = 5000L)
    raw_rows <- call_module_hook(
      record$module_env,
      "pbpk_platform_qualification_evidence",
      list(
        parameters = record$parameters,
        parameter_catalog = record$parameter_catalog,
        parameterCatalog = record$parameter_catalog,
        parameter_table = parameter_table,
        parameterTable = parameter_table,
        simulation_id = record$simulation_id,
        simulationId = record$simulation_id,
        metadata = record$metadata,
        capabilities = record$capabilities,
        profile = record$profile,
        file_path = record$file_path,
        filePath = record$file_path
      )
    )
    source <- "pbpk_platform_qualification_evidence"
  } else {
    raw_rows <- platform_qualification_rows_from_profile(platform_qualification)
  }

  rows <- normalize_supporting_evidence_rows(raw_rows, prefix = "platform-qualification")
  total_rows <- length(rows)
  if (total_rows > limit_value) {
    rows <- rows[seq_len(limit_value)]
  }

  list(
    source = source,
    included = TRUE,
    limit = limit_value,
    totalRows = total_rows,
    returnedRows = length(rows),
    truncated = total_rows > limit_value,
    rows = rows
  )
}

record_executable_verification_snapshot <- function(record) {
  verification <- record$metadata$verification %||% list()
  if (!is.list(verification) || length(verification) == 0) {
    return(list(
      source = "metadata.verification",
      included = FALSE,
      status = "not-run",
      summary = "No stored run_verification_checks snapshot is attached to this simulation record.",
      generatedAt = NULL,
      requestedPopulationSmoke = FALSE,
      qualificationState = NULL,
      checkCount = 0L,
      passedCount = 0L,
      failedCount = 0L,
      warningCount = 0L,
      skippedCount = 0L,
      checks = list(),
      artifacts = list()
    ))
  }

  list(
    source = "metadata.verification",
    included = TRUE,
    status = safe_chr(verification$status, "unreported"),
    summary = safe_chr(verification$summary),
    generatedAt = safe_chr(verification$generatedAt),
    requestedPopulationSmoke = safe_lgl(verification$requestedPopulationSmoke, FALSE),
    qualificationState = verification$qualificationState %||% NULL,
    checkCount = as.integer(safe_num(verification$checkCount, 0)),
    passedCount = as.integer(safe_num(verification$passedCount, 0)),
    failedCount = as.integer(safe_num(verification$failedCount, 0)),
    warningCount = as.integer(safe_num(verification$warningCount, 0)),
    skippedCount = as.integer(safe_num(verification$skippedCount, 0)),
    checks = verification$checks %||% list(),
      artifacts = verification$artifacts %||% list()
  )
}

assessment_context_from_record <- function(record, request = list(), validation = NULL) {
  request_payload <- request %||% list()
  assessment <- validation$assessment %||% list()
  declared_context <- record$profile$contextOfUse %||% list()
  declared_domain <- record$profile$applicabilityDomain %||% list()
  requested_context <- coerce_request_section(
    request_payload$contextOfUse %||% request_payload$context_of_use,
    scalar_key = "regulatoryUse"
  )
  requested_domain <- coerce_request_section(
    request_payload$applicabilityDomain %||% request_payload$applicability %||% request_payload$domain
  )
  requested_target_output <- safe_chr(request_payload$targetOutput) %||%
    safe_chr(request_payload$outputPath) %||%
    safe_chr(request_payload$output)
  declared_target_outputs <- normalize_text_values(
    record$profile$modelPerformance$targetOutputs %||% list()
  )

  list(
    objectType = "assessmentContext.v1",
    objectId = sprintf("%s-assessment-context", record$simulation_id),
    simulationId = record$simulation_id,
    backend = record$backend,
    assessmentBoundary = "pbpk-context-alignment-only",
    decisionBoundary = "no-ngra-decision-policy",
    validationDecision = safe_chr(assessment$decision),
    contextOfUse = list(
      regulatoryUse = selection_triplet(
        first_text_value(
          requested_context$regulatoryUse %||%
            requested_context$intendedUse %||%
            request_payload$regulatoryUse %||%
            request_payload$intendedUse
        ),
        first_text_value(declared_context$regulatoryUse)
      ),
      scientificPurpose = selection_triplet(
        first_text_value(requested_context$scientificPurpose %||% request_payload$scientificPurpose),
        first_text_value(declared_context$scientificPurpose)
      ),
      decisionContext = selection_triplet(
        first_text_value(requested_context$decisionContext %||% request_payload$decisionContext),
        first_text_value(declared_context$decisionContext)
      )
    ),
    domain = list(
      species = selection_triplet(
        first_text_value(requested_domain$species %||% request_payload$species),
        first_text_value(declared_domain$species)
      ),
      route = selection_triplet(
        first_text_value(
          requested_domain$routes %||%
            requested_domain$route %||%
            request_payload$routes %||%
            request_payload$route
        ),
        first_text_value(declared_domain$routes %||% declared_domain$route)
      ),
      lifeStage = selection_triplet(
        first_text_value(
          requested_domain$lifeStage %||%
            requested_domain$life_stage %||%
            request_payload$lifeStage %||%
            request_payload$life_stage
        ),
        first_text_value(declared_domain$lifeStage %||% declared_domain$life_stage)
      ),
      population = selection_triplet(
        first_text_value(requested_domain$population %||% request_payload$population),
        first_text_value(declared_domain$population %||% declared_domain$populations)
      ),
      compound = selection_triplet(
        first_text_value(
          requested_domain$compounds %||%
            requested_domain$compound %||%
            request_payload$compound
        ),
        first_text_value(declared_domain$compounds %||% declared_domain$compound)
      )
    ),
    doseScenario = request_payload$doseScenario %||% request_payload$dose_scenario %||% NULL,
    targetOutput = list(
      requested = requested_target_output,
      declared = as.list(declared_target_outputs)
    ),
    supports = list(
      declaredProfileComparison = TRUE,
      requestContextAlignment = TRUE,
      typedNgraHandoff = TRUE,
      decisionRecommendation = FALSE
    )
  )
}

qualification_required_external_inputs <- function(
  qualification_state = list(),
  performance_evidence = NULL
) {
  required <- c(
    "higher-level NGRA decision policy or orchestrator outside PBPK MCP"
  )

  boundary <- safe_chr(performance_evidence$qualificationBoundary)
  if (is.null(boundary) || identical(boundary, "no-bundled-performance-evidence")) {
    required <- c(
      required,
      "predictive or external qualification evidence for stronger regulatory-facing claims"
    )
  } else if (identical(boundary, "runtime-or-internal-evidence-only")) {
    required <- c(
      required,
      "observed-vs-predicted, predictive-dataset, or external qualification evidence"
    )
  }

  if (!safe_lgl(qualification_state$withinDeclaredContext, TRUE)) {
    required <- c(required, "request alignment with the declared PBPK context of use")
  }

  as.list(unique(required))
}

qualification_limitations_from_record <- function(
  qualification_state = list(),
  performance_evidence = NULL,
  executable_verification = NULL
) {
  limitations <- character()

  boundary <- safe_chr(performance_evidence$qualificationBoundary)
  if (identical(boundary, "runtime-or-internal-evidence-only")) {
    limitations <- c(
      limitations,
      "Bundled performance evidence is limited to runtime or internal supporting evidence."
    )
  } else if (identical(boundary, "no-bundled-performance-evidence")) {
    limitations <- c(
      limitations,
      "No bundled predictive-performance evidence is attached to this PBPK context."
    )
  }

  if (!isTRUE(executable_verification$included)) {
    limitations <- c(
      limitations,
      "No executable verification snapshot is attached to the current PBPK session."
    )
  }

  if (!safe_lgl(qualification_state$withinDeclaredContext, TRUE)) {
    limitations <- c(
      limitations,
      "The current request falls outside the model's declared PBPK context of use."
    )
  }

  as.list(unique(limitations))
}

pbpk_qualification_summary_from_record <- function(
  record,
  assessment = list(),
  performance_evidence = NULL,
  executable_verification = NULL
) {
  qualification_state <- assessment$qualificationState %||%
    derive_qualification_state(record$profile, record$capabilities, assessment)
  missing_evidence <- normalize_text_values(
    assessment$missingEvidence %||% profile_missing_evidence(record$profile, record$capabilities)
  )
  checklist_score <- safe_num(
    qualification_state$checklistScore %||% assessment$oecdChecklistScore,
    profile_oecd_checklist_score(profile_oecd_checklist(record$profile, record$capabilities))
  )

  list(
    objectType = "pbpkQualificationSummary.v1",
    objectId = sprintf("%s-qualification-summary", record$simulation_id),
    simulationId = record$simulation_id,
    backend = record$backend,
    assessmentBoundary = "pbpk-execution-and-qualification-substrate-only",
    decisionBoundary = "no-ngra-decision-policy",
    state = safe_chr(qualification_state$state, "unreported"),
    label = safe_chr(qualification_state$label),
    summary = safe_chr(qualification_state$summary),
    qualificationLevel = safe_chr(
      qualification_state$qualificationLevel %||% assessment$qualificationLevel,
      "unreported"
    ),
    oecdReadiness = safe_chr(assessment$oecdReadiness, "unreported"),
    validationDecision = safe_chr(assessment$decision, "unreported"),
    withinDeclaredContext = safe_lgl(qualification_state$withinDeclaredContext, FALSE),
    scientificProfile = safe_lgl(qualification_state$scientificProfile, FALSE),
    riskAssessmentReady = safe_lgl(qualification_state$riskAssessmentReady, FALSE),
    checklistScore = checklist_score,
    evidenceStatus = safe_chr(qualification_state$evidenceStatus, "unreported"),
    profileSource = safe_chr(record$profile$profileSource$type, "unreported"),
    missingEvidenceCount = as.integer(length(missing_evidence)),
    performanceEvidenceBoundary = safe_chr(performance_evidence$qualificationBoundary),
    executableVerificationStatus = if (isTRUE(executable_verification$included)) {
      safe_chr(executable_verification$status, "unreported")
    } else {
      "not-run"
    },
    supports = list(
      nativeExecution = TRUE,
      manifestValidation = TRUE,
      preflightValidation = TRUE,
      executableVerification = isTRUE(executable_verification$included),
      oecdDossierExport = TRUE,
      typedNgraHandoff = TRUE,
      externalBerHandoff = TRUE,
      regulatoryDecision = FALSE
    ),
    requiredExternalInputs = qualification_required_external_inputs(
      qualification_state = qualification_state,
      performance_evidence = performance_evidence
    ),
    limitations = qualification_limitations_from_record(
      qualification_state = qualification_state,
      performance_evidence = performance_evidence,
      executable_verification = executable_verification
    )
  )
}

uncertainty_summary_from_record <- function(record, uncertainty_evidence = NULL) {
  uncertainty <- record$profile$uncertainty %||% list()
  evidence <- uncertainty_evidence
  if (is.null(evidence)) {
    evidence <- record_uncertainty_evidence(record, limit = 50L)
  }

  row_kinds <- vapply(
    evidence$rows %||% list(),
    function(entry) safe_chr(entry$kind, "unspecified"),
    character(1)
  )

  has_sensitivity <- any(row_kinds == "sensitivity-analysis")
  has_variability_approach <- any(row_kinds == "variability-approach")
  has_variability_propagation <- any(row_kinds == "variability-propagation")
  has_residual_uncertainty <- any(row_kinds == "residual-uncertainty")

  variability_status <- if (has_variability_propagation) {
    "propagated"
  } else if (has_variability_approach) {
    "characterized"
  } else if (!identical(safe_chr(uncertainty$status), "unreported")) {
    "declared-without-structured-variability"
  } else {
    "unreported"
  }

  sensitivity_status <- if (has_sensitivity) {
    "available"
  } else if (!identical(safe_chr(uncertainty$status), "unreported")) {
    "not-bundled"
  } else {
    "unreported"
  }

  residual_status <- if (has_residual_uncertainty) {
    "declared"
  } else if (!identical(safe_chr(uncertainty$status), "unreported")) {
    "not-explicit"
  } else {
    "unreported"
  }

  required_external_inputs <- c(
    "cross-domain uncertainty synthesis outside PBPK MCP"
  )
  if (!has_residual_uncertainty) {
    required_external_inputs <- c(
      required_external_inputs,
      "explicit residual uncertainty register for broader NGRA interpretation"
    )
  }

  list(
    objectType = "uncertaintySummary.v1",
    objectId = sprintf("%s-uncertainty-summary", record$simulation_id),
    simulationId = record$simulation_id,
    backend = record$backend,
    assessmentBoundary = "pbpk-side-uncertainty-summary-only",
    decisionBoundary = "no-ngra-decision-policy",
    status = safe_chr(uncertainty$status, "unreported"),
    summary = safe_chr(uncertainty$summary),
    evidenceSource = safe_chr(evidence$source),
    sources = evidence$sources %||% list(),
    issueCount = as.integer(safe_num(evidence$issueCount, 0)),
    evidenceRowCount = as.integer(safe_num(evidence$returnedRows, 0)),
    totalEvidenceRows = as.integer(safe_num(evidence$totalRows, 0)),
    hasSensitivityAnalysis = has_sensitivity,
    hasVariabilityApproach = has_variability_approach,
    hasVariabilityPropagation = has_variability_propagation,
    hasResidualUncertainty = has_residual_uncertainty,
    variabilityStatus = variability_status,
    sensitivityStatus = sensitivity_status,
    residualUncertaintyStatus = residual_status,
    supports = list(
      qualitativeSummary = !identical(safe_chr(uncertainty$status), "unreported") ||
        safe_num(evidence$returnedRows, 0) > 0,
      sensitivityAnalysis = has_sensitivity,
      variabilityCharacterization = has_variability_approach,
      quantitativePropagation = has_variability_propagation,
      residualUncertaintyTracking = has_residual_uncertainty,
      typedNgraHandoff = TRUE,
      crossDomainUncertaintyRegister = FALSE,
      decisionRecommendation = FALSE
    ),
    requiredExternalInputs = as.list(unique(required_external_inputs)),
    bundleMetadata = evidence$bundleMetadata %||% NULL
  )
}

pk_metric_summary_from_series <- function(series_entry) {
  values <- series_entry$values %||% list()
  if (length(values) == 0) {
    return(list(
      outputPath = safe_chr(series_entry$parameter),
      unit = safe_chr(series_entry$unit, "unitless"),
      pointCount = 0L,
      cmax = NULL,
      tmax = NULL,
      auc0Tlast = NULL,
      aucUnitBasis = NULL
    ))
  }

  times <- suppressWarnings(as.numeric(vapply(values, function(entry) safe_num(entry$time, NA_real_), numeric(1))))
  observations <- suppressWarnings(as.numeric(vapply(values, function(entry) safe_num(entry$value, NA_real_), numeric(1))))
  finite_mask <- is.finite(times) & is.finite(observations)
  times <- times[finite_mask]
  observations <- observations[finite_mask]

  if (length(times) == 0 || length(observations) == 0) {
    return(list(
      outputPath = safe_chr(series_entry$parameter),
      unit = safe_chr(series_entry$unit, "unitless"),
      pointCount = 0L,
      cmax = NULL,
      tmax = NULL,
      auc0Tlast = NULL,
      aucUnitBasis = NULL
    ))
  }

  order_index <- order(times, na.last = NA)
  times <- times[order_index]
  observations <- observations[order_index]
  cmax_index <- which.max(observations)
  auc_value <- NULL
  if (length(times) >= 2) {
    auc_value <- sum(diff(times) * (head(observations, -1) + tail(observations, -1)) / 2)
  }

  list(
    outputPath = safe_chr(series_entry$parameter),
    unit = safe_chr(series_entry$unit, "unitless"),
    pointCount = as.integer(length(observations)),
    cmax = safe_num(observations[[cmax_index]]),
    tmax = safe_num(times[[cmax_index]]),
    auc0Tlast = safe_num(auc_value),
    aucUnitBasis = if (!is.null(safe_chr(series_entry$unit)) && nzchar(safe_chr(series_entry$unit, ""))) {
      sprintf("%s x model-time-axis", safe_chr(series_entry$unit))
    } else {
      "model-output-unit x model-time-axis"
    }
  )
}

internal_exposure_estimate_from_record <- function(record, request = list(), candidate_limit = 25L) {
  request_payload <- request %||% list()
  explicit_results_id <- safe_chr(request_payload$resultsId) %||% safe_chr(request_payload$resultId)
  latest_results_id <- safe_chr(record$metadata$latestResultsId)
  selected_results_id <- explicit_results_id %||% latest_results_id
  source <- if (!is.null(explicit_results_id) && nzchar(explicit_results_id)) {
    "explicit-results-id"
  } else if (!is.null(latest_results_id) && nzchar(latest_results_id)) {
    "latest-deterministic-results"
  } else {
    "none"
  }
  warnings <- character()
  requested_target_output <- safe_chr(request_payload$targetOutput) %||%
    safe_chr(request_payload$outputPath) %||%
    safe_chr(request_payload$output)

  unavailable <- function(reason, ...) {
    extra <- list(...)
    payload <- list(
      objectType = "internalExposureEstimate.v1",
      objectId = sprintf("%s-internal-exposure-estimate", record$simulation_id),
      simulationId = record$simulation_id,
      backend = record$backend,
      assessmentBoundary = "pbpk-side-internal-exposure-estimate-only",
      decisionBoundary = "no-ngra-decision-policy",
      status = "not-available",
      resultsId = selected_results_id,
      source = source,
      selectionReason = reason,
      requestedTargetOutput = requested_target_output,
      candidateOutputCount = 0L,
      candidateOutputs = list(),
      supports = list(
        deterministicMetricSelection = FALSE,
        populationDistributionSummary = FALSE,
        externalBerHandoff = FALSE,
        decisionRecommendation = FALSE
      ),
      warnings = as.list(unique(warnings))
    )
    for (name in names(extra)) {
      payload[[name]] <- extra[[name]]
    }
    payload
  }

  if (is.null(selected_results_id) || !nzchar(selected_results_id)) {
    warnings <- c(warnings, "No deterministic results handle is attached to this simulation context.")
    return(unavailable("missing-results"))
  }

  if (!exists(selected_results_id, envir = results_store, inherits = FALSE)) {
    warnings <- c(warnings, sprintf(
      "Deterministic results handle '%s' is not available in the current runtime.",
      selected_results_id
    ))
    return(unavailable("results-not-found"))
  }

  result <- result_record(selected_results_id)
  if (!identical(safe_chr(result$simulation_id), record$simulation_id)) {
    warnings <- c(warnings, sprintf(
      "Deterministic results handle '%s' belongs to simulation '%s', not '%s'.",
      selected_results_id,
      safe_chr(result$simulation_id, "unknown"),
      record$simulation_id
    ))
    return(unavailable("results-simulation-mismatch"))
  }

  series_entries <- result$series %||% list()
  candidate_summaries <- lapply(series_entries, pk_metric_summary_from_series)
  candidate_count <- length(candidate_summaries)
  if (candidate_count == 0) {
    warnings <- c(warnings, "The referenced deterministic results handle contains no result series.")
    return(unavailable("empty-results"))
  }

  selection_status <- "unresolved"
  selected_summary <- NULL
  if (!is.null(requested_target_output) && nzchar(requested_target_output)) {
    exact_matches <- which(vapply(
      candidate_summaries,
      function(entry) identical(safe_chr(entry$outputPath), requested_target_output),
      logical(1)
    ))
    if (length(exact_matches) == 0) {
      exact_matches <- which(vapply(
        candidate_summaries,
        function(entry) identical(
          tolower(safe_chr(entry$outputPath, "")),
          tolower(requested_target_output)
        ),
        logical(1)
      ))
    }

    if (length(exact_matches) == 1) {
      selected_summary <- candidate_summaries[[exact_matches[[1]]]]
      selection_status <- "explicit"
    } else if (length(exact_matches) > 1) {
      warnings <- c(warnings, sprintf(
        "Requested target output '%s' matched multiple result series.",
        requested_target_output
      ))
      selection_status <- "ambiguous-explicit-target"
    } else {
      warnings <- c(warnings, sprintf(
        "Requested target output '%s' was not found in the stored deterministic results.",
        requested_target_output
      ))
      selection_status <- "missing-explicit-target"
    }
  } else if (candidate_count == 1) {
    selected_summary <- candidate_summaries[[1]]
    selection_status <- "only-series"
  } else {
    warnings <- c(
      warnings,
      "Multiple result series are available; declare request.targetOutput or request.outputPath to resolve a single internal exposure target."
    )
  }

  returned_candidates <- candidate_summaries
  truncated <- FALSE
  if (candidate_count > as.integer(candidate_limit)) {
    returned_candidates <- candidate_summaries[seq_len(as.integer(candidate_limit))]
    truncated <- TRUE
  }

  list(
    objectType = "internalExposureEstimate.v1",
    objectId = sprintf("%s-internal-exposure-estimate", record$simulation_id),
    simulationId = record$simulation_id,
    backend = record$backend,
    assessmentBoundary = "pbpk-side-internal-exposure-estimate-only",
    decisionBoundary = "no-ngra-decision-policy",
    status = "available",
    resultsId = selected_results_id,
    source = source,
    requestedTargetOutput = requested_target_output,
    selectionStatus = selection_status,
    selectedOutput = selected_summary,
    candidateOutputCount = as.integer(candidate_count),
    candidateOutputs = returned_candidates,
    candidateOutputsTruncated = truncated,
    supports = list(
      deterministicMetricSelection = !is.null(selected_summary),
      populationDistributionSummary = FALSE,
      externalBerHandoff = !is.null(selected_summary),
      decisionRecommendation = FALSE
    ),
    warnings = as.list(unique(warnings))
  )
}

pod_metadata_from_request <- function(request = list()) {
  request_payload <- request %||% list()
  pod_payload <- request_payload$pod %||%
    request_payload$pointOfDeparture %||%
    request_payload$point_of_departure %||%
    list()
  if (!is.list(pod_payload)) {
    pod_payload <- list(ref = pod_payload)
  }

  list(
    ref = safe_chr(pod_payload$ref) %||%
      safe_chr(pod_payload$podRef) %||%
      safe_chr(request_payload$podRef) %||%
      safe_chr(request_payload$podReference) %||%
      safe_chr(request_payload$pointOfDepartureRef),
    source = safe_chr(pod_payload$source) %||%
      safe_chr(pod_payload$dataset) %||%
      safe_chr(request_payload$podSource),
    metric = safe_chr(pod_payload$metric) %||%
      safe_chr(pod_payload$comparisonMetric) %||%
      safe_chr(request_payload$podMetric),
    unit = safe_chr(pod_payload$unit) %||%
      safe_chr(request_payload$podUnit),
    basis = safe_chr(pod_payload$basis) %||%
      safe_chr(request_payload$podBasis),
    summary = safe_chr(pod_payload$summary) %||%
      safe_chr(request_payload$podSummary),
    value = safe_num(pod_payload$value %||% request_payload$podValue)
  )
}

true_dose_adjustment_from_request <- function(request = list()) {
  request_payload <- request %||% list()
  true_dose_payload <- request_payload$trueDose %||%
    request_payload$trueDoseAdjustment %||%
    request_payload$true_dose %||%
    list()
  if (!is.list(true_dose_payload)) {
    true_dose_payload <- list(applied = true_dose_payload)
  }

  list(
    applied = safe_lgl(
      true_dose_payload$applied %||%
        true_dose_payload$trueDoseAdjustmentApplied %||%
        request_payload$trueDoseAdjustmentApplied,
      FALSE
    ),
    basis = safe_chr(true_dose_payload$basis) %||%
      safe_chr(true_dose_payload$trueDoseBasis) %||%
      safe_chr(request_payload$trueDoseBasis),
    summary = safe_chr(true_dose_payload$summary) %||%
      safe_chr(request_payload$trueDoseAdjustmentSummary)
  )
}

point_of_departure_reference_from_request <- function(record, request = list()) {
  request_payload <- request %||% list()
  pod_metadata <- pod_metadata_from_request(request_payload)
  true_dose_adjustment <- true_dose_adjustment_from_request(request_payload)
  pod_ref <- safe_chr(pod_metadata$ref)
  attached <- !is.null(pod_ref) && nzchar(pod_ref)
  warnings <- character()

  if (attached &&
      (is.null(pod_metadata$metric) || !nzchar(safe_chr(pod_metadata$metric, "")))) {
    warnings <- c(
      warnings,
      "No explicit PoD metric metadata were attached; downstream BER logic should validate metric compatibility."
    )
  }

  if (isTRUE(true_dose_adjustment$applied) &&
      (is.null(true_dose_adjustment$basis) || !nzchar(safe_chr(true_dose_adjustment$basis, "")))) {
    warnings <- c(
      warnings,
      "True-dose adjustment is marked as applied, but no trueDoseBasis was attached."
    )
  }

  required_external_inputs <- c(
    "PoD interpretation and suitability assessment outside PBPK MCP",
    "BER calculation and decision policy outside PBPK MCP"
  )
  if (!attached) {
    required_external_inputs <- c(required_external_inputs, "external point-of-departure reference")
  }

  list(
    objectType = "pointOfDepartureReference.v1",
    objectId = sprintf("%s-point-of-departure-reference", record$simulation_id),
    simulationId = record$simulation_id,
    backend = record$backend,
    assessmentBoundary = "external-pod-reference-only",
    decisionBoundary = "pod-interpretation-and-ber-policy-owned-by-external-orchestrator",
    decisionOwner = "external-orchestrator",
    status = if (attached) "attached-external-reference" else "not-attached",
    podRef = pod_ref,
    source = safe_chr(pod_metadata$source),
    metric = safe_chr(pod_metadata$metric),
    unit = safe_chr(pod_metadata$unit),
    basis = safe_chr(pod_metadata$basis),
    summary = safe_chr(pod_metadata$summary),
    value = pod_metadata$value %||% NULL,
    trueDoseAdjustment = true_dose_adjustment,
    trueDoseAdjustmentApplied = safe_lgl(true_dose_adjustment$applied, FALSE),
    supports = list(
      typedReference = attached,
      metricMetadataAttached = !is.null(pod_metadata$metric) && nzchar(safe_chr(pod_metadata$metric, "")),
      trueDoseMetadataAttached = !isTRUE(true_dose_adjustment$applied) ||
        (!is.null(true_dose_adjustment$basis) && nzchar(safe_chr(true_dose_adjustment$basis, ""))),
      externalBerCalculation = FALSE,
      decisionRecommendation = FALSE
    ),
    requiredExternalInputs = as.list(unique(required_external_inputs)),
    warnings = as.list(unique(warnings))
  )
}

resolved_internal_exposure_metric <- function(selected_output, comparison_metric) {
  if (is.null(selected_output) || !is.list(selected_output)) {
    return(NULL)
  }

  metric_token <- normalize_context_token(comparison_metric)
  if (is.null(metric_token) || !nzchar(metric_token)) {
    metric_token <- "cmax"
  }

  if (metric_token %in% c("cmax", "maximum-concentration", "max-concentration")) {
    return(list(
      metric = "cmax",
      value = selected_output$cmax %||% NULL,
      unit = safe_chr(selected_output$unit),
      outputPath = safe_chr(selected_output$outputPath)
    ))
  }

  if (metric_token %in% c("tmax", "time-of-maximum-concentration", "time-to-cmax")) {
    return(list(
      metric = "tmax",
      value = selected_output$tmax %||% NULL,
      unit = "model-time-axis",
      outputPath = safe_chr(selected_output$outputPath)
    ))
  }

  if (metric_token %in% c("auc", "auc0-tlast", "auc0tlast", "area-under-curve")) {
    return(list(
      metric = "auc0Tlast",
      value = selected_output$auc0Tlast %||% NULL,
      unit = safe_chr(selected_output$aucUnitBasis),
      outputPath = safe_chr(selected_output$outputPath)
    ))
  }

  NULL
}

ber_input_bundle_from_record <- function(
  record,
  request = list(),
  internal_exposure_estimate = NULL,
  point_of_departure_reference = NULL,
  uncertainty_summary = NULL,
  qualification_summary = NULL
) {
  request_payload <- request %||% list()
  pod_metadata <- pod_metadata_from_request(request_payload)
  pod_ref <- safe_chr(pod_metadata$ref)
  comparison_metric <- safe_chr(
    request_payload$comparisonMetric %||% pod_metadata$metric,
    "cmax"
  )
  true_dose_adjustment <- true_dose_adjustment_from_request(request_payload)
  internal_metric <- resolved_internal_exposure_metric(
    internal_exposure_estimate$selectedOutput %||% NULL,
    comparison_metric
  )
  warnings <- character()
  blocking_reasons <- character()

  if (is.null(internal_exposure_estimate) ||
      !identical(safe_chr(internal_exposure_estimate$status), "available")) {
    blocking_reasons <- c(blocking_reasons, "No deterministic internal exposure estimate is currently attached.")
  } else if (is.null(internal_exposure_estimate$selectedOutput)) {
    blocking_reasons <- c(
      blocking_reasons,
      "An internal exposure result exists, but no single target output is resolved for direct BER comparison."
    )
  }

  if (is.null(pod_ref) || !nzchar(pod_ref)) {
    blocking_reasons <- c(blocking_reasons, "No external point-of-departure reference is attached.")
  }

  if (!is.null(internal_exposure_estimate$selectedOutput) && is.null(internal_metric)) {
    blocking_reasons <- c(
      blocking_reasons,
      sprintf(
        "Comparison metric '%s' is not mapped to a built-in deterministic PBPK exposure metric.",
        comparison_metric
      )
    )
  }

  if (!is.null(pod_ref) && nzchar(pod_ref) &&
      (is.null(pod_metadata$metric) || !nzchar(safe_chr(pod_metadata$metric, "")))) {
    warnings <- c(
      warnings,
      "No explicit PoD metric metadata were attached; downstream BER logic should validate metric compatibility."
    )
  }

  if (isTRUE(true_dose_adjustment$applied) &&
      (is.null(true_dose_adjustment$basis) || !nzchar(safe_chr(true_dose_adjustment$basis, "")))) {
    warnings <- c(
      warnings,
      "True-dose adjustment is marked as applied, but no trueDoseBasis was attached."
    )
  }

  ready <- (length(blocking_reasons) == 0)
  required_external_inputs <- c(
    "BER calculation and decision policy outside PBPK MCP"
  )
  if (is.null(pod_ref) || !nzchar(pod_ref)) {
    required_external_inputs <- c(required_external_inputs, "external point-of-departure reference")
  }
  list(
    objectType = "berInputBundle.v1",
    objectId = sprintf("%s-ber-input-bundle", record$simulation_id),
    simulationId = record$simulation_id,
    backend = record$backend,
    assessmentBoundary = "external-ber-calculation-only",
    decisionBoundary = "ber-calculation-and-decision-owned-by-external-orchestrator",
    decisionOwner = "external-orchestrator",
    status = if (ready) "ready-for-external-ber-calculation" else "incomplete",
    comparisonMetric = comparison_metric,
    internalExposureEstimateRef = internal_exposure_estimate$objectId %||% NULL,
    internalExposureMetric = internal_metric,
    pointOfDepartureReferenceRef = point_of_departure_reference$objectId %||% NULL,
    uncertaintySummaryRef = uncertainty_summary$objectId %||% NULL,
    qualificationSummaryRef = qualification_summary$objectId %||% NULL,
    podRef = pod_ref,
    podMetadata = pod_metadata,
    trueDoseAdjustment = true_dose_adjustment,
    trueDoseAdjustmentApplied = safe_lgl(true_dose_adjustment$applied, FALSE),
    supports = list(
      internalExposureMetricAttached = !is.null(internal_metric),
      externalPodReferenceAttached = !is.null(pod_ref) && nzchar(pod_ref),
      trueDoseMetadataAttached = !isTRUE(true_dose_adjustment$applied) ||
        (!is.null(true_dose_adjustment$basis) && nzchar(safe_chr(true_dose_adjustment$basis, ""))),
      externalBerCalculation = ready,
      decisionRecommendation = FALSE
    ),
    requiredExternalInputs = as.list(unique(required_external_inputs)),
    blockingReasons = as.list(unique(blocking_reasons)),
    warnings = as.list(unique(warnings))
  )
}

build_ngra_objects <- function(
  record,
  request = list(),
  validation = NULL,
  performance_evidence = NULL,
  uncertainty_evidence = NULL,
  executable_verification = NULL,
  include_ber_bundle = FALSE
) {
  resolved_validation <- validation %||% list()
  assessment <- resolved_validation$assessment %||% list()
  resolved_performance_evidence <- performance_evidence
  if (is.null(resolved_performance_evidence)) {
    resolved_performance_evidence <- record_performance_evidence(record, limit = 50L)
  }
  resolved_uncertainty_evidence <- uncertainty_evidence
  if (is.null(resolved_uncertainty_evidence)) {
    resolved_uncertainty_evidence <- record_uncertainty_evidence(record, limit = 50L)
  }
  resolved_executable_verification <- executable_verification
  if (is.null(resolved_executable_verification)) {
    resolved_executable_verification <- record_executable_verification_snapshot(record)
  }

  assessment_context <- assessment_context_from_record(record, request, resolved_validation)
  qualification_summary <- pbpk_qualification_summary_from_record(
    record,
    assessment = assessment,
    performance_evidence = resolved_performance_evidence,
    executable_verification = resolved_executable_verification
  )
  uncertainty_summary <- uncertainty_summary_from_record(
    record,
    uncertainty_evidence = resolved_uncertainty_evidence
  )
  internal_exposure_estimate <- internal_exposure_estimate_from_record(record, request)
  point_of_departure_reference <- point_of_departure_reference_from_request(record, request)

  payload <- list(
    assessmentContext = assessment_context,
    pbpkQualificationSummary = qualification_summary,
    uncertaintySummary = uncertainty_summary,
    internalExposureEstimate = internal_exposure_estimate,
    pointOfDepartureReference = point_of_departure_reference
  )

  if (isTRUE(include_ber_bundle)) {
    payload$berInputBundle <- ber_input_bundle_from_record(
      record,
      request = request,
      internal_exposure_estimate = internal_exposure_estimate,
      point_of_departure_reference = point_of_departure_reference,
      uncertainty_summary = uncertainty_summary,
      qualification_summary = qualification_summary
    )
  }

  payload
}

verification_check <- function(id, label, status, summary = NULL, ...) {
  payload <- list(
    id = safe_chr(id),
    label = safe_chr(label, safe_chr(id)),
    status = safe_chr(status, "unreported"),
    summary = safe_chr(summary)
  )
  extra <- list(...)
  for (name in names(extra)) {
    value <- extra[[name]]
    if (!is.null(value)) {
      payload[[name]] <- value
    }
  }
  payload
}

verification_counts <- function(checks) {
  statuses <- vapply(
    checks %||% list(),
    function(entry) safe_chr(entry$status, "unreported"),
    character(1)
  )
  list(
    checkCount = as.integer(length(statuses)),
    passedCount = as.integer(sum(statuses == "passed")),
    failedCount = as.integer(sum(statuses == "failed")),
    warningCount = as.integer(sum(statuses == "warning")),
    skippedCount = as.integer(sum(statuses == "skipped"))
  )
}

verification_status <- function(counts) {
  if (safe_num(counts$failedCount, 0) > 0) {
    return("failed")
  }
  if (safe_num(counts$warningCount, 0) > 0) {
    return("warning")
  }
  if (safe_num(counts$passedCount, 0) > 0) {
    return("passed")
  }
  "skipped"
}

verification_summary_text <- function(status, counts) {
  total <- as.integer(safe_num(counts$checkCount, 0))
  failed <- as.integer(safe_num(counts$failedCount, 0))
  warning <- as.integer(safe_num(counts$warningCount, 0))
  passed <- as.integer(safe_num(counts$passedCount, 0))
  skipped <- as.integer(safe_num(counts$skippedCount, 0))

  if (identical(status, "failed")) {
    return(sprintf(
      "Verification failed: %d of %d checks failed%s",
      failed,
      total,
      if (warning > 0) sprintf(", with %d warnings", warning) else ""
    ))
  }
  if (identical(status, "warning")) {
    return(sprintf(
      "Verification completed with %d warnings across %d checks",
      warning,
      total
    ))
  }
  if (identical(status, "passed")) {
    return(sprintf("All %d verification checks passed", passed))
  }
  sprintf("No verification checks were executed (%d skipped)", skipped)
}

verification_artifact_id <- function(simulation_id, suffix) {
  sprintf(
    "%s-%s-%s-%06d",
    simulation_id,
    suffix,
    as.integer(as.numeric(Sys.time())),
    sample.int(999999L, 1L)
  )
}

record_parameter_count <- function(record) {
  if (identical(record$backend, "ospsuite")) {
    ensure_ospsuite()
    return(as.integer(length(unique(getAllParameterPathsIn(record$simulation)))))
  }

  catalog_count <- as.integer(length(record$parameter_catalog %||% list()))
  if (catalog_count > 0) {
    return(catalog_count)
  }
  as.integer(length(record$parameters %||% list()))
}

result_integrity_check <- function(result) {
  series <- result$series %||% list()
  if (length(series) == 0) {
    return(verification_check(
      "deterministic-integrity",
      "Deterministic result integrity",
      "failed",
      "Deterministic result payload contains no series",
      totalSeries = 0L,
      totalPoints = 0L,
      emptySeriesCount = 0L,
      nonFinitePointCount = 0L,
      decreasingSeriesCount = 0L,
      duplicateTimeSeriesCount = 0L,
      duplicateParameterCount = 0L
    ))
  }

  total_points <- 0L
  empty_series_count <- 0L
  non_finite_point_count <- 0L
  decreasing_series_count <- 0L
  duplicate_time_series_count <- 0L
  duplicate_parameter_count <- 0L
  parameter_names <- character()

  for (entry in series) {
    parameter <- safe_chr(entry$parameter)
    if (!is.null(parameter) && nzchar(parameter)) {
      parameter_names <- c(parameter_names, parameter)
    }
    values <- entry$values %||% list()
    point_count <- length(values)
    total_points <- total_points + as.integer(point_count)
    if (point_count == 0) {
      empty_series_count <- empty_series_count + 1L
      next
    }

    times <- vapply(values, function(item) safe_num(item$time, NA_real_), numeric(1))
    numbers <- vapply(values, function(item) safe_num(item$value, NA_real_), numeric(1))
    finite_mask <- is.finite(times) & is.finite(numbers)
    if (any(!finite_mask)) {
      non_finite_point_count <- non_finite_point_count + as.integer(sum(!finite_mask))
    }

    if (length(times) > 1 && any(diff(times) < 0, na.rm = TRUE)) {
      decreasing_series_count <- decreasing_series_count + 1L
    }
    if (anyDuplicated(times) > 0) {
      duplicate_time_series_count <- duplicate_time_series_count + 1L
    }
  }

  if (length(parameter_names) > 0) {
    duplicate_parameter_count <- as.integer(sum(duplicated(parameter_names)))
  }

  status <- if (
    empty_series_count > 0L ||
    non_finite_point_count > 0L ||
    decreasing_series_count > 0L ||
    duplicate_parameter_count > 0L
  ) {
    "failed"
  } else if (duplicate_time_series_count > 0L) {
    "warning"
  } else {
    "passed"
  }

  summary <- if (identical(status, "passed")) {
    sprintf(
      "Deterministic result integrity checks passed across %d series and %d points",
      length(series),
      total_points
    )
  } else if (identical(status, "warning")) {
    sprintf(
      "Deterministic result integrity checks found duplicate time points in %d series",
      duplicate_time_series_count
    )
  } else {
    paste(
      "Deterministic result integrity checks failed:",
      sprintf("empty series=%d,", empty_series_count),
      sprintf("non-finite points=%d,", non_finite_point_count),
      sprintf("decreasing time series=%d,", decreasing_series_count),
      sprintf("duplicate parameters=%d", duplicate_parameter_count)
    )
  }

  verification_check(
    "deterministic-integrity",
    "Deterministic result integrity",
    status,
    summary,
    totalSeries = as.integer(length(series)),
    totalPoints = total_points,
    emptySeriesCount = empty_series_count,
    nonFinitePointCount = non_finite_point_count,
    decreasingSeriesCount = decreasing_series_count,
    duplicateTimeSeriesCount = duplicate_time_series_count,
    duplicateParameterCount = duplicate_parameter_count
  )
}

numeric_equal_with_tolerance <- function(lhs, rhs, abs_tol = 1e-8, rel_tol = 1e-6) {
  if (length(lhs) != length(rhs)) {
    return(FALSE)
  }
  if (length(lhs) == 0) {
    return(TRUE)
  }
  if (any(!is.finite(lhs)) || any(!is.finite(rhs))) {
    return(FALSE)
  }
  allowed <- abs_tol + rel_tol * pmax(abs(lhs), abs(rhs), 1)
  all(abs(lhs - rhs) <= allowed)
}

compare_result_series <- function(reference_result, candidate_result, abs_tol = 1e-8, rel_tol = 1e-6) {
  reference_series <- reference_result$series %||% list()
  candidate_series <- candidate_result$series %||% list()
  reference_map <- setNames(reference_series, vapply(reference_series, function(entry) safe_chr(entry$parameter, ""), character(1)))
  candidate_map <- setNames(candidate_series, vapply(candidate_series, function(entry) safe_chr(entry$parameter, ""), character(1)))

  reference_names <- sort(names(reference_map))
  candidate_names <- sort(names(candidate_map))
  if (!identical(reference_names, candidate_names)) {
    missing_in_candidate <- setdiff(reference_names, candidate_names)
    missing_in_reference <- setdiff(candidate_names, reference_names)
    return(verification_check(
      "deterministic-reproducibility",
      "Deterministic reproducibility",
      "failed",
      "Repeated deterministic run returned a different set of result series",
      comparedSeriesCount = as.integer(length(intersect(reference_names, candidate_names))),
      comparedPointCount = 0L,
      missingInRepeat = as.list(missing_in_candidate),
      extraInRepeat = as.list(missing_in_reference)
    ))
  }

  compared_points <- 0L
  unit_mismatch_count <- 0L
  point_count_mismatch_count <- 0L
  time_mismatch_count <- 0L
  value_mismatch_count <- 0L
  max_abs_difference <- 0
  max_rel_difference <- 0

  for (name in reference_names) {
    lhs <- reference_map[[name]]
    rhs <- candidate_map[[name]]

    if (!identical(safe_chr(lhs$unit, "unitless"), safe_chr(rhs$unit, "unitless"))) {
      unit_mismatch_count <- unit_mismatch_count + 1L
      next
    }

    lhs_values <- lhs$values %||% list()
    rhs_values <- rhs$values %||% list()
    if (length(lhs_values) != length(rhs_values)) {
      point_count_mismatch_count <- point_count_mismatch_count + 1L
      next
    }

    lhs_times <- vapply(lhs_values, function(item) safe_num(item$time, NA_real_), numeric(1))
    rhs_times <- vapply(rhs_values, function(item) safe_num(item$time, NA_real_), numeric(1))
    lhs_numbers <- vapply(lhs_values, function(item) safe_num(item$value, NA_real_), numeric(1))
    rhs_numbers <- vapply(rhs_values, function(item) safe_num(item$value, NA_real_), numeric(1))
    compared_points <- compared_points + as.integer(length(lhs_numbers))

    if (!numeric_equal_with_tolerance(lhs_times, rhs_times, abs_tol = abs_tol, rel_tol = rel_tol)) {
      time_mismatch_count <- time_mismatch_count + 1L
      next
    }

    diff_abs <- abs(lhs_numbers - rhs_numbers)
    max_abs_difference <- max(max_abs_difference, max(diff_abs, na.rm = TRUE))
    denom <- pmax(abs(lhs_numbers), abs(rhs_numbers), abs_tol)
    rel_values <- diff_abs / denom
    max_rel_difference <- max(max_rel_difference, max(rel_values, na.rm = TRUE))

    if (!numeric_equal_with_tolerance(lhs_numbers, rhs_numbers, abs_tol = abs_tol, rel_tol = rel_tol)) {
      value_mismatch_count <- value_mismatch_count + 1L
    }
  }

  status <- if (
    unit_mismatch_count > 0L ||
    point_count_mismatch_count > 0L ||
    time_mismatch_count > 0L ||
    value_mismatch_count > 0L
  ) {
    "failed"
  } else {
    "passed"
  }

  summary <- if (identical(status, "passed")) {
    sprintf(
      "Repeated deterministic run matched across %d series and %d points within tolerance",
      length(reference_names),
      compared_points
    )
  } else {
    paste(
      "Repeated deterministic run diverged:",
      sprintf("unit mismatches=%d,", unit_mismatch_count),
      sprintf("point-count mismatches=%d,", point_count_mismatch_count),
      sprintf("time mismatches=%d,", time_mismatch_count),
      sprintf("value mismatches=%d", value_mismatch_count)
    )
  }

  verification_check(
    "deterministic-reproducibility",
    "Deterministic reproducibility",
    status,
    summary,
    comparedSeriesCount = as.integer(length(reference_names)),
    comparedPointCount = compared_points,
    unitMismatchCount = unit_mismatch_count,
    pointCountMismatchCount = point_count_mismatch_count,
    timeMismatchCount = time_mismatch_count,
    valueMismatchCount = value_mismatch_count,
    maxAbsDifference = max_abs_difference,
    maxRelDifference = max_rel_difference,
    absTolerance = abs_tol,
    relTolerance = rel_tol
  )
}

normalize_runtime_verification_checks <- function(raw_checks, prefix = "model-check") {
  artifacts <- list()
  checks <- raw_checks

  if (is.list(raw_checks) &&
      !is.null(raw_checks$checks) &&
      is.list(raw_checks$checks) &&
      (length(raw_checks) == 0 || !"status" %in% names(raw_checks))) {
    checks <- raw_checks$checks
    artifacts <- raw_checks$artifacts %||% list()
  }

  normalized <- list()
  for (index in seq_along(checks %||% list())) {
    entry <- checks[[index]]
    if (!is.list(entry)) {
      next
    }

    payload <- entry
    payload$id <- safe_chr(entry$id) %||%
      safe_chr(entry$checkId) %||%
      safe_chr(entry$check_id) %||%
      sprintf("%s-%03d", prefix, index)
    payload$label <- safe_chr(entry$label) %||%
      safe_chr(entry$checkName) %||%
      safe_chr(entry$check_name) %||%
      payload$id
    payload$status <- safe_chr(entry$status, "unreported")
    payload$summary <- safe_chr(entry$summary) %||%
      safe_chr(entry$message) %||%
      safe_chr(entry$description)
    if (is.null(payload$source)) {
      payload$source <- "pbpk_run_verification_checks"
    }
    normalized[[length(normalized) + 1]] <- payload
  }

  list(checks = normalized, artifacts = artifacts %||% list())
}

record_runtime_verification_checks <- function(
  record,
  request = list(),
  include_population_smoke = FALSE,
  population_cohort = list(),
  population_outputs = list()
) {
  if (!identical(record$backend, "rxode2") ||
      !is.environment(record$module_env) ||
      !exists("pbpk_run_verification_checks", envir = record$module_env, inherits = FALSE)) {
    return(list(checks = list(), artifacts = list(), source = NULL))
  }

  parameter_table <- record_parameter_table(record, limit = 5000L)

  raw_checks <- call_module_hook(
    record$module_env,
    "pbpk_run_verification_checks",
    list(
      parameters = record$parameters,
      parameter_catalog = record$parameter_catalog,
      parameterCatalog = record$parameter_catalog,
      parameter_table = parameter_table,
      parameterTable = parameter_table,
      request = request,
      simulation_id = record$simulation_id,
      simulationId = record$simulation_id,
      metadata = record$metadata,
      capabilities = record$capabilities,
      profile = record$profile,
      file_path = record$file_path,
      filePath = record$file_path,
      include_population_smoke = include_population_smoke,
      includePopulationSmoke = include_population_smoke,
      population_cohort = population_cohort,
      populationCohort = population_cohort,
      population_outputs = population_outputs,
      populationOutputs = population_outputs
    )
  )

  normalized <- normalize_runtime_verification_checks(raw_checks)
  normalized$source <- "pbpk_run_verification_checks"
  normalized
}

build_verification_summary <- function(
  record,
  request = list(),
  validation = NULL,
  include_population_smoke = FALSE,
  population_cohort = list(),
  population_outputs = list()
) {
  request_payload <- request %||% list()
  resolved_validation <- validation
  if (is.null(resolved_validation)) {
    resolved_validation <- if (identical(record$backend, "ospsuite")) {
      ospsuite_validate_record(record, request = request_payload, stage = "run_verification_checks")
    } else {
      rxode_validate_record(record, request = request_payload, stage = "run_verification_checks")
    }
  }

  checks <- list()
  assessment <- resolved_validation$assessment %||% list()
  qualification_state <- assessment$qualificationState %||%
    derive_qualification_state(record$profile, record$capabilities, assessment)

  checks[[length(checks) + 1]] <- verification_check(
    "preflight-validation",
    "Preflight validation",
    if (isTRUE(resolved_validation$ok)) "passed" else "failed",
    safe_chr(
      resolved_validation$summary,
      if (isTRUE(resolved_validation$ok)) {
        "Request is within the declared profile and runtime guardrails"
      } else {
        "Request is outside the declared profile or runtime guardrails"
      }
    ),
    decision = safe_chr(assessment$decision),
    oecdReadiness = safe_chr(assessment$oecdReadiness),
    errorCount = as.integer(length(resolved_validation$errors %||% list())),
    warningCount = as.integer(length(resolved_validation$warnings %||% list()))
  )

  parameter_count <- record_parameter_count(record)
  checks[[length(checks) + 1]] <- verification_check(
    "parameter-catalog",
    "Parameter catalog coverage",
    if (parameter_count > 0) "passed" else "failed",
    if (parameter_count > 0) {
      sprintf("Detected %d exposed parameter paths", parameter_count)
    } else {
      "No exposed parameter paths were detected"
    },
    parameterCount = parameter_count,
    source = if (identical(record$backend, "ospsuite")) {
      "runtime-parameter-introspection"
    } else if (length(record$parameter_catalog %||% list()) > 0) {
      "parameter_catalog"
    } else {
      "default_parameters"
    }
  )

  verification_evidence <- record_verification_evidence(record, limit = 50L)
  evidence_rows <- as.integer(safe_num(verification_evidence$returnedRows, 0))
  checks[[length(checks) + 1]] <- verification_check(
    "verification-evidence",
    "Implementation verification evidence",
    if (evidence_rows > 0) "passed" else "warning",
    if (evidence_rows > 0) {
      sprintf("Returned %d structured implementation-verification evidence rows", evidence_rows)
    } else {
      "No structured implementation-verification evidence rows were returned"
    },
    returnedRows = evidence_rows,
    totalRows = as.integer(safe_num(verification_evidence$totalRows, evidence_rows)),
    source = safe_chr(verification_evidence$source),
    truncated = isTRUE(verification_evidence$truncated)
  )

  if (identical(record$backend, "ospsuite")) {
    output_selection <- ensure_ospsuite_output_selections(record$simulation)
    record$capabilities$outputSelectionMode <- output_selection$mode
    record$capabilities$outputSelectionCount <- output_selection$selectedCount
    if (length(output_selection$selectedPaths) > 0) {
      record$capabilities$runtimeOutputPreview <- utils::head(unlist(output_selection$selectedPaths), 5)
    }
    record$metadata$capabilities <- record$capabilities
    assign(record$simulation_id, record, envir = simulations)

    output_status <- if (safe_num(output_selection$selectedCount, 0) <= 0) {
      "failed"
    } else if (identical(output_selection$mode, "observer-fallback")) {
      "warning"
    } else {
      "passed"
    }
    output_summary <- if (safe_num(output_selection$selectedCount, 0) <= 0) {
      "No output selections are available for deterministic execution"
    } else if (identical(output_selection$mode, "observer-fallback")) {
      sprintf(
        "Auto-selected %d observer-backed outputs because the transfer file declared no OutputSelections",
        as.integer(safe_num(output_selection$selectedCount, 0))
      )
    } else {
      sprintf(
        "Detected %d declared output selections for runtime execution",
        as.integer(safe_num(output_selection$selectedCount, 0))
      )
    }
    checks[[length(checks) + 1]] <- verification_check(
      "output-selection",
      "OSPSuite output selection",
      output_status,
      output_summary,
      outputSelectionMode = safe_chr(output_selection$mode),
      outputSelectionCount = as.integer(safe_num(output_selection$selectedCount, 0))
    )
  }

  artifacts <- list()
  if (isTRUE(resolved_validation$ok)) {
    deterministic_payload <- modifyList(
      request_payload,
      list(
        simulationId = record$simulation_id,
        runId = verification_artifact_id(record$simulation_id, "verify"),
        verification = TRUE
      )
    )
    deterministic_check <- tryCatch(
      {
        run_payload <- handle_run_simulation_sync(deterministic_payload)
        result <- run_payload$result
        series_count <- as.integer(length(result$series %||% list()))
        first_series <- if (series_count > 0) result$series[[1]] else list()
        point_count <- as.integer(length(first_series$values %||% list()))
        artifacts$deterministicResultsId <- result$results_id
        verification_check(
          "deterministic-smoke",
          "Deterministic smoke run",
          if (series_count > 0) "passed" else "warning",
          if (series_count > 0) {
            sprintf("Deterministic smoke run returned %d result series", series_count)
          } else {
            "Deterministic smoke run completed but returned no result series"
          },
          resultsId = safe_chr(result$results_id),
          seriesCount = series_count,
          firstSeriesPointCount = point_count,
          firstParameter = safe_chr(first_series$parameter)
        )
      },
      error = function(exc) {
        verification_check(
          "deterministic-smoke",
          "Deterministic smoke run",
          "failed",
          conditionMessage(exc)
        )
      }
    )
    checks[[length(checks) + 1]] <- deterministic_check
    if (identical(safe_chr(deterministic_check$status), "passed")) {
      first_result <- result_record(safe_chr(deterministic_check$resultsId))
      integrity_check <- result_integrity_check(first_result)
      checks[[length(checks) + 1]] <- integrity_check

      if (!identical(safe_chr(integrity_check$status), "failed")) {
        reproducibility_payload <- modifyList(
          request_payload,
          list(
            simulationId = record$simulation_id,
            runId = verification_artifact_id(record$simulation_id, "verify-repeat"),
            verification = TRUE
          )
        )
        reproducibility_check <- tryCatch(
          {
            rerun_payload <- handle_run_simulation_sync(reproducibility_payload)
            rerun_result <- rerun_payload$result
            artifacts$deterministicRepeatResultsId <- rerun_result$results_id
            compare_result_series(first_result, rerun_result)
          },
          error = function(exc) {
            verification_check(
              "deterministic-reproducibility",
              "Deterministic reproducibility",
              "failed",
              conditionMessage(exc)
            )
          }
        )
        checks[[length(checks) + 1]] <- reproducibility_check
      } else {
        checks[[length(checks) + 1]] <- verification_check(
          "deterministic-reproducibility",
          "Deterministic reproducibility",
          "skipped",
          "Repeated deterministic run was skipped because result-integrity checks failed"
        )
      }
    } else {
      checks[[length(checks) + 1]] <- verification_check(
        "deterministic-integrity",
        "Deterministic result integrity",
        "skipped",
        "Result-integrity checks were skipped because deterministic smoke did not pass"
      )
      checks[[length(checks) + 1]] <- verification_check(
        "deterministic-reproducibility",
        "Deterministic reproducibility",
        "skipped",
        "Repeated deterministic run was skipped because deterministic smoke did not pass"
      )
    }
  } else {
    checks[[length(checks) + 1]] <- verification_check(
      "deterministic-smoke",
      "Deterministic smoke run",
      "skipped",
      "Deterministic smoke run was skipped because preflight validation failed"
    )
    checks[[length(checks) + 1]] <- verification_check(
      "deterministic-integrity",
      "Deterministic result integrity",
      "skipped",
      "Result-integrity checks were skipped because preflight validation failed"
    )
    checks[[length(checks) + 1]] <- verification_check(
      "deterministic-reproducibility",
      "Deterministic reproducibility",
      "skipped",
      "Repeated deterministic run was skipped because preflight validation failed"
    )
  }

  if (isTRUE(include_population_smoke)) {
    if (!identical(record$backend, "rxode2") || !isTRUE(record$capabilities$populationSimulation)) {
      checks[[length(checks) + 1]] <- verification_check(
        "population-smoke",
        "Population smoke run",
        "skipped",
        "Population smoke is only available for rxode2 models that declare population simulation support"
      )
    } else if (!isTRUE(resolved_validation$ok)) {
      checks[[length(checks) + 1]] <- verification_check(
        "population-smoke",
        "Population smoke run",
        "skipped",
        "Population smoke run was skipped because preflight validation failed"
      )
    } else {
      cohort <- population_cohort %||% list()
      if (is.null(cohort$size)) {
        cohort$size <- 10L
      }
      if (is.null(cohort$seed)) {
        cohort$seed <- 42L
      }
      outputs <- population_outputs %||% list()
      if (length(outputs) == 0) {
        outputs <- list(aggregates = list("meanCmax", "sdCmax", "meanAUC"))
      }
      population_payload <- modifyList(
        request_payload,
        list(
          simulationId = record$simulation_id,
          resultsId = verification_artifact_id(record$simulation_id, "verify-pop"),
          cohort = cohort,
          outputs = outputs,
          verification = TRUE
        )
      )
      population_check <- tryCatch(
        {
          run_payload <- handle_run_population_simulation_sync(population_payload)
          result <- run_payload$result
          aggregate_count <- as.integer(length(result$aggregates %||% list()))
          chunk_count <- as.integer(length(result$chunk_handles %||% list()))
          artifacts$populationResultsId <- result$results_id
          verification_check(
            "population-smoke",
            "Population smoke run",
            if (aggregate_count > 0 || chunk_count > 0) "passed" else "warning",
            if (aggregate_count > 0 || chunk_count > 0) {
              sprintf(
                "Population smoke run completed with %d aggregate metrics and %d chunk handles",
                aggregate_count,
                chunk_count
              )
            } else {
              "Population smoke run completed without aggregates or chunk handles"
            },
            resultsId = safe_chr(result$results_id),
            aggregateCount = aggregate_count,
            chunkCount = chunk_count,
            cohortSize = as.integer(safe_num(result$cohort$size, cohort$size %||% 0))
          )
        },
        error = function(exc) {
          verification_check(
            "population-smoke",
            "Population smoke run",
            "failed",
            conditionMessage(exc)
          )
        }
      )
      checks[[length(checks) + 1]] <- population_check
    }
  }

  runtime_verification <- if (isTRUE(resolved_validation$ok)) {
    tryCatch(
      record_runtime_verification_checks(
        record,
        request = request_payload,
        include_population_smoke = include_population_smoke,
        population_cohort = population_cohort,
        population_outputs = population_outputs
      ),
      error = function(exc) {
        list(
          checks = list(
            verification_check(
              "model-runtime-verification",
              "Model-specific runtime verification",
              "failed",
              conditionMessage(exc),
              source = "pbpk_run_verification_checks"
            )
          ),
          artifacts = list(),
          source = "pbpk_run_verification_checks"
        )
      }
    )
  } else {
    list(checks = list(), artifacts = list(), source = NULL)
  }

  if (length(runtime_verification$checks %||% list()) > 0) {
    for (entry in runtime_verification$checks) {
      checks[[length(checks) + 1]] <- entry
    }
  }
  if (length(runtime_verification$artifacts %||% list()) > 0) {
    artifacts <- utils::modifyList(artifacts, runtime_verification$artifacts)
  }

  counts <- verification_counts(checks)
  status <- verification_status(counts)
  list(
    generatedAt = now_utc(),
    status = status,
    summary = verification_summary_text(status, counts),
    requestedPopulationSmoke = isTRUE(include_population_smoke),
    oecdChecklistScore = safe_num(assessment$oecdChecklistScore),
    qualificationState = qualification_state,
    checkCount = counts$checkCount,
    passedCount = counts$passedCount,
    failedCount = counts$failedCount,
    warningCount = counts$warningCount,
    skippedCount = counts$skippedCount,
    checks = checks,
    artifacts = artifacts,
    verificationEvidence = verification_evidence
  )
}

build_oecd_report <- function(
  record,
  request = list(),
  validation = NULL,
  include_parameter_table = TRUE,
  parameter_pattern = NULL,
  parameter_limit = 200L,
  stage = "export_oecd_report"
) {
  resolved_validation <- validation
  if (is.null(resolved_validation)) {
    resolved_validation <- if (identical(record$backend, "ospsuite")) {
      ospsuite_validate_record(record, request = request, stage = stage)
    } else {
      rxode_validate_record(record, request = request, stage = stage)
    }
  }

  assessment <- resolved_validation$assessment %||% list()
  checklist <- assessment$oecdChecklist %||% profile_oecd_checklist(record$profile, record$capabilities)
  checklist_score <- safe_num(
    assessment$oecdChecklistScore,
    profile_oecd_checklist_score(checklist)
  )
  missing_evidence <- assessment$missingEvidence %||%
    as.list(profile_missing_evidence(record$profile, record$capabilities))
  performance_evidence <- record_performance_evidence(record, limit = 200L)
  uncertainty_evidence <- record_uncertainty_evidence(record, limit = 200L)
  verification_evidence <- record_verification_evidence(record, limit = 200L)
  platform_qualification_evidence <- record_platform_qualification_evidence(record, limit = 200L)
  executable_verification <- record_executable_verification_snapshot(record)
  ngra_objects <- build_ngra_objects(
    record,
    request = request,
    validation = resolved_validation,
    performance_evidence = performance_evidence,
    uncertainty_evidence = uncertainty_evidence,
    executable_verification = executable_verification,
    include_ber_bundle = TRUE
  )

  parameter_table <- if (isTRUE(include_parameter_table)) {
    record_parameter_table(
      record,
      pattern = parameter_pattern,
      limit = parameter_limit
    )
  } else {
    list(
      source = NULL,
      included = FALSE,
      pattern = safe_chr(parameter_pattern),
      limit = as.integer(safe_num(parameter_limit, 200)),
      totalRows = 0L,
      matchedRows = 0L,
      returnedRows = 0L,
      truncated = FALSE,
      rows = list()
    )
  }
  oecd_coverage <- build_oecd_coverage(
    record,
    validation = resolved_validation,
    checklist = checklist,
    missing_evidence = missing_evidence,
    performance_evidence = performance_evidence,
    uncertainty_evidence = uncertainty_evidence,
    verification_evidence = verification_evidence,
    platform_qualification_evidence = platform_qualification_evidence,
    executable_verification = executable_verification,
    parameter_table = parameter_table
  )

  list(
    reportVersion = "pbpk-oecd-report.v1",
    generatedAt = now_utc(),
    simulationId = record$simulation_id,
    backend = record$backend,
    qualificationState = assessment$qualificationState %||%
      derive_qualification_state(record$profile, record$capabilities, assessment),
    model = list(
      name = safe_chr(record$metadata$name, basename(record$file_path)),
      filePath = record$file_path,
      modelVersion = safe_chr(record$metadata$modelVersion),
      createdBy = safe_chr(record$metadata$createdBy),
      createdAt = safe_chr(record$metadata$createdAt)
    ),
    capabilities = record$capabilities %||% list(),
    profile = record$profile %||% list(),
    validation = resolved_validation,
    oecdChecklist = checklist,
    oecdChecklistScore = checklist_score,
    oecdCoverage = oecd_coverage,
    missingEvidence = missing_evidence,
    performanceEvidence = performance_evidence,
    uncertaintyEvidence = uncertainty_evidence,
    verificationEvidence = verification_evidence,
    executableVerification = executable_verification,
    platformQualificationEvidence = platform_qualification_evidence,
    ngraObjects = ngra_objects,
    parameterTable = parameter_table
  )
}

normalize_series_payload <- function(series) {
  normalized <- list()
  for (entry in series %||% list()) {
    parameter <- safe_chr(entry$parameter)
    if (is.null(parameter) || !nzchar(parameter)) {
      next
    }
    values <- list()
    for (value_entry in entry$values %||% list()) {
      values[[length(values) + 1]] <- list(
        time = safe_num(value_entry$time, 0),
        value = safe_num(value_entry$value, 0)
      )
    }
    normalized[[length(normalized) + 1]] <- list(
      parameter = parameter,
      unit = safe_chr(entry$unit, "unitless"),
      values = values
    )
  }
  normalized
}

normalize_population_chunk <- function(entry, index) {
  chunk_id <- safe_chr(entry$chunkId) %||% safe_chr(entry$chunk_id) %||% sprintf("chunk-%03d", index)
  subject_range <- entry$subjectRange %||% entry$subject_range %||% NULL
  time_range <- entry$timeRange %||% entry$time_range %||% NULL
  list(
    chunkId = chunk_id,
    subjectRange = if (is.null(subject_range)) NULL else as.integer(unlist(subject_range)),
    timeRange = if (is.null(time_range)) NULL else as.numeric(unlist(time_range)),
    preview = entry$preview %||% NULL,
    payload = entry$payload %||% list()
  )
}

handle_load_simulation <- function(payload) {
  file_path <- safe_chr(payload$filePath)
  simulation_id <- safe_chr(payload$simulationId, tools::file_path_sans_ext(basename(file_path)))
  backend <- detect_backend(file_path)

  if (backend == "ospsuite") {
    ensure_ospsuite()
    capabilities <- ospsuite_capabilities(file_path)
    profile <- ospsuite_profile(file_path, capabilities)
    capabilities$scientificProfile <- identical(safe_chr(profile$profileSource$type), "sidecar")
    capabilities$applicabilityDomain <- profile$applicabilityDomain
    simulation <- loadSimulation(file_path)
    output_selection <- ensure_ospsuite_output_selections(simulation)
    capabilities$outputSelectionMode <- output_selection$mode
    capabilities$outputSelectionCount <- output_selection$selectedCount
    if (length(output_selection$selectedPaths) > 0) {
      capabilities$runtimeOutputPreview <- utils::head(unlist(output_selection$selectedPaths), 5)
    }
    record <- list(
      backend = backend,
      simulation = simulation,
      simulation_id = simulation_id,
      file_path = file_path,
      profile = profile,
      capabilities = capabilities
    )
    validation <- ospsuite_validate_record(
      record,
      request = list(action = "load_simulation", simulationId = simulation_id, filePath = file_path),
      stage = "load_simulation"
    )
    record$metadata <- list(
      name = basename(file_path),
      modelVersion = NULL,
      createdBy = "ospsuite",
      createdAt = now_utc(),
      backend = "ospsuite",
      capabilities = capabilities,
      profile = profile,
      validation = validation
    )
    assign(simulation_id, record, envir = simulations)
    return(list(
      handle = list(
        simulation_id = simulation_id,
        file_path = file_path,
        metadata = record$metadata
      ),
      metadata = record$metadata,
      parameters = list()
    ))
  }

  rxode_model <- load_rxode_model(file_path)
  capabilities <- rxode_capabilities(file_path, rxode_model$module_env, rxode_model$parameter_catalog)
  profile <- rxode_profile(file_path, rxode_model$module_env, capabilities, rxode_model$parameter_catalog)
  capabilities$applicabilityDomain <- profile$applicabilityDomain
  metadata <- rxode_metadata(file_path, rxode_model$module_env)
  metadata$capabilities <- capabilities
  metadata$profile <- profile
  record <- list(
    backend = backend,
    simulation_id = simulation_id,
    file_path = file_path,
    metadata = metadata,
    profile = profile,
    capabilities = capabilities,
    module_env = rxode_model$module_env,
    parameters = rxode_model$parameters,
    parameter_catalog = rxode_model$parameter_catalog
  )
  validation <- rxode_validate_record(
    record,
    request = list(action = "load_simulation", simulationId = simulation_id, filePath = file_path),
    stage = "load_simulation"
  )
  metadata$validation <- validation
  record$metadata <- metadata
  enforce_validation(
    validation,
    sprintf("Default parameters rejected for '%s'", basename(file_path))
  )
  assign(simulation_id, record, envir = simulations)

  parameter_values <- lapply(names(record$parameters), function(path) {
    rxode_parameter_payload(record, path)
  })

  list(
    handle = list(
      simulation_id = simulation_id,
      file_path = file_path,
      metadata = metadata
    ),
    metadata = metadata,
    parameters = parameter_values
  )
}

handle_list_parameters <- function(payload) {
  record <- simulation_record(safe_chr(payload$simulationId))
  if (identical(record$backend, "ospsuite")) {
    ensure_ospsuite()
    paths <- getAllParameterPathsIn(record$simulation)
    pattern <- safe_chr(payload$pattern)
    if (!is.null(pattern) && nzchar(pattern)) {
      paths <- paths[grepl(glob2rx(pattern), paths)]
    }
    parameters <- lapply(paths, function(path) {
      parameter_summary_payload(getParameter(path = path, container = record$simulation))
    })
    return(list(parameters = parameters))
  }

  pattern <- safe_chr(payload$pattern)
  paths <- names(record$parameter_catalog)
  if (!is.null(pattern) && nzchar(pattern)) {
    paths <- paths[grepl(glob2rx(pattern), paths)]
  }
  parameters <- lapply(paths, function(path) {
    entry <- record$parameter_catalog[[path]]
    list(
      path = path,
      display_name = safe_chr(entry$display_name, path),
      unit = safe_chr(entry$unit, "unitless"),
      category = safe_chr(entry$category),
      is_editable = isTRUE(entry$is_editable)
    )
  })
  list(parameters = parameters)
}

handle_get_parameter_value <- function(payload) {
  record <- simulation_record(safe_chr(payload$simulationId))
  if (identical(record$backend, "ospsuite")) {
    ensure_ospsuite()
    parameter <- getParameter(
      path = safe_chr(payload$parameterPath),
      container = record$simulation
    )
    return(list(parameter = parameter_payload(parameter)))
  }

  path <- safe_chr(payload$parameterPath)
  if (!path %in% names(record$parameters)) {
    stop(sprintf("Parameter '%s' not found", path), call. = FALSE)
  }
  list(parameter = rxode_parameter_payload(record, path))
}

handle_set_parameter_value <- function(payload) {
  record <- simulation_record(safe_chr(payload$simulationId))
  if (identical(record$backend, "ospsuite")) {
    ensure_ospsuite()
    path <- safe_chr(payload$parameterPath)
    value <- safe_num(payload$value)
    unit <- safe_chr(payload$unit)
    if (is.null(unit)) {
      setParameterValuesByPath(
        parameterPaths = path,
        values = value,
        simulation = record$simulation
      )
    } else {
      setParameterValuesByPath(
        parameterPaths = path,
        values = value,
        units = unit,
        simulation = record$simulation
      )
    }
    parameter <- getParameter(path = path, container = record$simulation)
    return(list(parameter = parameter_payload(parameter)))
  }

  path <- safe_chr(payload$parameterPath)
  if (!path %in% names(record$parameters)) {
    stop(sprintf("Parameter '%s' not found", path), call. = FALSE)
  }
  candidate_record <- record
  candidate_record$parameters[[path]] <- safe_num(payload$value, record$parameters[[path]])
  if (!is.null(payload$unit) && !is.null(candidate_record$parameter_catalog[[path]])) {
    candidate_record$parameter_catalog[[path]]$unit <- safe_chr(payload$unit, candidate_record$parameter_catalog[[path]]$unit)
  }
  validation <- rxode_validate_record(
    candidate_record,
    request = list(
      action = "set_parameter_value",
      parameterPath = path,
      value = candidate_record$parameters[[path]],
      unit = safe_chr(payload$unit)
    ),
    stage = "set_parameter_value"
  )
  enforce_validation(
    validation,
    sprintf("Parameter update rejected for '%s'", path)
  )
  candidate_record$metadata$validation <- validation
  assign(candidate_record$simulation_id, candidate_record, envir = simulations)
  list(parameter = rxode_parameter_payload(candidate_record, path))
}

handle_run_simulation_sync <- function(payload) {
  record <- simulation_record(safe_chr(payload$simulationId))
  results_id <- safe_chr(payload$runId, sprintf(
    "%s-run-%s",
    record$simulation_id,
    as.integer(as.numeric(Sys.time()))
  ))

  if (identical(record$backend, "ospsuite")) {
    ensure_ospsuite()
    output_selection <- ensure_ospsuite_output_selections(record$simulation)
    existing_output_mode <- safe_chr(record$capabilities$outputSelectionMode)
    if (identical(existing_output_mode, "observer-fallback") && identical(output_selection$mode, "declared")) {
      output_selection$mode <- "observer-fallback"
      output_selection$autoSelectedCount <- safe_num(
        record$capabilities$outputSelectionCount,
        output_selection$selectedCount
      )
      output_selection$candidateCount <- output_selection$candidateCount %||%
        output_selection$selectedCount
      output_selection$selectedPaths <- output_selection$selectedPaths %||%
        (record$capabilities$runtimeOutputPreview %||% list())
    }
    record$capabilities$outputSelectionMode <- output_selection$mode
    record$capabilities$outputSelectionCount <- output_selection$selectedCount
    if (length(output_selection$selectedPaths) > 0) {
      record$capabilities$runtimeOutputPreview <- utils::head(unlist(output_selection$selectedPaths), 5)
    }
    record$metadata$capabilities <- record$capabilities
    validation <- ospsuite_validate_record(
      record,
      request = payload,
      stage = "run_simulation_sync"
    )
    enforce_validation(
      validation,
      sprintf("Simulation request rejected for '%s'", record$simulation_id)
    )
    record$metadata$validation <- validation
    assign(record$simulation_id, record, envir = simulations)
    simulation_results <- suppressWarnings(runSimulation(record$simulation))
    result <- list(
      results_id = results_id,
      simulation_id = record$simulation_id,
      generated_at = now_utc(),
      metadata = list(
        sourceModel = basename(record$file_path),
        engine = "ospsuite",
        outputSelectionMode = output_selection$mode,
        outputSelectionCount = output_selection$selectedCount,
        validation = validation
      ),
      series = series_from_results(simulation_results)
    )
    assign(results_id, result, envir = results_store)
    record$metadata$latestResultsId <- results_id
    record$metadata$latestResultsGeneratedAt <- result$generated_at
    assign(record$simulation_id, record, envir = simulations)
    return(list(result = result))
  }

  validation <- rxode_validate_record(
    record,
    request = payload,
    stage = "run_simulation_sync"
  )
  enforce_validation(
    validation,
    sprintf("Simulation request rejected for '%s'", record$simulation_id)
  )
  record$metadata$validation <- validation
  assign(record$simulation_id, record, envir = simulations)
  raw <- record$module_env$pbpk_run_simulation(
    parameters = record$parameters,
    simulation_id = record$simulation_id,
    run_id = results_id,
    request = payload
  )
  result_metadata <- raw$metadata %||% list(sourceModel = basename(record$file_path), engine = "rxode2")
  result_metadata$validation <- validation
  result <- list(
    results_id = results_id,
    simulation_id = record$simulation_id,
    generated_at = now_utc(),
    metadata = result_metadata,
    series = normalize_series_payload(raw$series)
  )
  assign(results_id, result, envir = results_store)
  record$metadata$latestResultsId <- results_id
  record$metadata$latestResultsGeneratedAt <- result$generated_at
  assign(record$simulation_id, record, envir = simulations)
  list(result = result)
}

handle_get_results <- function(payload) {
  list(result = result_record(safe_chr(payload$resultsId)))
}

handle_validate_simulation_request <- function(payload) {
  record <- simulation_record(safe_chr(payload$simulationId))
  stage <- safe_chr(payload$stage)
  request <- payload$request %||% list()

  validation <- if (identical(record$backend, "ospsuite")) {
    ospsuite_validate_record(record, request = request, stage = stage)
  } else {
    rxode_validate_record(record, request = request, stage = stage)
  }

  record$metadata$validation <- validation
  assign(record$simulation_id, record, envir = simulations)
  ngra_objects <- build_ngra_objects(
    simulation_record(record$simulation_id),
    request = request,
    validation = validation,
    include_ber_bundle = FALSE
  )

  list(
    simulationId = record$simulation_id,
    backend = record$backend,
    validation = validation,
    profile = record$profile,
    capabilities = record$capabilities,
    ngraObjects = ngra_objects
  )
}

handle_run_verification_checks <- function(payload) {
  record <- simulation_record(safe_chr(payload$simulationId))
  request <- payload$request %||% list()
  validation <- if (identical(record$backend, "ospsuite")) {
    ospsuite_validate_record(record, request = request, stage = "run_verification_checks")
  } else {
    rxode_validate_record(record, request = request, stage = "run_verification_checks")
  }

  record$metadata$validation <- validation
  assign(record$simulation_id, record, envir = simulations)

  verification <- build_verification_summary(
    simulation_record(record$simulation_id),
    request = request,
    validation = validation,
    include_population_smoke = safe_lgl(payload$includePopulationSmoke, FALSE),
    population_cohort = payload$populationCohort %||% list(),
    population_outputs = payload$populationOutputs %||% list()
  )

  updated_record <- simulation_record(record$simulation_id)
  updated_record$metadata$verification <- verification
  assign(updated_record$simulation_id, updated_record, envir = simulations)

  list(
    simulationId = updated_record$simulation_id,
    backend = updated_record$backend,
    generatedAt = verification$generatedAt,
    validation = validation,
    profile = updated_record$profile,
    capabilities = updated_record$capabilities,
    verification = verification
  )
}

handle_export_oecd_report <- function(payload) {
  record <- simulation_record(safe_chr(payload$simulationId))
  request <- payload$request %||% list()
  validation <- if (identical(record$backend, "ospsuite")) {
    ospsuite_validate_record(record, request = request, stage = "export_oecd_report")
  } else {
    rxode_validate_record(record, request = request, stage = "export_oecd_report")
  }

  record$metadata$validation <- validation
  assign(record$simulation_id, record, envir = simulations)

  report <- build_oecd_report(
    simulation_record(record$simulation_id),
    request = request,
    validation = validation,
    include_parameter_table = safe_lgl(payload$includeParameterTable, TRUE),
    parameter_pattern = safe_chr(payload$parameterPattern),
    parameter_limit = as.integer(safe_num(payload$parameterLimit, 200))
  )

  list(
    simulationId = record$simulation_id,
    backend = record$backend,
    generatedAt = report$generatedAt,
    ngraObjects = report$ngraObjects %||% list(),
    report = report
  )
}

handle_run_population_simulation_sync <- function(payload) {
  record <- simulation_record(safe_chr(payload$simulationId))
  if (!identical(record$backend, "rxode2")) {
    stop("Population simulations are only implemented for rxode2 models", call. = FALSE)
  }

  results_id <- safe_chr(payload$resultsId, sprintf(
    "%s-pop-%s",
    record$simulation_id,
    as.integer(as.numeric(Sys.time()))
  ))
  cohort <- payload$cohort %||% list()
  outputs <- payload$outputs %||% list()
  validation <- rxode_validate_record(
    record,
    request = payload,
    stage = "run_population_simulation_sync"
  )
  enforce_validation(
    validation,
    sprintf("Population request rejected for '%s'", record$simulation_id)
  )
  record$metadata$validation <- validation
  assign(record$simulation_id, record, envir = simulations)
  raw <- record$module_env$pbpk_run_population(
    parameters = record$parameters,
    simulation_id = record$simulation_id,
    cohort = cohort,
    outputs = outputs,
    request = payload
  )

  chunks <- list()
  for (index in seq_along(raw$chunks %||% list())) {
    chunks[[length(chunks) + 1]] <- normalize_population_chunk(raw$chunks[[index]], index)
  }

  result <- list(
    results_id = results_id,
    simulation_id = record$simulation_id,
    generated_at = now_utc(),
    cohort = list(
      size = as.integer(cohort$size %||% 1),
      sampling = safe_chr(cohort$sampling),
      seed = if (is.null(cohort$seed)) NULL else as.integer(cohort$seed),
      covariates = cohort$covariates %||% list()
    ),
    aggregates = raw$aggregates %||% list(),
    chunk_handles = chunks,
    metadata = {
      result_metadata <- raw$metadata %||% list(sourceModel = basename(record$file_path), engine = "rxode2")
      result_metadata$validation <- validation
      result_metadata
    }
  )
  assign(results_id, result, envir = population_results_store)
  list(result = result)
}

handle_get_population_results <- function(payload) {
  list(result = population_result_record(safe_chr(payload$resultsId)))
}

dispatch <- function(action, payload) {
  switch(
    action,
    load_simulation = handle_load_simulation(payload),
    list_parameters = handle_list_parameters(payload),
    get_parameter_value = handle_get_parameter_value(payload),
    set_parameter_value = handle_set_parameter_value(payload),
    run_simulation_sync = handle_run_simulation_sync(payload),
    get_results = handle_get_results(payload),
    validate_simulation_request = handle_validate_simulation_request(payload),
    run_verification_checks = handle_run_verification_checks(payload),
    export_oecd_report = handle_export_oecd_report(payload),
    run_population_simulation_sync = handle_run_population_simulation_sync(payload),
    get_population_results = handle_get_population_results(payload),
    stop(sprintf("Unsupported action '%s'", action), call. = FALSE)
  )
}

stdin_stream <- file("stdin")
repeat {
  input <- readLines(stdin_stream, n = 1, warn = FALSE)
  if (length(input) == 0) {
    break
  }
  if (!nzchar(trimws(input))) {
    next
  }
  request <- tryCatch(
    fromJSON(input, simplifyVector = FALSE),
    error = function(exc) {
      emit_error("InvalidInput", sprintf("Failed to parse request JSON: %s", exc$message))
      NULL
    }
  )
  if (is.null(request)) {
    next
  }
  action <- safe_chr(request$action)
  payload <- request$payload %||% list()
  response <- tryCatch(
    dispatch(action, payload),
    error = function(exc) {
      message_text <- conditionMessage(exc)
      if (grepl("not loaded|not found", message_text, ignore.case = TRUE)) {
        emit_error("NotFound", message_text)
      } else {
        emit_error("InteropError", message_text)
      }
      NULL
    }
  )
  if (!is.null(response)) {
    emit_json(response)
  }
}
