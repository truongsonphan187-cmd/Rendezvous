// =============================================================================
// APP.JS - Dynamic Real-Time Ordered Median Sandbox (Default 1-Slot, Custom up to 5)
// =============================================================================

let map = null;
let markersGroup = null;
let routesGroup = null;
let highlightGroup = null;
let currentMapMarkers = {};
let isPureOmpMode = true; // true: locks k=1.0 (Standard OMP), false: unlocks k > 1.0
let optDebounceTimer = null;
let lastSelectedCandidateIds = [];
let activeSlotIdx = 0; // Active slot index for sidebar editing

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
// 1. DEFAULT DATASET (Mặc định: 4 Người & 1 Chặng với 2 Ứng viên tránh cháy API)
// =============================================================================
const DEFAULT_PARTICIPANTS = [
  { id: "u1", name: "Người 1", lat: 10.8120, lng: 106.6980 },
  { id: "u2", name: "Người 2", lat: 10.8020, lng: 106.6800 },
  { id: "u3", name: "Người 3", lat: 10.8350, lng: 106.6720 },
  { id: "u4", name: "Người 4", lat: 10.7200, lng: 106.7150 },
];

const DEFAULT_SLOTS = [
  {
    slot_id: "slot_1",
    slot_name: "Chặng 1",
    candidates: [
      { id: "cand_1_1", name: "Địa điểm 1.1", lat: 10.8250, lng: 106.6850 },
      { id: "cand_1_2", name: "Địa điểm 1.2", lat: 10.7780, lng: 106.6890 },
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
  highlightGroup = L.layerGroup().addTo(map);

  setTimeout(() => {
    if (map) map.invalidateSize();
  }, 250);
}

function highlightEdgeOnMap(geometry) {
  if (!highlightGroup || !geometry || geometry.length === 0) return;
  highlightGroup.clearLayers();
  const leafletCoords = geometry.map((pt) => [pt[1], pt[0]]);
  // Outer bright border
  L.polyline(leafletCoords, {
    color: "#ffffff",
    weight: 9,
    opacity: 0.95,
  }).addTo(highlightGroup);
  // Inner amber neon core
  L.polyline(leafletCoords, {
    color: "#fbbf24",
    weight: 5,
    opacity: 1.0,
  }).addTo(highlightGroup);
}

function clearHighlightOnMap() {
  if (highlightGroup) {
    highlightGroup.clearLayers();
  }
}

function createCustomIcon(color, label, isWinner = false) {
  const size = isWinner ? 36 : 28;
  const border = isWinner ? "2.5px solid #fbbf24" : "2px solid rgba(255, 255, 255, 0.9)";
  const shadow = isWinner
    ? "0 0 20px rgba(251, 191, 36, 0.9), 0 2px 10px rgba(0, 0, 0, 0.8)"
    : "0 2px 8px rgba(0, 0, 0, 0.6)";

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
        color: ${isWinner ? "#050505" : "#ffffff"};
        font-family: 'DM Sans', sans-serif;
        font-weight: 800;
        font-size: ${isWinner ? "13px" : "11px"};
        cursor: grab;
        transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      ">${label}</div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

// =============================================================================
// 3. RENDER MAP MARKERS (Dx NOTATION FOR SLOTS, NO STARS)
// =============================================================================
function renderMapMarkers() {
  if (!map || !markersGroup) return {};
  markersGroup.clearLayers();

  const createdMarkers = {};

  // 1. Participant Homes (P1, P2...)
  currentData.participants.forEach((p, idx) => {
    const latLng = [p.lat, p.lng];
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

  // 2. Candidate Venues for all slots (D1..D5)
  currentData.slots.forEach((slot, sIdx) => {
    const slotLabel = `D${sIdx + 1}`; // All candidates of slot sIdx have label Dx

    slot.candidates.forEach((c) => {
      const latLng = [c.lat, c.lng];
      const isWinner = lastSelectedCandidateIds.includes(c.id);
      // Winner is GOLD (#fbbf24) with label Dx, losing is ORANGE (#ea580c) with label Dx
      const color = isWinner ? "#fbbf24" : "#ea580c";

      const marker = L.marker(latLng, {
        icon: createCustomIcon(color, slotLabel, isWinner),
        draggable: true,
      }).bindPopup(
        `<b>📍 ${c.name} (${slotLabel})</b>${isWinner ? "<br><b style='color:#fbbf24'>🏆 ĐỊA ĐIỂM ĐƯỢC CHỌN</b>" : ""}<br>Kéo thả icon để thay đổi vị trí quán!`
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
  });

  currentMapMarkers = createdMarkers;
  return createdMarkers;
}

// Update coordinate text in sidebar
function updateCoordLabels() {
  currentData.participants.forEach((p, idx) => {
    const el = $(`coord-p-${idx}`);
    if (el) el.textContent = `${p.lat.toFixed(3)}, ${p.lng.toFixed(3)}`;
  });

  const slot = currentData.slots[activeSlotIdx];
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

  // Shared Itinerary Path connecting D1 -> D2 -> ... -> Dk
  if (data.shared_itinerary_geometry && data.shared_itinerary_geometry.length > 0) {
    const leafletCoords = data.shared_itinerary_geometry.map((pt) => [pt[1], pt[0]]);
    L.polyline(leafletCoords, {
      color: "#fbbf24",
      weight: 6,
      opacity: 0.9,
    }).addTo(routesGroup);
  }

  // Individual Commute Paths (Nhà -> Chặng đầu và Chặng cuối -> Nhà)
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
// 5. SIDEBAR MANAGEMENT: PARTICIPANTS & CUSTOM SLOTS (UP TO 5)
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
              <button class="btn-del" data-idx="${idx}" title="Xóa người này" ${canDelete ? "" : "disabled"}>✕</button>
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

  // 2. Candidate Places List for Active Slot
  renderActiveSlotCandidates();
}

function renderActiveSlotCandidates() {
  if (activeSlotIdx >= currentData.slots.length) {
    activeSlotIdx = currentData.slots.length - 1;
  }
  const slot = currentData.slots[activeSlotIdx];
  const cList = $("candidates-list");
  const slotTitle = $("slot-section-title");
  const addCBtn = $("add-candidate-btn");
  const tabContainer = $("slots-tab-bar");

  const slotDx = `D${activeSlotIdx + 1}`;
  if (slotTitle) {
    const canDeleteSlot = currentData.slots.length > 1;
    slotTitle.innerHTML = `
      📍 Ứng viên Chặng ${activeSlotIdx + 1} (${slotDx})
      ${canDeleteSlot ? `<button id="del-slot-btn" class="btn-del-sm" type="button" title="Xóa chặng này">🗑️ Xóa chặng</button>` : ""}
    `;
    const delSlotBtn = $("del-slot-btn");
    if (delSlotBtn) {
      delSlotBtn.addEventListener("click", deleteCurrentSlot);
    }
  }

  if (addCBtn) addCBtn.innerHTML = `<span>➕</span> Thêm địa điểm ${slotDx}`;

  // Render Slots Tabs (D1, D2, D3...)
  if (tabContainer) {
    tabContainer.innerHTML = currentData.slots
      .map((s, idx) => {
        const isActive = idx === activeSlotIdx;
        return `
          <button class="slot-tab ${isActive ? "active" : ""}" data-slot-idx="${idx}" type="button">
            D${idx + 1}
          </button>
        `;
      })
      .join("");
  }

  if (cList && slot) {
    cList.innerHTML = slot.candidates
      .map((c, idx) => {
        const isWinner = lastSelectedCandidateIds.includes(c.id);
        const canDelete = slot.candidates.length > 1;
        return `
          <div class="entity-row" id="entity-c-${c.id}">
            <div class="entity-left">
              <span class="entity-badge badge-cand ${isWinner ? "badge-winner" : ""}">
                ${slotDx}
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
    name: `Người ${count}`,
    lat: parseFloat((center.lat + offsetLat).toFixed(4)),
    lng: parseFloat((center.lng + offsetLng).toFixed(4)),
  };

  currentData.participants.push(newP);
  renderSidebarLists();
  const createdMarkers = renderMapMarkers();

  if (map && createdMarkers && createdMarkers[newP.id]) {
    map.panTo([newP.lat, newP.lng], { animate: true, duration: 0.5 });
    createdMarkers[newP.id].openPopup();
  }

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

// Add Candidate to active slot
function addCandidate() {
  const slot = currentData.slots[activeSlotIdx];
  if (!slot) return;

  const count = slot.candidates.length + 1;
  const slotNum = activeSlotIdx + 1;
  const center = map ? map.getCenter() : { lat: 10.785, lng: 106.695 };
  const offsetLat = (Math.random() - 0.5) * 0.035;
  const offsetLng = (Math.random() - 0.5) * 0.035;

  const newC = {
    id: `cand_${slotNum}_${Date.now()}`,
    name: `Địa điểm ${slotNum}.${count}`,
    lat: parseFloat((center.lat + offsetLat).toFixed(4)),
    lng: parseFloat((center.lng + offsetLng).toFixed(4)),
  };

  slot.candidates.push(newC);
  renderActiveSlotCandidates();
  const createdMarkers = renderMapMarkers();

  if (map && createdMarkers && createdMarkers[newC.id]) {
    map.panTo([newC.lat, newC.lng], { animate: true, duration: 0.5 });
    createdMarkers[newC.id].openPopup();
  }

  const newRow = $(`entity-c-${newC.id}`);
  if (newRow) {
    newRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
    newRow.classList.add("highlight-flash");
  }

  scheduleOptimization(50);
}

// Delete Candidate from active slot
function deleteCandidate(idx) {
  const slot = currentData.slots[activeSlotIdx];
  if (!slot) return;

  if (slot.candidates.length <= 1) {
    alert("Mỗi chặng cần tối thiểu 1 địa điểm dừng chân!");
    return;
  }
  slot.candidates.splice(idx, 1);
  renderActiveSlotCandidates();
  renderMapMarkers();
  scheduleOptimization(50);
}

// Add New Slot (Custom up to 5 slots)
function addSlot() {
  if (currentData.slots.length >= 5) {
    alert("Hệ thống hỗ trợ tối đa 5 chặng!");
    return;
  }
  const newSlotIdx = currentData.slots.length;
  const slotNum = newSlotIdx + 1;
  const center = map ? map.getCenter() : { lat: 10.785, lng: 106.695 };
  const offset1Lat = (Math.random() - 0.5) * 0.03;
  const offset1Lng = (Math.random() - 0.5) * 0.03;
  const offset2Lat = (Math.random() - 0.5) * 0.03;
  const offset2Lng = (Math.random() - 0.5) * 0.03;

  const newSlot = {
    slot_id: `slot_${slotNum}`,
    slot_name: `Chặng ${slotNum}`,
    candidates: [
      {
        id: `cand_${slotNum}_1_${Date.now()}`,
        name: `Địa điểm ${slotNum}.1`,
        lat: parseFloat((center.lat + offset1Lat).toFixed(4)),
        lng: parseFloat((center.lng + offset1Lng).toFixed(4)),
      },
      {
        id: `cand_${slotNum}_2_${Date.now() + 1}`,
        name: `Địa điểm ${slotNum}.2`,
        lat: parseFloat((center.lat + offset2Lat).toFixed(4)),
        lng: parseFloat((center.lng + offset2Lng).toFixed(4)),
      },
    ],
  };

  currentData.slots.push(newSlot);
  activeSlotIdx = newSlotIdx;
  renderActiveSlotCandidates();
  renderMapMarkers();
  scheduleOptimization(50);
}

// Delete Current Slot
function deleteCurrentSlot() {
  if (currentData.slots.length <= 1) {
    alert("Cần tối thiểu 1 chặng để giải quyết hòa vote!");
    return;
  }
  currentData.slots.splice(activeSlotIdx, 1);
  // Re-number remaining slots
  currentData.slots.forEach((s, i) => {
    s.slot_id = `slot_${i + 1}`;
    s.slot_name = `Chặng ${i + 1}`;
  });
  if (activeSlotIdx >= currentData.slots.length) {
    activeSlotIdx = currentData.slots.length - 1;
  }
  renderActiveSlotCandidates();
  renderMapMarkers();
  scheduleOptimization(50);
}

// Reset to Default Setup (4 people, 1 slot with 2 options)
function resetToDefault() {
  currentData = {
    participants: JSON.parse(JSON.stringify(DEFAULT_PARTICIPANTS)),
    slots: JSON.parse(JSON.stringify(DEFAULT_SLOTS)),
  };
  activeSlotIdx = 0;
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
function setSolverStatus(busy) {
  const pill = $("live-pill");
  const text = $("live-text");
  if (!pill || !text) return;
  if (busy) {
    pill.classList.add("live-pill-busy");
    text.textContent = "Đang tính lộ trình";
  } else {
    pill.classList.remove("live-pill-busy");
    text.textContent = "Lộ trình hoàn tất";
  }
}

function scheduleOptimization(delayMs = 100) {
  setSolverStatus(true);
  if (optDebounceTimer) clearTimeout(optDebounceTimer);
  optDebounceTimer = setTimeout(() => {
    executeOptimization();
  }, delayMs);
}

async function executeOptimization() {
  if (!currentData || !currentData.participants || currentData.participants.length < 2) {
    setSolverStatus(false);
    return;
  }

  setSolverStatus(true);

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
  } finally {
    setSolverStatus(false);
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

  // Re-render markers with winner gold Dx & draw real street routes
  renderMapMarkers();
  drawRealRoadRoutes(data);
  renderActiveSlotCandidates(); // update winner badges in active slot tab

  // Render Layered DP on DAG Flow Visualization
  renderDAGVisualization(data.dag_visualization, data.selected_combination);

  // Active exponent k for mathematical formula notation
  const expSlider = $("exponent-slider");
  const currentK = expSlider ? parseFloat(expSlider.value) : 1.0;

  // Render Table 1: Participants sorted by Rank: c_(1) <= c_(2) <= ... <= c_(N)
  const sortedByRank = [...data.participant_breakdowns].sort((a, b) => a.rank - b.rank);
  const pTable = $("participant-table-body");
  if (pTable) {
    pTable.innerHTML = sortedByRank
      .map((p) => {
        const outKm = (p.outbound_distance_km !== undefined ? p.outbound_distance_km : (p.total_distance_km / 2)).toFixed(2);
        const midKm = (p.middle_distance_km !== undefined ? p.middle_distance_km : 0.0).toFixed(2);
        const inKm = (p.inbound_distance_km !== undefined ? p.inbound_distance_km : (p.total_distance_km / 2)).toFixed(2);
        const totalKm = p.total_distance_km.toFixed(2);

        const costDisplay = `<code>${p.penalized_cost.toFixed(2)}</code>`;

        return `
          <tr>
            <td><strong>#${p.rank}</strong></td>
            <td><strong>${p.name}</strong></td>
            <td>
              <div class="dist-breakdown">
                <span class="dist-pill dist-out" title="Đi riêng: Nhà ➔ Điểm hẹn đầu (${outKm} km)">🏠 Đi: ${outKm} km</span>
                <span class="dist-operator">+</span>
                <span class="dist-pill dist-mid" title="Đi chung: Cả nhóm cùng di chuyển qua các chặng do DP tối ưu (${midKm} km)">⚡ Chung: ${midKm} km</span>
                <span class="dist-operator">+</span>
                <span class="dist-pill dist-in" title="Về riêng: Điểm hẹn cuối ➔ Nhà (${inKm} km)">🏠 Về: ${inKm} km</span>
                <span class="dist-operator">=</span>
                <span class="dist-sum">${totalKm} km</span>
              </div>
            </td>
            <td>${costDisplay}</td>
            <td><span class="mini-tag">${p.rank_weight.toFixed(3)}</span></td>
            <td><strong>${p.weighted_score.toFixed(2)}</strong></td>
          </tr>
        `;
      })
      .join("");
  }

  // Render Table 2: Combinations Comparison (Đã xóa cột Kết luận theo yêu cầu)
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
          </tr>
        `;
      })
      .join("");
  }
}

// =============================================================================
// LAYERED DP ON MULTI-STAGE DAG VISUALIZATION
// =============================================================================
function renderDAGVisualization(dagData, selectedCombo) {
  const container = $("dag-board");
  const summaryPill = $("dag-summary-pill");
  if (!container) return;

  // Case 1: Single Slot (K = 1) -> No middle legs exist yet
  if (!dagData || !dagData.enabled || dagData.layers_count < 2) {
    if (summaryPill) {
      summaryPill.innerHTML = `
        <span class="dag-summary-badge" style="background: rgba(255, 255, 255, 0.05); color: var(--text-muted); border: 1px solid rgba(255, 255, 255, 0.1);">
          📍 Lịch trình 1 điểm hẹn (K = 1)
        </span>
      `;
    }
    container.innerHTML = `
      <div class="dag-single-slot-notice">
        <div class="dag-single-slot-icon">ℹ️</div>
        <div class="dag-single-slot-title">Chuyến đi 1 chặng: Di chuyển trực tiếp không qua chặng giữa</div>
        <p class="dag-single-slot-desc">
          Các thành viên chỉ gặp nhau tại một điểm hẹn duy nhất (<strong>D1</strong>). Toàn bộ lộ trình gồm 2 chặng cá nhân: 
          <code>Nhà ➔ D1</code> và <code>D1 ➔ Nhà</code>. Chưa phát sinh chặng di chuyển trung gian giữa các quán, do đó đồ thị đa tầng (Layered DP) chưa kích hoạt.
        </p>
        <div class="dag-single-slot-hint">
          💡 <strong>Trải nghiệm thuật toán:</strong> Bấm <strong>"➕ Thêm chặng"</strong> ở thanh bên trái (tạo lịch trình 2–5 chặng như Ăn trưa ➔ Cafe ➔ Bida) để kích hoạt đồ thị Quy hoạch động trực quan!
        </div>
      </div>
    `;
    return;
  }

  // Case 2: Multi-Stage DAG (K >= 2) - Tối ưu chỉ giữ ô Đã loại trừ ở góc trên bên phải
  if (summaryPill) {
    summaryPill.innerHTML = `
      <span class="dag-summary-badge badge-pruned" title="Số lượng phương án chặng giữa khác bị loại bỏ nhờ nguyên lý tối ưu Bellman">
        ✂️ Đã loại trừ: <strong>${dagData.combinations_pruned_count} phương án kém hơn</strong>
      </span>
    `;
  }

  const selectedCandIds = new Set((selectedCombo || []).map((c) => c.id));

  // Build Multi-stage Flow
  let flowHtml = '<div class="dag-stages-flow">';

  currentData.slots.forEach((slot, sIdx) => {
    const slotTag = `D${sIdx + 1}`;
    flowHtml += `
      <div class="dag-stage-col" data-slot-idx="${sIdx}">
        <div class="dag-stage-header">
          <span class="stage-tag">${slotTag}</span>
          <span class="stage-name">${slot.slot_name}</span>
        </div>
        <div class="dag-nodes-list">
    `;

    slot.candidates.forEach((cand) => {
      const isWinner = selectedCandIds.has(cand.id);
      flowHtml += `
        <div class="dag-node-card ${isWinner ? "is-winner" : ""}" data-cand-id="${cand.id}">
          <div class="dag-node-top">
            <div class="dag-node-left">
              <span class="dag-node-pin" style="background-color: ${isWinner ? "#fbbf24" : "rgba(255, 255, 255, 0.15)"}; color: ${isWinner ? "#050505" : "#ffffff"};">
                ${slotTag}
              </span>
              <span class="dag-node-name" title="${cand.name}">${cand.name}</span>
            </div>
          </div>
        </div>
      `;
    });

    flowHtml += `
        </div>
      </div>
    `;

    // Connector Bridge between slot sIdx and sIdx + 1
    if (sIdx < currentData.slots.length - 1) {
      const nextSlot = currentData.slots[sIdx + 1];
      const connectingEdges = (dagData.edges || []).filter(
        (e) => e.from_slot_name === slot.slot_name && e.to_slot_name === nextSlot.slot_name
      );

      flowHtml += `<div class="dag-transition-bridge">`;

      connectingEdges.forEach((edge, edgeIdx) => {
        const edgeOptimal = edge.is_optimal;
        flowHtml += `
          <div class="dag-edge-pill ${edgeOptimal ? "is-optimal" : "is-pruned"}"
               data-edge-idx="${edgeIdx}"
               data-from-id="${edge.from_candidate_id}"
               data-to-id="${edge.to_candidate_id}"
               title="Rê chuột để soi tuyến đường này trên bản đồ">
            <div class="edge-pill-route">
              <span>${edge.from_candidate_name} ➔ ${edge.to_candidate_name}</span>
            </div>
            <div class="edge-pill-dist">
              <span>${edge.distance_km.toFixed(2)} km</span>
            </div>
          </div>
        `;
      });

      flowHtml += `</div>`;
    }
  });

  flowHtml += '</div>'; // End dag-stages-flow

  // Decision Stepper
  const is2Slots = currentData.slots.length === 2;
  let stepsHtml = `
    <div class="dag-decision-stepper">
      <div class="dag-stepper-title">
        <span>📌</span> ${is2Slots ? "Phân Tích Quyết Định Lựa Chọn Chặng Giữa (K = 2 Chặng):" : "Tiến Trình Quy Hoạch Động (Layered DP) & Nguyên Lý Tối Ưu Bellman:"}
      </div>
  `;

  (dagData.steps || []).forEach((step, sIdx) => {
    stepsHtml += `
      <div class="dag-step-card">
        <div class="dag-step-header">
          <div class="dag-step-left">
            <span class="dag-step-idx">Bước ${sIdx + 1}</span>
            <span class="dag-step-target">Chuyển sang ${step.slot_name}: Chọn ${step.chosen_candidate_name}</span>
          </div>
          <span class="dag-step-km">Lũy kế chặng giữa: ${step.cumulative_distance_km.toFixed(2)} km</span>
        </div>
        <p class="dag-step-desc">${step.decision_explanation}</p>
        <div>
          <span class="bellman-formula-tag">
            ${is2Slots ? "Cân bằng OMP: min { Đi riêng (Nhà ➔ D1) + Đi chung (D1 ➔ D2) + Về riêng (D2 ➔ Nhà) }" : "Nguyên lý Bellman: C*(s) = min { C*(p) + cost(p, s) } (Cắt tỉa các nhánh dài hơn)"}
          </span>
        </div>
      </div>
    `;
  });

  stepsHtml += '</div>'; // End dag-decision-stepper

  container.innerHTML = flowHtml + stepsHtml;

  // Interactivity 1: Hover edge pill -> Highlight street route on Leaflet Map
  const edgePills = container.querySelectorAll(".dag-edge-pill");
  edgePills.forEach((pill) => {
    const fromId = pill.getAttribute("data-from-id");
    const toId = pill.getAttribute("data-to-id");
    const matchingEdge = (dagData.edges || []).find(
      (e) => e.from_candidate_id === fromId && e.to_candidate_id === toId
    );

    pill.addEventListener("mouseenter", () => {
      if (matchingEdge && matchingEdge.geometry && matchingEdge.geometry.length > 0) {
        highlightEdgeOnMap(matchingEdge.geometry);
      }
    });

    pill.addEventListener("mouseleave", () => {
      clearHighlightOnMap();
    });
  });

  // Interactivity 2: Hover candidate card -> Open marker popup on Leaflet Map
  const nodeCards = container.querySelectorAll(".dag-node-card");
  nodeCards.forEach((card) => {
    const candId = card.getAttribute("data-cand-id");
    card.addEventListener("mouseenter", () => {
      if (currentMapMarkers && currentMapMarkers[candId]) {
        currentMapMarkers[candId].openPopup();
      }
    });
  });
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
  const addSlotBtn = $("add-slot-btn");
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
  if (addSlotBtn) addSlotBtn.addEventListener("click", addSlot);
  if (resetBtn) resetBtn.addEventListener("click", resetToDefault);

  // Slots Tab Bar (D1 -> D5) click delegation
  const tabContainer = $("slots-tab-bar");
  if (tabContainer) {
    tabContainer.addEventListener("click", (e) => {
      const btn = e.target.closest(".slot-tab");
      if (btn) {
        activeSlotIdx = parseInt(btn.getAttribute("data-slot-idx"));
        renderActiveSlotCandidates();
      }
    });
  }
}

// =============================================================================
// 8. BOOTSTRAP INITIALIZATION
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
