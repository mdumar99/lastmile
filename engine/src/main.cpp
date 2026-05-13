#include "Simulation.h"
#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    SimConfig cfg;

    if (argc > 1) cfg.num_robots     = std::stoi(argv[1]);
    if (argc > 2) cfg.sim_duration_s = std::stod(argv[2]);

    for (int i = 3; i < argc - 1; ++i) {
        std::string flag = argv[i];
        if (flag == "--hubs")  cfg.hubs_csv   = argv[i+1];
        if (flag == "--proto") cfg.proto_path = argv[i+1];
    }

    std::string hub_mode = cfg.hubs_csv.empty() ? "hardcoded" : "MILP optimised";
    std::cout << "=== Last-Mile Delivery Simulation ===\n";
    std::cout << "Robots  : " << cfg.num_robots     << "\n";
    std::cout << "Duration: " << cfg.sim_duration_s << "s\n";
    std::cout << "Hubs    : " << hub_mode           << "\n";
    if (!cfg.proto_path.empty())
        std::cout << "Proto   : " << cfg.proto_path << "\n";
    std::cout << "\n";

    Simulation sim(cfg);
    sim.run();
    return 0;
}
