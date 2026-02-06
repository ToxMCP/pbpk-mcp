#!/usr/bin/env Rscript

# convert_pksim_to_pkml.R
# Converts .pksim5 projects to .pkml simulation files via snapshots.
# Usage: Rscript scripts/convert_pksim_to_pkml.R <input_file> <output_dir>

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 2) {
  stop("Usage: Rscript scripts/convert_pksim_to_pkml.R <input_file> <output_dir>")
}

input_file <- args[1]
output_dir <- args[2]

if (!file.exists(input_file)) {
  stop(paste("Input file not found:", input_file))
}

if (!dir.exists(output_dir)) {
  dir.create(output_dir, recursive = TRUE)
}

if (!requireNamespace("ospsuite", quietly = TRUE)) {
  stop("The 'ospsuite' R package is required but not installed.")
}

library(ospsuite)
# Note: initPKSim() is available but not required for snapshot conversion

# Function to process a snapshot JSON
process_snapshot <- function(json_path, out_dir) {
  message(paste("Exporting PKML from snapshot:", json_path))
  # runSimulationsFromSnapshot exports to the output directory
  # It creates files named after the simulations in the snapshot
  runSimulationsFromSnapshot(
    json_path,
    output = out_dir,
    exportCSV = FALSE,
    exportPKML = TRUE,
    exportJSON = FALSE,
    exportXML = FALSE
  )
}

# Main logic
ext <- tools::file_ext(input_file)

if (tolower(ext) == "pksim5") {
  message(paste("Converting .pksim5 project to snapshot:", input_file))
  
  # convertSnapshot creates a .json file in the output folder
  # The output argument for convertSnapshot is the folder where json will be saved
  snapshot_dir <- file.path(output_dir, "snapshots")
  if (!dir.exists(snapshot_dir)) dir.create(snapshot_dir)
  
  # convertSnapshot(file, format, output)
  # It creates snapshot JSON files in the output directory
  convertSnapshot(input_file, format = "snapshot", output = snapshot_dir)
  
  # Find the created JSON snapshot files
  snapshots <- list.files(snapshot_dir, pattern = "\\.json$", full.names = TRUE)
  
  if (length(snapshots) == 0) {
    stop("No snapshots were created from the project.")
  }
  
  for (snap in snapshots) {
    process_snapshot(snap, output_dir)
  }
  
} else if (tolower(ext) == "json") {
  # Assume it is already a snapshot
  process_snapshot(input_file, output_dir)
  
} else {
  stop(paste("Unsupported extension:", ext, "- expected .pksim5 or .json"))
}

message("Conversion completed.")
