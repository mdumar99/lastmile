# Last-Mile Delivery Simulation

A multi-agent simulation platform modelling a city's last-mile delivery
ecosystem using Discrete Event Simulation (DES). Built in two layers:
a high-performance C++20 engine and a Python analytics/optimisation stack.

## Architecture

    lastmile/
    ├── engine/          # C++20 simulation core
    │   ├── include/     # Robot, Quadtree, EventScheduler, Simulation, RoadGraph, AStar
    │   └── src/         # Implementations + main.cpp
    ├── or_module/       # MILP hub optimiser (HiGHS)
    ├── ai_layer/        # RL agent (Milestone 4 — planned)
    ├── bridge/          # pybind11 C++↔Python bridge (Milestone 4 — planned)
    ├── dashboard/       # Deck.gl web dashboard (Milestone 5 — planned)
    ├── scripts/         # Python visualisation utilities
    └── data/
        ├── osm/         # OpenStreetMap extracts (not committed — see setup below)
        ├── orders/      # Simulated order data + MILP hub output
        └── logs/        # Simulation output CSVs (not committed)

## Milestones

- [x] Milestone 1 — C++ Engine (SoA, DES, Quadtree, rule-based agent)
- [x] Milestone 2 — OSM map parsing + A* pathfinding on real Singapore roads
- [x] Milestone 3 — MILP hub optimisation (HiGHS) + management dashboard
- [ ] Milestone 4 — pybind11 bridge + Python AI layer
- [ ] Milestone 5 — Deck.gl web dashboard

---

## Milestone 1 — C++ Engine

**What it does:** Runs a discrete event simulation of delivery robots
across a virtual world. Instead of ticking every millisecond, the engine
jumps directly between meaningful events (DEPART, ARRIVE, RECHARGE).

**Key design decisions:**

- Struct of Arrays (SoA) memory layout for cache efficiency —
  all robot x-positions in one contiguous array, y-positions in another.
  At 500+ robots this measurably reduces cache misses vs Array of Structs.
- Priority-queue DES: 500 robots over 3600s = ~16,000 events
  instead of 3,600,000 millisecond ticks.
- Static quadtree spatial partitioning rebuilt every 50 events.
  Turns O(n^2) proximity checks into O(log n).
- Rule-based battery agent: battery < 20% triggers return to nearest hub.

**Tested:** 500 robots, 3600s, 16,031 events processed.

---

## Milestone 2 — OSM Map + A* Pathfinding

**What it does:** Replaces random destinations with real Singapore road
navigation. Robots travel along actual streets in the Toa Payoh /
Novena / Bishan area.

**Pipeline:**

    region.osm.pbf (234MB)
        → parse_osm.py       → 785,200 nodes, 1,756,022 edges (all Singapore)
        → sample_graph.py    → 5,000 connected nodes, 10,840 edges (subgraph)
        → RoadGraph.cpp      → adjacency list in C++
        → AStar.cpp          → A* with Euclidean heuristic

**Parameters:** Robot speed 5 m/s, delivery radius 800m, hubs snap to
nearest real road node.

**Tested:** 50 robots, 28,800s, 34,368 events, 16,936 deliveries,
0 failed A* paths.

---

## Milestone 3 — MILP Hub Optimisation

**What it does:** Solves the Facility Location Problem — given 16,500
delivery orders across 90 days, find the 3 hub locations that minimise
total weighted travel distance.

**Formulation:**

    Minimise:   sum(demand[i] * distance(i,j) * x[i,j])
    Subject to: exactly 3 hubs selected
                each demand node assigned to exactly one hub
                assignment only to open hubs (x[i,j] <= y[j])

**Solver:** HiGHS (open source MILP, production-grade)
205,800 variables, 209,866 constraints, solve time 124s, status kOptimal.

**Result:**

    Baseline (hardcoded hubs)  :  8,235,794 weighted metre-orders
    Optimised (MILP hubs)      :  6,095,001 weighted metre-orders
    Improvement                :      26.0%

**Simulation comparison (50 robots, 8 hours):**

    Metric          Hardcoded    MILP      Delta
    Deliveries      16,950       17,634    +684  (+4.0%)
    Energy          676.23 kWh   674.21    -2.02 (-0.3%)

---

## Build Instructions

### Requirements

- Ubuntu 24.04 (or WSL2 on Windows 11)
- g++ 13+, cmake 3.20+, python3 12+

### Install system dependencies

    sudo apt install -y build-essential g++-13 cmake python3 python3-pip git

### Install Python dependencies

    pip3 install pandas matplotlib osmium networkx highspy --break-system-packages

### Build C++ engine

    mkdir build && cd build
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make -j$(nproc)

### OSM setup (one-time, ~5 minutes)

    cd data/osm
    wget "https://download.geofabrik.de/asia/malaysia-singapore-brunei-latest.osm.pbf" -O region.osm.pbf
    cd ../..
    python3 scripts/parse_osm.py
    python3 scripts/sample_graph.py

---

## Running the Simulation

    # From project root
    mkdir -p data/logs

    # Hardcoded hubs
    ./build/engine/lastmile_engine [robots] [duration_seconds]

    # MILP optimised hubs
    ./build/engine/lastmile_engine [robots] [duration_seconds] --hubs data/orders/hubs_optimised.csv

    # Examples
    ./build/engine/lastmile_engine 50 3600                                          # 1 hour
    ./build/engine/lastmile_engine 50 28800                                         # 8 hours
    ./build/engine/lastmile_engine 50 28800 --hubs data/orders/hubs_optimised.csv  # MILP hubs

## Running the OR Module

    # Generate 90 days of simulated orders
    python3 or_module/generate_orders.py

    # Run MILP optimisation (~2 minutes)
    python3 or_module/optimise_hubs.py

## Visualisation

    python3 scripts/visualize.py              # throughput + battery + heatmap
    python3 scripts/visualize_overlay.py      # robot activity on real streets
    python3 scripts/visualize_graph.py        # road network only
    python3 scripts/visualize_comparison.py   # before vs after dashboard

    # All images saved to data/logs/
