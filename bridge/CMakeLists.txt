find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
find_package(TBB REQUIRED)

execute_process(
    COMMAND ${Python3_EXECUTABLE} -c "import pybind11; print(pybind11.get_include())"
    OUTPUT_VARIABLE PYBIND11_INCLUDE
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

message(STATUS "pybind11 include: ${PYBIND11_INCLUDE}")

add_library(lastmile MODULE
    bindings.cpp
    ../engine/src/Robot.cpp
    ../engine/src/Quadtree.cpp
    ../engine/src/EventScheduler.cpp
    ../engine/src/Simulation.cpp
    ../engine/src/RoadGraph.cpp
    ../engine/src/AStar.cpp
)

target_include_directories(lastmile PRIVATE
    ../engine/include
    ${Python3_INCLUDE_DIRS}
    ${PYBIND11_INCLUDE}
)

target_link_libraries(lastmile PRIVATE
    ${Python3_LIBRARIES}
    TBB::tbb
)

set_target_properties(lastmile PROPERTIES
    PREFIX ""
    SUFFIX ".so"
    CXX_STANDARD 20
)
