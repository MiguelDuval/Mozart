cmake_minimum_required(VERSION 3.22.1)

project(MozartNativeTests LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(MOZART_ENABLE_LINK "Enable Ableton Link tests" OFF)

add_executable(mozart_core_tests
    MozartCoreTests.cpp
    ../src/core/MidiTypes.cpp
    ../src/core/TransportMath.cpp
    ../src/core/MidiEndpoint.cpp
    ../src/generation/RhythmGenerator.cpp
)

target_include_directories(mozart_core_tests PRIVATE
    ../src
)

if(MOZART_ENABLE_LINK)
    set(MOZART_LINK_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../third_party/ableton_link")
    if(NOT EXISTS "${MOZART_LINK_ROOT}/AbletonLinkConfig.cmake")
        message(FATAL_ERROR
            "MOZART_ENABLE_LINK=ON but pinned Ableton Link is missing. "
            "Run tools/fetch_link.sh first.")
    endif()

    include("${MOZART_LINK_ROOT}/AbletonLinkConfig.cmake")
    target_compile_features(mozart_core_tests PRIVATE cxx_std_20)
    target_sources(mozart_core_tests PRIVATE
        ../src/clock/LinkClock.cpp
    )
    target_compile_definitions(mozart_core_tests PRIVATE
        LINK_PLATFORM_LINUX=1
    )
    target_link_libraries(mozart_core_tests PRIVATE Ableton::Link)
endif()
