cmake_minimum_required(VERSION 3.22.1)

project(Mozart VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(MOZART_ENABLE_LINK "Enable the pinned Ableton Link clock integration" OFF)

add_library(mozart-core STATIC
    src/core/MozartEngine.cpp
    src/core/MidiTypes.cpp
    src/core/TransportMath.cpp
    src/core/MidiEndpoint.cpp
    src/musical/KeyScale.cpp
    src/generation/RhythmGenerator.cpp
    src/generation/BassGenerator.cpp
)

target_include_directories(mozart-core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

if(MOZART_ENABLE_LINK)
    set(MOZART_LINK_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/third_party/ableton_link")
    if(NOT EXISTS "${MOZART_LINK_ROOT}/AbletonLinkConfig.cmake")
        message(FATAL_ERROR
            "MOZART_ENABLE_LINK=ON but pinned Ableton Link is missing. "
            "Run tools/fetch_link.sh first.")
    endif()
    include("${MOZART_LINK_ROOT}/AbletonLinkConfig.cmake")
endif()

if(ANDROID)
    add_library(mozart SHARED
        src/platform/android/MozartJni.cpp
        src/platform/android/AndroidMidiOutput.cpp
    )

    if(MOZART_ENABLE_LINK)
        target_sources(mozart PRIVATE
            src/clock/LinkClock.cpp
            src/scheduler/MidiSendQueue.cpp
            src/scheduler/AccompanimentScheduler.cpp
            src/runtime/MozartRuntime.cpp
        )
        target_compile_definitions(mozart PRIVATE LINK_PLATFORM_LINUX=1)
    endif()

    target_compile_features(mozart PRIVATE cxx_std_20)

    target_link_libraries(mozart
        PRIVATE
        mozart-core
        log
        ${CMAKE_DL_LIBS}
    )

    if(MOZART_ENABLE_LINK)
        target_link_libraries(mozart PRIVATE Ableton::Link)
    endif()
else()
    add_library(mozart-platform INTERFACE)
endif()

option(MOZART_FETCH_AUDIO_STACK "Fetch pinned audio/timing dependencies for development" OFF)

if(MOZART_FETCH_AUDIO_STACK)
    include(cmake/Dependencies.cmake)
endif()
