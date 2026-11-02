cmake_minimum_required(VERSION 3.22.1)

project(MozartNativeTests LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(mozart_core_tests
    MozartCoreTests.cpp
    ../src/core/MidiTypes.cpp
    ../src/core/TransportMath.cpp
    ../src/core/Track.cpp
    ../src/core/Pattern.cpp
    ../src/core/Pattern.h
    ../src/core/Project.cpp
    ../src/core/Project.h
    ../src/core/ChannelMixer.cpp
    ../src/core/Metronome.cpp
    ../src/generation/RhythmGenerator.cpp
)

target_include_directories(mozart_core_tests PRIVATE
    ../src
)
