#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "Simulation.h"

namespace py = pybind11;

class SimEngine {
public:
    SimEngine(int robots, double duration,
              double low_battery  = 20.0,
              float  jam_prob     = 0.02f,
              float  fail_prob    = 0.05f) {
        _cfg.num_robots        = robots;
        _cfg.sim_duration_s    = duration;
        _cfg.low_battery_thr   = static_cast<float>(low_battery);
        _cfg.traffic_jam_prob  = jam_prob;
        _cfg.delivery_fail_prob= fail_prob;
        _cfg.log_path          = "data/logs/sim_log.csv";
        _cfg.nodes_csv         = "data/osm/graph_nodes.csv";
        _cfg.edges_csv         = "data/osm/graph_edges.csv";
    }

    void set_hubs_csv(const std::string& path) { _cfg.hubs_csv  = path; }
    void set_log_path(const std::string& path) { _cfg.log_path  = path; }

    void run() {
        _sim = std::make_unique<Simulation>(_cfg);
        _sim->run();
        _ran = true;
    }

    py::dict get_stats() {
        if (!_ran)
            throw std::runtime_error("Call run() before get_stats()");
        auto s = _sim->stats();
        py::dict d;
        d["deliveries"]     = s.total_deliveries;
        d["energy_kwh"]     = s.total_energy_kwh;
        d["recharges"]      = s.recharge_events;
        d["failed_paths"]   = s.failed_paths;
        d["traffic_jams"]   = s.traffic_jams;
        d["delivery_fails"] = s.delivery_fails;
        d["weather_delays"] = s.weather_delays;
        return d;
    }

private:
    SimConfig                   _cfg;
    std::unique_ptr<Simulation> _sim;
    bool                        _ran{false};
};

PYBIND11_MODULE(lastmile, m) {
    m.doc() = "Last-Mile Delivery Simulation — Python bridge";

    py::class_<SimEngine>(m, "SimEngine")
        .def(py::init<int, double, double, float, float>(),
             py::arg("robots")       = 50,
             py::arg("duration")     = 3600.0,
             py::arg("low_battery")  = 20.0,
             py::arg("jam_prob")     = 0.02f,
             py::arg("fail_prob")    = 0.05f)
        .def("set_hubs_csv",  &SimEngine::set_hubs_csv)
        .def("set_log_path",  &SimEngine::set_log_path)
        .def("run",           &SimEngine::run)
        .def("get_stats",     &SimEngine::get_stats);
}
