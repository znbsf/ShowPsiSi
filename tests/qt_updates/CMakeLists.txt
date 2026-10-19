cmake_minimum_required(VERSION 3.22)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  project(ShowPsiSiUpdaterTests VERSION 0.1.0 LANGUAGES CXX)
  enable_testing()
endif()
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(Qt6 6.5 REQUIRED COMPONENTS Core Gui Network Test)
set(CMAKE_AUTOMOC ON)
add_executable(showpsisi-updater-tests
  test_updates.cpp
  ../../ui/qt/ReleaseMetadata.cpp ../../ui/qt/ReleaseMetadata.h
  ../../ui/qt/ReleaseUpdater.cpp ../../ui/qt/ReleaseUpdater.h)
target_include_directories(showpsisi-updater-tests PRIVATE ../../ui/qt)
# Keep the fixture baseline fixed when the production project version advances.
# The production Qt target still embeds the real CMake project version.
target_compile_definitions(showpsisi-updater-tests PRIVATE SHOWPSISI_VERSION="0.1.0")
target_link_libraries(showpsisi-updater-tests PRIVATE Qt6::Core Qt6::Gui Qt6::Network Qt6::Test)
if(MSVC)
  target_compile_options(showpsisi-updater-tests PRIVATE /utf-8 /W3)
endif()
add_test(NAME updater-contract COMMAND showpsisi-updater-tests)
set_tests_properties(updater-contract PROPERTIES TIMEOUT 90)
