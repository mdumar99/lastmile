#pragma once
#include "AStar.h"
#include "RoadGraph.h"
#include <vector>
#include <cstdint>
#include <tbb/parallel_for.h>
#include <tbb/blocked_range.h>

struct PathRequest {
    uint32_t robot_id;
    uint32_t from_node;
    uint32_t to_node;
    float    max_dist{0.0f};  // 0 = no limit
};

struct PathResponse {
    uint32_t   robot_id;
    PathResult result;
};

class ParallelPlanner {
public:
    explicit ParallelPlanner(const RoadGraph& graph)
        : _graph(graph) {}

    std::vector<PathResponse> plan(
        const std::vector<PathRequest>& requests) const
    {
        std::vector<PathResponse> responses(requests.size());
        tbb::parallel_for(
            tbb::blocked_range<std::size_t>(0, requests.size()),
            [&](const tbb::blocked_range<std::size_t>& range) {
                AStar astar(_graph);
                for (std::size_t i = range.begin(); i < range.end(); ++i) {
                    const auto& req = requests[i];
                    responses[i] = {
                        req.robot_id,
                        astar.find_path(req.from_node, req.to_node,
                                        req.max_dist)
                    };
                }
            }
        );
        return responses;
    }

private:
    const RoadGraph& _graph;
};
