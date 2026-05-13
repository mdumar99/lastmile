#include "Simulation.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <cmath>
#include <algorithm>
#include <iomanip>

static constexpr float ROBOT_SPEED_MS      = 5.0f;
static constexpr float MAX_DELIVERY_RADIUS = 2000.0f;

Simulation::Simulation(SimConfig cfg)
    : _cfg(cfg)
    , _qt(AABB{1000.0f, 2000.0f, 6000.0f, 6000.0f})
    , _astar(_graph)
    , _planner(_graph)
    , _proto(cfg.proto_path)
    , _rng(std::random_device{}())
{
    if (!_graph.load(cfg.nodes_csv, cfg.edges_csv))
        throw std::runtime_error("Failed to load road graph");

    if (!cfg.hubs_csv.empty())
        load_hubs_from_csv(cfg.hubs_csv);
    else
        load_hubs_hardcoded();

    std::uniform_int_distribution<std::size_t> nd(
        0, _graph.node_ids().size()-1);

    for (int i = 0; i < cfg.num_robots; ++i) {
        uint32_t    nid = _graph.node_ids()[nd(_rng)];
        const Node& n   = _graph.node(nid);
        std::size_t rid = _robots.add(n.x, n.y,
            std::uniform_real_distribution<float>(60.0f,100.0f)(_rng));
        _robot_node.push_back(nid);
        _qt.insert(static_cast<uint32_t>(rid), n.x, n.y);
        double jitter = std::uniform_real_distribution<double>(0.0,5.0)(_rng);
        _sched.push({jitter, EventType::DEPART,
                     static_cast<uint32_t>(rid), nid, 0.0f});
    }

    seed_weather_events();

    _log.open(cfg.log_path);
    if (!_log.is_open())
        std::cerr << "[WARN] Could not open log: " << cfg.log_path << "\n";
    else
        _log << "time,event,robot_id,x,y,battery,status,note\n";
}

void Simulation::seed_weather_events() {
    double t = _cfg.weather_interval;
    while (t < _cfg.sim_duration_s) {
        _sched.push({t, EventType::WEATHER_DELAY, 0, 0, 0.0f});
        t += _cfg.weather_interval;
    }
}

void Simulation::load_hubs_hardcoded() {
    std::vector<std::pair<float,float>> positions = {
        {200.0f,200.0f},{500.0f,800.0f},{800.0f,300.0f}
    };
    for (std::size_t i = 0; i < positions.size(); ++i) {
        auto [hx,hy] = positions[i];
        uint32_t    nid = _graph.nearest_node(hx,hy);
        const Node& n   = _graph.node(nid);
        _hubs.push_back({static_cast<uint32_t>(i),nid,n.x,n.y,2.0f});
        std::cout << "[HUB " << i << "] hardcoded -> node "
                  << nid << " (" << n.x << ", " << n.y << ")\n";
    }
}

void Simulation::load_hubs_from_csv(const std::string& path) {
    std::ifstream f(path);
    if (!f.is_open())
        throw std::runtime_error("Cannot open hubs CSV: " + path);
    std::string line;
    std::getline(f, line);
    uint32_t idx = 0;
    while (std::getline(f, line)) {
        std::istringstream ss(line);
        std::string tok;
        std::getline(ss,tok,',');
        std::getline(ss,tok,','); uint32_t nid = std::stoul(tok);
        std::getline(ss,tok,','); float x      = std::stof(tok);
        std::getline(ss,tok,','); float y      = std::stof(tok);
        uint32_t    snap = _graph.nearest_node(x,y);
        const Node& n    = _graph.node(snap);
        _hubs.push_back({idx++,snap,n.x,n.y,2.0f});
        std::cout << "[HUB " << idx-1 << "] MILP -> node "
                  << snap << " (" << n.x << ", " << n.y << ")\n";
        (void)nid;
    }
    std::cout << "[HUBS] Loaded " << _hubs.size()
              << " from " << path << "\n";
}

// ── Main loop ─────────────────────────────────────────────────
void Simulation::run() {
    std::cout << std::fixed << std::setprecision(2);
    std::cout << "[SIM] Starting: " << _cfg.num_robots
              << " robots, " << _cfg.sim_duration_s << "s\n\n";

    while (!_sched.empty() &&
           _sched.peek_time() <= _cfg.sim_duration_s) {
        Event e = _sched.pop();
        _now = e.time;
        ++_event_count;

        switch (e.type) {
            case EventType::DEPART:        handle_depart(e);        break;
            case EventType::ARRIVE:        handle_arrive(e);        break;
            case EventType::RECHARGE:      handle_recharge(e);      break;
            case EventType::TRAFFIC_JAM:   handle_traffic_jam(e);   break;
            case EventType::DELIVERY_FAIL: handle_delivery_fail(e); break;
            case EventType::WEATHER_DELAY: handle_weather_delay(e); break;
        }

        // Flush pending departs when batch is full
        if ((int)_pending_departs.size() >= _cfg.parallel_batch)
            flush_pending_departs();
    }

    // Flush any remaining pending departs
    if (!_pending_departs.empty())
        flush_pending_departs();

    auto s = stats();
    std::cout << "\n[SIM] Done.\n";
    std::cout << "  Events processed  : " << _event_count        << "\n";
    std::cout << "  Deliveries        : " << s.total_deliveries   << "\n";
    std::cout << "  Delivery fails    : " << s.delivery_fails     << "\n";
    std::cout << "  Traffic jams      : " << s.traffic_jams       << "\n";
    std::cout << "  Weather delays    : " << s.weather_delays     << "\n";
    std::cout << "  Energy used       : " << s.total_energy_kwh  << " kWh\n";
    std::cout << "  Recharge events   : " << s.recharge_events    << "\n";
    std::cout << "  Failed A* paths   : " << s.failed_paths       << "\n";
    std::cout << "  Quadtree updates  : " << _qt_updates          << "\n";
    std::cout << "  Parallel batches  : " << s.parallel_batches   << "\n";

    // Write protobuf output
    if (_proto.enabled()) {
        _proto.set_stats(s.total_deliveries, s.total_energy_kwh,
                         s.recharge_events, s.failed_paths,
                         s.traffic_jams, s.delivery_fails,
                         s.weather_delays, s.parallel_batches);
        _proto.set_meta(_cfg.num_robots, _cfg.sim_duration_s,
                        _cfg.hubs_csv.empty() ? "hardcoded" : "milp");
        if (_proto.write())
            std::cout << "  Proto written     : " << _cfg.proto_path
                      << " (" << _proto.event_count() << " events)\n";
    }
}

// ── Parallel path planning flush ──────────────────────────────
void Simulation::flush_pending_departs() {
    if (_pending_departs.empty()) return;

    // Build path requests
    std::vector<PathRequest> requests;
    requests.reserve(_pending_departs.size());
    for (const auto& pd : _pending_departs) {
        requests.push_back({
            pd.event.robot_id,
            _robot_node[pd.event.robot_id],
            pd.dest_nid
        });
    }

    // Solve all paths in parallel via TBB
    auto responses = _planner.plan(requests);
    ++_stats.parallel_batches;

    // Process results sequentially
    for (std::size_t i = 0; i < _pending_departs.size(); ++i) {
        const auto& pd   = _pending_departs[i];
        const auto& resp = responses[i];
        uint32_t    rid  = pd.event.robot_id;

        if (!resp.result.found) {
            ++_stats.failed_paths;
            _sched.push({_now+2.0, EventType::DEPART,
                         rid, _robot_node[rid], 0.0f});
            continue;
        }

        float  dist   = resp.result.distance;
        double travel = dist / (_weather_speed_mult * ROBOT_SPEED_MS);

        _robots.battery[rid] -= dist * _cfg.battery_drain;
        _robots.battery[rid]  = std::max(0.0f, _robots.battery[rid]);
        _robots.total_energy_used[rid] += dist * 0.0001f;

        const Node& dest = _graph.node(pd.dest_nid);

        _qt.update(rid, _robots.x[rid], _robots.y[rid], dest.x, dest.y);
        ++_qt_updates;

        _robots.x[rid]      = dest.x;
        _robots.y[rid]      = dest.y;
        _robots.status[rid] = pd.to_hub
            ? RobotStatus::RETURNING
            : RobotStatus::DELIVERING;

        EventType arrive_type = EventType::ARRIVE;
        _sched.push({_now + travel, arrive_type,
                     rid, pd.dest_nid, 0.0f});
        log_event(pd.event,
                  pd.to_hub ? "low_battery->hub" : "depart->deliver");
    }

    _pending_departs.clear();
}

// ── Event handlers ────────────────────────────────────────────
void Simulation::handle_depart(const Event& e) {
    uint32_t rid = e.robot_id;

    // Traffic jam check
    std::uniform_real_distribution<float> prob(0.0f, 1.0f);
    if (prob(_rng) < _cfg.traffic_jam_prob) {
        float jam = std::uniform_real_distribution<float>(30.0f,120.0f)(_rng);
        _sched.push({_now, EventType::TRAFFIC_JAM,
                     rid, _robot_node[rid], jam});
        _sched.push({_now+jam, EventType::DEPART,
                     rid, _robot_node[rid], 0.0f});
        return;
    }

    // Low battery → queue path to hub
    if (_robots.battery[rid] < _cfg.low_battery_thr) {
        Hub& h = nearest_hub(_robots.x[rid], _robots.y[rid]);
        _pending_departs.push_back({e, h.node_id, true});
        return;
    }

    // Normal delivery → pick destination, queue path
    const Node& origin = _graph.node(_robot_node[rid]);
    uint32_t dest_nid  = 0;
    float    best_dist = std::numeric_limits<float>::max();

    std::uniform_int_distribution<std::size_t> nd(
        0, _graph.node_ids().size()-1);

    for (int attempt = 0; attempt < 20; ++attempt) {
        uint32_t    cid = _graph.node_ids()[nd(_rng)];
        const Node& cn  = _graph.node(cid);
        float dx = cn.x-origin.x, dy = cn.y-origin.y;
        float d  = std::sqrt(dx*dx+dy*dy);
        if (d < MAX_DELIVERY_RADIUS && d > 50.0f && d < best_dist) {
            best_dist = d; dest_nid = cid;
        }
    }
    if (dest_nid == 0)
        dest_nid = _graph.node_ids()[nd(_rng)];

    _pending_departs.push_back({e, dest_nid, false});
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
        _sched.push({_now+ctime, EventType::RECHARGE,
                     rid, e.node_id, 0.0f});
        ++_stats.recharge_events;
        log_event(e, "arrived_hub");
    } else {
        std::uniform_real_distribution<float> prob(0.0f,1.0f);
        if (prob(_rng) < _cfg.delivery_fail_prob) {
            _sched.push({_now, EventType::DELIVERY_FAIL,
                         rid, e.node_id, 0.0f});
            return;
        }
        ++_robots.deliveries_completed[rid];
        ++_stats.total_deliveries;
        _robots.status[rid] = RobotStatus::IDLE;
        double rest = std::uniform_real_distribution<double>(2.0,8.0)(_rng);
        _sched.push({_now+rest, EventType::DEPART,
                     rid, e.node_id, 0.0f});
        log_event(e, "delivered");
    }
}

void Simulation::handle_recharge(const Event& e) {
    uint32_t rid = e.robot_id;
    _robots.battery[rid] = 100.0f;
    _robots.status[rid]  = RobotStatus::IDLE;
    _sched.push({_now+1.0, EventType::DEPART,
                 rid, e.node_id, 0.0f});
    log_event(e, "fully_charged");
}

void Simulation::handle_traffic_jam(const Event& e) {
    ++_stats.traffic_jams;
    _robots.status[e.robot_id] = RobotStatus::BLOCKED;
    log_event(e, "traffic_jam_"
              + std::to_string((int)e.payload) + "s");
}

void Simulation::handle_delivery_fail(const Event& e) {
    ++_stats.delivery_fails;
    uint32_t rid = e.robot_id;
    _robots.status[rid] = RobotStatus::IDLE;
    double rest = std::uniform_real_distribution<double>(5.0,15.0)(_rng);
    _sched.push({_now+rest, EventType::DEPART,
                 rid, e.node_id, 0.0f});
    log_event(e, "delivery_failed");
}

void Simulation::handle_weather_delay(const Event& e) {
    if (e.payload > 0.5f) {
        _weather_speed_mult = 1.0f;
        log_event(e, "weather_cleared");
        return;
    }
    ++_stats.weather_delays;
    std::uniform_real_distribution<float> sev(0.4f,0.8f);
    _weather_speed_mult = sev(_rng);
    double dur = std::uniform_real_distribution<double>(600.0,1800.0)(_rng);
    _sched.push({_now+dur, EventType::WEATHER_DELAY, 0, 0, 1.0f});
    log_event(e, "weather_speed_"
              + std::to_string(_weather_speed_mult).substr(0,4));
}

float Simulation::distance(float x1,float y1,float x2,float y2) const {
    float dx=x2-x1, dy=y2-y1;
    return std::sqrt(dx*dx+dy*dy);
}

Hub& Simulation::nearest_hub(float x, float y) {
    Hub* best    = &_hubs[0];
    float best_d = distance(x,y,best->x,best->y);
    for (auto& h : _hubs) {
        float d = distance(x,y,h.x,h.y);
        if (d < best_d) { best_d=d; best=&h; }
    }
    return *best;
}

void Simulation::log_event(const Event& e, const std::string& note) {
    // Write to protobuf
    if (_proto.enabled()) {
        uint32_t rid = e.robot_id;
        _proto.add_event(_now, eventTypeToString(e.type), rid,
                         _robots.x[rid], _robots.y[rid],
                         _robots.battery[rid],
                         statusToString(_robots.status[rid]), note);
    }
    // Write to protobuf
    if (_proto.enabled()) {
        uint32_t rid = e.robot_id;
        _proto.add_event(_now, eventTypeToString(e.type), rid,
                         _robots.x[rid], _robots.y[rid],
                         _robots.battery[rid],
                         statusToString(_robots.status[rid]), note);
    }
    if (!_log.is_open()) return;
    uint32_t rid = e.robot_id;
    _log << _now << ","
         << eventTypeToString(e.type) << ","
         << rid << ","
         << _robots.x[rid] << ","
         << _robots.y[rid] << ","
         << _robots.battery[rid] << ","
         << statusToString(_robots.status[rid]) << ","
         << note << "\n";
}

Simulation::Stats Simulation::stats() const {
    Stats s = _stats;
    s.total_energy_kwh = 0.0;
    for (auto v : _robots.total_energy_used)
        s.total_energy_kwh += v;
    return s;
}

// ── RL query methods ──────────────────────────────────────────

std::vector<std::vector<float>> Simulation::get_robot_states_raw() const {
    std::vector<std::vector<float>> out;
    out.reserve(_robots.size());
    for (std::size_t i = 0; i < _robots.size(); ++i) {
        out.push_back({
            _robots.x[i],
            _robots.y[i],
            _robots.battery[i],
            static_cast<float>(static_cast<uint8_t>(_robots.status[i]))
        });
    }
    return out;
}

std::vector<int> Simulation::get_hub_queue_lengths() const {
    std::vector<int> queues(_hubs.size(), 0);
    for (std::size_t i = 0; i < _robots.size(); ++i) {
        if (_robots.status[i] == RobotStatus::CHARGING) {
            // Find which hub this robot is at
            float best_d = std::numeric_limits<float>::max();
            int   best_h = 0;
            for (std::size_t h = 0; h < _hubs.size(); ++h) {
                float dx = _robots.x[i] - _hubs[h].x;
                float dy = _robots.y[i] - _hubs[h].y;
                float d  = dx*dx + dy*dy;
                if (d < best_d) { best_d = d; best_h = (int)h; }
            }
            queues[best_h]++;
        }
    }
    return queues;
}
