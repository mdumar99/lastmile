# Last-Mile Delivery Simulation

A multi-agent simulation platform modelling a city's last-mile delivery
ecosystem using Discrete Event Simulation (DES).

## Architecture

    lastmile/
    ├── engine/          # C++20 simulation core
    │   ├── include/     # Headers (Robot, Quadtree, EventScheduler, Simulation, RoadGraph, AStar)
    │   └── src/         # Implementations + main.cpp
    ├── or_module/       # MILP hub optimiser (Milestone 3)
    ├── ai_layer/        # RL agent (Milestone 4)
    ├── bridge/          # pybind11 C++↔Python bridge (Milestone 4)
    ├── dashboard/       # Deck.gl web dashboard (Milestone 5)
    ├── scripts/         # Python utilities
    └── data/
        ├── osm/         # OpenStreetMap extracts (not committed)
        ├── orders/      # Simulated order data
        └── logs/        # Simulation output CSVs (not committed)

## Milestones

- [x] Milestone 1 — C++ Engine (SoA, DES, Quadtree, rule-based agent)
- [x] Milestone 2 — OSM map parsing + A* pathfinding on real Singapore roads
- [ ] Milestone 3 — MILP hub optimisation (HiGHS)
- [ ] Milestone 4 — pybind11 bridge + Python AI layer
- [ ] Milestone 5 — Deck.gl dashboard

## Milestone 1 — C++ Engine

- SoA (Struct of Arrays) robot memory layout for cache efficiency
- Priority-queue Discrete Event Simulation engine (jumps between events, no fixed tick)
- Static quadtree spatial partitioning (rebuilt every N events)
- Rule-based battery agent (low battery -> nearest hub)
- CSV event logging + Python dashboard
- Tested: 500 robots, 3600s, 16031 events processed

## Milestone 2 — OSM Map + A*

- Downloads Malaysia/Singapore/Brunei OSM extract from Geofabrik (234MB)
- Parses 785,200 Singapore road nodes and 1,756,022 directed edges
- BFS samples a 5,000-node connected subgraph (Toa Payoh / Novena / Bishan area)
- Converts lat/lon to local XY metres for simulation coordinate space
- A* pathfinder with Euclidean heuristic navigates real road topology
- Hubs snap to nearest real road nodes
- Robot speed: 5 m/s, delivery radius: 800m
- Tested: 50 robots, 28800s, 34368 events, 16936 deliveries, 0 failed A* paths

## Build Instructions

### Requirements

- Ubuntu 24.04 (or WSL2 on Windows 11)
- g++ 13+, cmake 3.20+, python3 12+

### Build

    mkdir build && cd build
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make -j$(nproc)

### Run

    # From project root
    mkdir -p data/logs
    ./build/engine/lastmile_engine [num_robots] [duration_seconds]

    # Examples
    ./build/engine/lastmile_engine 50 3600      # 50 robots, 1 hour
    ./build/engine/lastmile_engine 50 28800     # 50 robots, 8 hours
    ./build/engine/lastmile_engine 500 3600     # 500 robots, 1 hour

### OSM Setup (one-time)

    # Download Singapore road data
    cd data/osm
    wget "https://download.geofabrik.de/asia/malaysia-singapore-brunei-latest.osm.pbf" -O region.osm.pbf

    # Parse and sample road graph
    cd ../..
    pip3 install osmium networkx --break-system-packages
    python3 scripts/parse_osm.py
    python3 scripts/sample_graph.py

### Visualize

    pip3 install pandas matplotlib --break-system-packages

    python3 scripts/visualize.py           # throughput + battery + heatmap dashboard
    python3 scripts/visualize_overlay.py   # robot activity overlaid on real streets
    python3 scripts/visualize_graph.py     # road network only

    # Images saved to data/logs/
