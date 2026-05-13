find_package(TBB REQUIRED)
find_package(Protobuf REQUIRED)

add_executable(lastmile_engine
  src/main.cpp
  src/Robot.cpp
  src/Quadtree.cpp
  src/EventScheduler.cpp
  src/Simulation.cpp
  src/RoadGraph.cpp
  src/AStar.cpp
  src/simulation.pb.cc
)

target_include_directories(lastmile_engine PRIVATE
  include
  ${Protobuf_INCLUDE_DIRS}
)

target_link_libraries(lastmile_engine PRIVATE
  TBB::tbb
  ${Protobuf_LIBRARIES}
)
