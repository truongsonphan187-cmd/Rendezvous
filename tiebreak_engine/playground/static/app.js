// =============================================================================
// APP.JS - Interactive State, Real OSRM Road Routes & Visual OMP Pipeline
// =============================================================================

let map = null;
let markersGroup = null;
let routesGroup = null;
let currentPresetData = null;
let presetsCollection = {};
let isPureOmpMode = true; // true: locks k=1.0 (Standard OMP), false: unlocks k > 1.0

const PARTICIPANT_COLORS = [
  "#38bdf8", // Sky Blue
  "#34d399", // Emerald Green
  "#c084fc", // Purple
  "#f472b6", // Pink
  "#fb923c", // Orange
  "#a3e635", // Lime
  "#e879f9", // Fuchsia
];

// Helper for safe DOM queries
const $ = (id) => document.getElementById(id);

// DOM Elements
const presetSelect = $("preset-select");
const runBtn = $("run-btn");
const tabPureOmp = $("tab-pure-omp");
const tabCustomPenalty = $("tab-custom-penalty");
const modeBadge = $("mode-badge");

const exponentSlider = $("exponent-slider");
const exponentVal = $("exponent-val");
const exponentDesc = $("exponent-desc");
const exponentHint = $("exponent-hint");

const fairnessSlider = $("fairness-slider");
const fairnessVal = $("fairness-val");
const fairnessDesc = $("fairness-desc");
const osrmToggle = $("osrm-toggle");

const scenarioDesc = $("scenario-desc");
const tippingBadge = $("tipping-badge");
const flipBanner = $("flip-banner");
const flipTitle = $("flip-title");
const flipDetail = $("flip-detail");

const participantCount = $("participant-count");
const slotCount = $("slot-count");
const participantsList = $("participants-list");
const slotsList = $("slots-list");

const telemetryTime = $("telemetry-time");
const telemetryRouting = $("telemetry-routing");
const winningItineraryNames = $("winning-itinerary-names");
const metricPsi = $("metric-psi");
const metricAvgDist = $("metric-avg-dist");
const metricMaxDist = $("metric-max-dist");

const step1Container = $("step-1-container");
const step2Container = $("step-2-container");
const step3Container = $("step-3-container");
const participantTableBody = $("participant-table-body");
const combinationsTableBody = $("combinations-table-body");

// Initialize Map
function initMap() {
  const mapEl = $("map");
  if (!mapEl) return;
  map = L.map("map", { zoomControl: true }).setView([10.7769, 106.7009], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);

  routesGroup = L.layerGroup().addTo(map);
  markersGroup = L.layerGroup().addTo(map);
}

// Marker Icon Factory
function createCustomIcon(color, label, isWinner = false) {
  const size = isWinner ? 36 : 28;
  const border = isWinner ? "3px solid #fbbf24" : "2px solid #ffffff";
  const shadow = isWinner ? "0 0 12px rgba(251, 191, 36, 0.9)" : "0 2px 5px rgba(0,0,0,0.4)";

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
        cursor: grab;
      ">${label}</div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

// Load Scenario Presets
async function loadPresets() {
  try {
    const res = await fetch("/api/sample-data");
    const data = await res.json();
    presetsCollection = data.presets;

    if (presetSelect) {
      presetSelect.innerHTML = "";
      Object.keys(presetsCollection).forEach((key) => {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = presetsCollection[key].name;
        presetSelect.appendChild(opt);
      });
      selectPreset(presetSelect.value);
    }
  } catch (err) {
    console.error("Failed to load presets:", err);
  }
}

// Select Scenario
function selectPreset(presetKey) {
  const presetRaw = presetsCollection[presetKey];
  if (!presetRaw) return;

  currentPresetData = JSON.parse(JSON.stringify(presetRaw));

  if (scenarioDesc) scenarioDesc.textContent = currentPresetData.description || "";
  if (tippingBadge && currentPresetData.flip_threshold_k) {
    tippingBadge.textContent = `Kèo Lật: k ≈ ${currentPresetData.flip_threshold_k}`;
  }

  // Set default slider values
  if (exponentSlider) {
    if (isPureOmpMode) {
      exponentSlider.value = 1.0;
    } else {
      exponentSlider.value = currentPresetData.default_penalty_exponent || 1.0;
    }
  }
  if (fairnessSlider) {
    fairnessSlider.value = currentPresetData.default_fairness_factor || 0.0;
  }
  updateSliderLabels();

  renderSidebar();
  renderMapMarkers();
  executeOptimization();
}

// Mode Tabs Switch (Pure OMP vs Custom Exponent)
if (tabPureOmp) {
  tabPureOmp.addEventListener("click", () => {
    isPureOmpMode = true;
    tabPureOmp.classList.add("active");
    if (tabCustomPenalty) tabCustomPenalty.classList.remove("active");
    if (modeBadge) modeBadge.textContent = "Standard OMP";

    if (exponentSlider) {
      exponentSlider.value = 1.0;
      exponentSlider.disabled = true;
    }
    if (exponentHint) {
      exponentHint.innerHTML = "Ở chế độ OMP Thuần túy: <b>k khóa cố định ở 1.0</b> (chi phí cá nhân c<sub>i</sub> chính là quãng đường km thực tế theo sách giáo khoa).";
    }
    updateSliderLabels();
    executeOptimization();
  });
}

if (tabCustomPenalty) {
  tabCustomPenalty.addEventListener("click", () => {
    isPureOmpMode = false;
    tabCustomPenalty.classList.add("active");
    if (tabPureOmp) tabPureOmp.classList.remove("active");
    if (modeBadge) modeBadge.textContent = "OMP + Phạt Cấp Số Nhân";

    if (exponentSlider) exponentSlider.disabled = false;
    if (exponentHint) {
      exponentHint.innerHTML = "Mở khóa hệ số lũy thừa k: c<sub>i</sub> = d<sub>i</sub><sup>k</sup>. Khi k > 1.0, người đi xa bị phạt cấp số nhân trước khi tổng hợp OMP.";
    }
    updateSliderLabels();
    executeOptimization();
  });
}

// Update Slider Labels
function updateSliderLabels() {
  const k = exponentSlider ? parseFloat(exponentSlider.value) : 1.0;
  const lambda = fairnessSlider ? parseFloat(fairnessSlider.value) : 0.0;

  if (exponentVal) exponentVal.textContent = k.toFixed(1);
  if (exponentDesc) {
    if (k === 1.0) exponentDesc.textContent = "Bậc 1 (OMP Tuyến tính)";
    else if (k < 1.6) exponentDesc.textContent = "Phạt lũy thừa vừa phải";
    else exponentDesc.textContent = "Phạt cấp số nhân cực mạnh";
  }

  if (fairnessVal) fairnessVal.textContent = lambda.toFixed(1);
  if (fairnessDesc) {
    if (lambda === 0.0) fairnessDesc.textContent = "MinSum (Tổng km ngắn nhất)";
    else if (lambda < 1.0) fairnessDesc.textContent = "Ordered Median cân bằng";
    else fairnessDesc.textContent = "MinMax (Ưu tiên người xa nhất)";
  }
}

// Render Sidebar Lists
function renderSidebar() {
  if (!currentPresetData) return;

  if (participantCount) participantCount.textContent = currentPresetData.participants.length;
  if (participantsList) {
    participantsList.innerHTML = currentPresetData.participants
      .map(
        (p, idx) => `
        <div class="list-item">
          <div>
            <span style="color:${PARTICIPANT_COLORS[idx % PARTICIPANT_COLORS.length]}; margin-right:6px;">👤</span>
            <span class="item-name">${p.name}</span>
          </div>
          <span class="item-coord">${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}</span>
        </div>
      `
      )
      .join("");
  }

  if (slotCount) slotCount.textContent = currentPresetData.slots.length;
  if (slotsList) {
    slotsList.innerHTML = currentPresetData.slots
      .map(
        (slot) => `
        <div style="margin-bottom: 0.5rem;">
          <div style="font-size:0.75rem; color:#94a3b8; font-weight:700; margin-bottom:0.25rem;">
            📅 ${slot.slot_name} (${slot.candidates.length} quán hòa vote)
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
}

// Render Draggable Markers on Leaflet Map
function renderMapMarkers(selectedCandidateIds = []) {
  if (!map || !currentPresetData || !markersGroup) return;
  markersGroup.clearLayers();

  const bounds = [];

  // 1. Participant Homes (Draggable)
  currentPresetData.participants.forEach((p, idx) => {
    const latLng = [p.lat, p.lng];
    bounds.push(latLng);
    const color = PARTICIPANT_COLORS[idx % PARTICIPANT_COLORS.length];

    const marker = L.marker(latLng, {
      icon: createCustomIcon(color, `P${idx + 1}`),
      draggable: true,
    }).bindPopup(`<b>${p.name}</b><br>Kéo thả để đổi tọa độ nhà!`);

    marker.on("dragend", (e) => {
      const newPos = e.target.getLatLng();
      p.lat = newPos.lat;
      p.lng = newPos.lng;
      renderSidebar();
      executeOptimization();
    });

    markersGroup.addLayer(marker);
  });

  // 2. Candidate Places (Draggable)
  currentPresetData.slots.forEach((slot, sIdx) => {
    slot.candidates.forEach((c) => {
      const latLng = [c.lat, c.lng];
      bounds.push(latLng);
      const isWinner = selectedCandidateIds.includes(c.id);
      const color = isWinner ? "#fbbf24" : "#ea580c";
      const iconLabel = isWinner ? "★" : `S${sIdx + 1}`;

      const marker = L.marker(latLng, {
        icon: createCustomIcon(color, iconLabel, isWinner),
        draggable: true,
      }).bindPopup(
        `<b>${c.name}</b><br>${slot.slot_name}${isWinner ? "<br><b style='color:#fbbf24'>🏆 QUÁN CHIẾN THẮNG</b>" : ""}<br>Kéo thả để đổi vị trí quán!`
      );

      marker.on("dragend", (e) => {
        const newPos = e.target.getLatLng();
        c.lat = newPos.lat;
        c.lng = newPos.lng;
        renderSidebar();
        executeOptimization();
      });

      markersGroup.addLayer(marker);
    });
  });

  if (bounds.length > 0 && selectedCandidateIds.length === 0) {
    map.fitBounds(bounds, { padding: [50, 50] });
  }
}

// Draw Real Road Routes from OSRM
function drawRealRoadRoutes(data) {
  if (!routesGroup || !data || !data.selected_combination) return;
  routesGroup.clearLayers();

  const isOsrmActive = osrmToggle ? osrmToggle.checked && !data.fallback_used : false;

  // Shared Itinerary Path
  if (data.shared_itinerary_geometry && data.shared_itinerary_geometry.length > 0) {
    const leafletCoords = data.shared_itinerary_geometry.map((pt) => [pt[1], pt[0]]);
    L.polyline(leafletCoords, {
      color: "#fbbf24",
      weight: 6,
      opacity: 0.9,
    }).addTo(routesGroup);
  }

  // Individual Commute Paths
  data.participant_breakdowns.forEach((p, idx) => {
    const color = PARTICIPANT_COLORS[idx % PARTICIPANT_COLORS.length];

    if (p.outbound_geometry && p.outbound_geometry.length > 0) {
      const outboundCoords = p.outbound_geometry.map((pt) => [pt[1], pt[0]]);
      L.polyline(outboundCoords, {
        color: color,
        weight: 3.5,
        opacity: 0.75,
        dashArray: isOsrmActive ? null : "6, 6",
      }).addTo(routesGroup);
    }

    if (p.inbound_geometry && p.inbound_geometry.length > 0) {
      const inboundCoords = p.inbound_geometry.map((pt) => [pt[1], pt[0]]);
      L.polyline(inboundCoords, {
        color: color,
        weight: 3.5,
        opacity: 0.75,
        dashArray: isOsrmActive ? null : "6, 6",
      }).addTo(routesGroup);
    }
  });
}

// Call Backend TieBreak API
async function executeOptimization() {
  if (!currentPresetData) return;

  if (runBtn) {
    runBtn.disabled = true;
    runBtn.innerHTML = `<span class="btn-icon">⏳</span> Đang tính...`;
  }

  const payload = {
    participants: currentPresetData.participants,
    slots: currentPresetData.slots,
    penalty_exponent: exponentSlider ? parseFloat(exponentSlider.value) : 1.0,
    fairness_factor: fairnessSlider ? parseFloat(fairnessSlider.value) : 0.0,
    enable_osrm: osrmToggle ? osrmToggle.checked : true,
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
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.innerHTML = `<span class="btn-icon">⚡</span> Run Optimization`;
    }
  }
}

// Display Optimization Output & Visual OMP Pipeline
function displayResults(data) {
  const selectedIds = data.selected_combination.map((c) => c.id);

  // Telemetry Tags
  if (telemetryTime) telemetryTime.textContent = `${data.execution_time_ms} ms`;
  if (telemetryRouting) {
    if (data.fallback_used) {
      telemetryRouting.textContent = "Đường chim bay Haversine (1.35x)";
      telemetryRouting.className = "tag tag-warning";
    } else {
      telemetryRouting.textContent = "Đường phố OSRM thực tế";
      telemetryRouting.className = "tag tag-success";
    }
  }

  // Winning Names
  if (winningItineraryNames) {
    winningItineraryNames.innerHTML = data.selected_combination
      .map((c, i) => `<strong>${i + 1}.</strong> ${c.name}`)
      .join("<br>");
  }

  if (metricPsi) metricPsi.textContent = data.total_penalty_score.toFixed(2);

  const bestComboSummary = data.evaluated_combinations[0];
  if (bestComboSummary) {
    if (metricAvgDist) metricAvgDist.textContent = `${bestComboSummary.average_distance_km.toFixed(1)} km`;
    if (metricMaxDist) metricMaxDist.textContent = `${bestComboSummary.max_distance_km.toFixed(1)} km`;
  }

  // Cập nhật Marker trên bản đồ & vẽ đường phố OSRM thực tế
  renderMapMarkers(selectedIds);
  drawRealRoadRoutes(data);

  // Sort by Rank Ascending for OMP Display: c_(1) <= c_(2) <= ... <= c_(N)
  const sortedByRank = [...data.participant_breakdowns].sort((a, b) => a.rank - b.rank);

  // 1. VISUAL STEP 1: Individual Distances
  if (step1Container) {
    step1Container.innerHTML = data.participant_breakdowns
      .map(
        (p) => `
        <div class="step-item">
          <span>👤 ${p.name}</span>
          <code>d = ${p.total_distance_km.toFixed(1)} km</code>
        </div>
      `
      )
      .join("");
  }

  // 2. VISUAL STEP 2: ORDERED Sorting
  if (step2Container) {
    step2Container.innerHTML = sortedByRank
      .map(
        (p) => `
        <div class="step-item">
          <div>
            <span class="step-rank-badge">#${p.rank}</span>
            <span>${p.name}</span>
          </div>
          <div>
            <code>c<sub>(${p.rank})</sub> = ${p.penalized_cost.toFixed(1)}</code>
            <span style="font-size:0.7rem; color:#94a3b8; margin-left:4px;">(w = ${p.rank_weight.toFixed(2)})</span>
          </div>
        </div>
      `
      )
      .join("");
  }

  // 3. VISUAL STEP 3: OMP Aggregator Dot Product
  if (step3Container) {
    let calcTerms = sortedByRank
      .map((p) => `(${p.rank_weight.toFixed(2)} × ${p.penalized_cost.toFixed(1)})`)
      .join(" + ");

    step3Container.innerHTML = `
      <div style="color:#94a3b8; margin-bottom:0.25rem;">Công thức tổng điểm:</div>
      <div style="font-size:0.7rem; color:#38bdf8; word-break:break-all; margin-bottom:0.5rem;">
        &Psi; = ${calcTerms}
      </div>
      <div style="font-size:1.1rem; font-weight:700; color:#fbbf24;">
        &Psi; = ${data.total_penalty_score.toFixed(2)}
      </div>
      <div style="font-size:0.7rem; color:#94a3b8; margin-top:0.25rem;">
        (Tổ hợp đạt điểm phạt thấp nhất là tổ hợp chiến thắng)
      </div>
    `;
  }

  // Render Table 1: Participants
  if (participantTableBody) {
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
  }

  // Render Table 2: Combinations Comparison
  if (combinationsTableBody) {
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
            <td>${isWinner ? '<span class="winner-tag">CHIẾN THẮNG 🏆</span>' : '<span style="color:#94a3b8">Hạng dưới</span>'}</td>
          </tr>
        `;
      })
      .join("");
  }
}

// Event Listeners
if (presetSelect) presetSelect.addEventListener("change", (e) => selectPreset(e.target.value));
if (runBtn) runBtn.addEventListener("click", executeOptimization);

if (exponentSlider) {
  exponentSlider.addEventListener("input", updateSliderLabels);
  exponentSlider.addEventListener("change", executeOptimization);
}

if (fairnessSlider) {
  fairnessSlider.addEventListener("input", updateSliderLabels);
  fairnessSlider.addEventListener("change", executeOptimization);
}

if (osrmToggle) osrmToggle.addEventListener("change", executeOptimization);

// Initialize on Load
window.addEventListener("DOMContentLoaded", () => {
  initMap();
  loadPresets();
});
