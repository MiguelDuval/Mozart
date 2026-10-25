cmake_minimum_required(VERSION 3.22.1)

project(Mozart VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Use local nlohmann/json single-header if available, otherwise fetch
set(NLOHMANN_JSON_LOCAL "${CMAKE_CURRENT_SOURCE_DIR}/third_party/nlohmann")
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

add_library(mozart-core STATIC
    src/core/MozartEngine.cpp
    src/core/MidiTypes.cpp
    src/core/TransportMath.cpp
    src/core/GenerationTypes.cpp
    src/core/PatternProposalValidator.cpp
    src/core/PatternProposalValidatorSanitize.cpp
    src/core/RemiDecoderConfig.cpp
    src/core/RemiEventAdapter.cpp
    src/core/RemiEventAdapterConvert.cpp
    src/core/RemiEventAdapterDecode.cpp
    src/core/RemiEventAdapterFinalize.cpp
    src/core/RemiVocabulary.cpp
    src/core/BpeTokenizer.cpp
    src/core/LocalNeuralPatternProvider.cpp
    src/core/LocalNeuralPatternProviderGenerate.cpp
    src/core/LocalNeuralPatternProviderFallback.cpp
    src/generation/RhythmGenerator.cpp
)

target_include_directories(mozart-core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

if(EXISTS "${NLOHMANN_JSON_LOCAL}/json.hpp")
    target_include_directories(mozart-core PUBLIC ${NLOHMANN_JSON_LOCAL})
else()
    target_link_libraries(mozart-core PUBLIC nlohmann_json::nlohmann_json)
    # Source files include the single-header name "json.hpp"; the fetched package
    # exposes that header from include/nlohmann rather than directly from include.
    target_include_directories(mozart-core PUBLIC "${nlohmann_json_SOURCE_DIR}/include/nlohmann")
endif()

if(ANDROID)
    add_library(mozart SHARED
        src/platform/android/MozartJni.cpp
    )

    target_link_libraries(mozart
        PRIVATE
        mozart-core
        log
    )
else()
    add_library(mozart-platform INTERFACE)
endif()

option(MOZART_FETCH_AUDIO_STACK "Fetch pinned audio/timing dependencies for development" OFF)

if(MOZART_FETCH_AUDIO_STACK)
    include(cmake/Dependencies.cmake)
endif()
