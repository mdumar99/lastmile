#pragma once
#include <vector>
#include <unordered_map>
#include <cstdint>

struct AABB {
    float cx, cy;  // centre
    float hw, hh;  // half-width, half-height

    bool contains(float px, float py) const;
    bool intersects(const AABB& other) const;
};

class Quadtree {
public:
    static constexpr int CAPACITY = 8;
    static constexpr int MAX_DEPTH = 8;

    explicit Quadtree(AABB boundary, int depth = 0);

    // ── Phase 1 API (unchanged) ──────────────────
    bool insert(uint32_t id, float px, float py);
    void query(const AABB& range, std::vector<uint32_t>& out) const;
    void clear();
    std::size_t count() const { return _count; }

    // ── Phase 2 API (dynamic operations) ─────────
    // Remove a specific robot by id and position
    bool remove(uint32_t id, float px, float py);

    // Move a robot from old position to new position
    // Returns false if robot wasn't found at old position
    bool update(uint32_t id,
                float old_x, float old_y,
                float new_x, float new_y);

    // Nearest neighbour search — returns closest robot id
    // Useful for Phase 2 congestion detection
    uint32_t nearest(float px, float py, float& out_dist) const;

private:
    AABB        _boundary;
    int         _depth;
    std::size_t _count{0};

    struct Point { uint32_t id; float x, y; };
    std::vector<Point>    _points;
    std::vector<Quadtree> _children;
    bool                  _divided{false};

    void subdivide();

    // Internal remove — returns true if found and removed
    bool _remove(uint32_t id, float px, float py);

    // Internal nearest search
    void _nearest(float px, float py,
                  uint32_t& best_id, float& best_dist) const;
};
