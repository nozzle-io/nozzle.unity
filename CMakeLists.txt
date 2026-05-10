cmake_minimum_required(VERSION 3.20)

project(nozzle_unity
    VERSION 0.1.0
    DESCRIPTION "Unity native plugin for nozzle GPU texture sharing"
    LANGUAGES CXX
)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(APPLE)
    if(NOT CMAKE_OSX_DEPLOYMENT_TARGET)
        set(CMAKE_OSX_DEPLOYMENT_TARGET "12.0" CACHE STRING "macOS deployment target" FORCE)
    endif()
endif()

add_subdirectory(nozzle)
