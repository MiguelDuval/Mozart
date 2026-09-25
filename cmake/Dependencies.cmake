include(FetchContent)

set(FETCHCONTENT_QUIET OFF)

FetchContent_Declare(
    JUCE
    GIT_REPOSITORY https://github.com/juce-framework/JUCE.git
    GIT_TAG 72782788ce18c2d4d760b28e0921d6ffc6431102
)

FetchContent_Declare(
    Oboe
    GIT_REPOSITORY https://github.com/google/oboe.git
    GIT_TAG faa019cb12f448d18b5ab2b933272cf0c16763b2
)

FetchContent_Declare(
    AbletonLink
    GIT_REPOSITORY https://github.com/Ableton/link.git
    GIT_TAG e9a2e414d63f55f1aad158370b007a6fbdc1eeb9
)

FetchContent_Declare(
    TracktionEngine
    GIT_REPOSITORY https://github.com/Tracktion/tracktion_engine.git
    GIT_TAG 0a5f4e6a5f53d09c89b414a44386a12df7fa1ec6
)

message(STATUS "Mozart pinned dependency manifest loaded.")
message(STATUS "JUCE 9.0.2  @ 72782788ce18c2d4d760b28e0921d6ffc6431102")
message(STATUS "Oboe 1.10.2 @ faa019cb12f448d18b5ab2b933272cf0c16763b2")
message(STATUS "Link 4.0    @ e9a2e414d63f55f1aad158370b007a6fbdc1eeb9")
message(STATUS "Tracktion 3.2.0 @ 0a5f4e6a5f53d09c89b414a44386a12df7fa1ec6")

# Intentionally do not call FetchContent_MakeAvailable here.
# Each implementation slice should enable only the dependencies it actually
# needs and should verify the resulting Android build before proceeding.
