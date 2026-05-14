#pragma once
#include "RoadGraph.h"
#include <vector>
#include <cstdint>

struct PathResult {
    std::vector<uint32_t> nodes;
    float                 distance;
    bool                  found;
};

class AStar {
public:
    explicit AStar(const RoadGraph& graph);

    // max_dist = 0 means no limit
    PathResult find_path(uint32_t from, uint32_t to,
                         float max_dist = 0.0f) const;

private:
    const RoadGraph& _graph;
    float heuristic(uint32_t a, uint32_t b) const;
};
