#pragma once
#include "simulation.pb.h"
#include <string>
#include <fstream>

class ProtoWriter {
public:
    explicit ProtoWriter(const std::string& path)
        : _path(path), _enabled(!path.empty()) {}

    bool enabled() const { return _enabled; }

    void add_event(double time, const std::string& type,
                   uint32_t robot_id,
                   float x, float y, float battery,
                   const std::string& status,
                   const std::string& note)
    {
        if (!_enabled) return;
        auto* e = _output.add_events();
        e->set_time(time);
        e->set_type(type);
        e->set_robot_id(robot_id);
        e->set_x(x);
        e->set_y(y);
        e->set_battery(battery);
        e->set_status(status);
        e->set_note(note);
    }

    void set_stats(uint32_t deliveries, double energy,
                   uint32_t recharges, uint32_t failed,
                   uint32_t jams, uint32_t fails,
                   uint32_t weather, uint32_t batches)
    {
        if (!_enabled) return;
        auto* s = _output.mutable_stats();
        s->set_total_deliveries(deliveries);
        s->set_total_energy_kwh(energy);
        s->set_recharge_events(recharges);
        s->set_failed_paths(failed);
        s->set_traffic_jams(jams);
        s->set_delivery_fails(fails);
        s->set_weather_delays(weather);
        s->set_parallel_batches(batches);
    }

    void set_meta(uint32_t robots, double duration,
                  const std::string& hub_mode)
    {
        if (!_enabled) return;
        _output.set_num_robots(robots);
        _output.set_duration_s(duration);
        _output.set_hub_mode(hub_mode);
    }

    bool write() {
        if (!_enabled) return true;
        std::ofstream f(_path, std::ios::binary);
        if (!f.is_open()) return false;
        return _output.SerializeToOstream(&f);
    }

    std::size_t event_count() const {
        return static_cast<std::size_t>(_output.events_size());
    }

private:
    std::string         _path;
    bool                _enabled;
    lastmile::SimOutput _output;
};
