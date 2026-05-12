#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "Simulation.h"

namespace py = pybind11;

// ── Thin wrapper around Simulation ────────────────────────────
// Exposes a clean Python API without exposing C++ internals
class SimEngine {
public:
    SimEngine(int robots, double duration, double low_battery = 20.0) {
        _cfg.num_robots      = robots;
        _cfg.sim_duration_s  = duration;
        _cfg.low_battery_thr = static_cast<float>(low_battery);
        _cfg.log_path        = "data/logs/sim_log.csv";
        _cfg.nodes_csv       = "data/osm/graph_nodes.csv";
        _cfg.edges_csv       = "data/osm/graph_edges.csv";
    }

    void set_hubs_csv(const std::string& path) {
        _cfg.hubs_csv = path;
    }

    void set_log_path(const std::string& path) {
        _cfg.log_path = path;
    }

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
        d["deliveries"]    = s.total_deliveries;
        d["energy_kwh"]    = s.total_energy_kwh;
        d["recharges"]     = s.recharge_events;
        d["failed_paths"]  = s.failed_paths;
        return d;
    }

private:
    SimConfig                  _cfg;
    std::unique_ptr<Simulation> _sim;
    bool                       _ran{false};
};

// ── pybind11 module definition ─────────────────────────────────
PYBIND11_MODULE(lastmile, m) {
    m.doc() = "Last-Mile Delivery Simulation — Python bridge";

    py::class_<SimEngine>(m, "SimEngine")
        .def(py::init<int, double, double>(),
             py::arg("robots")       = 50,
             py::arg("duration")     = 3600.0,
             py::arg("low_battery")  = 20.0)
        .def("set_hubs_csv",  &SimEngine::set_hubs_csv,
             "Load MILP-optimised hub locations from CSV")
        .def("set_log_path",  &SimEngine::set_log_path,
             "Set output log path")
        .def("run",           &SimEngine::run,
             "Run the simulation")
        .def("get_stats",     &SimEngine::get_stats,
             "Return dict of {deliveries, energy_kwh, recharges, failed_paths}");
}
