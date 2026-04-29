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

add_library(nozzle_unity MODULE)

target_sources(nozzle_unity PRIVATE
    src/nozzle_unity.cpp
)

target_include_directories(nozzle_unity PRIVATE
    src
)

target_link_libraries(nozzle_unity PRIVATE nozzle)

target_compile_options(nozzle_unity PRIVATE
    $<$<CXX_COMPILER_ID:Clang,AppleClang>:-fno-exceptions -fno-rtti>
    $<$<CXX_COMPILER_ID:GNU>:-fno-exceptions -fno-rtti>
    $<$<CXX_COMPILER_ID:MSVC>:/EHs-c- /GR->
)

set_target_properties(nozzle_unity PROPERTIES
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON
    POSITION_INDEPENDENT_CODE ON
)

if(APPLE)
    set_target_properties(nozzle_unity PROPERTIES
        BUNDLE TRUE
        PREFIX ""
        SUFFIX ".bundle"
    )
endif()

if(WIN32)
    set_target_properties(nozzle_unity PROPERTIES
        PREFIX ""
    )
endif()
