cmake_minimum_required(VERSION 3.22.1)

project(MozartNativeTests LANGUAGES CXX)

find_package(Threads REQUIRED)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(MOZART_ENABLE_LINK "Enable Ableton Link tests" OFF)

add_executable(mozart_core_tests
    MozartCoreTests.cpp
    ../src/core/MidiTypes.cpp
    ../src/core/TransportMath.cpp
    ../src/core/MidiEndpoint.cpp
    ../src/musical/KeyScale.cpp
    ../src/musical/AudioKeyDetector.cpp
    ../src/musical/AudioKeyStabilityFilter.cpp
    ../src/musical/KeyContext.cpp
    ../src/musical/AudioChromaEstimator.cpp
    ../src/musical/Chord.cpp
    ../src/musical/VoiceLeading.cpp
    ../src/generation/RhythmGenerator.cpp
    ../src/generation/BassGenerator.cpp
    ../src/generation/ArpeggioGenerator.cpp
    ../src/generation/DrumPatternGenerator.cpp
    ../src/generation/ChordProgressionGenerator.cpp
    ../src/generation/NoteRepeat.cpp
    ../src/generation/DeterministicPatternProvider.cpp
    ../src/generation/LocalNeuralPatternProvider.cpp
    ../src/generation/GenerationService.cpp
    ../src/generation/OnnxTokenInferenceBackend.cpp
    ../src/midi/MidiReceiveQueue.cpp
    ../src/midi/ControllerMapping.cpp
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
        ../src/scheduler/MidiSendQueue.cpp
        ../src/scheduler/AccompanimentScheduler.cpp
        ../src/scheduler/PerformanceScene.cpp
        ../src/scheduler/MacroControl.cpp
        ../src/runtime/MozartRuntime.cpp
    )
    target_compile_definitions(mozart_core_tests PRIVATE
        LINK_PLATFORM_LINUX=1
    )
    target_link_libraries(mozart_core_tests PRIVATE Ableton::Link Threads::Threads)
endif()

add_executable(mozart_generation_provider_tests
    GenerationProviderTests.cpp
    ../src/generation/LocalNeuralPatternProvider.cpp
    ../src/musical/KeyScale.cpp
    ../src/musical/Chord.cpp
)

target_include_directories(mozart_generation_provider_tests PRIVATE
    ../src
)
target_compile_features(mozart_generation_provider_tests PRIVATE cxx_std_20)

add_executable(mozart_pattern_variation_tests
    PatternVariationTests.cpp
    ../src/musical/KeyScale.cpp
    ../src/musical/Chord.cpp
    ../src/generation/RhythmGenerator.cpp
    ../src/generation/BassGenerator.cpp
    ../src/generation/ArpeggioGenerator.cpp
    ../src/generation/DrumPatternGenerator.cpp
    ../src/generation/DeterministicPatternProvider.cpp
)

target_include_directories(mozart_pattern_variation_tests PRIVATE
    ../src
)
target_compile_features(mozart_pattern_variation_tests PRIVATE cxx_std_20)

add_executable(mozart_model_catalog_tests
    ModelCatalogTests.cpp
)

add_executable(mozart_onnx_token_inference_backend_tests
    OnnxTokenInferenceBackendTests.cpp
    ../src/generation/OnnxTokenInferenceBackend.cpp
    ../src/musical/KeyScale.cpp
)

target_include_directories(mozart_onnx_token_inference_backend_tests PRIVATE
    ../src
)
target_compile_features(mozart_onnx_token_inference_backend_tests PRIVATE cxx_std_20)

add_executable(mozart_generation_service_tests
    GenerationServiceTests.cpp
    ../src/generation/GenerationService.cpp
    ../src/generation/LocalNeuralPatternProvider.cpp
    ../src/musical/KeyScale.cpp
    ../src/musical/Chord.cpp
)

target_include_directories(mozart_generation_service_tests PRIVATE
    ../src
)
target_compile_features(mozart_generation_service_tests PRIVATE cxx_std_20)
target_link_libraries(mozart_generation_service_tests PRIVATE Threads::Threads)

add_executable(mozart_generation_request_json_tests
    GenerationRequestJsonTests.cpp
    ../src/musical/KeyScale.cpp
)

target_include_directories(mozart_generation_request_json_tests PRIVATE
    ../src
)
target_compile_features(mozart_generation_request_json_tests PRIVATE cxx_std_20)

add_executable(mozart_generation_request_ticket_tests
    GenerationRequestTicketTests.cpp
)

target_include_directories(mozart_generation_request_ticket_tests PRIVATE
    ../src
)
target_compile_features(mozart_generation_request_ticket_tests PRIVATE cxx_std_20)


target_include_directories(mozart_model_catalog_tests PRIVATE
    ../src
)
target_compile_features(mozart_model_catalog_tests PRIVATE cxx_std_20)
