#pragma once
#include <queue>
#include <vector>
#include <string>
#include <cstdint>
#include <functional>

enum class EventType : uint8_t {
    DEPART   = 0,
    ARRIVE   = 1,
    RECHARGE = 2,
};

std::string eventTypeToString(EventType e);

struct Event {
    double    time;
    EventType type;
    uint32_t  robot_id;
    uint32_t  node_id;

    bool operator>(const Event& o) const { return time > o.time; }
};

class EventScheduler {
public:
    void        push(Event e);
    Event       pop();
    bool        empty() const;
    double      peek_time() const;
    std::size_t size() const;

private:
    std::priority_queue<Event, std::vector<Event>, std::greater<Event>> _pq;
};
