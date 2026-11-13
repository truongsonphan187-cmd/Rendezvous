# Technical Specification: Ordered Median Tie-Break Engine (`tiebreak_engine`)

> **Project:** Group Outing & Meeting Scheduler (Computational Thinking Project)  
> **Component:** Multi-Criteria Tie-Break Engine using the Ordered Median Problem (OMP)  
> **Audience:** Core Engineers, Backend Integrators, and Technical Evaluators  
> **Status:** Approved Baseline  
> **Version:** 1.0.0  

---

## 1. Executive Summary & Problem Context

### 1.1 Context
In group outing schedulers, participants vote on places of interest for various itinerary slots (e.g., lunch, entertainment, coffee). When multiple candidate locations receive an identical number of upvotes, a **tie-break stalemate** occurs. Traditional resolution mechanisms (such as random tie-breaking or first-come-first-served) neglect participant travel burdens, leading to participant dissatisfaction and dropouts.

### 1.2 Objective
The `tiebreak_engine` is a standalone, plug-and-play decision module that automatically resolves tie votes. It evaluates candidate combinations against all participants' home locations, optimizing simultaneously for:
1. **System Efficiency (MinSum / Utilitarian Objective):** Minimizing the aggregate travel distance across the entire group to conserve fuel and time.
2. **Individual Fairness (MinMax / Egalitarian Objective):** Mitigating disproportionate travel burdens on outlier participants so that no single member suffers an excessive commute.

---

## 2. Mathematical Optimization Model

The engine employs a **Two-Tier Non-Linear Cost & Aggregation Model** combining customizable individual penalty functions with the Ordered Median Problem (OMP).

```
   [Participant Homes: H_1..H_n] + [Fixed Slots with Tied Candidate Spots]
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │       TIER 1: Individual Cost Penalty            │
             │           c_i = f(d_i) = d_i ^ k                 │
             │   (Configurable via core/scoring_formula.py)     │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │     TIER 2: Ordered Median Aggregation (OMP)     │
             │   1. Rank Sort: c_(1) <= c_(2) <= ... <= c_(n)   │
             │   2. Dot Product: Ψ = Σ (w_i * c_(i))            │
             │   (Balances Utilitarian vs Egalitarian Fairness) │
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
               [Optimal Itinerary Combination Selected]
```

### 2.1 Tier 1: Individual Cost & Penalty Function
Let $d_i$ be the total round-trip distance traveled by participant $i \in \{1, \dots, N\}$ for a given itinerary candidate sequence (Home $\to S_1 \to S_2 \to \dots \to S_K \to$ Home), measured in kilometers.

The individual penalized cost $c_i$ is defined as:

$$c_i = f(d_i) = d_i^k$$

Where $k \ge 1.0$ is the **Penalty Exponent**:
* **$k = 1.0$ (Linear / Standard OMP):** Cost is directly proportional to physical distance.
* **$k > 1.0$ (Super-linear / Exponential Penalty, e.g., $k = 1.5$ or $2.0$):** Penalizes long commutes aggressively, heavily penalizing candidates that isolate any single participant.

### 2.2 Tier 2: Ordered Median Aggregator (Group Level)
Given the set of individual penalized costs $\{c_1, c_2, \dots, c_N\}$:

1. **Permutation & Rank Sorting:** Sort costs in non-decreasing order:
   $$c_{(1)} \le c_{(2)} \le \dots \le c_{(N)}$$
   where $c_{(1)}$ represents the least-burdened participant and $c_{(N)}$ represents the most-burdened participant.

2. **Rank Weight Vector $\vec{w}$:** Define an order-dependent weight vector $W = (w_1, w_2, \dots, w_N)$ such that $w_i \ge 0$.
   * **Utilitarian (MinSum):** $W = (1, 1, \dots, 1) \implies \Psi = \sum c_i$.
   * **Egalitarian (MinMax / Chebyshev):** $W = (0, 0, \dots, 0, 1) \implies \Psi = c_{(N)}$.
   * **Compromise Ordered Median:**
     $$w_i = 1.0 + \lambda \cdot \left(\frac{i - 1}{N - 1}\right)$$
     where $\lambda \in [0.0, 2.0]$ is the **Fairness Factor**, balancing overall efficiency against maximum individual penalty.

3. **Global Penalty Metric ($\Psi$):**
   $$\Psi = \sum_{i=1}^N w_i \cdot c_{(i)}$$

The engine evaluates all candidate combinations in the Cartesian product of tied slots and selects the combination that minimizes $\Psi$.

---

## 3. Key Architectural & Product Decisions

| Decision Area | Chosen Approach | Rationale & Trade-off Analysis |
| :--- | :--- | :--- |
| **Itinerary Sequence** | **Fixed Time Slots (Case B)** | Group events follow a chronological timeline (e.g., 12:00 Lunch $\to$ 15:00 Activity $\to$ 18:00 Coffee). The engine preserves slot ordering and solves the combinatorial selection problem across tied candidates, rather than solving an unconstrained Traveling Salesperson Problem (TSP). |
| **Distance Metric** | **Network Distance (km) via OSRM** | OpenStreetMap (OSRM) does **not** provide reliable live traffic or congestion metrics for urban Southeast Asia (e.g., Vietnam). Travel time estimates under OSM assume free-flow conditions, yielding unrealistic results. Real road network distance (km) provides a deterministic, physical ground truth directly correlated with fuel consumption and rider fatigue. |
| **API Resilience & Rate Limiting** | **In-Memory Cache + Haversine Fallback ($1.35\times$)** | To prevent rate-limit blocks from public OSRM servers during interactive testing: (1) An LRU coordinate cache stores computed distance pairs. (2) If network or API failure occurs, the engine automatically falls back to great-circle Haversine distance multiplied by an urban tortuosity detour factor ($1.35\times$) with a telemetry warning. |
| **Carpooling Mode** | **Deferred to Phase 2 (Scope Guard)** | Implementing dynamic pickup-and-delivery vehicle routing (VRPPD) at this stage introduces disproportionate complexity into both the routing logic and the client UX. Carpooling is isolated as a roadmap item for subsequent iterations. |
| **Developer Customization** | **Isolated `scoring_formula.py`** | Decouples mathematical scoring from networking, routing, and data access. Any engineer can modify the penalty curve or ranking weights in pure Python without risk of breaking routing pipelines. |
| **Standalone Playground** | **FastAPI Server + Interactive Leaflet Web UI** | Teammates and evaluators can launch a local sandbox with one command (`python run_playground.py`) to drag participant pins, adjust $k$ and $\lambda$ sliders, and inspect step-by-step cost breakdown tables. |

---

## 4. Repository & Package Architecture

The package is organized as a self-contained module under `tiebreak_engine/`:

```text
tiebreak_engine/
│
├── README.md                           # Quickstart & integration guide (3-step copy-paste)
├── requirements.txt                    # Minimal dependencies (fastapi, uvicorn, httpx, pydantic)
│
├── core/                               # Standalone mathematical & routing core (zero framework lock-in)
│   ├── __init__.py
│   ├── scoring_formula.py              # [DEVELOPER ZONE] Customizable penalty & weight formulas
│   ├── ordered_median.py               # Pure OMP sorting, dot-product, and rank aggregation
│   ├── itinerary_solver.py             # Cartesian product candidate generator & path evaluator
│   └── router.py                       # OSRM HTTP client + memory cache + 1.35x Haversine fallback
│
├── integration/                        # Bridge for existing FastAPI backend
│   ├── __init__.py
│   ├── schemas.py                      # Pydantic DTOs (Request / Response validation models)
│   └── tie_break_service.py            # Facade service for backend/app/domain/patterns/TieBreak
│
└── playground/                         # Interactive visual test environment
    ├── __init__.py
    ├── run_playground.py               # Lightweight standalone FastAPI server (Port 8080)
    └── static/
        ├── index.html                  # Leaflet map, interactive sliders, data tables
        ├── app.js                      # Reactive state management & API dispatcher
        └── style.css                   # Responsive modern styling
```

---

## 5. Developer Customization API (`core/scoring_formula.py`)

Engineers modifying the scoring criteria only need to interact with this single module:

```python
"""
Module: tiebreak_engine.core.scoring_formula
Purpose: Centralized mathematical definition for individual penalty curves
         and Ordered Median ranking weights.
"""

def compute_individual_penalty(distance_km: float, penalty_exponent: float = 1.0) -> float:
    """
    Computes penalized travel cost for a single participant.
    
    Args:
        distance_km: Total round-trip distance traveled (km).
        penalty_exponent: Exponent factor (k >= 1.0).
            - k = 1.0: Linear cost (standard OMP).
            - k > 1.0: Super-linear penalty for outlier participants.
    Returns:
        Penalized cost value.
    """
    if distance_km <= 0.0:
        return 0.0
    return float(distance_km ** penalty_exponent)


def generate_ordered_median_weights(num_participants: int, fairness_factor: float = 0.5) -> list[float]:
    """
    Generates rank-dependent weight vector W = (w_1, ..., w_n) for ordered costs.
    
    Args:
        num_participants: Total number of participants (N).
        fairness_factor: lambda parameter in [0.0, 2.0].
            - 0.0: Strict MinSum (equal weights [1, 1, ..., 1]).
            - 1.0+: Prioritizes mitigating highest individual burdens.
    Returns:
        List of float weights matching the length of sorted participant costs.
    """
    if num_participants <= 0:
        return []
    if num_participants == 1:
        return [1.0]

    weights = []
    for rank in range(num_participants):
        # rank 0: lowest cost participant, rank N-1: highest cost participant
        weight = 1.0 + fairness_factor * (rank / (num_participants - 1))
        weights.append(round(weight, 4))
        
    return weights
```

---

## 6. Integration Contract for the Backend Team

The primary web backend (`backend/app/`) integrates the engine via `TieBreakService` without modifying database models:

```python
from tiebreak_engine.integration.tie_break_service import TieBreakService
from tiebreak_engine.integration.schemas import (
    TieBreakRequest,
    ParticipantLocation,
    ItinerarySlot,
    CandidatePlace
)

# 1. Instantiate the Service
tie_break_service = TieBreakService()

# 2. Construct Strongly-Typed Request Payload
payload = TieBreakRequest(
    participants=[
        ParticipantLocation(id="user_1", name="Alice", lat=10.7769, lng=106.7009),
        ParticipantLocation(id="user_2", name="Bob", lat=10.7550, lng=106.6660),
    ],
    slots=[
        ItinerarySlot(
            slot_id="slot_lunch",
            slot_name="Lunch (12:00 PM)",
            candidates=[
                CandidatePlace(id="cand_1", name="Bistro Central", lat=10.7720, lng=106.6980),
                CandidatePlace(id="cand_2", name="Riverside Diner", lat=10.7610, lng=106.6850),
            ]
        )
    ],
    penalty_exponent=1.0,
    fairness_factor=0.5
)

# 3. Execute Async Resolution
resolution_result = await tie_break_service.resolve(payload)

# resolution_result contains:
# - selected_combination: list of chosen candidate places
# - total_penalty_score: global objective value (Psi)
# - participant_breakdowns: per-participant distances, penalized costs, and rank weights
```

---

## 7. Verification & Implementation Roadmap

- [x] Architectural & mathematical requirements alignment.
- [x] Formal English specification completed (`SPEC.md`).
- [x] Implement `core/`:
  - [x] `scoring_formula.py` (Customizable cost and weight generators).
  - [x] `ordered_median.py` (OMP rank sorting and scalar product).
  - [x] `router.py` (OSRM client, memory cache, Haversine 1.35x fallback).
  - [x] `itinerary_solver.py` (Combinatorial evaluator across fixed slots).
- [x] Implement `integration/`:
  - [x] `schemas.py` (Pydantic validation models).
  - [x] `tie_break_service.py` (Asynchronous adapter interface).
- [x] Implement `playground/`:
  - [x] `run_playground.py` (FastAPI test application).
  - [x] Interactive Leaflet frontend with dynamic sliders and route rendering.
- [x] Automated Test Suite:
  - [x] Unit tests for OMP math and monotonicity properties (18 tests passing).
  - [x] Fallback routing tests under network timeout simulations.
- [x] Delivery:
  - [x] Root `README.md` for team onboarding.
