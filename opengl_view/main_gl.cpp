#include "OpenGLView.h"
#include "Simulation.h"
#include <iostream>
#include <thread>
#include <atomic>
#include <mutex>
#include <chrono>
#include <cmath>

struct SharedState {
    std::vector<ViewRobot> robots;
    std::vector<ViewHub>   hubs;
    ViewStats              stats{};
    std::mutex             mtx;
    std::atomic<bool>      sim_done{false};
    float min_x{-25000.f}, max_x{25000.f};
    float min_y{-16000.f}, max_y{16000.f};
};

void run_simulation(SharedState& shared, SimConfig cfg) {
    Simulation sim(cfg);
    sim.run();

    auto robot_states = sim.get_robot_states_raw();
    auto hub_queues   = sim.get_hub_queue_lengths();
    auto s            = sim.stats();

    float min_x= 1e9f, max_x=-1e9f;
    float min_y= 1e9f, max_y=-1e9f;
    std::vector<ViewRobot> robots;

    for (const auto& rs : robot_states) {
        robots.push_back({rs[0], rs[1], rs[2], (int)rs[3]});
        if (rs[0]!=0.f || rs[1]!=0.f) {
            min_x=std::min(min_x,rs[0]); max_x=std::max(max_x,rs[0]);
            min_y=std::min(min_y,rs[1]); max_y=std::max(max_y,rs[1]);
        }
    }

    float px=(max_x-min_x)*0.05f, py=(max_y-min_y)*0.05f;

    std::lock_guard<std::mutex> lock(shared.mtx);
    shared.robots = robots;
    shared.min_x  = min_x-px; shared.max_x = max_x+px;
    shared.min_y  = min_y-py; shared.max_y = max_y+py;
    shared.hubs = {
        {92.57f,   74.63f,  hub_queues.size()>0?hub_queues[0]:0},
        {498.45f, 797.77f,  hub_queues.size()>1?hub_queues[1]:0},
        {820.34f, 286.75f,  hub_queues.size()>2?hub_queues[2]:0},
    };
    shared.stats = {
        (int)s.total_deliveries, (int)s.recharge_events,
        (int)s.traffic_jams,     (int)s.delivery_fails,
        s.total_energy_kwh, 0, cfg.sim_duration_s
    };
    shared.sim_done = true;
    std::cout << "\n[GL] Done — " << s.total_deliveries
              << " deliveries\n";
    std::cout << "[GL] Bounds x[" << shared.min_x
              << ", " << shared.max_x << "] y["
              << shared.min_y << ", " << shared.max_y << "]\n";
    std::cout << "[GL] " << robots.size()
              << " robots to render\n";
    std::cout << "[GL] Close window to exit.\n";
}

int main(int argc, char* argv[]) {
    SimConfig cfg;
    cfg.num_robots     = argc>1 ? std::stoi(argv[1]) : 100;
    cfg.sim_duration_s = argc>2 ? std::stod(argv[2]) : 3600.0;
    cfg.log_path       = "data/logs/gl_sim_log.csv";

    std::cout << "=== Last-Mile — OpenGL Engineering View ===\n";
    std::cout << "Robots: " << cfg.num_robots
              << "  Duration: " << cfg.sim_duration_s << "s\n\n";

    SharedState shared;
    shared.hubs = {
        {92.57f,74.63f,0},{498.45f,797.77f,0},{820.34f,286.75f,0}
    };

    OpenGLView view(1280, 720,
                    "Last-Mile Delivery — Engineering View");
    if (!view.init()) return 1;

    std::thread sim_thread(run_simulation, std::ref(shared), cfg);

    int  frame     = 0;
    bool announced = false;

    while (!view.should_close()) {
        view.poll_events();

        std::vector<ViewRobot> robots;
        std::vector<ViewHub>   hubs;
        ViewStats              stats;
        float min_x, max_x, min_y, max_y;
        bool  done;
        {
            std::lock_guard<std::mutex> lock(shared.mtx);
            robots = shared.robots;
            hubs   = shared.hubs;
            stats  = shared.stats;
            min_x  = shared.min_x; max_x = shared.max_x;
            min_y  = shared.min_y; max_y = shared.max_y;
            done   = shared.sim_done;
        }

        if (done && !announced) {
            std::cout << "[GL] Now rendering "
                      << robots.size() << " robots\n";
            announced = true;
        }

        view.render(robots, hubs, stats,
                    min_x, max_x, min_y, max_y);

        std::this_thread::sleep_for(std::chrono::milliseconds(16));
        ++frame;
    }

    sim_thread.join();
    return 0;
}
