// =============================================================================
// APP.JS - Interactive State, Leaflet Map & Reactive Optimization Engine
// =============================================================================

let map = null;
let markersGroup = null;
let routesGroup = null;
let currentPresetData = null;
let presetsCollection = {};

// DOM Elements
const presetSelect = document.getElementById("preset-select");
const runBtn = document.getElementById("run-btn");
const exponentSlider = document.getElementById("exponent-slider");
const exponentVal = document.getElementById("exponent-val");
const exponentDesc = document.getElementById("exponent-desc");
const fairnessSlider = document.getElementById("fairness-slider");
const fairnessVal = document.getElementById("fairness-val");
const fairnessDesc = document.getElementById("fairness-desc");
const osrmToggle = document.getElementById("osrm-toggle");

const participantCount = document.getElementById("participant-count");
const slotCount = document.getElementById("slot-count");
const participantsList = document.getElementById("participants-list");
const slotsList = document.getElementById("slots-list");

const telemetryTime = document.getElementById("telemetry-time");
const telemetryRouting = document.getElementById("telemetry-routing");
const winningItineraryNames = document.getElementById("winning-itinerary-names");
const metricPsi = document.getElementById("metric-psi");
const metricAvgDist = document.getElementById("metric-avg-dist");
const metricMaxDist = document.getElementById("metric-max-dist");
const mathContent = document.getElementById("math-explanation-content");
const participantTableBody = document.getElementById("participant-table-body");
const combinationsTableBody = document.getElementById("combinations-table-body");

// Initialize Map
function initMap() {
  map = L.map("map", { zoomControl: true }).setView([10.7769, 106.7009], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);

  markersGroup = L.layerGroup().addTo(map);
  routesGroup = L.layerGroup().addTo(map);
}

// Custom Marker Icons
function createCustomIcon(color, label, isWinner = false) {
  const size = isWinner ? 36 : 28;
  const border = isWinner ? "3px solid #fbbf24" : "2px solid #ffffff";
  const shadow = isWinner ? "0 0 10px rgba(251, 191, 36, 0.8)" : "0 2px 5px rgba(0,0,0,0.4)";

  return L.divIcon({
    className: "custom-leaflet-pin",
    html: `
      <div style="
        background-color: ${color};
        width: ${size}px;
        height: ${size}px;
        border-radius: 50%;
        border: ${border};
        box-shadow: ${shadow};
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 700;
        font-size: 11px;
      ">${label}</div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

// Fetch Sample Presets
async function loadPresets() {
  try {
    const res = await fetch("/api/sample-data");
    const data = await res.json();
    presetsCollection = data.presets;

    // Populate dropdown
    presetSelect.innerHTML = "";
    Object.keys(presetsCollection).forEach((key) => {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = presetsCollection[key].name;
      presetSelect.appendChild(opt);
    });

    selectPreset(presetSelect.value);
  } catch (err) {
    console.error("Failed to load presets:", err);
  }
}

// Select and Render Preset
function selectPreset(presetKey) {
  currentPresetData = presetsCollection[presetKey];
  if (!currentPresetData) return;

  // Set default slider values from preset
  exponentSlider.value = currentPresetData.default_penalty_exponent || 1.0;
  fairnessSlider.value = currentPresetData.default_fairness_factor || 0.5;
  updateSliderLabels();

  renderSidebar();
  renderMapMarkers();
  executeOptimization();
}

// Update Slider Text Indicators
function updateSliderLabels() {
  const k = parseFloat(exponentSlider.value);
  const lambda = parseFloat(fairnessSlider.value);

  exponentVal.textContent = k.toFixed(1);
  if (k === 1.0) exponentDesc.textContent = "Linear (Standard OMP)";
  else if (k <= 1.5) exponentDesc.textContent = "Progressive Commute Penalty";
  else exponentDesc.textContent = "Aggressive Outlier Penalty";

  fairnessVal.textContent = lambda.toFixed(1);
  if (lambda === 0.0) fairnessDesc.textContent = "Strict MinSum (Total km)";
  else if (lambda <= 0.8) fairnessDesc.textContent = "Balanced OMP";
  else fairnessDesc.textContent = "Fairness-First / MinMax";
}

// Render Sidebar Lists
function renderSidebar() {
  if (!currentPresetData) return;

  // Participants
  participantCount.textContent = currentPresetData.participants.length;
  participantsList.innerHTML = currentPresetData.participants
    .map(
      (p, idx) => `
      <div class="list-item">
        <div>
          <span style="color:#38bdf8; margin-right:4px;">👤</span>
          <span class="item-name">${p.name}</span>
        </div>
        <span class="item-coord">${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}</span>
      </div>
    `
    )
    .join("");

  // Slots & Candidates
  slotCount.textContent = currentPresetData.slots.length;
  slotsList.innerHTML = currentPresetData.slots
    .map(
      (slot) => `
      <div style="margin-bottom: 0.5rem;">
        <div style="font-size:0.75rem; color:#94a3b8; font-weight:600; margin-bottom:0.25rem;">
          📅 ${slot.slot_name} (${slot.candidates.length} tied)
        </div>
        ${slot.candidates
          .map(
            (c) => `
          <div class="list-item" style="margin-left: 0.5rem; margin-bottom: 0.25rem;">
            <div>
              <span style="color:#f97316; margin-right:4px;">📍</span>
              <span class="item-name">${c.name}</span>
            </div>
            <span class="item-coord">${c.lat.toFixed(4)}, ${c.lng.toFixed(4)}</span>
          </div>
        `
          )
          .join("")}
      </div>
    `
    )
    .join("");
}

// Render Markers on Leaflet Map
function renderMapMarkers(selectedCandidateIds = []) {
  if (!map || !currentPresetData) return;
  markersGroup.clearLayers();

  const bounds = [];

  // 1. Participant Homes
  currentPresetData.participants.forEach((p, idx) => {
    const latLng = [p.lat, p.lng];
    bounds.push(latLng);
    const marker = L.marker(latLng, {
      icon: createCustomIcon("#0284c7", `P${idx + 1}`),
    }).bindPopup(`<b>${p.name}</b><br>Participant Home`);
    markersGroup.addLayer(marker);
  });

  // 2. Candidate Places
  currentPresetData.slots.forEach((slot, sIdx) => {
    slot.candidates.forEach((c) => {
      const latLng = [c.lat, c.lng];
      bounds.push(latLng);
      const isWinner = selectedCandidateIds.includes(c.id);
      const color = isWinner ? "#fbbf24" : "#ea580c";
      const iconLabel = isWinner ? "★" : `S${sIdx + 1}`;

      const marker = L.marker(latLng, {
        icon: createCustomIcon(color, iconLabel, isWinner),
      }).bindPopup(`<b>${c.name}</b><br>${slot.slot_name}${isWinner ? "<br><b>🏆 WINNING CHOICE</b>" : ""}`);
      markersGroup.addLayer(marker);
    });
  });

  if (bounds.length > 0) {
    map.fitBounds(bounds, { padding: [50, 50] });
  }
}

// Draw Route Lines between Participants and Spots
function drawRouteLines(selectedCandidates) {
  routesGroup.clearLayers();
  if (!selectedCandidates || selectedCandidates.length === 0) return;

  const firstSpot = [selectedCandidates[0].lat, selectedCandidates[0].lng];
  const lastSpot = [
    selectedCandidates[selectedCandidates.length - 1].lat,
    selectedCandidates[selectedCandidates.length - 1].lng,
  ];

  // Draw shared itinerary path
  const itineraryPath = selectedCandidates.map((c) => [c.lat, c.lng]);
  if (itineraryPath.length > 1) {
    L.polyline(itineraryPath, {
      color: "#fbbf24",
      weight: 4,
      dashArray: "6, 6",
      opacity: 0.9,
    }).addTo(routesGroup);
  }

  // Draw individual commute lines (Home -> First Spot, Last Spot -> Home)
  currentPresetData.participants.forEach((p, idx) => {
    const home = [p.lat, p.lng];
    // Outbound leg
    L.polyline([home, firstSpot], {
      color: "#38bdf8",
      weight: 2,
      opacity: 0.5,
    }).addTo(routesGroup);
    // Inbound return leg
    L.polyline([lastSpot, home], {
      color: "#34d399",
      weight: 2,
      opacity: 0.5,
    }).addTo(routesGroup);
  });
}

// Call FastAPI TieBreak Resolution
async function executeOptimization() {
  if (!currentPresetData) return;

  runBtn.disabled = true;
  runBtn.innerHTML = `<span class="btn-icon">⏳</span> Computing...`;

  const payload = {
    participants: currentPresetData.participants,
    slots: currentPresetData.slots,
    penalty_exponent: parseFloat(exponentSlider.value),
    fairness_factor: parseFloat(fairnessSlider.value),
    enable_osrm: osrmToggle.checked,
  };

  try {
    const res = await fetch("/api/tiebreak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "API computation failed");
    }

    const data = await res.json();
    displayResults(data);
  } catch (err) {
    alert("Optimization failed: " + err.message);
    console.error(err);
  } finally {
    runBtn.disabled = false;
    runBtn.innerHTML = `<span class="btn-icon">⚡</span> Run Optimization`;
  }
}

// Display Optimization Output & Math
function displayResults(data) {
  const selectedIds = data.selected_combination.map((c) => c.id);

  // Update Telemetry
  telemetryTime.textContent = `${data.execution_time_ms} ms`;
  if (data.fallback_used) {
    telemetryRouting.textContent = "Haversine Fallback (1.35x)";
    telemetryRouting.className = "tag tag-warning";
  } else {
    telemetryRouting.textContent = "OSRM Network Routing";
    telemetryRouting.className = "tag tag-success";
  }

  // Update Winning Cards
  winningItineraryNames.innerHTML = data.selected_combination
    .map((c, i) => `<strong>${i + 1}.</strong> ${c.name}`)
    .join("<br>");

  metricPsi.textContent = data.total_penalty_score.toFixed(2);

  const bestComboSummary = data.evaluated_combinations[0];
  if (bestComboSummary) {
    metricAvgDist.textContent = `${bestComboSummary.average_distance_km.toFixed(1)} km`;
    metricMaxDist.textContent = `${bestComboSummary.max_distance_km.toFixed(1)} km`;
  }

  // Update Markers & Polylines
  renderMapMarkers(selectedIds);
  drawRouteLines(data.selected_combination);

  // Mathematical Step-by-Step Breakdown
  const k = data.applied_parameters.penalty_exponent;
  const lambda = data.applied_parameters.fairness_factor;

  let mathExplanation = `=== MATHEMATICAL STEP-BY-STEP BREAKDOWN ===\n`;
  mathExplanation += `1. Tier 1 Individual Penalties: c_i = (distance_km) ^ ${k.toFixed(1)}\n`;
  mathExplanation += `2. Cost Rank Sorting (Ascending): c_(1) <= c_(2) <= ... <= c_(N)\n`;

  // Sort participant breakdowns by rank
  const sortedByRank = [...data.participant_breakdowns].sort((a, b) => a.rank - b.rank);
  sortedByRank.forEach((p) => {
    mathExplanation += `   - Rank ${p.rank} [${p.name}]: dist = ${p.total_distance_km.toFixed(1)} km  -->  c_i = ${p.penalized_cost.toFixed(2)}  x  w_i = ${p.rank_weight.toFixed(3)}  =  ${p.weighted_score.toFixed(2)}\n`;
  });

  mathExplanation += `\n3. Tier 2 Ordered Median Dot Product:\n`;
  mathExplanation += `   Psi = sum(w_i * c_(i)) = ${data.total_penalty_score.toFixed(2)}\n`;
  mathExplanation += `   (Fairness Factor lambda = ${lambda.toFixed(1)}; Exponent k = ${k.toFixed(1)})\n`;

  mathContent.textContent = mathExplanation;

  // Render Participant Table
  participantTableBody.innerHTML = sortedByRank
    .map(
      (p) => `
      <tr>
        <td><strong>#${p.rank}</strong></td>
        <td>${p.name}</td>
        <td><code>${p.total_distance_km.toFixed(2)} km</code></td>
        <td><code>${p.penalized_cost.toFixed(2)}</code></td>
        <td><span class="mini-tag">${p.rank_weight.toFixed(3)}</span></td>
        <td><strong>${p.weighted_score.toFixed(2)}</strong></td>
      </tr>
    `
    )
    .join("");

  // Render Combinations Comparison Table
  combinationsTableBody.innerHTML = data.evaluated_combinations
    .map((combo, idx) => {
      const isWinner = idx === 0;
      const names = combo.places.map((p) => p.name).join("  ➔  ");
      return `
        <tr class="${isWinner ? "winner-row" : ""}">
          <td><strong>#${idx + 1}</strong></td>
          <td>${names}</td>
          <td><strong>${combo.total_penalty_score.toFixed(2)}</strong></td>
          <td>${combo.average_distance_km.toFixed(2)} km</td>
          <td>${combo.max_distance_km.toFixed(2)} km</td>
          <td>${isWinner ? '<span class="winner-tag">WINNER</span>' : '<span style="color:#94a3b8">Runner-up</span>'}</td>
        </tr>
      `;
    })
    .join("");
}

// Event Listeners
presetSelect.addEventListener("change", (e) => selectPreset(e.target.value));
runBtn.addEventListener("click", executeOptimization);

exponentSlider.addEventListener("input", updateSliderLabels);
exponentSlider.addEventListener("change", executeOptimization);

fairnessSlider.addEventListener("input", updateSliderLabels);
fairnessSlider.addEventListener("change", executeOptimization);

osrmToggle.addEventListener("change", executeOptimization);

// Initialize on Load
window.addEventListener("DOMContentLoaded", () => {
  initMap();
  loadPresets();
});
