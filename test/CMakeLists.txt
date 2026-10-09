find_package(Python3 COMPONENTS Interpreter REQUIRED)
add_test(NAME dependency-resolution COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/ResolutionTest.py" "${CMAKE_COMMAND}" "${PROJECT_SOURCE_DIR}")
