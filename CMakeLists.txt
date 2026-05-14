cmake_minimum_required(VERSION 3.20)
project(LastMile VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_compile_options(-Wall -Wextra -Wpedantic)

if(CMAKE_BUILD_TYPE STREQUAL "Release")
  add_compile_options(-O3)
endif()

find_package(TBB REQUIRED)
find_package(Protobuf REQUIRED)

add_subdirectory(engine)
add_subdirectory(bridge)
add_subdirectory(opengl_view)
