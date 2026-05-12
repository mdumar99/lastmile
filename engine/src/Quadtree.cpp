#include "Quadtree.h"
#include <cmath>
#include <limits>
#include <algorithm>

// ── AABB ──────────────────────────────────────────────────────

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

// ── Quadtree ──────────────────────────────────────────────────

Quadtree::Quadtree(AABB boundary, int depth)
    : _boundary(boundary), _depth(depth) {}

void Quadtree::subdivide() {
    float hw = _boundary.hw / 2.0f;
    float hh = _boundary.hh / 2.0f;
    float cx = _boundary.cx;
    float cy = _boundary.cy;
    _children.reserve(4);
    _children.emplace_back(AABB{cx-hw, cy+hh, hw, hh}, _depth+1); // NW
    _children.emplace_back(AABB{cx+hw, cy+hh, hw, hh}, _depth+1); // NE
    _children.emplace_back(AABB{cx-hw, cy-hh, hw, hh}, _depth+1); // SW
    _children.emplace_back(AABB{cx+hw, cy-hh, hw, hh}, _depth+1); // SE
    _divided = true;
}

// ── Insert ────────────────────────────────────────────────────

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

// ── Query ─────────────────────────────────────────────────────

void Quadtree::query(const AABB& range,
                     std::vector<uint32_t>& out) const {
    if (!_boundary.intersects(range)) return;
    for (const auto& p : _points)
        if (range.contains(p.x, p.y))
            out.push_back(p.id);
    if (_divided)
        for (const auto& c : _children)
            c.query(range, out);
}

// ── Clear ─────────────────────────────────────────────────────

void Quadtree::clear() {
    _points.clear();
    _children.clear();
    _divided = false;
    _count   = 0;
}

// ── Remove (Phase 2) ──────────────────────────────────────────

bool Quadtree::_remove(uint32_t id, float px, float py) {
    if (!_boundary.contains(px, py)) return false;

    // Check points at this node
    for (auto it = _points.begin(); it != _points.end(); ++it) {
        if (it->id == id) {
            _points.erase(it);
            --_count;
            return true;
        }
    }

    // Recurse into children
    if (_divided) {
        for (auto& c : _children) {
            if (c._remove(id, px, py)) {
                --_count;
                // Collapse children if total points fits in one node
                if (_count <= (std::size_t)CAPACITY) {
                    for (auto& child : _children)
                        for (auto& p : child._points)
                            _points.push_back(p);
                    _children.clear();
                    _divided = false;
                }
                return true;
            }
        }
    }
    return false;
}

bool Quadtree::remove(uint32_t id, float px, float py) {
    return _remove(id, px, py);
}

// ── Update (Phase 2) ──────────────────────────────────────────

bool Quadtree::update(uint32_t id,
                      float old_x, float old_y,
                      float new_x, float new_y) {
    // Remove from old position, insert at new position
    // If remove fails (robot not found) still try to insert
    bool removed = _remove(id, old_x, old_y);
    if (removed) --_count; // _remove already decremented internally
    // re-increment since insert will add
    bool inserted = insert(id, new_x, new_y);
    return removed && inserted;
}

// ── Nearest neighbour (Phase 2) ───────────────────────────────

void Quadtree::_nearest(float px, float py,
                         uint32_t& best_id,
                         float& best_dist) const {
    // Prune: if closest point in this AABB is farther than best, skip
    float dx = std::max(0.0f, std::abs(px - _boundary.cx) - _boundary.hw);
    float dy = std::max(0.0f, std::abs(py - _boundary.cy) - _boundary.hh);
    if (dx*dx + dy*dy >= best_dist) return;

    for (const auto& p : _points) {
        float ddx = p.x - px, ddy = p.y - py;
        float d2  = ddx*ddx + ddy*ddy;
        if (d2 < best_dist) {
            best_dist = d2;
            best_id   = p.id;
        }
    }

    if (_divided)
        for (const auto& c : _children)
            c._nearest(px, py, best_id, best_dist);
}

uint32_t Quadtree::nearest(float px, float py, float& out_dist) const {
    uint32_t best_id   = 0;
    float    best_dist = std::numeric_limits<float>::max();
    _nearest(px, py, best_id, best_dist);
    out_dist = std::sqrt(best_dist);
    return best_id;
}
