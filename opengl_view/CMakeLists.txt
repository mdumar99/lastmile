find_package(OpenGL REQUIRED)
find_package(glfw3 REQUIRED)
find_package(GLEW REQUIRED)

add_executable(lastmile_gl
    main_gl.cpp
    OpenGLView.cpp
    ../engine/src/Robot.cpp
    ../engine/src/Quadtree.cpp
    ../engine/src/EventScheduler.cpp
    ../engine/src/Simulation.cpp
    ../engine/src/RoadGraph.cpp
    ../engine/src/AStar.cpp
    ../engine/src/simulation.pb.cc
)

target_include_directories(lastmile_gl PRIVATE
    ../engine/include
    ${OPENGL_INCLUDE_DIRS}
    ${GLEW_INCLUDE_DIRS}
)

target_link_libraries(lastmile_gl PRIVATE
    ${OPENGL_LIBRARIES}
    GLEW::GLEW
    glfw
    TBB::tbb
    ${Protobuf_LIBRARIES}
)

target_compile_features(lastmile_gl PRIVATE cxx_std_20)
