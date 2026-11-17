// =============================================================================
// APP.JS - Dynamic Real-Time Ordered Median Sandbox (Add/Remove & Drag Anywhere)
// =============================================================================

let map = null;
let markersGroup = null;
let routesGroup = null;
let isPureOmpMode = true; // true: locks k=1.0 (Standard OMP), false: unlocks k > 1.0
let optDebounceTimer = null;
let lastSelectedCandidateIds = [];

// Palette of 15 vibrant colors for participants
const PARTICIPANT_COLORS = [
  "#38bdf8", // Sky Blue
  "#34d399", // Emerald Green
  "#c084fc", // Purple
  "#f472b6", // Pink
  "#fb923c", // Orange
  "#a3e635", // Lime
  "#e879f9", // Fuchsia
  "#22d3ee", // Cyan
  "#facc15", // Amber
  "#818cf8", // Indigo
  "#4ade80", // Light Green
  "#fb7185", // Rose
  "#67e8f9", // Pale Cyan
  "#fdba74", // Light Orange
  "#d8b4fe", // Light Purple
];

// Helper for safe DOM queries
const $ = (id) => document.getElementById(id);

// =============================================================================
// 1. DEFAULT DATASET (4 Thành viên & 2 Địa điểm Chặng 1 tại TP.HCM)
// =============================================================================
const DEFAULT_PARTICIPANTS = [
  { id: "u1", name: "An (Bình Thạnh)", lat: 10.8120, lng: 106.6980 },
  { id: "u2", name: "Bình (Phú Nhuận)", lat: 10.8020, lng: 106.6800 },
  { id: "u3", name: "Cường (Gò Vấp)", lat: 10.8350, lng: 106.6720 },
  { id: "u4", name: "Dũng (Quận 7 - Bạn ở xa)", lat: 10.7200, lng: 106.7150 },
];

const DEFAULT_SLOTS = [
  {
    slot_id: "slot_1",
    slot_name: "Chặng 1 - Hòa Vote",
    candidates: [
      { id: "cand_bac", name: "Quán 1 (Gò Vấp - Tiện 3 bạn Bắc)", lat: 10.8250, lng: 106.6850 },
      { id: "cand_trungtam", name: "Quán 2 (Quận 3 - Cân bằng)", lat: 10.7780, lng: 106.6890 },
    ],
  },
];

// Active runtime state
let currentData = {
  participants: JSON.parse(JSON.stringify(DEFAULT_PARTICIPANTS)),
  slots: JSON.parse(JSON.stringify(DEFAULT_SLOTS)),
};

// =============================================================================
// 2. MAP INITIALIZATION & PIN ICONS
// =============================================================================
function initMap() {
  const mapEl = $("map");
  if (!mapEl || map) return;

  map = L.map("map", { zoomControl: true }).setView([10.785, 106.695], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);

  routesGroup = L.layerGroup().addTo(map);
  markersGroup = L.layerGroup().addTo(map);

  setTimeout(() => {
    if (map) map.invalidateSize();
  }, 250);
}

function createCustomIcon(color, label, isWinner = false) {
  const size = isWinner ? 36 : 28;
  const border = isWinner ? "3px solid #fbbf24" : "2px solid #ffffff";
  const shadow = isWinner ? "0 0 14px rgba(251, 191, 36, 1)" : "0 2px 6px rgba(0,0,0,0.45)";

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
        color: ${isWinner ? "#0f172a" : "#ffffff"};
        font-weight: 800;
        font-size: ${isWinner ? "13px" : "11px"};
        cursor: grab;
      ">${label}</div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

// =============================================================================
// 3. RENDER MAP MARKERS (RETURNS DICT OF MARKERS BY ID)
// =============================================================================
function renderMapMarkers() {
  if (!map || !markersGroup) return {};
  markersGroup.clearLayers();

  const createdMarkers = {};
  const bounds = [];

  // 1. Participant Homes (P1, P2...)
  currentData.participants.forEach((p, idx) => {
    const latLng = [p.lat, p.lng];
    bounds.push(latLng);
    const color = PARTICIPANT_COLORS[idx % PARTICIPANT_COLORS.length];

    const marker = L.marker(latLng, {
      icon: createCustomIcon(color, `P${idx + 1}`),
      draggable: true,
    }).bindPopup(`<b>👤 ${p.name}</b><br>Kéo thả icon để thay đổi vị trí nhà!`);

    marker.on("dragend", (e) => {
      const newPos = e.target.getLatLng();
      p.lat = parseFloat(newPos.lat.toFixed(4));
      p.lng = parseFloat(newPos.lng.toFixed(4));
      updateCoordLabels();
      scheduleOptimization(60);
    });

    markersGroup.addLayer(marker);
    createdMarkers[p.id] = marker;
  });

  // 2. Candidate Venues (C1, C2... or ★ if Winner)
  const slot = currentData.slots[0];
  if (slot && slot.candidates) {
    slot.candidates.forEach((c, idx) => {
      const latLng = [c.lat, c.lng];
      bounds.push(latLng);
      const isWinner = lastSelectedCandidateIds.includes(c.id);
      const color = isWinner ? "#fbbf24" : "#ea580c";
      const iconLabel = isWinner ? "★" : `C${idx + 1}`;

      const marker = L.marker(latLng, {
        icon: createCustomIcon(color, iconLabel, isWinner),
        draggable: true,
      }).bindPopup(
        `<b>📍 ${c.name}</b>${isWinner ? "<br><b style='color:#fbbf24'>🏆 ĐỊA ĐIỂM CHIẾN THẮNG</b>" : ""}<br>Kéo thả icon để thay đổi vị trí quán!`
      );

      marker.on("dragend", (e) => {
        const newPos = e.target.getLatLng();
        c.lat = parseFloat(newPos.lat.toFixed(4));
        c.lng = parseFloat(newPos.lng.toFixed(4));
        updateCoordLabels();
        scheduleOptimization(60);
      });

      markersGroup.addLayer(marker);
      createdMarkers[c.id] = marker;
    });
  }

  return createdMarkers;
}

// Update coordinate text in sidebar
function updateCoordLabels() {
  currentData.participants.forEach((p, idx) => {
    const el = $(`coord-p-${idx}`);
    if (el) el.textContent = `${p.lat.toFixed(3)}, ${p.lng.toFixed(3)}`;
  });
  const slot = currentData.slots[0];
  if (slot) {
    slot.candidates.forEach((c, idx) => {
      const el = $(`coord-c-${idx}`);
      if (el) el.textContent = `${c.lat.toFixed(3)}, ${c.lng.toFixed(3)}`;
    });
  }
}

// =============================================================================
// 4. DRAW ROAD ROUTES VIA OSRM
// =============================================================================
function drawRealRoadRoutes(data) {
  if (!routesGroup || !data || !data.selected_combination) return;
  routesGroup.clearLayers();

  const isOsrmActive = $("osrm-toggle") ? $("osrm-toggle").checked && !data.fallback_used : false;

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
        opacity: 0.8,
        dashArray: isOsrmActive ? null : "6, 6",
      }).addTo(routesGroup);
    }

    if (p.inbound_geometry && p.inbound_geometry.length > 0) {
      const inboundCoords = p.inbound_geometry.map((pt) => [pt[1], pt[0]]);
      L.polyline(inboundCoords, {
        color: color,
        weight: 3.5,
        opacity: 0.8,
        dashArray: isOsrmActive ? null : "6, 6",
      }).addTo(routesGroup);
    }
  });
}

// =============================================================================
// 5. SIDEBAR MANAGEMENT: RENDER LISTS, ADD, EDIT & DELETE
// =============================================================================
function renderSidebarLists() {
  // 1. Participant List
  const pList = $("participants-list");
  if (pList) {
    pList.innerHTML = currentData.participants
      .map((p, idx) => {
        const color = PARTICIPANT_COLORS[idx % PARTICIPANT_COLORS.length];
        const canDelete = currentData.participants.length > 2;
        return `
          <div class="entity-row" id="entity-p-${p.id}">
            <div class="entity-left">
              <span class="entity-badge" style="background-color: ${color}">P${idx + 1}</span>
              <input type="text" class="entity-input p-input" data-idx="${idx}" value="${p.name}" title="Click để sửa tên" />
            </div>
            <div class="entity-right">
              <span class="entity-coord-tag" id="coord-p-${idx}">${p.lat.toFixed(3)}, ${p.lng.toFixed(3)}</span>
              <button class="btn-del" data-idx="${idx}" title="Xóa thành viên này" ${canDelete ? "" : "disabled"}>✕</button>
            </div>
          </div>
        `;
      })
      .join("");

    pList.querySelectorAll(".p-input").forEach((inp) => {
      inp.addEventListener("change", (e) => {
        const idx = parseInt(e.target.getAttribute("data-idx"));
        const newName = e.target.value.trim();
        if (newName && currentData.participants[idx]) {
          currentData.participants[idx].name = newName;
          renderMapMarkers();
          scheduleOptimization(50);
        }
      });
    });

    pList.querySelectorAll(".btn-del").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const idx = parseInt(e.currentTarget.getAttribute("data-idx"));
        deleteParticipant(idx);
      });
    });
  }

  // 2. Candidate Places List
  const slot = currentData.slots[0];
  const cList = $("candidates-list");
  if (cList && slot) {
    cList.innerHTML = slot.candidates
      .map((c, idx) => {
        const isWinner = lastSelectedCandidateIds.includes(c.id);
        const canDelete = slot.candidates.length > 2;
        return `
          <div class="entity-row" id="entity-c-${c.id}">
            <div class="entity-left">
              <span class="entity-badge badge-cand ${isWinner ? "badge-winner" : ""}">
                ${isWinner ? "★" : "C" + (idx + 1)}
              </span>
              <input type="text" class="entity-input c-input" data-idx="${idx}" value="${c.name}" title="Click để sửa tên" />
            </div>
            <div class="entity-right">
              <span class="entity-coord-tag" id="coord-c-${idx}">${c.lat.toFixed(3)}, ${c.lng.toFixed(3)}</span>
              <button class="btn-del-cand" data-idx="${idx}" title="Xóa địa điểm này" ${canDelete ? "" : "disabled"}>✕</button>
            </div>
          </div>
        `;
      })
      .join("");

    cList.querySelectorAll(".c-input").forEach((inp) => {
      inp.addEventListener("change", (e) => {
        const idx = parseInt(e.target.getAttribute("data-idx"));
        const newName = e.target.value.trim();
        if (newName && slot.candidates[idx]) {
          slot.candidates[idx].name = newName;
          renderMapMarkers();
          scheduleOptimization(50);
        }
      });
    });

    cList.querySelectorAll(".btn-del-cand").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const idx = parseInt(e.currentTarget.getAttribute("data-idx"));
        deleteCandidate(idx);
      });
    });
  }
}

// Add Participant
function addParticipant() {
  const count = currentData.participants.length + 1;
  const center = map ? map.getCenter() : { lat: 10.785, lng: 106.695 };
  const offsetLat = (Math.random() - 0.5) * 0.035;
  const offsetLng = (Math.random() - 0.5) * 0.035;

  const newP = {
    id: `u_${Date.now()}`,
    name: `Bạn ${count} (Mới)`,
    lat: parseFloat((center.lat + offsetLat).toFixed(4)),
    lng: parseFloat((center.lng + offsetLng).toFixed(4)),
  };

  currentData.participants.push(newP);
  renderSidebarLists();
  const createdMarkers = renderMapMarkers();

  // Focus map on newly created marker and open popup!
  if (map && createdMarkers && createdMarkers[newP.id]) {
    map.panTo([newP.lat, newP.lng], { animate: true, duration: 0.5 });
    createdMarkers[newP.id].openPopup();
  }

  // Scroll to new row in sidebar and flash
  const newRow = $(`entity-p-${newP.id}`);
  if (newRow) {
    newRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
    newRow.classList.add("highlight-flash");
  }

  scheduleOptimization(50);
}

// Delete Participant
function deleteParticipant(idx) {
  if (currentData.participants.length <= 2) {
    alert("Nhóm cần tối thiểu 2 thành viên để tính toán công bằng!");
    return;
  }
  currentData.participants.splice(idx, 1);
  renderSidebarLists();
  renderMapMarkers();
  scheduleOptimization(50);
}

// Add Candidate
function addCandidate() {
  const slot = currentData.slots[0];
  if (!slot) return;

  const count = slot.candidates.length + 1;
  const center = map ? map.getCenter() : { lat: 10.785, lng: 106.695 };
  const offsetLat = (Math.random() - 0.5) * 0.035;
  const offsetLng = (Math.random() - 0.5) * 0.035;

  const newC = {
    id: `cand_${Date.now()}`,
    name: `Địa điểm ${count} (Ứng viên mới)`,
    lat: parseFloat((center.lat + offsetLat).toFixed(4)),
    lng: parseFloat((center.lng + offsetLng).toFixed(4)),
  };

  slot.candidates.push(newC);
  renderSidebarLists();
  const createdMarkers = renderMapMarkers();

  // Focus map on newly created candidate and open popup!
  if (map && createdMarkers && createdMarkers[newC.id]) {
    map.panTo([newC.lat, newC.lng], { animate: true, duration: 0.5 });
    createdMarkers[newC.id].openPopup();
  }

  // Scroll to new row in sidebar and flash
  const newRow = $(`entity-c-${newC.id}`);
  if (newRow) {
    newRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
    newRow.classList.add("highlight-flash");
  }

  scheduleOptimization(50);
}

// Delete Candidate
function deleteCandidate(idx) {
  const slot = currentData.slots[0];
  if (!slot) return;

  if (slot.candidates.length <= 2) {
    alert("Cần tối thiểu 2 quán để giải quyết bài toán hòa vote!");
    return;
  }
  slot.candidates.splice(idx, 1);
  renderSidebarLists();
  renderMapMarkers();
  scheduleOptimization(50);
}

// Reset to Default Setup
function resetToDefault() {
  currentData = {
    participants: JSON.parse(JSON.stringify(DEFAULT_PARTICIPANTS)),
    slots: JSON.parse(JSON.stringify(DEFAULT_SLOTS)),
  };
  lastSelectedCandidateIds = [];
  if (map) {
    map.setView([10.785, 106.695], 12);
  }
  renderSidebarLists();
  renderMapMarkers();
  scheduleOptimization(50);
}

// =============================================================================
// 6. EXECUTE OPTIMIZATION (REAL-TIME ENGINE)
// =============================================================================
function scheduleOptimization(delayMs = 100) {
  if (optDebounceTimer) clearTimeout(optDebounceTimer);
  optDebounceTimer = setTimeout(() => {
    executeOptimization();
  }, delayMs);
}

async function executeOptimization() {
  if (!currentData || !currentData.participants || currentData.participants.length < 2) return;

  const expSlider = $("exponent-slider");
  const fairSlider = $("fairness-slider");
  const osmToggle = $("osrm-toggle");

  const payload = {
    participants: currentData.participants,
    slots: currentData.slots,
    penalty_exponent: expSlider ? parseFloat(expSlider.value) : 1.0,
    fairness_factor: fairSlider ? parseFloat(fairSlider.value) : 0.0,
    enable_osrm: osmToggle ? osmToggle.checked : true,
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
    console.error("Optimization error:", err);
  }
}

// Display Output
function displayResults(data) {
  lastSelectedCandidateIds = data.selected_combination.map((c) => c.id);

  // Telemetry Tags
  const tTime = $("telemetry-time");
  const tRoute = $("telemetry-routing");
  if (tTime) tTime.textContent = `${data.execution_time_ms} ms`;
  if (tRoute) {
    if (data.fallback_used) {
      tRoute.textContent = "Đường chim bay Haversine (1.35x)";
      tRoute.className = "tag tag-warning";
    } else {
      tRoute.textContent = "Đường phố OSRM thực tế";
      tRoute.className = "tag tag-success";
    }
  }

  // 3 Central Metric Cards
  const mPsi = $("metric-psi");
  const mAvg = $("metric-avg-dist");
  const mMax = $("metric-max-dist");

  if (mPsi) mPsi.textContent = data.total_penalty_score.toFixed(2);
  const bestComboSummary = data.evaluated_combinations[0];
  if (bestComboSummary) {
    if (mAvg) mAvg.textContent = `${bestComboSummary.average_distance_km.toFixed(1)} km`;
    if (mMax) mMax.textContent = `${bestComboSummary.max_distance_km.toFixed(1)} km`;
  }

  // Re-render markers with winner star (★) & draw real street routes
  renderMapMarkers();
  drawRealRoadRoutes(data);
  renderSidebarLists(); // update winner badge in sidebar

  // Render Table 1: Participants sorted by Rank: c_(1) <= c_(2) <= ... <= c_(N)
  const sortedByRank = [...data.participant_breakdowns].sort((a, b) => a.rank - b.rank);
  const pTable = $("participant-table-body");
  if (pTable) {
    pTable.innerHTML = sortedByRank
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
  const cTable = $("combinations-table-body");
  if (cTable) {
    cTable.innerHTML = data.evaluated_combinations
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

// =============================================================================
// 7. PARAMETER SLIDER EVENT HANDLERS
// =============================================================================
function updateSliderLabels() {
  const expSlider = $("exponent-slider");
  const fairSlider = $("fairness-slider");
  const expVal = $("exponent-val");
  const expDesc = $("exponent-desc");
  const fairVal = $("fairness-val");
  const fairDesc = $("fairness-desc");

  const k = expSlider ? parseFloat(expSlider.value) : 1.0;
  const lambda = fairSlider ? parseFloat(fairSlider.value) : 0.0;

  if (expVal) expVal.textContent = k.toFixed(1);
  if (expDesc) {
    if (k === 1.0) expDesc.textContent = "Bậc 1 (OMP Tuyến tính)";
    else if (k < 1.6) expDesc.textContent = "Phạt lũy thừa vừa phải";
    else expDesc.textContent = "Phạt cấp số nhân cực mạnh";
  }

  if (fairVal) fairVal.textContent = lambda.toFixed(1);
  if (fairDesc) {
    if (lambda === 0.0) fairDesc.textContent = "MinSum (Tổng km ngắn nhất)";
    else if (lambda < 1.0) fairDesc.textContent = "Ordered Median cân bằng";
    else fairDesc.textContent = "MinMax (Ưu tiên người xa nhất)";
  }
}

function setupEventListeners() {
  const tabPure = $("tab-pure-omp");
  const tabCustom = $("tab-custom-penalty");
  const modeBadge = $("mode-badge");
  const expSlider = $("exponent-slider");
  const expHint = $("exponent-hint");
  const fairSlider = $("fairness-slider");
  const osmToggle = $("osrm-toggle");

  const addPBtn = $("add-participant-btn");
  const addCBtn = $("add-candidate-btn");
  const resetBtn = $("reset-default-btn");

  if (tabPure) {
    tabPure.addEventListener("click", () => {
      isPureOmpMode = true;
      tabPure.classList.add("active");
      if (tabCustom) tabCustom.classList.remove("active");
      if (modeBadge) modeBadge.textContent = "Standard OMP";

      if (expSlider) {
        expSlider.value = 1.0;
        expSlider.disabled = true;
      }
      if (expHint) {
        expHint.innerHTML = "Ở chế độ OMP Thuần túy: <b>k khóa cố định ở 1.0</b> (chi phí cá nhân c<sub>i</sub> chính là quãng đường km thực tế theo sách giáo khoa).";
      }
      updateSliderLabels();
      scheduleOptimization(50);
    });
  }

  if (tabCustom) {
    tabCustom.addEventListener("click", () => {
      isPureOmpMode = false;
      tabCustom.classList.add("active");
      if (tabPure) tabPure.classList.remove("active");
      if (modeBadge) modeBadge.textContent = "OMP + Phạt Cấp Số Nhân";

      if (expSlider) expSlider.disabled = false;
      if (expHint) {
        expHint.innerHTML = "Mở khóa hệ số lũy thừa k: c<sub>i</sub> = d<sub>i</sub><sup>k</sup>. Khi k > 1.0, người đi xa bị phạt cấp số nhân trước khi tổng hợp OMP.";
      }
      updateSliderLabels();
      scheduleOptimization(50);
    });
  }

  if (expSlider) {
    expSlider.addEventListener("input", () => {
      updateSliderLabels();
      scheduleOptimization(60);
    });
  }

  if (fairSlider) {
    fairSlider.addEventListener("input", () => {
      updateSliderLabels();
      scheduleOptimization(60);
    });
  }

  if (osmToggle) {
    osmToggle.addEventListener("change", () => {
      scheduleOptimization(50);
    });
  }

  if (addPBtn) addPBtn.addEventListener("click", addParticipant);
  if (addCBtn) addCBtn.addEventListener("click", addCandidate);
  if (resetBtn) resetBtn.addEventListener("click", resetToDefault);
}

// =============================================================================
// 8. ROBUST BOOTSTRAP INITIALIZATION
// =============================================================================
function startApp() {
  initMap();
  setupEventListeners();
  renderSidebarLists();
  renderMapMarkers();
  scheduleOptimization(50);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", startApp);
} else {
  startApp();
}
