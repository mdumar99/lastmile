#pragma once
#include "RoadGraph.h"
#include <vector>
#include <cstdint>

struct PathResult {
    std::vector<uint32_t> nodes;    // node ids along path
    float                 distance; // total metres
    bool                  found;
};

class AStar {
public:
    explicit AStar(const RoadGraph& graph);

    PathResult find_path(uint32_t from, uint32_t to) const;

private:
    const RoadGraph& _graph;

    float heuristic(uint32_t a, uint32_t b) const;
};
