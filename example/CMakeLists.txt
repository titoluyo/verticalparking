# The following lines of boilerplate have to be in your project's CMakeLists
# in this exact order for cmake to work correctly
cmake_minimum_required(VERSION 3.5)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

set(
  COMPONENTS
  "main esptool_py"
  CACHE STRING
  "List of components to include"
  )

project(vl53l_example)

set(CMAKE_CXX_STANDARD 20)
