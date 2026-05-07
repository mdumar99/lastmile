# Last-Mile Delivery Simulation

A multi-agent simulation platform modelling a city's last-mile delivery
ecosystem using Discrete Event Simulation (DES).

## Architecture

lastmile/
├── engine/          # C++20 simulation core
│   ├── include/     # Headers (Robot, Quadtree, EventScheduler, Simulation)
│   └── src/         # Implementations + main.cpp
├── or_module/       # MILP hub optimiser (Milestone 3)
├── ai_layer/        # RL agent (Milestone 4)
├── bridge/          # pybind11 C++↔Python bridge (Milestone 4)
├── dashboard/       # Deck.gl web dashboard (Milestone 5)
├── scripts/         # Python utilities (visualize.py)
└── data/
├── osm/         # OpenStreetMap extracts (not committed)
├── orders/      # Simulated order data
└── logs/        # Simulation output CSVs (not committed)
## Phase 1 — Done

- SoA (Struct of Arrays) robot memory layout for cache efficiency
- Priority-queue Discrete Event Simulation engine
- Static quadtree spatial partitioning (rebuilt every N events)
- Rule-based battery agent (low battery → nearest hub)
- CSV event logging + Python dashboard

## Build Instructions

### Requirements
- Ubuntu 24.04 (or WSL2 on Windows 11)
- g++ 13+, cmake 3.20+, python3 12+

### Build

```bash
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

### Run

```bash
# From project root
mkdir -p data/logs
./build/engine/lastmile_engine [num_robots] [duration_seconds]

# Examples
./build/engine/lastmile_engine 50 3600    # 50 robots, 1 hour
./build/engine/lastmile_engine 500 3600   # 500 robots, 1 hour
```

### Visualize

```bash
pip3 install pandas matplotlib --break-system-packages
python3 scripts/visualize.py
# Dashboard saved to data/logs/dashboard.png
```

## Milestones

- [x] Milestone 1 — C++ Engine (SoA, DES, Quadtree, rule-based agent)
- [ ] Milestone 2 — OSM map parsing + A* pathfinding
- [ ] Milestone 3 — MILP hub optimisation (HiGHS)
- [ ] Milestone 4 — pybind11 bridge + Python AI layer
- [ ] Milestone 5 — Deck.gl dashboard
