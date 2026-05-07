#pragma once
#include "Robot.h"
#include "Quadtree.h"
#include "EventScheduler.h"
#include <string>
#include <fstream>
#include <random>

struct Hub {
    uint32_t id;
    float    x, y;
    float    charge_rate;  // % battery per simulated second
};

struct SimConfig {
    int         num_robots      = 50;
    double      sim_duration_s  = 3600.0;
    float       world_width     = 1000.0f;
    float       world_height    = 1000.0f;
    float       battery_drain   = 0.05f;
    float       low_battery_thr = 20.0f;
    int         quadtree_rebuild= 50;
    std::string log_path        = "data/logs/sim_log.csv";
};

class Simulation {
public:
    explicit Simulation(SimConfig cfg);
    void run();

    struct Stats {
        uint32_t total_deliveries;
        double   total_energy_kwh;
        uint32_t recharge_events;
    };
    Stats stats() const;

private:
    SimConfig      _cfg;
    RobotPool      _robots;
    Quadtree       _qt;
    EventScheduler _sched;
    double         _now{0.0};
    std::mt19937   _rng;

    std::vector<Hub> _hubs;
    std::ofstream    _log;
    int              _event_count{0};
    Stats            _stats{};

    void handle_depart  (const Event& e);
    void handle_arrive  (const Event& e);
    void handle_recharge(const Event& e);

    float  distance(float x1, float y1, float x2, float y2) const;
    Hub&   nearest_hub(float x, float y);
    void   log_event(const Event& e, const std::string& note = "");
    void   maybe_rebuild_quadtree(int event_count);
};
