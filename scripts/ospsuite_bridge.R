#!/usr/bin/env Rscript

# ospsuite_bridge.R
# Robust version with targeted silencing

# ------------------------------------------------------------------------------
# 1. SETUP
# ------------------------------------------------------------------------------
# Silence startup messages
suppressPackageStartupMessages({
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    cat('{"error": {"code": "environment_missing", "message": "R package jsonlite is missing"}}', "\n")
    quit(status = 1)
  }
  library(jsonlite)
})

has_ospsuite <- suppressPackageStartupMessages(requireNamespace("ospsuite", quietly = TRUE))
if (has_ospsuite) {
  suppressPackageStartupMessages(library(ospsuite))
  # Silence init
  invisible(capture.output({
    tryCatch(ospsuite::initOSPSuite(), error = function(e) {})
  }, type = "output"))
  invisible(capture.output({
    tryCatch(ospsuite::initOSPSuite(), error = function(e) {})
  }, type = "message"))
}

# Global state
simulations <- list()
results_cache <- list()

# ------------------------------------------------------------------------------
# 2. HELPERS
# ------------------------------------------------------------------------------
write_response <- function(data) {
  json_data <- jsonlite::toJSON(data, auto_unbox = TRUE, null = "null")
  cat(json_data, "\n")
  flush(stdout())
}

run_silently <- function(expr) {
  # Capture both output and messages to prevent pollution
  # We use a temporary file or connection if needed, but capture.output is easiest
  # Note: capture.output evaluates the expression in a context where output is diverted.
  
  # We return the result of the expression, not the captured text.
  # But capture.output returns the text.
  # So we need to wrap.
  
  res <- NULL
  logs <- capture.output({
    capture.output({
      res <- withVisible(expr)
    }, type = "message")
  }, type = "output")
  
  if (res$visible) {
    return(res$value)
  } else {
    return(invisible(res$value))
  }
}

# ------------------------------------------------------------------------------
# 3. HANDLERS
# ------------------------------------------------------------------------------

handle_load_simulation <- function(payload) {
  if (!has_ospsuite) stop("ospsuite package not available")
  
  file_path <- payload$filePath
  sim_id <- payload$simulationId
  
  if (is.null(file_path) || !file.exists(file_path)) {
    stop(paste("Simulation file not found:", file_path))
  }
  
  # Load with silencing
  sim <- NULL
  # ospsuite::loadSimulation can be chatty
  # We use a simple capture.output wrapper
  junk <- capture.output({
    junk2 <- capture.output({
       sim <- ospsuite::loadSimulation(file_path)
    }, type = "message")
  }, type = "output")
  
  simulations[[sim_id]] <<- sim
  
  list(
    handle = list(
      simulation_id = sim_id,
      file_path = file_path
    ),
    metadata = list(
      loadedAt = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ")
    )
  )
}

handle_list_parameters <- function(payload) {
  if (!has_ospsuite) stop("ospsuite package not available")
  sim_id <- payload$simulationId
  pattern <- payload$pattern
  sim <- simulations[[sim_id]]
  if (is.null(sim)) stop(paste("Simulation not loaded:", sim_id))
  
  all_params <- NULL
  junk <- capture.output({
    all_params <- ospsuite::getAllParametersMatching(paths = "**", container = sim)
  }, type = "output")
  
  params <- list()
  count <- 0
  if (!is.null(pattern) && pattern != "*") {
    for (p in all_params) {
      if (grepl(pattern, p$path, fixed = TRUE)) {
        count <- count + 1
        if (count > 2000) break
        params[[length(params) + 1]] <- list(
          path = p$path,
          display_name = p$name,
          unit = p$unit,
          value = p$value,
          is_editable = p$isEditable
        )
      }
    }
  } else {
    for (p in all_params) {
      count <- count + 1
      if (count > 2000) break
      params[[length(params) + 1]] <- list(
        path = p$path,
        display_name = p$name,
        unit = p$unit,
        value = p$value,
        is_editable = p$isEditable
      )
    }
  }
  list(parameters = params)
}

handle_get_parameter_value <- function(payload) {
  if (!has_ospsuite) stop("ospsuite package not available")
  sim_id <- payload$simulationId
  param_path <- payload$parameterPath
  sim <- simulations[[sim_id]]
  if (is.null(sim)) stop(paste("Simulation not loaded:", sim_id))
  
  param <- ospsuite::getParameter(path = param_path, container = sim)
  if (is.null(param)) stop(paste("Parameter not found:", param_path))
  
  list(
    parameter = list(
      path = param$path,
      value = param$value,
      unit = param$unit,
      display_name = param$name
    )
  )
}

handle_set_parameter_value <- function(payload) {
  if (!has_ospsuite) stop("ospsuite package not available")
  sim_id <- payload$simulationId
  param_path <- payload$parameterPath
  new_value <- payload$value
  new_unit <- payload$unit
  sim <- simulations[[sim_id]]
  if (is.null(sim)) stop(paste("Simulation not loaded:", sim_id))
  
  param <- ospsuite::getParameter(path = param_path, container = sim)
  if (is.null(param)) stop(paste("Parameter not found:", param_path))
  
  junk <- capture.output({
    ospsuite::setParameterValues(parameters = param, values = new_value, units = new_unit)
  })
  
  list(
    parameter = list(
      path = param$path,
      value = param$value,
      unit = param$unit,
      display_name = param$name
    )
  )
}

handle_run_simulation_sync <- function(payload) {
  if (!has_ospsuite) stop("ospsuite package not available")
  sim_id <- payload$simulationId
  run_id <- payload$runId
  if (is.null(run_id)) {
    run_id <- paste0(sim_id, "_", format(Sys.time(), "%s"))
  }
  
  sim <- simulations[[sim_id]]
  if (is.null(sim)) stop(paste("Simulation not loaded:", sim_id))
  
  # Ensure Brain and Blood are outputs
  # We use 'Paracetamol' as the proxy molecule name found in the template
  proxy_mol <- "Paracetamol"
  
  paths_to_add <- c(
    paste0("Organism|Brain|Intracellular|", proxy_mol, "|Concentration"),
    paste0("Organism|ArterialBlood|Plasma|", proxy_mol, "|Concentration")
  )
  
  for (path in paths_to_add) {
    # Try to find the quantity first to verify existence
    q <- ospsuite::getQuantity(path, container = sim)
    if (!is.null(q)) {
      ospsuite::addOutputs(quantities = q, simulation = sim)
    }
  }
  
  results <- NULL
  junk <- capture.output({
    junk2 <- capture.output({
      results <- ospsuite::runSimulations(simulations = list(sim))
    }, type = "message")
  }, type = "output")
  
  result_obj <- results[[1]]
  
  # Extract the paths we explicitly added
  series_list <- list()
  for (path in paths_to_add) {
    vals <- ospsuite::getOutputValues(result_obj, quantitiesOrPaths = path)
    
    # vals$data is a data.frame with Time and the quantity columns
    if (!is.null(vals$data)) {
      time_vec <- vals$data$Time
      val_vec <- vals$data[[path]]
      unit <- vals$metaData[[path]]$unit
      
      # Decimate
      indices <- seq(1, length(time_vec), length.out = min(length(time_vec), 50))
      points <- list()
      for (i in indices) {
        points[[length(points) + 1]] <- list(time = time_vec[i], value = val_vec[i])
      }
      series_list[[length(series_list) + 1]] <- list(
        parameter = path,
        unit = unit,
        values = points
      )
    }
  }
  
  result_payload <- list(
    results_id = run_id,
    simulation_id = sim_id,
    generated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ"),
    series = series_list
  )
  
  results_cache[[run_id]] <<- result_payload
  
  list(result = result_payload)
}

handle_get_results <- function(payload) {
  run_id <- payload$resultsId
  if (is.null(results_cache[[run_id]])) {
    stop(paste("Results not found:", run_id))
  }
  list(result = results_cache[[run_id]])
}

handle_health <- function() {
  list(status = "ok", environment = list(ospsuite = has_ospsuite))
}

# ------------------------------------------------------------------------------
# 4. MAIN LOOP
# ------------------------------------------------------------------------------
input <- file("stdin", "r")
while (TRUE) {
  line <- readLines(input, n = 1, warn = FALSE)
  if (length(line) == 0) break
  
  req <- tryCatch(jsonlite::fromJSON(line), error = function(e) NULL)
  if (is.null(req) || is.null(req$action)) next
  
  response <- tryCatch({
    if (req$action == "load_simulation") {
      handle_load_simulation(req$payload)
    } else if (req$action == "list_parameters") {
      handle_list_parameters(req$payload)
    } else if (req$action == "get_parameter_value") {
      handle_get_parameter_value(req$payload)
    } else if (req$action == "set_parameter_value") {
      handle_set_parameter_value(req$payload)
    } else if (req$action == "run_simulation_sync") {
      handle_run_simulation_sync(req$payload)
    } else if (req$action == "get_results") {
      handle_get_results(req$payload)
    } else if (req$action == "health") {
      handle_health()
    } else {
      stop(paste("Unknown action:", req$action))
    }
  }, error = function(e) {
    list(error = list(code = "execution_error", message = e$message))
  })
  
  write_response(response)
}
close(input)
quit(status = 0)
