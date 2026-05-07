#pragma once
#include <vector>
#include <unordered_map>
#include <string>
#include <cstdint>

struct Node {
    uint32_t id;
    double   lat, lon;
    float    x, y;    // local metres from centre
};

struct Edge {
    uint32_t to;
    float    distance_m;
};

class RoadGraph {
public:
    bool load(const std::string& nodes_csv,
              const std::string& edges_csv);

    const Node&              node(uint32_t id) const;
    const std::vector<Edge>& neighbours(uint32_t id) const;

    // Return a random node id
    uint32_t random_node(uint32_t seed) const;

    // Return node id nearest to (x, y)
    uint32_t nearest_node(float x, float y) const;

    std::size_t node_count() const { return _nodes.size(); }
    std::size_t edge_count() const { return _edge_count; }

    // All node ids (for random selection)
    const std::vector<uint32_t>& node_ids() const { return _node_ids; }

private:
    std::unordered_map<uint32_t, Node>              _nodes;
    std::unordered_map<uint32_t, std::vector<Edge>> _adj;
    std::vector<uint32_t>                           _node_ids;
    std::size_t                                     _edge_count{0};
    std::vector<Edge>                               _empty{};
};
