#include "Quadtree.h"

bool AABB::contains(float px, float py) const {
    return px >= cx - hw && px <= cx + hw &&
           py >= cy - hh && py <= cy + hh;
}

bool AABB::intersects(const AABB& o) const {
    return !(o.cx - o.hw > cx + hw ||
             o.cx + o.hw < cx - hw ||
             o.cy - o.hh > cy + hh ||
             o.cy + o.hh < cy - hh);
}

Quadtree::Quadtree(AABB boundary, int depth)
    : _boundary(boundary), _depth(depth) {}

void Quadtree::subdivide() {
    float hw = _boundary.hw / 2.0f;
    float hh = _boundary.hh / 2.0f;
    float cx = _boundary.cx;
    float cy = _boundary.cy;
    _children.reserve(4);
    _children.emplace_back(AABB{cx - hw, cy + hh, hw, hh}, _depth + 1);
    _children.emplace_back(AABB{cx + hw, cy + hh, hw, hh}, _depth + 1);
    _children.emplace_back(AABB{cx - hw, cy - hh, hw, hh}, _depth + 1);
    _children.emplace_back(AABB{cx + hw, cy - hh, hw, hh}, _depth + 1);
    _divided = true;
}

bool Quadtree::insert(uint32_t id, float px, float py) {
    if (!_boundary.contains(px, py)) return false;
    ++_count;
    if (!_divided && (int)_points.size() < CAPACITY) {
        _points.push_back({id, px, py});
        return true;
    }
    if (!_divided) {
        if (_depth >= MAX_DEPTH) {
            _points.push_back({id, px, py});
            return true;
        }
        subdivide();
        for (auto& p : _points)
            for (auto& c : _children)
                c.insert(p.id, p.x, p.y);
        _points.clear();
    }
    for (auto& c : _children)
        if (c.insert(id, px, py)) return true;
    return false;
}

void Quadtree::query(const AABB& range, std::vector<uint32_t>& out) const {
    if (!_boundary.intersects(range)) return;
    for (const auto& p : _points)
        if (range.contains(p.x, p.y))
            out.push_back(p.id);
    if (_divided)
        for (const auto& c : _children)
            c.query(range, out);
}

void Quadtree::clear() {
    _points.clear();
    _children.clear();
    _divided = false;
    _count   = 0;
}
