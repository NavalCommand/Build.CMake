cmake_minimum_required(VERSION 4.2)
cmake_policy(SET CMP0168 NEW)
include_guard(GLOBAL)
include(FetchContent)
set(CMAKE_FIND_PACKAGE_TARGETS_GLOBAL TRUE)

function(NavalCommandDependencyIdentity url identity fetchName)
    string(REGEX REPLACE "\\.git/?$" "" canonical "${url}")
    if(NOT canonical MATCHES "^https://github.com/([^/]+)/([^/]+)$")
        message(FATAL_ERROR "Expected a canonical GitHub repository URL: ${url}")
    endif()
    string(TOLOWER "${CMAKE_MATCH_1}.${CMAKE_MATCH_2}" id)
    string(SHA256 hash "${id}")
    # Names remain derived from full canonical identity, never caller aliases. Short names apply on
    # every platform for consistent local registrations.
    string(SUBSTRING "${hash}" 0 12 shortHash)
    set(${identity}
        "${id}"
        PARENT_SCOPE)
    set(${fetchName}
        "nc_${shortHash}"
        PARENT_SCOPE)
endfunction()

function(NavalCommandSetDependencyPath url path)
    NavalCommandDependencyIdentity("${url}" id name)
    get_filename_component(absolute "${path}" ABSOLUTE BASE_DIR "${CMAKE_SOURCE_DIR}")
    if(NOT IS_DIRECTORY "${absolute}" OR NOT EXISTS "${absolute}/CMakeLists.txt")
        message(FATAL_ERROR "Invalid explicit dependency path for ${id}: ${absolute}")
    endif()
    file(REAL_PATH "${absolute}" absolute)
    get_property(old GLOBAL PROPERTY "${name}_local")
    if(old AND NOT old STREQUAL absolute)
        message(FATAL_ERROR "Conflicting local dependency registrations for ${id}")
    endif()
    get_property(resolved GLOBAL PROPERTY "${name}_resolved")
    if(resolved AND NOT old STREQUAL absolute)
        message(FATAL_ERROR "Local override for ${id} must precede FetchContent_Declare")
    endif()
    set_property(GLOBAL PROPERTY "${name}_local" "${absolute}")
endfunction()

function(NavalCommandAddDependency url tag)
    NavalCommandDependencyIdentity("${url}" id name)
    get_property(oldId GLOBAL PROPERTY "${name}_identity")
    if(oldId AND NOT oldId STREQUAL id)
        message(FATAL_ERROR "Hashed dependency identity collision: ${id}")
    endif()
    get_property(oldTag GLOBAL PROPERTY "${name}_tag")
    if(oldTag AND NOT oldTag STREQUAL tag)
        message(FATAL_ERROR "Conflicting Git references for ${id}: ${oldTag} versus ${tag}")
    endif()
    get_property(resolved GLOBAL PROPERTY "${name}_resolved")
    if(resolved)
        return()
    endif()
    set_property(GLOBAL PROPERTY "${name}_identity" "${id}")
    set_property(GLOBAL PROPERTY "${name}_tag" "${tag}")
    get_property(local GLOBAL PROPERTY "${name}_local")
    if(local)
        FetchContent_Declare(${name} SOURCE_DIR "${local}")
        message(STATUS "NavalCommand dependency ${id} -> ${name} local ${local}")
    else()
        FetchContent_Declare(
            ${name}
            GIT_REPOSITORY "${url}"
            GIT_TAG "${tag}")
        message(STATUS "NavalCommand dependency ${id} -> ${name} Git ${tag}")
    endif()
    # Set before descent: repeated/cyclic requests never re-declare an identity.
    set_property(GLOBAL PROPERTY "${name}_resolved" TRUE)
    FetchContent_MakeAvailable(${name})
    set_property(GLOBAL PROPERTY "${name}_source" "${${name}_SOURCE_DIR}")
    file(APPEND "${CMAKE_BINARY_DIR}/dependency-resolution.log"
         "${id}|${tag}|${${name}_SOURCE_DIR}\n")
endfunction()

function(NavalCommandGetDependencySource url output)
    NavalCommandDependencyIdentity("${url}" id name)
    get_property(
        source
        GLOBAL
        PROPERTY "${name}_source")
    if(NOT source)
        message(FATAL_ERROR "Dependency has not been resolved: ${id}")
    endif()
    set(${output}
        "${source}"
        PARENT_SCOPE)
endfunction()

# Only the top-level developer file is read, once and before any declaration.
if(EXISTS "${CMAKE_SOURCE_DIR}/Build.Local.cmake")
    include("${CMAKE_SOURCE_DIR}/Build.Local.cmake")
endif()
file(WRITE "${CMAKE_BINARY_DIR}/build-runner.txt"
     "${CMAKE_CURRENT_LIST_DIR}/scripts/Build-Native.ps1")

# MSVC's current CMake compiler table has no 26 mode, but /std:c++latest enables the compiler's
# available C++26 features. Keep policy in one place.
if(MSVC AND CMAKE_CXX_COMPILER_ID STREQUAL "MSVC")
    set(CMAKE_CXX26_STANDARD_COMPILE_OPTION /std:c++latest)
    set(CMAKE_CXX26_EXTENSION_COMPILE_OPTION /std:c++latest)
endif()

function(NavalCommandConfigureTarget target)
    set_target_properties(
        ${target}
        PROPERTIES CXX_STANDARD 26
                   CXX_STANDARD_REQUIRED YES
                   CXX_EXTENSIONS NO)
    get_target_property(type ${target} TYPE)
    if(type STREQUAL "INTERFACE_LIBRARY")
        return()
    endif()
    if(MSVC)
        target_compile_options(${target} PRIVATE /EHsc /utf-8 /Zc:__cplusplus)
    else()
        target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
    endif()
endfunction()

macro(NavalCommandConfigureModule)
    if(PROJECT_IS_TOP_LEVEL)
        include(CTest)
    endif()
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/src/CMakeLists.txt")
        add_subdirectory(src)
    endif()
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/mock/CMakeLists.txt")
        add_subdirectory(mock)
    endif()
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/app/CMakeLists.txt")
        add_subdirectory(app)
    endif()
    if(PROJECT_IS_TOP_LEVEL
       AND BUILD_TESTING
       AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/test/CMakeLists.txt")
        add_subdirectory(test)
    endif()
    if(PROJECT_IS_TOP_LEVEL AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/benchmark/CMakeLists.txt")
        add_subdirectory(benchmark EXCLUDE_FROM_ALL)
    endif()
endmacro()
