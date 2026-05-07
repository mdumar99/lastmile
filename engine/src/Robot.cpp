#include "Robot.h"
#include <stdexcept>

std::string statusToString(RobotStatus s) {
    switch (s) {
        case RobotStatus::IDLE:       return "IDLE";
        case RobotStatus::DELIVERING: return "DELIVERING";
        case RobotStatus::RETURNING:  return "RETURNING";
        case RobotStatus::CHARGING:   return "CHARGING";
        case RobotStatus::BLOCKED:    return "BLOCKED";
        default:                      return "UNKNOWN";
    }
}

std::size_t RobotPool::add(float start_x, float start_y, float battery_pct) {
    std::size_t id = x.size();
    x.push_back(start_x);
    y.push_back(start_y);
    battery.push_back(battery_pct);
    status.push_back(RobotStatus::IDLE);
    target_node.push_back(0);
    payload_kg.push_back(0.0f);
    deliveries_completed.push_back(0);
    total_energy_used.push_back(0.0f);
    return id;
}

RobotPool::Snapshot RobotPool::snapshot(std::size_t id) const {
    if (id >= x.size())
        throw std::out_of_range("Robot id out of range");
    return Snapshot{id, x[id], y[id], battery[id],
                    status[id], deliveries_completed[id]};
}
