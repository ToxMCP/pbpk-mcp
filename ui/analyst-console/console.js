const sampleSelect = document.getElementById("sample-select");
const sampleSimulationInput = document.getElementById("sample-simulation");
const loadSampleButton = document.getElementById("load-sample");
const manualSimulationInput = document.getElementById("manual-simulation");
const extractionTextarea = document.getElementById("extraction-json");
const generateManualButton = document.getElementById("generate-manual");
const suggestionsTableBody = document.querySelector("#suggestions-table tbody");
const suggestionSummary = document.getElementById("suggestion-summary");
const messages = document.getElementById("messages");
const captureBaselineButton = document.getElementById("capture-baseline");
const restoreBaselineButton = document.getElementById("restore-baseline");
const baselineStatus = document.getElementById("baseline-status");

let currentSuggestions = [];
let currentSimulationId = "";

if (captureBaselineButton) {
  captureBaselineButton.disabled = true;
}
if (restoreBaselineButton) {
  restoreBaselineButton.disabled = true;
}

function addMessage(text, type = "info") {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${type}`;
  wrapper.textContent = text;
  messages.prepend(wrapper);
  setTimeout(() => wrapper.remove(), 8000);
}

function formatProvenance(provenance) {
  if (!Array.isArray(provenance) || provenance.length === 0) {
    return "-";
  }
  return provenance
    .map((item) => `Component ${item.componentId} (page ${item.page ?? "?"})`)
    .join(", ");
}

async function refreshBaselineStatus() {
  if (!baselineStatus || !captureBaselineButton || !restoreBaselineButton) {
    return;
  }

  if (!currentSimulationId) {
    baselineStatus.textContent = "Load suggestions to capture a baseline snapshot.";
    captureBaselineButton.disabled = true;
    restoreBaselineButton.disabled = true;
    return;
  }

  captureBaselineButton.disabled = false;
  try {
    const response = await fetch(
      `/get_simulation_snapshot?simulationId=${encodeURIComponent(currentSimulationId)}`
    );
    if (!response.ok) {
      throw new Error(`Server responded with ${response.status}`);
    }
    const payload = await response.json();
    const latest = payload.latestSnapshot;
    if (latest) {
      baselineStatus.textContent = `Baseline captured ${latest.createdAt} (snapshot ${latest.snapshotId}).`;
      restoreBaselineButton.disabled = false;
    } else {
      baselineStatus.textContent = "No baseline snapshot captured.";
      restoreBaselineButton.disabled = true;
    }
  } catch (error) {
    console.error(error);
    baselineStatus.textContent = `Baseline status unavailable: ${error.message}`;
    restoreBaselineButton.disabled = true;
  }
}

async function captureBaseline() {
  if (!captureBaselineButton || !currentSimulationId) {
    addMessage("Load suggestions before capturing a baseline.", "error");
    return;
  }

  captureBaselineButton.disabled = true;
  try {
    const response = await fetch("/snapshot_simulation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ simulationId: currentSimulationId }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || payload.error?.message || `Server responded with ${response.status}`);
    }
    const snapshot = payload.snapshot || {};
    addMessage(`Captured baseline snapshot ${snapshot.snapshotId ?? "(unknown)"}.`, "success");
  } catch (error) {
    console.error(error);
    addMessage(`Unable to capture baseline: ${error.message}`, "error");
  }
  await refreshBaselineStatus();
}

async function restoreBaseline() {
  if (!restoreBaselineButton || !currentSimulationId) {
    addMessage("Load suggestions before restoring a baseline.", "error");
    return;
  }

  restoreBaselineButton.disabled = true;
  try {
    const response = await fetch("/restore_simulation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ simulationId: currentSimulationId }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || payload.error?.message || `Server responded with ${response.status}`);
    }
    const snapshot = payload.snapshot || {};
    addMessage(`Restored baseline snapshot ${snapshot.snapshotId ?? "(unknown)"}.`, "success");
  } catch (error) {
    console.error(error);
    addMessage(`Unable to restore baseline: ${error.message}`, "error");
  }
  await refreshBaselineStatus();
}

function renderSuggestions(simulationId, suggestions, extraction) {
  currentSuggestions = suggestions;
  currentSimulationId = simulationId;
  suggestionsTableBody.innerHTML = "";

  suggestionSummary.textContent = suggestions.length
    ? `Simulation ${simulationId} — ${suggestions.length} suggestion(s)`
    : `Simulation ${simulationId} — no actionable suggestions`;

  suggestions.forEach((suggestion, index) => {
    const row = document.createElement("tr");
    const { args, confidence, summary, provenance } = suggestion;
    const value = `${args.value?.toFixed?.(3) ?? args.value} ${args.unit ?? ""}`.trim();

    row.innerHTML = `
      <td data-label="Parameter">${args.parameterPath ?? "?"}</td>
      <td data-label="Value">${value || "-"}</td>
      <td data-label="Confidence">${confidence !== undefined ? confidence.toFixed(2) : "-"}</td>
      <td data-label="Summary">${summary}</td>
      <td data-label="Provenance">${formatProvenance(provenance)}</td>
      <td data-label="Actions">
        <div class="button-group">
          <button class="apply-button" data-index="${index}">Accept</button>
          <button class="reject-button button-secondary" data-index="${index}">Reject</button>
        </div>
      </td>
    `;
    suggestionsTableBody.appendChild(row);
  });

  if (extraction) {
    extractionTextarea.value = JSON.stringify(extraction, null, 2);
    manualSimulationInput.value = simulationId;
  }

  void refreshBaselineStatus();
}

async function loadSamples() {
  try {
    const response = await fetch("/console/api/samples");
    if (!response.ok) {
      throw new Error(`Failed to load samples (${response.status})`);
    }
    const payload = await response.json();
    sampleSelect.innerHTML = "";
    (payload.entries || []).forEach((entry) => {
      const option = document.createElement("option");
      option.value = entry.sourceId;
      option.textContent = entry.label || entry.sourceId;
      sampleSelect.appendChild(option);
    });
  } catch (error) {
    console.error(error);
    addMessage(`Unable to load samples: ${error.message}`, "error");
  }
}

async function fetchSampleSuggestions() {
  const sourceId = sampleSelect.value;
  if (!sourceId) {
    addMessage("Select a sample before loading suggestions.", "error");
    return;
  }
  const simulationId = sampleSimulationInput.value.trim() || "sample-sim";
  try {
    const response = await fetch(
      `/console/api/samples/${encodeURIComponent(sourceId)}/suggestions?simulationId=${encodeURIComponent(
        simulationId
      )}`
    );
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `Server responded with ${response.status}`);
    }
    const payload = await response.json();
    renderSuggestions(payload.simulationId, payload.suggestions || [], payload.extraction);
    addMessage(`Loaded ${payload.suggestions?.length ?? 0} suggestion(s) from ${sourceId}.`, "success");
  } catch (error) {
    console.error(error);
    addMessage(`Unable to load sample suggestions: ${error.message}`, "error");
  }
}

async function generateManualSuggestions() {
  const simulationId = manualSimulationInput.value.trim();
  if (!simulationId) {
    addMessage("Provide a simulation ID for manual generation.", "error");
    return;
  }

  let extraction;
  try {
    extraction = JSON.parse(extractionTextarea.value);
  } catch (error) {
    addMessage("Extraction JSON is invalid. Please provide a valid JSON payload.", "error");
    return;
  }

  try {
    const response = await fetch("/console/api/suggestions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ simulationId, extraction }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `Server responded with ${response.status}`);
    }
    const payload = await response.json();
    renderSuggestions(payload.simulationId, payload.suggestions || [], payload.extraction);
    addMessage(`Generated ${payload.suggestions?.length ?? 0} suggestion(s).`, "success");
  } catch (error) {
    console.error(error);
    addMessage(`Unable to generate suggestions: ${error.message}`, "error");
  }
}

async function sendDecision(index, decision) {
  const suggestion = currentSuggestions[index];
  if (!suggestion) {
    addMessage("Suggestion no longer available.", "error");
    return;
  }

  try {
    const response = await fetch("/console/api/decisions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        decision,
        simulationId: currentSimulationId,
        suggestion,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || `Server responded with ${response.status}`);
    }

    if (decision === "accepted") {
      addMessage(
        `Applied ${suggestion.args.parameterPath} = ${payload.parameter?.value ?? suggestion.args.value} ${payload.parameter?.unit ?? suggestion.args.unit ||
          ""}`,
        "success"
      );
    } else {
      addMessage(`Marked suggestion for ${suggestion.args.parameterPath} as rejected.`, "info");
    }
  } catch (error) {
    console.error(error);
    addMessage(`Unable to submit decision: ${error.message}`, "error");
  }
}

function bindTableActions() {
  suggestionsTableBody.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    if (target.classList.contains("apply-button")) {
      const index = Number(target.dataset.index ?? "-1");
      if (index >= 0) {
        void sendDecision(index, "accepted");
      }
    } else if (target.classList.contains("reject-button")) {
      const index = Number(target.dataset.index ?? "-1");
      if (index >= 0) {
        void sendDecision(index, "rejected");
      }
    }
  });
}

function init() {
  void loadSamples().then(() => {
    if (sampleSelect.options.length > 0) {
      sampleSelect.selectedIndex = 0;
      void fetchSampleSuggestions();
    }
  });

  loadSampleButton.addEventListener("click", () => {
    void fetchSampleSuggestions();
  });

  generateManualButton.addEventListener("click", () => {
    void generateManualSuggestions();
  });

  if (captureBaselineButton) {
    captureBaselineButton.addEventListener("click", () => {
      void captureBaseline();
    });
  }

  if (restoreBaselineButton) {
    restoreBaselineButton.addEventListener("click", () => {
      void restoreBaseline();
    });
  }

  bindTableActions();

  void refreshBaselineStatus();
}

init();
