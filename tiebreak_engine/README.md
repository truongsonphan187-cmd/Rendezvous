# 📍 Ordered Median Tie-Break Engine (`tiebreak_engine`)

> **Multi-Criteria Optimization Module for Group Outings & Meeting Schedulers**  
> Resolves tied location votes using a **Two-Tier Non-Linear Cost & Ordered Median Problem (OMP)** model.

---

## 🚀 Quickstart: Launch Interactive Playground

Anyone on the team can test and visualize the algorithm with interactive sliders and a real-time OpenStreetMap:

```bash
# 1. Install dependencies (if not already installed)
pip install -r tiebreak_engine/requirements.txt

# 2. Run the Playground server
python tiebreak_engine/playground/run_playground.py
```

Then open your browser at **[http://localhost:8080](http://localhost:8080)**.

### 🛑 How to Stop the Playground Server:
* **Normal stop:** Press `Ctrl + C` in the terminal where the server is running.
* **If the terminal is closed or port 8080 is stuck (Windows PowerShell):**
  ```powershell
  # Free up port 8080 by stopping the owning process
  Stop-Process -Id (Get-NetTCPConnection -LocalPort 8080).OwningProcess -Force
  ```
* **macOS / Linux:**
  ```bash
  lsof -ti:8080 | xargs kill -9
  ```

### Features in the Playground:
* **Interactive Sliders:**
  * **Penalty Exponent $(k)$**: Shift from linear distance ($k=1.0$) to aggressive commute penalties ($k=1.5, 2.0$).
  * **Fairness Factor $(\lambda)$**: Tune between group efficiency (MinSum $\lambda=0.0$) and outlier protection (MinMax $\lambda \ge 1.0$).
* **Real-time Map:** Visualizes participant homes, candidate venues, and route lines.
* **Step-by-Step Math Card:** Shows exact calculation steps, sorted cost ranks, and weighted scores.
* **Combinations Comparison Table:** Ranks all candidate combinations from winner to runners-up.

---

## 🛠️ Developer Customization Zone: `core/scoring_formula.py`

All mathematical penalty curves and ranking weights are isolated in **`tiebreak_engine/core/scoring_formula.py`**.

You can modify the scoring logic directly in pure Python without touching routing, API, or database code:

```python
# tiebreak_engine/core/scoring_formula.py

def compute_individual_penalty(distance_km: float, penalty_exponent: float = 1.0) -> float:
    """
    Tier 1: Adjust how individual distance is penalized.
    E.g. change to distance_km ** 1.5, or add threshold penalties.
    """
    return float(distance_km ** penalty_exponent)


def generate_ordered_median_weights(num_participants: int, fairness_factor: float = 0.5) -> list[float]:
    """
    Tier 2: Adjust how rank weights W = (w_1, ..., w_n) are assigned to sorted costs.
    """
    weights = [1.0 + fairness_factor * (i / (num_participants - 1)) for i in range(num_participants)]
    return weights
```

---

## 🔌 Integration Guide for the Backend Team

The module is designed to plug directly into `backend/app/domain/patterns/TieBreak` or application services.

### Step 1: Copy `tiebreak_engine/` into your project
Place the `tiebreak_engine` folder inside your repository (e.g. `backend/app/domain/patterns/TieBreak/` or `backend/app/services/`).

### Step 2: Call the Service

```python
from tiebreak_engine.integration.tie_break_service import TieBreakService
from tiebreak_engine.integration.schemas import (
    TieBreakRequest,
    ParticipantLocation,
    ItinerarySlot,
    CandidatePlace,
)

# Initialize service (reuses in-memory cache)
service = TieBreakService()

# Build request payload
request = TieBreakRequest(
    participants=[
        ParticipantLocation(id="u1", name="An", lat=10.7769, lng=106.7009),
        ParticipantLocation(id="u2", name="Binh", lat=10.7550, lng=106.6660),
        ParticipantLocation(id="u3", name="Cuong", lat=10.8030, lng=106.6950),
    ],
    slots=[
        ItinerarySlot(
            slot_id="slot_lunch",
            slot_name="Lunch (12:00 PM)",
            candidates=[
                CandidatePlace(id="c1", name="Restaurant A", lat=10.7780, lng=106.6850),
                CandidatePlace(id="c2", name="Restaurant B", lat=10.7580, lng=106.7030),
            ],
        )
    ],
    penalty_exponent=1.0,  # k factor
    fairness_factor=0.5,   # lambda factor
    enable_osrm=True,      # Uses live OSRM with auto-fallback to Haversine (1.35x)
)

# Execute
response = await service.resolve(request)

# Access results
print("Winning Venue Combination:", [c.name for c in response.selected_combination])
print("Objective Score (Psi):", response.total_penalty_score)
print("Execution Time:", response.execution_time_ms, "ms")
for breakdown in response.participant_breakdowns:
    print(f"User {breakdown.name}: {breakdown.total_distance_km} km | Cost: {breakdown.penalized_cost} | Rank: {breakdown.rank}")
```

---

## 🧪 Running Automated Tests

Run the full automated test suite (18 unit and integration tests):

```bash
python -m unittest discover -s tiebreak_engine/tests -v
```

All tests run using Python's standard library `unittest` with **zero external test runners required**.

---

## 📂 Package Architecture

```text
tiebreak_engine/
├── README.md                      # This onboarding guide
├── requirements.txt               # fastapi, uvicorn, httpx, pydantic
│
├── core/                          # Pure algorithm core (no DB lock-in)
│   ├── scoring_formula.py         # [CUSTOMIZE HERE] Penalty math & rank weights
│   ├── ordered_median.py          # OMP rank sorting & dot product aggregator
│   ├── itinerary_solver.py        # Fixed-itinerary combinatorial evaluator
│   └── router.py                  # OSRM HTTP client + LRU cache + Haversine fallback
│
├── integration/                   # Pydantic DTOs & Service Facade
│   ├── schemas.py                 # Request & Response models
│   └── tie_break_service.py       # Async service interface
│
├── playground/                    # Interactive visual sandbox
│   ├── run_playground.py          # Standalone FastAPI server
│   └── static/                    # Leaflet map, sliders, dynamic tables
│       ├── index.html
│       ├── app.js
│       └── style.css
│
└── tests/                         # 18 automated tests
    ├── test_math.py
    ├── test_router.py
    ├── test_solver.py
    ├── test_service.py
    └── test_playground_api.py
```

---

## 🌿 Git Guide: How to Push to Team Repository

### Scenario A: If you already have the team's cloned repo in another folder
1. Copy the `tiebreak_engine/` folder and `SPEC.md` into the root of that cloned repository.
2. In the team repository terminal, run:
   ```bash
   git checkout -b feat/tiebreak-engine
   git add tiebreak_engine SPEC.md
   git commit -m "feat(algorithm): implement ordered median tiebreak engine and playground"
   git push -u origin feat/tiebreak-engine
   ```

### Scenario B: If pushing directly from this folder
1. Initialize git and link to the team's remote repo:
   ```bash
   git init
   git remote add origin <TEAM_REPO_URL>
   git fetch origin
   ```
2. Create and switch to your feature branch:
   ```bash
   git checkout -b feat/tiebreak-engine
   git add tiebreak_engine SPEC.md
   git commit -m "feat(algorithm): implement ordered median tiebreak engine and playground"
   git push -u origin feat/tiebreak-engine
   ```
3. Open your browser on GitHub/GitLab and click **"Compare & pull request"** to merge without disturbing the `main` or `develop` branches.

