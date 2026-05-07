#include "AStar.h"
#include <queue>
#include <unordered_map>
#include <cmath>
#include <limits>
#include <algorithm>

AStar::AStar(const RoadGraph& graph) : _graph(graph) {}

float AStar::heuristic(uint32_t a, uint32_t b) const {
    const Node& na = _graph.node(a);
    const Node& nb = _graph.node(b);
    float dx = na.x - nb.x, dy = na.y - nb.y;
    return std::sqrt(dx*dx + dy*dy);
}

PathResult AStar::find_path(uint32_t from, uint32_t to) const {
    if (from == to)
        return {{from}, 0.0f, true};

    using PQEntry = std::pair<float, uint32_t>;
    std::priority_queue<PQEntry,
                        std::vector<PQEntry>,
                        std::greater<PQEntry>> open;

    std::unordered_map<uint32_t, float>    g_score;
    std::unordered_map<uint32_t, uint32_t> came_from;
    const float INF = std::numeric_limits<float>::max();

    g_score[from] = 0.0f;
    open.push({heuristic(from, to), from});

    while (!open.empty()) {
        auto [f, current] = open.top();
        open.pop();

        if (current == to) {
            PathResult result;
            result.found    = true;
            result.distance = g_score[to];

            uint32_t node = to;
            while (node != from) {
                result.nodes.push_back(node);
                node = came_from[node];
            }
            result.nodes.push_back(from);
            std::reverse(result.nodes.begin(), result.nodes.end());
            return result;
        }

        float g_cur = g_score.count(current) ? g_score[current] : INF;

        for (const Edge& e : _graph.neighbours(current)) {
            float tentative_g = g_cur + e.distance_m;
            float known_g     = g_score.count(e.to) ? g_score[e.to] : INF;

            if (tentative_g < known_g) {
                came_from[e.to] = current;
                g_score[e.to]   = tentative_g;
                float f_new     = tentative_g + heuristic(e.to, to);
                open.push({f_new, e.to});
            }
        }
    }

    return {{}, 0.0f, false};
}
