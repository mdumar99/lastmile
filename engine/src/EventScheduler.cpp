#include "EventScheduler.h"
#include <stdexcept>

std::string eventTypeToString(EventType e) {
    switch (e) {
        case EventType::DEPART:   return "DEPART";
        case EventType::ARRIVE:   return "ARRIVE";
        case EventType::RECHARGE: return "RECHARGE";
        default:                  return "UNKNOWN";
    }
}

void EventScheduler::push(Event e) { _pq.push(e); }

Event EventScheduler::pop() {
    if (_pq.empty())
        throw std::runtime_error("pop on empty queue");
    Event e = _pq.top();
    _pq.pop();
    return e;
}

bool        EventScheduler::empty()     const { return _pq.empty(); }
double      EventScheduler::peek_time() const { return _pq.empty() ? -1.0 : _pq.top().time; }
std::size_t EventScheduler::size()      const { return _pq.size(); }
