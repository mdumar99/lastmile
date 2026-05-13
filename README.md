# Last-Mile Delivery Simulation

A multi-agent simulation platform modelling a city's last-mile delivery
ecosystem using Discrete Event Simulation (DES). Built in two layers:
a high-performance C++20 engine and a Python analytics/optimisation stack.

## Architecture

    lastmile/
    ├── engine/          # C++20 simulation core
    │   ├── include/     # Robot, Quadtree, EventScheduler, Simulation,
    │   │                # RoadGraph, AStar, ParallelPlanner, ProtoWriter
    │   └── src/         # Implementations + main.cpp + simulation.pb.cc
    ├── or_module/       # MILP hub optimiser (HiGHS) + rolling MILP
    ├── ai_layer/        # Python experiment runner via pybind11 bridge
    ├── bridge/          # pybind11 C++↔Python bridge + Protobuf schema
    │   └── proto/       # simulation.proto + generated bindings
    ├── dashboard/       # React + Deck.gl web dashboard
    ├── scripts/         # Python visualisation + OSM utilities
    └── data/
        ├── osm/         # OpenStreetMap extracts (not committed)
        ├── orders/      # Simulated orders + MILP hub outputs
        └── logs/        # Simulation output CSVs/proto (not committed)

## Phase 1 — Complete

    C++ Engine            SoA layout, DES priority queue, quadtree, rule-based agent
    OSM + A*              Real Singapore roads, A* pathfinding, 0 failed paths
    MILP optimiser        26% hub placement improvement via HiGHS
    pybind11 bridge       Python calling C++ directly, experiment runner
    Deck.gl dashboard     Interactive map, heatmap, before/after KPIs

## Phase 2 — Complete

    Dynamic quadtree      Per-move update instead of full rebuild (2.4x faster)
    Full event taxonomy   TRAFFIC_JAM, DELIVERY_FAIL, WEATHER_DELAY added
    Multi-district OSM    5,000 -> 50,000 nodes, 6.7km x 10.6km Singapore
    TBB parallelism       Parallel A* via Intel TBB: 500 robots 3.9s -> 1.6s
    Rolling MILP          Re-optimises hubs every 30 days as demand shifts
    Protobuf bridge       Binary simulation output, Python reads via _pb2

## Phase 3 — Planned (feature branches)

    feature/offline-rl    Train RL policy on Phase 1 logs, evaluate vs rule-based
    feature/gurobi        Swap HiGHS for Gurobi (academic license)
    feature/opengl-view   C++ engineering view alongside Deck.gl dashboard

---

## Key Results

    Metric                         Value
    Singapore road nodes parsed    785,200
    Simulation subgraph            50,000 nodes, 112,614 edges
    Coverage                       6.7km x 10.6km (central Singapore)
    Max robots tested              2,000
    Events at 2000 robots (1h)     76,697
    Wall time at 2000 robots       5.89s (TBB, ~4 cores)
    Failed A* paths                0 (across all runs)
    MILP improvement               26.0% reduction in weighted travel distance
    TBB speedup (500 robots)       3.9s -> 1.6s (2.4x)

---

## Build Instructions

### Requirements

    Ubuntu 24.04 (or WSL2 on Windows 11)
    g++ 13+, cmake 3.20+, python3 12+

### System dependencies

    sudo apt install -y build-essential g++-13 cmake python3 python3-pip \
                        git libtbb-dev libprotobuf-dev protobuf-compiler

### Python dependencies

    pip3 install pandas matplotlib osmium networkx highspy pybind11 protobuf \
                 --break-system-packages

### Build

    mkdir build && cd build
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make -j$(nproc)
    cd ..
    cp build/bridge/lastmile.so .

### OSM setup (one-time, ~5 minutes)

    cd data/osm
    wget "https://download.geofabrik.de/asia/malaysia-singapore-brunei-latest.osm.pbf" \
         -O region.osm.pbf
    cd ../..
    python3 scripts/parse_osm.py
    python3 scripts/sample_graph.py

---

## Running the Simulation

    mkdir -p data/logs

    # Hardcoded hubs
    ./build/engine/lastmile_engine [robots] [duration_seconds]

    # MILP optimised hubs
    ./build/engine/lastmile_engine [robots] [duration_seconds] \
        --hubs data/orders/hubs_optimised.csv

    # Rolling MILP hubs (latest 30-day window)
    ./build/engine/lastmile_engine [robots] [duration_seconds] \
        --hubs data/orders/rolling_hubs_latest.csv

    # With Protobuf binary output
    ./build/engine/lastmile_engine [robots] [duration_seconds] \
        --proto data/logs/sim_output.pb

    # Examples
    ./build/engine/lastmile_engine 50 3600       # 50 robots, 1 hour
    ./build/engine/lastmile_engine 500 3600      # 500 robots, 1 hour
    ./build/engine/lastmile_engine 2000 3600     # 2000 robots, 1 hour

## OR Module

    # Generate 90 days of simulated orders
    python3 or_module/generate_orders.py

    # Run single MILP optimisation (~2 minutes)
    python3 or_module/optimise_hubs.py

    # Run rolling MILP (re-optimises every 30 days)
    python3 or_module/rolling_milp.py

## Python Bridge

    import lastmile

    engine = lastmile.SimEngine(robots=50, duration=3600,
                                low_battery=20.0,
                                jam_prob=0.02,
                                fail_prob=0.05)
    engine.set_hubs_csv("data/orders/hubs_optimised.csv")
    engine.set_log_path("data/logs/run.csv")
    engine.run()
    stats = engine.get_stats()
    # keys: deliveries, energy_kwh, recharges, failed_paths,
    #       traffic_jams, delivery_fails, weather_delays, parallel_batches

    # Run all experiments
    python3 ai_layer/run_experiments.py

## Protobuf Bridge

    # Run simulation with binary output
    ./build/engine/lastmile_engine 50 3600 --proto data/logs/sim_output.pb

    # Read from Python
    import sys
    sys.path.insert(0, "bridge/proto")
    from simulation_pb2 import SimOutput

    with open("data/logs/sim_output.pb", "rb") as f:
        output = SimOutput()
        output.ParseFromString(f.read())

    print(output.stats.total_deliveries)
    print(output.events[0].type)

## Visualisation

    python3 scripts/visualize.py              # throughput + battery + heatmap
    python3 scripts/visualize_overlay.py      # robot activity on real streets
    python3 scripts/visualize_graph.py        # road network
    python3 scripts/visualize_comparison.py   # before vs after dashboard
    python3 scripts/export_dashboard_data.py  # export JSON for Deck.gl

    # Start Deck.gl dashboard
    cd dashboard && npm start
    # Open http://localhost:3000





---

## How the System Works Together

The project is split into two layers that communicate through two bridges:

    C++ Engine  ←→  pybind11 bridge  ←→  Python AI / OR layer
    C++ Engine  ←→  Protobuf bridge  ←→  Python analytics / dashboard

### The C++ Engine (Brawn)

The engine runs entirely in C++ and owns all performance-critical work:

    main.cpp
      └── Simulation
            ├── RoadGraph      loads 50,000 Singapore road nodes + 112,614 edges
            ├── AStar          finds shortest path between any two road nodes
            ├── ParallelPlanner  batches A* calls, solves in parallel via TBB
            ├── Quadtree       spatial index — updates per robot move, not full rebuild
            ├── EventScheduler priority queue — jumps between events, no fixed tick
            ├── RobotPool      Struct of Arrays layout for cache-efficient updates
            └── ProtoWriter    serialises events to binary protobuf at end of run

At each simulated event:
  1. EventScheduler pops the earliest event (DEPART / ARRIVE / RECHARGE /
     TRAFFIC_JAM / DELIVERY_FAIL / WEATHER_DELAY)
  2. The handler decides what to do (deliver, recharge, wait, retry)
  3. PathRequests accumulate in a batch; when the batch is full,
     ParallelPlanner solves all paths simultaneously across CPU cores
  4. Results feed back into EventScheduler as future ARRIVE events
  5. Every robot move calls Quadtree.update() — surgical re-index, not full rebuild
  6. Events are logged to CSV and/or Protobuf binary

### The Python Layer (Brain)

Python owns everything above the raw simulation:

    or_module/
      generate_orders.py   →  16,500 simulated orders with realistic demand patterns
      optimise_hubs.py     →  MILP facility location (HiGHS), 205,800 variables
      rolling_milp.py      →  re-runs MILP every 30 days as demand shifts

    ai_layer/
      run_experiments.py   →  calls C++ engine via pybind11, varies parameters,
                               collects stats, plots results

    scripts/
      parse_osm.py         →  extracts Singapore roads from 234MB OSM file
      sample_graph.py      →  BFS samples 50,000 connected nodes
      export_dashboard_data.py  →  runs both simulations, converts XY to lat/lon,
                                    exports 526KB JSON for Deck.gl

    dashboard/
      App.js               →  React + Deck.gl, reads simulation.json,
                               renders heatmap + robot positions on Singapore map

### The Two Bridges

    pybind11 bridge (lastmile.so)
      Python imports lastmile.so like any Python module.
      SimEngine.run() calls directly into C++ — same process, same memory.
      No subprocess, no serialisation overhead during the run.
      Stats are returned as a Python dict when the run completes.

    Protobuf bridge (simulation.pb / simulation_pb2.py)
      C++ writes binary SimOutput to disk at end of run.
      Python reads it via generated _pb2 bindings — typed fields, no CSV parsing.
      Schema defined in simulation.proto — adding fields is backward compatible.

### Data Flow (end to end)

    OSM file (234MB)
        → parse_osm.py → nodes.csv + edges.csv (785k nodes)
        → sample_graph.py → graph_nodes.csv + graph_edges.csv (50k nodes)
        → RoadGraph.cpp (loaded at engine startup)

    generate_orders.py → orders.csv (16,500 orders, 90 days)
        → optimise_hubs.py → hubs_optimised.csv (3 hub locations)
        → rolling_milp.py → rolling_hubs_latest.csv (re-optimised monthly)

    C++ engine (reads graph + hubs, runs DES)
        → sim_log.csv (human-readable events)
        → sim_output.pb (binary events + stats)
        → pybind11 stats dict (in-memory, no file)

    export_dashboard_data.py (reads CSVs, runs engine via pybind11)
        → simulation.json (526KB, lat/lon converted)
        → dashboard/public/data/simulation.json

    React dashboard (reads simulation.json)
        → Deck.gl heatmap + robot layer on Singapore map
        → KPI cards, throughput charts, before/after toggle
