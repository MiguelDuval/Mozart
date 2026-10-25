cmake_minimum_required(VERSION 3.22.1)

project(MozartNativeTests LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Use local nlohmann/json single-header if available, otherwise fetch
set(NLOHMANN_JSON_LOCAL "${CMAKE_CURRENT_SOURCE_DIR}/../third_party/nlohmann")
if(EXISTS "${NLOHMANN_JSON_LOCAL}/json.hpp")
    message(STATUS "Using local nlohmann/json at ${NLOHMANN_JSON_LOCAL}")
    set(NLOHMANN_JSON_FOUND TRUE)
else()
    # Fetch nlohmann/json for tokenizer parsing
    include(FetchContent)
    FetchContent_Declare(
        nlohmann_json
        GIT_REPOSITORY https://github.com/nlohmann/json.git
        GIT_TAG v3.11.2
    )
    FetchContent_MakeAvailable(nlohmann_json)
    set(NLOHMANN_JSON_FOUND TRUE)
endif()

function(add_mozart_test name)
    add_executable(${name} ${ARGN})
    target_include_directories(${name} PRIVATE ../src)
    if(EXISTS "${NLOHMANN_JSON_LOCAL}/json.hpp")
        target_include_directories(${name} PRIVATE ${NLOHMANN_JSON_LOCAL})
    else()
        target_link_libraries(${name} PRIVATE nlohmann_json::nlohmann_json)
    endif()
endfunction()

add_mozart_test(mozart_core_tests
    MozartCoreTests.cpp
    ../src/core/MidiTypes.cpp
    ../src/core/TransportMath.cpp
    ../src/generation/RhythmGenerator.cpp
)

# REMI Adapter tests
add_mozart_test(remi_adapter_tests_1
    RemiAdapterTests.cpp
    ../src/core/GenerationTypes.cpp
    ../src/core/PatternProposalValidator.cpp
    ../src/core/PatternProposalValidatorSanitize.cpp
    ../src/core/RemiDecoderConfig.cpp
    ../src/core/RemiEventAdapter.cpp
    ../src/core/RemiEventAdapterConvert.cpp
    ../src/core/RemiEventAdapterDecode.cpp
    ../src/core/RemiEventAdapterFinalize.cpp
    ../src/core/RemiVocabulary.cpp
    ../src/core/BpeTokenizer.cpp
    ../src/core/LocalNeuralPatternProvider.cpp
    ../src/core/LocalNeuralPatternProviderGenerate.cpp
    ../src/core/LocalNeuralPatternProviderFallback.cpp
    ../src/generation/RhythmGenerator.cpp
)

add_mozart_test(remi_adapter_tests_2
    RemiAdapterTests2.cpp
    ../src/core/GenerationTypes.cpp
    ../src/core/PatternProposalValidator.cpp
    ../src/core/PatternProposalValidatorSanitize.cpp
    ../src/core/RemiDecoderConfig.cpp
    ../src/core/RemiEventAdapter.cpp
    ../src/core/RemiEventAdapterConvert.cpp
    ../src/core/RemiEventAdapterDecode.cpp
    ../src/core/RemiEventAdapterFinalize.cpp
    ../src/core/RemiVocabulary.cpp
    ../src/core/BpeTokenizer.cpp
    ../src/core/LocalNeuralPatternProvider.cpp
    ../src/core/LocalNeuralPatternProviderGenerate.cpp
    ../src/core/LocalNeuralPatternProviderFallback.cpp
    ../src/generation/RhythmGenerator.cpp
)

add_mozart_test(remi_adapter_tests_3
    RemiAdapterTests3.cpp
    ../src/core/GenerationTypes.cpp
    ../src/core/PatternProposalValidator.cpp
    ../src/core/PatternProposalValidatorSanitize.cpp
    ../src/core/RemiDecoderConfig.cpp
    ../src/core/RemiEventAdapter.cpp
    ../src/core/RemiEventAdapterConvert.cpp
    ../src/core/RemiEventAdapterDecode.cpp
    ../src/core/RemiEventAdapterFinalize.cpp
    ../src/core/RemiVocabulary.cpp
    ../src/core/BpeTokenizer.cpp
    ../src/core/LocalNeuralPatternProvider.cpp
    ../src/core/LocalNeuralPatternProviderGenerate.cpp
    ../src/core/LocalNeuralPatternProviderFallback.cpp
    ../src/generation/RhythmGenerator.cpp
)
