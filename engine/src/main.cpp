#include "Simulation.h"
#include <iostream>

int main(int argc, char* argv[]) {
    SimConfig cfg;
    if (argc > 1) cfg.num_robots     = std::stoi(argv[1]);
    if (argc > 2) cfg.sim_duration_s = std::stod(argv[2]);

    std::cout << "=== Last-Mile Delivery Simulation (Phase 1) ===\n";
    std::cout << "Robots: "   << cfg.num_robots
              << "  Duration: " << cfg.sim_duration_s << "s\n\n";

    Simulation sim(cfg);
    sim.run();
    return 0;
}
