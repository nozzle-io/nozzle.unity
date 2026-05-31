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

option(NOZZLE_UNITY_BUILD_NOZZLE_CORE "Build the nozzle core submodule next to the Unity bridge" ON)
option(NOZZLE_UNITY_USE_UNITY_HEADERS "Build nozzle_unity with Unity Native Plugin API headers" OFF)
set(NOZZLE_UNITY_PLUGIN_API_DIR "" CACHE PATH "Path containing Unity IUnityInterface.h and IUnityGraphics.h")

if(NOZZLE_UNITY_BUILD_NOZZLE_CORE)
    add_subdirectory(nozzle)
endif()

set(NOZZLE_UNITY_NATIVE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/Packages/org.nozzle-io.unity/Native~")
set(NOZZLE_UNITY_NATIVE_INCLUDE_DIR "${NOZZLE_UNITY_NATIVE_ROOT}/include")

add_library(nozzle_unity SHARED
    "${NOZZLE_UNITY_NATIVE_ROOT}/src/nozzle_unity_bridge_common.cpp"
)

target_compile_definitions(nozzle_unity PRIVATE NOZZLE_UNITY_EXPORTS)
target_include_directories(nozzle_unity PRIVATE
    "${NOZZLE_UNITY_NATIVE_INCLUDE_DIR}"
    "${NOZZLE_UNITY_NATIVE_ROOT}/src"
)

set_target_properties(nozzle_unity PROPERTIES
    OUTPUT_NAME "nozzle_unity"
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON
)

if(NOZZLE_UNITY_USE_UNITY_HEADERS)
    if(NOT NOZZLE_UNITY_PLUGIN_API_DIR)
        message(FATAL_ERROR "NOZZLE_UNITY_USE_UNITY_HEADERS=ON requires NOZZLE_UNITY_PLUGIN_API_DIR")
    endif()
    if(NOT EXISTS "${NOZZLE_UNITY_PLUGIN_API_DIR}/IUnityInterface.h")
        message(FATAL_ERROR "IUnityInterface.h not found in NOZZLE_UNITY_PLUGIN_API_DIR=${NOZZLE_UNITY_PLUGIN_API_DIR}")
    endif()
    if(NOT EXISTS "${NOZZLE_UNITY_PLUGIN_API_DIR}/IUnityGraphics.h")
        message(FATAL_ERROR "IUnityGraphics.h not found in NOZZLE_UNITY_PLUGIN_API_DIR=${NOZZLE_UNITY_PLUGIN_API_DIR}")
    endif()

    target_sources(nozzle_unity PRIVATE
        "${NOZZLE_UNITY_NATIVE_ROOT}/src/nozzle_unity_bridge_unity.cpp"
    )
    target_include_directories(nozzle_unity PRIVATE "${NOZZLE_UNITY_PLUGIN_API_DIR}")
    target_compile_definitions(nozzle_unity PRIVATE NOZZLE_UNITY_WITH_UNITY_HEADERS=1)
else()
    target_sources(nozzle_unity PRIVATE
        "${NOZZLE_UNITY_NATIVE_ROOT}/src/nozzle_unity_bridge_stub.cpp"
    )
endif()

if(TARGET nozzle)
    target_link_libraries(nozzle_unity PRIVATE nozzle)
endif()
