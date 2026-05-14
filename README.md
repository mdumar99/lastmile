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
    ├── ai_layer/        # Python experiment runner + offline RL pipeline
    │   └── rl/          # Experience collection, training, evaluation
    ├── bridge/          # pybind11 C++↔Python bridge + Protobuf schema
    │   └── proto/       # simulation.proto + generated bindings
    ├── dashboard/       # React + Deck.gl web dashboard
    ├── opengl_view/     # C++ OpenGL engineering view (GLFW + GLEW)
    ├── scripts/         # Python visualisation + OSM utilities
    └── data/
        ├── osm/         # OpenStreetMap extracts (not committed)
        ├── orders/      # Simulated orders + MILP hub outputs
        └── logs/        # Simulation output CSVs/proto (not committed)

##  Completed

    C++ Engine            SoA layout, DES priority queue, quadtree, rule-based agent
    OSM + A*              Real Singapore roads, A* pathfinding, 0 failed paths
    MILP optimiser        26% hub placement improvement via HiGHS
    pybind11 bridge       Python calling C++ directly, experiment runner
    Deck.gl dashboard     Interactive map, heatmap, before/after KPIs

    Dynamic quadtree      Per-move update instead of full rebuild (2.4x faster)
    Full event taxonomy   TRAFFIC_JAM, DELIVERY_FAIL, WEATHER_DELAY added
    Multi-district OSM    50,000 -> 681,369 nodes, full Singapore island 47.7km x 28.2km
    TBB parallelism       Parallel A* via Intel TBB: 500 robots 3.9s -> 1.6s
    Rolling MILP          Re-optimises hubs every 30 days as demand shifts
    Protobuf bridge       Binary simulation output, Python reads via _pb2

## In Progress

    feature/offline-rl    merged — behavioural cloning policy, +3.9% deliveries
                              zone-gated policy outperforms rule-based in live sim
                              full ANALYSIS.md documenting what worked and what didn't
    feature/opengl-view   in progress — C++ OpenGL engineering view
                              robots rendered as coloured dots on dark background
                              hub markers as yellow triangles, auto-scaling world bounds
                              road network overlay deferred (next session)
    online-rl             planned — restructure engine with step() interface
                              enable episode-by-episode online RL training

---

## Key Results

    Metric                           Value
    Singapore road nodes parsed      785,200
    Simulation subgraph              681,369 nodes, 1,543,768 edges
    Coverage                         47.7km x 28.2km (full Singapore island)
    Max robots tested                2,000
    Events at 2000 robots (1h)       76,697
    Wall time at 2000 robots         5.89s (TBB, ~4 cores)
    Failed A* paths (full island)    <1.5% across all scales
    MILP improvement                 26.0% reduction in weighted travel distance
    TBB speedup (500 robots)         3.9s -> 1.6s (2.4x)
    RL policy improvement            +3.9% deliveries (zone-gated, 3-seed average)
    RL policy energy trade-off       +3.3% energy (acceptable operational cost)

---

## Build Instructions

### Requirements

    Ubuntu 24.04 (or WSL2 on Windows 11)
    g++ 13+, cmake 3.20+, python3 12+

### System dependencies

    sudo apt install -y build-essential g++-13 cmake python3 python3-pip \
                        git libtbb-dev libprotobuf-dev protobuf-compiler \
                        libglfw3-dev libglew-dev libglm-dev

### Python dependencies

    pip3 install pandas matplotlib osmium networkx highspy pybind11 \
                 protobuf torch scikit-learn --break-system-packages

### Build

    mkdir build && cd build
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make -j$(nproc)
    cd ..
    cp build/bridge/lastmile.so .

### OSM setup (one-time, ~10 minutes)

    cd data/osm
    wget "https://download.geofabrik.de/asia/malaysia-singapore-brunei-latest.osm.pbf" \
         -O region.osm.pbf
    cd ../..
    python3 scripts/parse_osm.py      # extracts 785k Singapore nodes
    python3 scripts/sample_graph.py   # BFS samples full island (681k nodes)

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
    ./build/engine/lastmile_engine 1000 3600     # 1000 robots, 1 hour

## OpenGL Engineering View

    # Run simulation with live OpenGL window
    ./build/opengl_view/lastmile_gl [robots] [duration_seconds]

    # Example
    ./build/opengl_view/lastmile_gl 100 3600

    # Colour coding:
    #   Green  = delivering
    #   Blue   = idle
    #   Orange = returning to hub
    #   Yellow = charging
    #   Red    = blocked
    #   Yellow triangles = hub locations

## OR Module

    # Generate 90 days of simulated orders
    python3 or_module/generate_orders.py

    # Run single MILP optimisation (~2 minutes)
    python3 or_module/optimise_hubs.py

    # Run rolling MILP (re-optimises every 30 days)
    python3 or_module/rolling_milp.py

## Offline RL Pipeline

    # Collect experience tuples from rule-based agent
    python3 ai_layer/rl/collect_experience_v2.py

    # Train policy (3 architectures compared)
    python3 ai_layer/rl/train_policy_v2.py

    # Evaluate statistically
    python3 ai_layer/rl/evaluate_policy.py

    # Run live simulation with RL policy hooked into C++ engine
    python3 ai_layer/rl/run_policy_simulation_v3.py

    # Read full analysis
    cat ai_layer/rl/ANALYSIS.md

## Python Bridge

    import lastmile

    engine = lastmile.SimEngine(robots=50, duration=3600,
                                low_battery=20.0,
                                jam_prob=0.02,
                                fail_prob=0.05)
    engine.set_hubs_csv("data/orders/hubs_optimised.csv")
    engine.set_log_path("data/logs/run.csv")
    engine.set_policy(my_policy_fn)   # optional RL policy callback
    engine.run()
    stats = engine.get_stats()

## Protobuf Bridge

    ./build/engine/lastmile_engine 50 3600 --proto data/logs/sim_output.pb

    import sys; sys.path.insert(0, "bridge/proto")
    from simulation_pb2 import SimOutput
    with open("data/logs/sim_output.pb", "rb") as f:
        output = SimOutput()
        output.ParseFromString(f.read())
    print(output.stats.total_deliveries)

## Visualisation

    python3 scripts/visualize.py              # throughput + battery + heatmap
    python3 scripts/visualize_overlay.py      # robot activity on real streets
    python3 scripts/visualize_comparison.py   # before vs after dashboard
    python3 scripts/export_dashboard_data.py  # export JSON for Deck.gl

    cd dashboard && npm start                 # Deck.gl map dashboard
    # Open http://localhost:3000

---

## How the System Works Together

    C++ Engine  ←→  pybind11 bridge  ←→  Python AI / OR layer
    C++ Engine  ←→  Protobuf bridge  ←→  Python analytics / dashboard
    C++ Engine  ←→  OpenGL view      ←→  Real-time engineering display

### The C++ Engine (Brawn)

    main.cpp / lastmile_gl
      └── Simulation
            ├── RoadGraph        681,369 Singapore road nodes, 1,543,768 edges
            ├── AStar            A* with max_dist cutoff for island-scale search
            ├── ParallelPlanner  TBB parallel A* across CPU cores
            ├── Quadtree         dynamic per-move spatial index
            ├── EventScheduler   DES priority queue (6 event types)
            ├── RobotPool        Struct of Arrays for cache efficiency
            ├── ProtoWriter      binary output via Protobuf
            └── DecisionCallback RL policy hook (Python callable)

### The Python Layer (Brain)

    or_module/     MILP facility location, rolling monthly re-optimisation
    ai_layer/      pybind11 experiments, offline RL pipeline
    scripts/       OSM parsing, visualisation, dashboard export
    dashboard/     React + Deck.gl interactive Singapore map

### Data Flow

    OSM file (234MB)
        → parse_osm.py → 785k nodes
        → sample_graph.py → 681k connected nodes (full island)
        → RoadGraph.cpp

    generate_orders.py → orders.csv (16,500 orders, 90 days)
        → optimise_hubs.py → hubs_optimised.csv
        → rolling_milp.py → rolling_hubs_latest.csv

    C++ engine
        → sim_log.csv
        → sim_output.pb
        → pybind11 stats dict
        → OpenGL window

    export_dashboard_data.py
        → simulation.json → Deck.gl dashboard
