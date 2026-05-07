#pragma once
#include <vector>
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

    bool insert(uint32_t id, float px, float py);
    void query(const AABB& range, std::vector<uint32_t>& out) const;
    void clear();

    std::size_t count() const { return _count; }

private:
    AABB        _boundary;
    int         _depth;
    std::size_t _count{0};

    struct Point { uint32_t id; float x, y; };
    std::vector<Point>     _points;
    std::vector<Quadtree>  _children;
    bool                   _divided{false};

    void subdivide();
};
