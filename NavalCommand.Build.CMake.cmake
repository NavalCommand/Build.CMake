cmake_minimum_required(VERSION 4.2)
cmake_policy(SET CMP0168 NEW)
include_guard(GLOBAL)
include(FetchContent)
set(CMAKE_FIND_PACKAGE_TARGETS_GLOBAL TRUE)

function(NavalCommandDependencyIdentity url identity fetchName)
    string(REGEX REPLACE "\\.git/?$" "" canonicalUrl "${url}")
    if(NOT canonicalUrl MATCHES "^https://github.com/([^/]+)/([^/]+)$")
        message(FATAL_ERROR "Expected a canonical GitHub repository URL: ${url}")
    endif()
    string(TOLOWER "${CMAKE_MATCH_1}.${CMAKE_MATCH_2}" canonicalIdentity)
    string(SHA256 identityHash "${canonicalIdentity}")
    # Names remain derived from full canonical repository identity, never caller aliases. Short names apply
    # on every platform for consistent local checkout registrations.
    string(SUBSTRING "${identityHash}" 0 12 shortHash)
    set(${identity}
        "${canonicalIdentity}"
        PARENT_SCOPE)
    set(${fetchName}
        "nc_${shortHash}"
        PARENT_SCOPE)
endfunction()

function(NavalCommandSetDependencyPath url path)
    NavalCommandDependencyIdentity("${url}" canonicalIdentity fetchName)
    get_filename_component(absoluteCheckoutPath "${path}" ABSOLUTE BASE_DIR "${CMAKE_SOURCE_DIR}")
    if(NOT IS_DIRECTORY "${absoluteCheckoutPath}" OR NOT EXISTS
                                                     "${absoluteCheckoutPath}/CMakeLists.txt")
        message(
            FATAL_ERROR
                "Invalid explicit dependency path for ${canonicalIdentity}: ${absoluteCheckoutPath}"
        )
    endif()
    file(REAL_PATH "${absoluteCheckoutPath}" absoluteCheckoutPath)
    get_property(previousLocalPath GLOBAL PROPERTY "${fetchName}_local")
    if(previousLocalPath AND NOT previousLocalPath STREQUAL absoluteCheckoutPath)
        message(FATAL_ERROR "Conflicting local dependency registrations for ${canonicalIdentity}")
    endif()
    get_property(alreadyResolved GLOBAL PROPERTY "${fetchName}_resolved")
    if(alreadyResolved AND NOT previousLocalPath STREQUAL absoluteCheckoutPath)
        message(
            FATAL_ERROR "Local override for ${canonicalIdentity} must precede FetchContent_Declare")
    endif()
    set_property(GLOBAL PROPERTY "${fetchName}_local" "${absoluteCheckoutPath}")
endfunction()

function(NavalCommandAddDependency url tag)
    NavalCommandDependencyIdentity("${url}" canonicalIdentity fetchName)
    get_property(previousIdentity GLOBAL PROPERTY "${fetchName}_identity")
    if(previousIdentity AND NOT previousIdentity STREQUAL canonicalIdentity)
        message(FATAL_ERROR "Hashed dependency identity collision: ${canonicalIdentity}")
    endif()
    get_property(previousGitRef GLOBAL PROPERTY "${fetchName}_tag")
    if(previousGitRef AND NOT previousGitRef STREQUAL tag)
        message(
            FATAL_ERROR
                "Conflicting Git references for ${canonicalIdentity}: ${previousGitRef} versus ${tag}"
        )
    endif()
    get_property(alreadyResolved GLOBAL PROPERTY "${fetchName}_resolved")
    if(alreadyResolved)
        return()
    endif()
    set_property(GLOBAL PROPERTY "${fetchName}_identity" "${canonicalIdentity}")
    set_property(GLOBAL PROPERTY "${fetchName}_tag" "${tag}")
    get_property(localCheckoutPath GLOBAL PROPERTY "${fetchName}_local")
    if(localCheckoutPath)
        FetchContent_Declare(${fetchName} SOURCE_DIR "${localCheckoutPath}")
        message(
            STATUS
                "NavalCommand dependency ${canonicalIdentity} -> ${fetchName} local ${localCheckoutPath}"
        )
    else()
        FetchContent_Declare(
            ${fetchName}
            GIT_REPOSITORY "${url}"
            GIT_TAG "${tag}")
        message(STATUS "NavalCommand dependency ${canonicalIdentity} -> ${fetchName} Git ${tag}")
    endif()
    # Set before descent: repeated/cyclic requests never re-declare an identity.
    set_property(GLOBAL PROPERTY "${fetchName}_resolved" TRUE)
    FetchContent_MakeAvailable(${fetchName})
    set_property(GLOBAL PROPERTY "${fetchName}_source" "${${fetchName}_SOURCE_DIR}")
    file(APPEND "${CMAKE_BINARY_DIR}/dependency-resolution.log"
         "${canonicalIdentity}|${tag}|${${fetchName}_SOURCE_DIR}\n")
endfunction()

function(NavalCommandGetDependencySource url output)
    NavalCommandDependencyIdentity("${url}" canonicalIdentity fetchName)
    get_property(dependencySource GLOBAL PROPERTY "${fetchName}_source")
    if(NOT dependencySource)
        message(FATAL_ERROR "Dependency has not been resolved: ${canonicalIdentity}")
    endif()
    set(${output}
        "${dependencySource}"
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
    get_target_property(targetType ${target} TYPE)
    if(targetType STREQUAL "INTERFACE_LIBRARY")
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
