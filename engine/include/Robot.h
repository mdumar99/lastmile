#pragma once
#include <vector>
#include <cstdint>
#include <string>

enum class RobotStatus : uint8_t {
    IDLE       = 0,
    DELIVERING,
    RETURNING,
    CHARGING,
    BLOCKED
};

std::string statusToString(RobotStatus s);

// Struct of Arrays — keeps hot data (x, y, battery)
// contiguous in memory for cache efficiency
struct RobotPool {
    // Hot data (touched every event)
    std::vector<float>       x;
    std::vector<float>       y;
    std::vector<float>       battery;

    // Warm data (touched on state change)
    std::vector<RobotStatus> status;
    std::vector<uint32_t>    target_node;
    std::vector<float>       payload_kg;

    // Cold data (logging only)
    std::vector<uint32_t>    deliveries_completed;
    std::vector<float>       total_energy_used;

    std::size_t size() const { return x.size(); }

    std::size_t add(float start_x, float start_y,
                    float battery_pct = 100.0f);

    struct Snapshot {
        std::size_t id;
        float       x, y, battery;
        RobotStatus status;
        uint32_t    deliveries;
    };
    Snapshot snapshot(std::size_t id) const;
};
