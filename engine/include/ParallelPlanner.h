#pragma once
#include "AStar.h"
#include "RoadGraph.h"
#include <vector>
#include <cstdint>
#include <tbb/parallel_for.h>
#include <tbb/blocked_range.h>

// ── PathRequest — one robot's planning task ────────────────────
struct PathRequest {
    uint32_t robot_id;
    uint32_t from_node;
    uint32_t to_node;
};

// ── PathResponse — result of one A* search ────────────────────
struct PathResponse {
    uint32_t   robot_id;
    PathResult result;
};

// ── ParallelPlanner ────────────────────────────────────────────
// Takes a batch of PathRequests, solves them in parallel via TBB,
// returns a vector of PathResponses in arbitrary order.
//
// Why this works:
//   A* is a pure read operation on the RoadGraph — no shared
//   mutable state. Each robot's search is completely independent.
//   TBB splits the batch across available cores automatically.
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
                // Each thread gets its own AStar instance
                AStar astar(_graph);
                for (std::size_t i = range.begin(); i < range.end(); ++i) {
                    const auto& req = requests[i];
                    responses[i] = {
                        req.robot_id,
                        astar.find_path(req.from_node, req.to_node)
                    };
                }
            }
        );

        return responses;
    }

private:
    const RoadGraph& _graph;
};
