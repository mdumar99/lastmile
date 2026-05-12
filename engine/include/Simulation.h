#pragma once
#include "Robot.h"
#include "Quadtree.h"
#include "EventScheduler.h"
#include "RoadGraph.h"
#include "AStar.h"
#include <string>
#include <fstream>
#include <random>

struct Hub {
    uint32_t id;
    uint32_t node_id;
    float    x, y;
    float    charge_rate;
};

struct SimConfig {
    int         num_robots       = 50;
    double      sim_duration_s   = 28800.0;
    float       battery_drain    = 0.002f;
    float       low_battery_thr  = 20.0f;
    float       traffic_jam_prob = 0.02f;   // probability per depart
    float       delivery_fail_prob = 0.05f; // probability per arrive
    float       weather_interval = 3600.0f; // seconds between weather events
    std::string log_path         = "data/logs/sim_log.csv";
    std::string nodes_csv        = "data/osm/graph_nodes.csv";
    std::string edges_csv        = "data/osm/graph_edges.csv";
    std::string hubs_csv         = "";
};

class Simulation {
public:
    explicit Simulation(SimConfig cfg);
    void run();

    struct Stats {
        uint32_t total_deliveries;
        double   total_energy_kwh;
        uint32_t recharge_events;
        uint32_t failed_paths;
        uint32_t traffic_jams;
        uint32_t delivery_fails;
        uint32_t weather_delays;
    };
    Stats stats() const;

private:
    SimConfig      _cfg;
    RobotPool      _robots;
    Quadtree       _qt;
    EventScheduler _sched;
    RoadGraph      _graph;
    AStar          _astar;
    double         _now{0.0};
    std::mt19937   _rng;

    std::vector<Hub>      _hubs;
    std::vector<uint32_t> _robot_node;
    std::ofstream         _log;
    int                   _event_count{0};
    int                   _qt_updates{0};
    float                 _weather_speed_mult{1.0f}; // 1.0=normal, 0.5=slow
    Stats                 _stats{};

    void load_hubs_from_csv(const std::string& path);
    void load_hubs_hardcoded();
    void seed_weather_events();

    void handle_depart        (const Event& e);
    void handle_arrive        (const Event& e);
    void handle_recharge      (const Event& e);
    void handle_traffic_jam   (const Event& e);
    void handle_delivery_fail (const Event& e);
    void handle_weather_delay (const Event& e);

    float  distance(float x1, float y1, float x2, float y2) const;
    Hub&   nearest_hub(float x, float y);
    void   log_event(const Event& e, const std::string& note = "");
};
