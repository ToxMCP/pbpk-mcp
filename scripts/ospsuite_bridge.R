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
          entry$rationale
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
    "peerReview",
    "profileSource"
  )

  for (name in setdiff(names(payload), normalized_sections)) {
    merged[[name]] <- payload[[name]]
  }

  for (name in normalized_sections) {
    merged[[name]] <- normalize_profile_section(payload[[name]], defaults[[name]])
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
  metrics <- performance$goodnessOfFit$metrics %||% list()
  for (index in seq_along(metrics)) {
    entry <- metrics[[index]]
    if (is.character(entry) || is.numeric(entry) || is.logical(entry)) {
      rows[[length(rows) + 1]] <- list(
        id = sprintf("goodness-of-fit-metric-%03d", index),
        kind = "goodness-of-fit-metric",
        metric = safe_chr(entry),
        status = safe_chr(performance$goodnessOfFit$status, "declared")
      )
    } else if (is.list(entry)) {
      rows[[length(rows) + 1]] <- utils::modifyList(
        list(
          id = sprintf("goodness-of-fit-metric-%03d", index),
          kind = "goodness-of-fit-metric",
          status = safe_chr(performance$goodnessOfFit$status, "declared")
        ),
        entry
      )
    }
  }

  goodness_datasets <- normalize_text_values(performance$goodnessOfFit$datasets)
  if (length(goodness_datasets) > 0) {
    for (dataset in goodness_datasets) {
      rows[[length(rows) + 1]] <- list(
        id = sprintf("goodness-of-fit-dataset-%03d", length(rows) + 1),
        kind = "goodness-of-fit-dataset",
        dataset = dataset,
        status = safe_chr(performance$goodnessOfFit$status, "declared")
      )
    }
  }

  predictive_datasets <- normalize_text_values(performance$predictiveChecks$datasets)
  if (length(predictive_datasets) > 0) {
    for (dataset in predictive_datasets) {
      rows[[length(rows) + 1]] <- list(
        id = sprintf("predictive-check-dataset-%03d", length(rows) + 1),
        kind = "predictive-check-dataset",
        dataset = dataset,
        status = safe_chr(performance$predictiveChecks$status, "declared")
      )
    }
  }

  rows
}

performance_metric_count <- function(performance) {
  metrics <- performance$goodnessOfFit$metrics %||% list()
  if (is.null(metrics)) {
    return(0L)
  }
  if (is.list(metrics)) {
    return(length(metrics))
  }
  length(normalize_text_values(metrics))
}

performance_dataset_count <- function(performance) {
  as.integer(length(unique(c(
    normalize_text_values(performance$goodnessOfFit$datasets),
    normalize_text_values(performance$predictiveChecks$datasets),
    normalize_text_values(performance$evaluationData$datasets)
  ))))
}

performance_evidence_count <- function(performance) {
  explicit_count <- safe_num(performance$evidenceCount, 0)
  if (is.finite(explicit_count) && explicit_count > 0) {
    return(as.integer(explicit_count))
  }
  as.integer(length(performance_evidence_rows_from_profile(performance)))
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
  performance_present <- character()
  performance_missing <- character()
  metric_count <- performance_metric_count(performance)
  dataset_count <- performance_dataset_count(performance)
  evidence_count <- performance_evidence_count(performance)
  if (!is_missing_evidence_token(performance$status)) {
    performance_present <- c(performance_present, "status")
  } else {
    performance_missing <- c(performance_missing, "status")
  }
  if (!is_missing_evidence_token(performance$goodnessOfFit$status) &&
      (metric_count > 0 || dataset_count > 0 || evidence_count > 0)) {
    performance_present <- c(performance_present, "goodnessOfFit")
  } else {
    performance_missing <- c(performance_missing, "goodnessOfFit")
  }
  if (!is_missing_evidence_token(performance$predictiveChecks$status) &&
      (dataset_count > 0 || evidence_count > 0)) {
    performance_present <- c(performance_present, "predictiveChecks")
  } else {
    performance_missing <- c(performance_missing, "predictiveChecks")
  }
  if (length(normalize_text_values(performance$targetOutputs)) > 0) {
    performance_present <- c(performance_present, "targetOutputs")
  } else {
    performance_missing <- c(performance_missing, "targetOutputs")
  }
  if (is_limited_evidence_token(performance$status) ||
      is_limited_evidence_token(performance$predictiveChecks$status)) {
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

  verification <- profile$implementationVerification %||% list()
  verification_present <- character()
  verification_missing <- character()
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

  review <- profile$peerReview %||% list()
  review_present <- character()
  review_missing <- character()
  if (!is_unreported_token(review$status)) {
    review_present <- c(review_present, "status")
  } else {
    review_missing <- c(review_missing, "status")
  }
  if (!is.null(review$priorRegulatoryUse)) {
    review_present <- c(review_present, "priorRegulatoryUse")
  } else {
    review_missing <- c(review_missing, "priorRegulatoryUse")
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
  if (is_missing_evidence_token(performance$status)) {
    append_missing("Model performance or predictivity evidence")
  }
  if (performance_metric_count(performance) == 0) {
    append_missing("Formal goodness-of-fit metrics and acceptance criteria")
  }
  if (performance_dataset_count(performance) == 0 && performance_evidence_count(performance) == 0) {
    append_missing("Observed-versus-predicted or predictive evaluation datasets")
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

  verification <- profile$implementationVerification %||% list()
  if (is_unreported_token(verification$status) ||
      length(verification$verifiedChecks %||% list()) == 0) {
    append_missing("Implementation verification evidence")
  }
  for (check in normalize_text_values(verification$missingChecks)) {
    append_missing(check)
  }

  review <- profile$peerReview %||% list()
  if (is_unreported_token(review$status)) {
    append_missing("Peer review or prior use record")
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
             is_limited_evidence_token(profile$modelPerformance$status) ||
             is_limited_evidence_token(profile$modelPerformance$predictiveChecks$status)) {
    warnings[[length(warnings) + 1]] <- list(
      code = "model_performance_evidence_limited",
      message = paste(
        "Model-performance metadata are present, but structured fit or predictive evidence",
        "remain limited for qualification-focused use."
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

  if (is_unreported_token(profile$peerReview$status)) {
    warnings[[length(warnings) + 1]] <- list(
      code = "peer_review_metadata_missing",
      message = "Peer-review or prior-use metadata are not declared for this model.",
      field = "profile.peerReview",
      severity = "warning"
    )
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

    row$provenance_status <- safe_chr(entry$provenance_status) %||%
      safe_chr(entry$provenanceStatus) %||%
      if (length(normalize_text_values(list(
        entry$source,
        entry$sourceType,
        entry$sourceCitation,
        entry$sourceTable,
        entry$evidenceType,
        entry$rationale,
        entry$notes
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
    if (!is.null(entry$value)) {
      row$value <- safe_num(entry$value, 0)
    }
    if (!is.null(entry$observedValue)) {
      row$observedValue <- safe_num(entry$observedValue, 0)
    }
    if (!is.null(entry$predictedValue)) {
      row$predictedValue <- safe_num(entry$predictedValue, 0)
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

  raw_rows <- NULL
  source <- "profile-modelPerformance"
  performance <- record$profile$modelPerformance %||% list()

  if (identical(record$backend, "rxode2") &&
      is.environment(record$module_env) &&
      exists("pbpk_performance_evidence", envir = record$module_env, inherits = FALSE)) {
    raw_rows <- call_module_hook(
      record$module_env,
      "pbpk_performance_evidence",
      list(
        simulation_id = record$simulation_id,
        simulationId = record$simulation_id,
        metadata = record$metadata,
        capabilities = record$capabilities,
        profile = record$profile,
        file_path = record$file_path,
        filePath = record$file_path
      )
    )
    source <- "pbpk_performance_evidence"
  } else {
    raw_rows <- performance_evidence_rows_from_profile(performance)
  }

  rows <- normalize_performance_evidence_rows(raw_rows)
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

record_parameter_table <- function(record, pattern = NULL, limit = 200L) {
  pattern_value <- safe_chr(pattern)
  limit_value <- as.integer(safe_num(limit, 200))
  if (is.na(limit_value) || limit_value < 1) {
    limit_value <- 200L
  }

  raw_rows <- NULL
  source <- "runtime-parameter-enumeration"
  fallback_values <- record$parameters %||% list()

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
  } else if (length(record$parameter_catalog %||% list()) > 0) {
    raw_rows <- unname(record$parameter_catalog)
    source <- "parameter_catalog"
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
  }

  rows <- normalize_parameter_table_rows(raw_rows, fallback_values)
  total_rows <- length(rows)

  if (!is.null(pattern_value) && nzchar(pattern_value)) {
    rows <- Filter(function(entry) {
      isTRUE(grepl(glob2rx(pattern_value), safe_chr(entry$path, "")))
    }, rows)
  }
  matched_rows <- length(rows)

  if (matched_rows > limit_value) {
    rows <- rows[seq_len(limit_value)]
  }

  list(
    source = source,
    included = TRUE,
    pattern = pattern_value,
    limit = limit_value,
    totalRows = total_rows,
    matchedRows = matched_rows,
    returnedRows = length(rows),
    truncated = matched_rows > limit_value,
    rows = rows
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
    missingEvidence = missing_evidence,
    performanceEvidence = performance_evidence,
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

  list(
    simulationId = record$simulation_id,
    backend = record$backend,
    validation = validation,
    profile = record$profile,
    capabilities = record$capabilities
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
    record,
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
