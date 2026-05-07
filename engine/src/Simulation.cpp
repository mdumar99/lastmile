#include "Simulation.h"
#include <iostream>
#include <cmath>
#include <algorithm>
#include <iomanip>

static constexpr float ROBOT_SPEED_MS = 5.0f;   // metres per second (~18 km/h)
static constexpr float MAX_DELIVERY_RADIUS = 800.0f; // metres

Simulation::Simulation(SimConfig cfg)
    : _cfg(cfg)
    , _qt(AABB{500.0f, 500.0f, 2000.0f, 2000.0f})
    , _astar(_graph)
    , _rng(std::random_device{}())
{
    if (!_graph.load(cfg.nodes_csv, cfg.edges_csv))
        throw std::runtime_error("Failed to load road graph");

    // Snap hubs to nearest road nodes
    std::vector<std::pair<float,float>> hub_positions = {
        {200.0f, 200.0f},
        {500.0f, 800.0f},
        {800.0f, 300.0f},
    };

    for (std::size_t i = 0; i < hub_positions.size(); ++i) {
        auto [hx, hy] = hub_positions[i];
        uint32_t nid  = _graph.nearest_node(hx, hy);
        const Node& n = _graph.node(nid);
        _hubs.push_back({static_cast<uint32_t>(i), nid, n.x, n.y, 2.0f});
        std::cout << "[HUB " << i << "] node " << nid
                  << " at (" << n.x << ", " << n.y << ")\n";
    }

    // Spawn robots on random road nodes
    std::uniform_int_distribution<std::size_t> nd(
        0, _graph.node_ids().size() - 1);

    for (int i = 0; i < cfg.num_robots; ++i) {
        uint32_t    nid = _graph.node_ids()[nd(_rng)];
        const Node& n   = _graph.node(nid);
        std::size_t rid = _robots.add(n.x, n.y,
            std::uniform_real_distribution<float>(60.0f, 100.0f)(_rng));
        _robot_node.push_back(nid);
        _qt.insert(static_cast<uint32_t>(rid), n.x, n.y);
        double jitter = std::uniform_real_distribution<double>(0.0, 5.0)(_rng);
        _sched.push({jitter, EventType::DEPART,
                     static_cast<uint32_t>(rid), nid});
    }

    _log.open(cfg.log_path);
    if (!_log.is_open())
        std::cerr << "[WARN] Could not open log: " << cfg.log_path << "\n";
    else
        _log << "time,event,robot_id,x,y,battery,status,note\n";
}

void Simulation::run() {
    std::cout << std::fixed << std::setprecision(2);
    std::cout << "\n[SIM] Starting: " << _cfg.num_robots
              << " robots, " << _cfg.sim_duration_s << "s\n\n";

    while (!_sched.empty() &&
           _sched.peek_time() <= _cfg.sim_duration_s) {
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
    std::cout << "\n[SIM] Done.\n";
    std::cout << "  Events processed : " << _event_count       << "\n";
    std::cout << "  Deliveries       : " << s.total_deliveries  << "\n";
    std::cout << "  Energy used      : " << s.total_energy_kwh << " kWh\n";
    std::cout << "  Recharge events  : " << s.recharge_events   << "\n";
    std::cout << "  Failed A* paths  : " << s.failed_paths      << "\n";
}

void Simulation::handle_depart(const Event& e) {
    uint32_t rid = e.robot_id;

    // Rule-based agent: low battery → return to hub
    if (_robots.battery[rid] < _cfg.low_battery_thr) {
        Hub& h = nearest_hub(_robots.x[rid], _robots.y[rid]);
        PathResult path = _astar.find_path(_robot_node[rid], h.node_id);

        double travel;
        if (!path.found) {
            ++_stats.failed_paths;
            travel = distance(_robots.x[rid], _robots.y[rid],
                              h.x, h.y) / ROBOT_SPEED_MS;
        } else {
            travel = path.distance / ROBOT_SPEED_MS;
            _robots.battery[rid] -= path.distance * _cfg.battery_drain;
            _robots.battery[rid]  = std::max(0.0f, _robots.battery[rid]);
            _robots.total_energy_used[rid] += path.distance * 0.0001f;
        }
        _robots.status[rid] = RobotStatus::RETURNING;
        _sched.push({_now + travel, EventType::ARRIVE, rid, h.node_id});
        log_event(e, "low_battery->hub");
        return;
    }

    // Pick destination within MAX_DELIVERY_RADIUS
    const Node& origin = _graph.node(_robot_node[rid]);
    uint32_t dest_nid  = 0;
    float    best_dist = std::numeric_limits<float>::max();

    // Sample 20 random nodes, pick nearest within radius
    std::uniform_int_distribution<std::size_t> nd(
        0, _graph.node_ids().size() - 1);

    for (int attempt = 0; attempt < 20; ++attempt) {
        uint32_t    cid = _graph.node_ids()[nd(_rng)];
        const Node& cn  = _graph.node(cid);
        float dx = cn.x - origin.x, dy = cn.y - origin.y;
        float d  = std::sqrt(dx*dx + dy*dy);
        if (d < MAX_DELIVERY_RADIUS && d > 50.0f && d < best_dist) {
            best_dist = d;
            dest_nid  = cid;
        }
    }

    // Fallback: just pick any random node
    if (dest_nid == 0)
        dest_nid = _graph.node_ids()[nd(_rng)];

    const Node& dest = _graph.node(dest_nid);
    PathResult path  = _astar.find_path(_robot_node[rid], dest_nid);

    if (!path.found) {
        ++_stats.failed_paths;
        double rest = std::uniform_real_distribution<double>(1.0, 3.0)(_rng);
        _sched.push({_now + rest, EventType::DEPART, rid, _robot_node[rid]});
        return;
    }

    double travel = path.distance / ROBOT_SPEED_MS;
    _robots.battery[rid] -= path.distance * _cfg.battery_drain;
    _robots.battery[rid]  = std::max(0.0f, _robots.battery[rid]);
    _robots.total_energy_used[rid] += path.distance * 0.0001f;
    _robots.x[rid] = dest.x;
    _robots.y[rid] = dest.y;
    _robots.status[rid] = RobotStatus::DELIVERING;

    _sched.push({_now + travel, EventType::ARRIVE, rid, dest_nid});
    log_event(e, "depart->deliver");
}

void Simulation::handle_arrive(const Event& e) {
    uint32_t rid    = e.robot_id;
    _robot_node[rid] = e.node_id;

    if (_robots.status[rid] == RobotStatus::RETURNING) {
        Hub* hub = &_hubs[0];
        for (auto& h : _hubs)
            if (h.node_id == e.node_id) { hub = &h; break; }

        float  need  = 100.0f - _robots.battery[rid];
        double ctime = need / hub->charge_rate;
        _robots.status[rid] = RobotStatus::CHARGING;
        _sched.push({_now + ctime, EventType::RECHARGE, rid, e.node_id});
        ++_stats.recharge_events;
        log_event(e, "arrived_hub");
    } else {
        ++_robots.deliveries_completed[rid];
        ++_stats.total_deliveries;
        _robots.status[rid] = RobotStatus::IDLE;
        double rest = std::uniform_real_distribution<double>(2.0, 8.0)(_rng);
        _sched.push({_now + rest, EventType::DEPART, rid, e.node_id});
        log_event(e, "delivered");
    }
}

void Simulation::handle_recharge(const Event& e) {
    uint32_t rid = e.robot_id;
    _robots.battery[rid] = 100.0f;
    _robots.status[rid]  = RobotStatus::IDLE;
    _sched.push({_now + 1.0, EventType::DEPART, rid, e.node_id});
    log_event(e, "fully_charged");
}

float Simulation::distance(float x1, float y1, float x2, float y2) const {
    float dx = x2-x1, dy = y2-y1;
    return std::sqrt(dx*dx + dy*dy);
}

Hub& Simulation::nearest_hub(float x, float y) {
    Hub* best    = &_hubs[0];
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
    _log << _now                                 << ","
         << eventTypeToString(e.type)            << ","
         << rid                                  << ","
         << _robots.x[rid]                      << ","
         << _robots.y[rid]                      << ","
         << _robots.battery[rid]                << ","
         << statusToString(_robots.status[rid]) << ","
         << note                                 << "\n";
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
    for (auto v : _robots.total_energy_used)
        s.total_energy_kwh += v;
    return s;
}
