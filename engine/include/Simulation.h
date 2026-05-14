#pragma once
#include "Robot.h"
#include "Quadtree.h"
#include "EventScheduler.h"
#include "RoadGraph.h"
#include "AStar.h"
#include "ParallelPlanner.h"
#include "ProtoWriter.h"
#include <string>
#include <fstream>
#include <random>
#include <vector>
#include <functional>

struct Hub {
    uint32_t id;
    uint32_t node_id;
    float    x, y;
    float    charge_rate;
};

struct SimConfig {
    int         num_robots         = 50;
    double      sim_duration_s     = 28800.0;
    float       battery_drain      = 0.002f;
    float       low_battery_thr    = 20.0f;
    float       traffic_jam_prob   = 0.02f;
    float       delivery_fail_prob = 0.05f;
    float       weather_interval   = 3600.0f;
    int         parallel_batch     = 32;
    std::string log_path           = "data/logs/sim_log.csv";
    std::string proto_path         = "";
    std::string nodes_csv          = "data/osm/graph_nodes.csv";
    std::string edges_csv          = "data/osm/graph_edges.csv";
    std::string hubs_csv           = "";
};

// ── Decision callback ──────────────────────────────────────────
// Called at each DEPART event with robot state.
// Returns: 0=DELIVER, 1=RECHARGE, 2=WAIT
// If nullptr, uses rule-based logic.
struct RobotDecisionState {
    uint32_t robot_id;
    float    battery;
    float    x, y;
    float    hub_dist;
    float    weather_mult;
    float    sim_time;
    int      deliveries_done;
    int      recharges_done;
    int      nearby_robots;
    int      max_hub_queue;
};

using DecisionCallback = std::function<int(const RobotDecisionState&)>;

class Simulation {
public:
    explicit Simulation(SimConfig cfg);
    void run();

    // Register Python policy callback
    void set_decision_callback(DecisionCallback cb) { _callback = cb; }

    struct Stats {
        uint32_t total_deliveries;
        double   total_energy_kwh;
        uint32_t recharge_events;
        uint32_t failed_paths;
        uint32_t traffic_jams;
        uint32_t delivery_fails;
        uint32_t weather_delays;
        uint32_t parallel_batches;
        uint32_t policy_decisions;  // how many times callback was called
    };
    Stats stats() const;

    std::vector<std::vector<float>> get_robot_states_raw() const;
    std::vector<int>                get_hub_queue_lengths() const;

private:
    SimConfig       _cfg;
    RobotPool       _robots;
    Quadtree        _qt;
    EventScheduler  _sched;
    RoadGraph       _graph;
    AStar           _astar;
    ParallelPlanner _planner;
    ProtoWriter     _proto;
    double          _now{0.0};
    std::mt19937    _rng;
    DecisionCallback _callback{nullptr};

    std::vector<Hub>      _hubs;
    std::vector<uint32_t> _robot_node;
    std::vector<int>      _robot_deliveries;  // per-robot delivery count
    std::vector<int>      _robot_recharges;   // per-robot recharge count
    std::ofstream         _log;
    int                   _event_count{0};
    int                   _qt_updates{0};
    float                 _weather_speed_mult{1.0f};
    Stats                 _stats{};

    struct PendingDepart {
        Event    event;
        uint32_t dest_nid;
        bool     to_hub;
    };
    std::vector<PendingDepart> _pending_departs;

    void load_hubs_from_csv(const std::string& path);
    void load_hubs_hardcoded();
    void seed_weather_events();
    void flush_pending_departs();

    // Makes a decision for one robot — uses callback if set,
    // otherwise falls back to rule-based logic
    // Returns: 0=DELIVER, 1=RECHARGE, 2=WAIT
    int  make_decision(uint32_t rid);

    void handle_depart        (const Event& e);
    void handle_arrive        (const Event& e);
    void handle_recharge      (const Event& e);
    void handle_traffic_jam   (const Event& e);
    void handle_delivery_fail (const Event& e);
    void handle_weather_delay (const Event& e);

    float distance(float x1, float y1, float x2, float y2) const;
    Hub&  nearest_hub(float x, float y);
    void  log_event(const Event& e, const std::string& note = "");
};
