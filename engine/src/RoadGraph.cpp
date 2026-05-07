#include "RoadGraph.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <cmath>
#include <limits>
#include <stdexcept>

bool RoadGraph::load(const std::string& nodes_csv,
                     const std::string& edges_csv) {
    // ── Load nodes ──────────────────────────────
    std::ifstream nf(nodes_csv);
    if (!nf.is_open()) {
        std::cerr << "[RoadGraph] Cannot open " << nodes_csv << "\n";
        return false;
    }

    std::string line;
    std::getline(nf, line); // skip header

    while (std::getline(nf, line)) {
        std::istringstream ss(line);
        std::string tok;
        Node nd;

        std::getline(ss, tok, ','); nd.id  = std::stoul(tok);
        std::getline(ss, tok, ','); nd.lat = std::stod(tok);
        std::getline(ss, tok, ','); nd.lon = std::stod(tok);
        std::getline(ss, tok, ','); nd.x   = std::stof(tok);
        std::getline(ss, tok, ','); nd.y   = std::stof(tok);

        _nodes[nd.id] = nd;
        _node_ids.push_back(nd.id);
    }

    std::cout << "[RoadGraph] Loaded " << _nodes.size() << " nodes\n";

    // ── Load edges ──────────────────────────────
    std::ifstream ef(edges_csv);
    if (!ef.is_open()) {
        std::cerr << "[RoadGraph] Cannot open " << edges_csv << "\n";
        return false;
    }

    std::getline(ef, line); // skip header

    while (std::getline(ef, line)) {
        std::istringstream ss(line);
        std::string tok;

        std::getline(ss, tok, ','); uint32_t from = std::stoul(tok);
        std::getline(ss, tok, ','); uint32_t to   = std::stoul(tok);
        std::getline(ss, tok, ','); float    dist = std::stof(tok);

        // Only add edge if both nodes exist
        if (_nodes.count(from) && _nodes.count(to)) {
            _adj[from].push_back({to, dist});
            ++_edge_count;
        }
    }

    std::cout << "[RoadGraph] Loaded " << _edge_count << " edges\n";
    return true;
}

const Node& RoadGraph::node(uint32_t id) const {
    auto it = _nodes.find(id);
    if (it == _nodes.end())
        throw std::out_of_range("RoadGraph: node not found");
    return it->second;
}

const std::vector<Edge>& RoadGraph::neighbours(uint32_t id) const {
    auto it = _adj.find(id);
    if (it == _adj.end()) return _empty;
    return it->second;
}

uint32_t RoadGraph::random_node(uint32_t seed) const {
    return _node_ids[seed % _node_ids.size()];
}

uint32_t RoadGraph::nearest_node(float x, float y) const {
    uint32_t best_id   = _node_ids[0];
    float    best_dist = std::numeric_limits<float>::max();

    for (const auto& [id, nd] : _nodes) {
        float dx = nd.x - x, dy = nd.y - y;
        float d  = dx*dx + dy*dy;
        if (d < best_dist) { best_dist = d; best_id = id; }
    }
    return best_id;
}
