#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include "Simulation.h"

namespace py = pybind11;

class SimEngine {
public:
    SimEngine(int robots, double duration,
              double low_battery  = 20.0,
              float  jam_prob     = 0.02f,
              float  fail_prob    = 0.05f) {
        _cfg.num_robots         = robots;
        _cfg.sim_duration_s     = duration;
        _cfg.low_battery_thr    = static_cast<float>(low_battery);
        _cfg.traffic_jam_prob   = jam_prob;
        _cfg.delivery_fail_prob = fail_prob;
        _cfg.log_path           = "data/logs/sim_log.csv";
        _cfg.nodes_csv          = "data/osm/graph_nodes.csv";
        _cfg.edges_csv          = "data/osm/graph_edges.csv";
    }

    void set_hubs_csv  (const std::string& p) { _cfg.hubs_csv   = p; }
    void set_log_path  (const std::string& p) { _cfg.log_path   = p; }
    void set_proto_path(const std::string& p) { _cfg.proto_path = p; }

    // Register a Python callable as the decision policy
    void set_policy(py::function fn) {
        _policy_fn = fn;
        _has_policy = true;
    }

    void run() {
        _sim = std::make_unique<Simulation>(_cfg);

        if (_has_policy) {
            _sim->set_decision_callback(
                [this](const RobotDecisionState& s) -> int {
                    py::gil_scoped_acquire gil;
                    try {
                        return _policy_fn(
                            s.robot_id, s.battery,
                            s.x, s.y, s.hub_dist,
                            s.weather_mult, s.sim_time,
                            s.deliveries_done, s.recharges_done,
                            s.nearby_robots, s.max_hub_queue
                        ).cast<int>();
                    } catch (...) {
                        return 0; // fallback: deliver
                    }
                }
            );
        }

        _sim->run();
        _ran = true;
    }

    py::dict get_stats() {
        if (!_ran) throw std::runtime_error("Call run() first");
        auto s = _sim->stats();
        py::dict d;
        d["deliveries"]       = s.total_deliveries;
        d["energy_kwh"]       = s.total_energy_kwh;
        d["recharges"]        = s.recharge_events;
        d["failed_paths"]     = s.failed_paths;
        d["traffic_jams"]     = s.traffic_jams;
        d["delivery_fails"]   = s.delivery_fails;
        d["weather_delays"]   = s.weather_delays;
        d["parallel_batches"] = s.parallel_batches;
        d["policy_decisions"] = s.policy_decisions;
        return d;
    }

    std::vector<std::vector<float>> get_robot_states() {
        if (!_ran) throw std::runtime_error("Call run() first");
        return _sim->get_robot_states_raw();
    }

    std::vector<int> get_hub_queue_lengths() {
        if (!_ran) throw std::runtime_error("Call run() first");
        return _sim->get_hub_queue_lengths();
    }

private:
    SimConfig                   _cfg;
    std::unique_ptr<Simulation> _sim;
    py::function                _policy_fn;
    bool                        _has_policy{false};
    bool                        _ran{false};
};

PYBIND11_MODULE(lastmile, m) {
    m.doc() = "Last-Mile Delivery Simulation — Python bridge";

    py::class_<SimEngine>(m, "SimEngine")
        .def(py::init<int,double,double,float,float>(),
             py::arg("robots")      = 50,
             py::arg("duration")    = 3600.0,
             py::arg("low_battery") = 20.0,
             py::arg("jam_prob")    = 0.02f,
             py::arg("fail_prob")   = 0.05f)
        .def("set_hubs_csv",         &SimEngine::set_hubs_csv)
        .def("set_log_path",         &SimEngine::set_log_path)
        .def("set_proto_path",       &SimEngine::set_proto_path)
        .def("set_policy",           &SimEngine::set_policy,
             "Register Python callable as decision policy.\n"
             "Signature: fn(robot_id, battery, x, y, hub_dist,\n"
             "              weather, sim_time, deliveries,\n"
             "              recharges, nearby, max_queue) -> int\n"
             "Returns: 0=DELIVER, 1=RECHARGE, 2=WAIT")
        .def("run",                  &SimEngine::run)
        .def("get_stats",            &SimEngine::get_stats)
        .def("get_robot_states",     &SimEngine::get_robot_states)
        .def("get_hub_queue_lengths",&SimEngine::get_hub_queue_lengths);
}
