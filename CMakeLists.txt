cmake_minimum_required(VERSION 3.22.1)

project(Mozart VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(mozart-core STATIC
    src/core/MozartEngine.cpp
    src/core/MidiTypes.cpp
    src/core/TransportMath.cpp
    src/core/MidiEndpoint.cpp
    src/generation/RhythmGenerator.cpp
)

target_include_directories(mozart-core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

if(ANDROID)
    find_library(AMIDI_LIBRARY amidi REQUIRED)

    add_library(mozart SHARED
        src/platform/android/MozartJni.cpp
        src/platform/android/AndroidMidiOutput.cpp
    )

    target_link_libraries(mozart
        PRIVATE
        mozart-core
        log
        ${AMIDI_LIBRARY}
    )
else()
    add_library(mozart-platform INTERFACE)
endif()

option(MOZART_FETCH_AUDIO_STACK "Fetch pinned audio/timing dependencies for development" OFF)

if(MOZART_FETCH_AUDIO_STACK)
    include(cmake/Dependencies.cmake)
endif()
