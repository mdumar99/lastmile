#include "Simulation.h"
#include <iostream>
#include <cmath>
#include <algorithm>
#include <iomanip>

Simulation::Simulation(SimConfig cfg)
    : _cfg(cfg)
    , _qt(AABB{cfg.world_width / 2.0f, cfg.world_height / 2.0f,
               cfg.world_width / 2.0f, cfg.world_height / 2.0f})
    , _rng(std::random_device{}())
{
    // 3 hubs — Phase 1 hardcoded, replaced by MILP output in Milestone 3
    _hubs = {
        {0, 200.0f, 200.0f, 1.5f},
        {1, 500.0f, 800.0f, 1.5f},
        {2, 800.0f, 300.0f, 1.5f},
    };

    std::uniform_real_distribution<float> dx(0.0f, cfg.world_width);
    std::uniform_real_distribution<float> dy(0.0f, cfg.world_height);
    std::uniform_real_distribution<float> dbatt(60.0f, 100.0f);

    for (int i = 0; i < cfg.num_robots; ++i) {
        std::size_t rid = _robots.add(dx(_rng), dy(_rng), dbatt(_rng));
        _qt.insert(static_cast<uint32_t>(rid),
                   _robots.x[rid], _robots.y[rid]);
        double jitter = std::uniform_real_distribution<double>(0.0, 5.0)(_rng);
        _sched.push({jitter, EventType::DEPART,
                     static_cast<uint32_t>(rid), 0});
    }

    // Open log — creates data/logs/ relative to where binary is run
    _log.open(cfg.log_path);
    if (!_log.is_open())
        std::cerr << "[WARN] Could not open log: " << cfg.log_path << "\n";
    else
        _log << "time,event,robot_id,x,y,battery,status,note\n";
}

void Simulation::run() {
    std::cout << std::fixed << std::setprecision(2);
    std::cout << "[SIM] Starting: " << _cfg.num_robots
              << " robots, " << _cfg.sim_duration_s << "s\n\n";

    while (!_sched.empty() && _sched.peek_time() <= _cfg.sim_duration_s) {
        Event e = _sched.pop();
        _now = e.time;
        ++_event_count;

        switch (e.type) {
            case EventType::DEPART:   handle_depart(e);   break;
            case EventType::ARRIVE:   handle_arrive(e);   break;
            case EventType::RECHARGE: handle_recharge(e); break;
        }

        maybe_rebuild_quadtree(_event_count);
    }

    auto s = stats();
    std::cout << "[SIM] Done.\n";
    std::cout << "  Events processed : " << _event_count       << "\n";
    std::cout << "  Deliveries       : " << s.total_deliveries  << "\n";
    std::cout << "  Energy used      : " << s.total_energy_kwh << " kWh\n";
    std::cout << "  Recharge events  : " << s.recharge_events   << "\n";
}

void Simulation::handle_depart(const Event& e) {
    uint32_t rid = e.robot_id;

    // Rule-based agent: low battery → return to nearest hub
    if (_robots.battery[rid] < _cfg.low_battery_thr) {
        Hub& h = nearest_hub(_robots.x[rid], _robots.y[rid]);
        double travel = distance(_robots.x[rid], _robots.y[rid],
                                 h.x, h.y) / 2.0;
        _robots.status[rid] = RobotStatus::RETURNING;
        _sched.push({_now + travel, EventType::ARRIVE, rid, h.id});
        log_event(e, "low_battery->hub");
        return;
    }

    // Normal delivery: random destination
    std::uniform_real_distribution<float> dx(0.0f, _cfg.world_width);
    std::uniform_real_distribution<float> dy(0.0f, _cfg.world_height);
    float tx = dx(_rng), ty = dy(_rng);
    float dist = distance(_robots.x[rid], _robots.y[rid], tx, ty);

    _robots.battery[rid] -= dist * _cfg.battery_drain;
    _robots.battery[rid]  = std::max(0.0f, _robots.battery[rid]);
    _robots.total_energy_used[rid] += dist * 0.0001f;
    _robots.status[rid] = RobotStatus::DELIVERING;

    _sched.push({_now + dist / 2.0, EventType::ARRIVE, rid, 0});
    log_event(e, "depart->deliver");
}

void Simulation::handle_arrive(const Event& e) {
    uint32_t rid = e.robot_id;

    if (_robots.status[rid] == RobotStatus::RETURNING) {
        Hub& h = nearest_hub(_robots.x[rid], _robots.y[rid]);
        float  charge_needed = 100.0f - _robots.battery[rid];
        double charge_time   = charge_needed / h.charge_rate;
        _robots.status[rid]  = RobotStatus::CHARGING;
        _sched.push({_now + charge_time, EventType::RECHARGE, rid, h.id});
        ++_stats.recharge_events;
        log_event(e, "arrived_hub");
    } else {
        ++_robots.deliveries_completed[rid];
        ++_stats.total_deliveries;
        _robots.status[rid] = RobotStatus::IDLE;
        double rest = std::uniform_real_distribution<double>(2.0, 8.0)(_rng);
        _sched.push({_now + rest, EventType::DEPART, rid, 0});
        log_event(e, "delivered");
    }
}

void Simulation::handle_recharge(const Event& e) {
    uint32_t rid = e.robot_id;
    _robots.battery[rid] = 100.0f;
    _robots.status[rid]  = RobotStatus::IDLE;
    _sched.push({_now + 1.0, EventType::DEPART, rid, 0});
    log_event(e, "fully_charged");
}

float Simulation::distance(float x1, float y1, float x2, float y2) const {
    float dx = x2 - x1, dy = y2 - y1;
    return std::sqrt(dx*dx + dy*dy);
}

Hub& Simulation::nearest_hub(float x, float y) {
    Hub* best = &_hubs[0];
    float best_d = distance(x, y, best->x, best->y);
    for (auto& h : _hubs) {
        float d = distance(x, y, h.x, h.y);
        if (d < best_d) { best_d = d; best = &h; }
    }
    return *best;
}

void Simulation::log_event(const Event& e, const std::string& note) {
    if (!_log.is_open()) return;
    uint32_t rid = e.robot_id;
    _log << _now                              << ","
         << eventTypeToString(e.type)         << ","
         << rid                               << ","
         << _robots.x[rid]                   << ","
         << _robots.y[rid]                   << ","
         << _robots.battery[rid]             << ","
         << statusToString(_robots.status[rid]) << ","
         << note                              << "\n";
}

void Simulation::maybe_rebuild_quadtree(int n) {
    if (n % _cfg.quadtree_rebuild != 0) return;
    _qt.clear();
    for (std::size_t i = 0; i < _robots.size(); ++i)
        _qt.insert(static_cast<uint32_t>(i), _robots.x[i], _robots.y[i]);
}

Simulation::Stats Simulation::stats() const {
    Stats s = _stats;
    s.total_energy_kwh = 0.0;
    for (auto e : _robots.total_energy_used)
        s.total_energy_kwh += e;
    return s;
}
