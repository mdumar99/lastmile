add_executable(lastmile_engine
  src/main.cpp
  src/Robot.cpp
  src/Quadtree.cpp
  src/EventScheduler.cpp
  src/Simulation.cpp
  src/RoadGraph.cpp
  src/AStar.cpp
)

target_include_directories(lastmile_engine PRIVATE include)
