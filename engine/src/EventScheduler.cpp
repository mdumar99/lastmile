#include "EventScheduler.h"
#include <stdexcept>

std::string eventTypeToString(EventType e) {
    switch (e) {
        case EventType::DEPART:        return "DEPART";
        case EventType::ARRIVE:        return "ARRIVE";
        case EventType::RECHARGE:      return "RECHARGE";
        case EventType::TRAFFIC_JAM:   return "TRAFFIC_JAM";
        case EventType::DELIVERY_FAIL: return "DELIVERY_FAIL";
        case EventType::WEATHER_DELAY: return "WEATHER_DELAY";
        default:                       return "UNKNOWN";
    }
}

void        EventScheduler::push(Event e)  { _pq.push(e); }
bool        EventScheduler::empty()  const { return _pq.empty(); }
std::size_t EventScheduler::size()   const { return _pq.size(); }
double      EventScheduler::peek_time() const {
    return _pq.empty() ? -1.0 : _pq.top().time;
}

Event EventScheduler::pop() {
    if (_pq.empty())
        throw std::runtime_error("pop on empty queue");
    Event e = _pq.top();
    _pq.pop();
    return e;
}
