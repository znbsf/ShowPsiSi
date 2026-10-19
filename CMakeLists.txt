cmake_minimum_required(VERSION 3.22)
project(ShowPsiSi VERSION 0.1.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
option(BUILD_QT_UI "Build Qt Quick prototype" ON)
option(SHOWPSISI_BUILD_CANCELLATION_TESTS "Build the test-only gated native engine" OFF)
option(SHOWPSISI_BUILD_UPDATER_TESTS "Build isolated Qt release/update contract tests" OFF)
find_package(Threads REQUIRED)
if(WIN32)
  set(_TSDUCK_DEFAULT "C:/Program Files/TSDuck")
else()
  set(_TSDUCK_DEFAULT "/usr")
endif()
set(TSDUCK_ROOT "${_TSDUCK_DEFAULT}" CACHE PATH "Installed TSDuck developer SDK")
# TSDuck 3.40+ separates the base TSCore API from the MPEG/DTV library.
# Search only the requested SDK so headers and libraries cannot silently mix.
# find_* skips searching when a variable is already cached, even with
# NO_DEFAULT_PATH. Treat TSDUCK_ROOT as the sole selector and redo these five
# bounded local lookups on every configure, including pre-migration caches.
# Data must follow the same root as headers/libraries when reusing a build tree.
foreach(_sdk_path IN ITEMS TSDUCK_INCLUDE TSCORE_INCLUDE TSDUCK_LIB TSCORE_LIB TSDUCK_DATA_DIR)
  unset(${_sdk_path} CACHE)
  unset(${_sdk_path})
endforeach()
find_path(TSDUCK_INCLUDE tsduck.h PATHS "${TSDUCK_ROOT}/include/tsduck" "${TSDUCK_ROOT}/include" NO_DEFAULT_PATH)
find_path(TSCORE_INCLUDE tscore.h PATHS "${TSDUCK_ROOT}/include/tscore" "${TSDUCK_ROOT}/include" NO_DEFAULT_PATH)
find_library(TSDUCK_LIB NAMES tsduck PATHS "${TSDUCK_ROOT}/lib/Release-Win64" "${TSDUCK_ROOT}/lib" "${TSDUCK_ROOT}/lib64" NO_DEFAULT_PATH)
find_library(TSCORE_LIB NAMES tscore PATHS "${TSDUCK_ROOT}/lib/Release-Win64" "${TSDUCK_ROOT}/lib" "${TSDUCK_ROOT}/lib64" NO_DEFAULT_PATH)
if(NOT TSDUCK_INCLUDE OR NOT TSCORE_INCLUDE OR NOT TSDUCK_LIB OR NOT TSCORE_LIB)
  message(FATAL_ERROR "TSDuck 3.45+ developer SDK (both TSDuck and TSCore) missing. Set TSDUCK_ROOT.")
endif()
# Native XML and names lookup is relative to the application executable,
# not the shared library. Ship the matching SDK data alongside each engine.
find_path(TSDUCK_DATA_DIR tsduck.tables.model.xml PATHS "${TSDUCK_ROOT}/share/tsduck" "${TSDUCK_ROOT}/bin" NO_DEFAULT_PATH)
if(NOT TSDUCK_DATA_DIR OR NOT EXISTS "${TSDUCK_DATA_DIR}/tsduck.dtv.names")
  message(FATAL_ERROR "Matching TSDuck XML/name runtime data missing. Set TSDUCK_ROOT to the complete SDK.")
endif()
file(GLOB TSDUCK_RUNTIME_DATA CONFIGURE_DEPENDS "${TSDUCK_DATA_DIR}/*.xml" "${TSDUCK_DATA_DIR}/*.names" "${TSDUCK_ROOT}/share/tscore/*.xml" "${TSDUCK_ROOT}/share/tscore/*.names")
# Both engines share one runtime directory. Stage it once per build graph,
# rather than racing two POST_BUILD copy commands under parallel MSBuild.
set(SHOWPSISI_RUNTIME_FILES ${TSDUCK_RUNTIME_DATA})
if(WIN32)
  list(APPEND SHOWPSISI_RUNTIME_FILES "${TSDUCK_ROOT}/bin/tsduck.dll" "${TSDUCK_ROOT}/bin/tscore.dll")
endif()
get_property(_SHOWPSISI_MULTI_CONFIG GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
set(_SHOWPSISI_RUNTIME_DIR "${CMAKE_RUNTIME_OUTPUT_DIRECTORY}")
if(_SHOWPSISI_MULTI_CONFIG)
  string(APPEND _SHOWPSISI_RUNTIME_DIR "/$<CONFIG>")
endif()
add_custom_target(showpsisi-runtime ALL
  COMMAND ${CMAKE_COMMAND} -E make_directory "${_SHOWPSISI_RUNTIME_DIR}"
  COMMAND ${CMAKE_COMMAND} -E copy_if_different ${SHOWPSISI_RUNTIME_FILES} "${_SHOWPSISI_RUNTIME_DIR}"
  VERBATIM)
function(configure_showpsisi_core target)
  target_include_directories(${target} PRIVATE "${TSDUCK_INCLUDE}" "${TSCORE_INCLUDE}" third_party)
  target_link_libraries(${target} PRIVATE "${TSDUCK_LIB}" "${TSCORE_LIB}" Threads::Threads)
  add_dependencies(${target} showpsisi-runtime)
  if(WIN32)
    target_compile_definitions(${target} PRIVATE _TSDUCKDLL_USE _TSCOREDLL_USE NOMINMAX)
  endif()
  if(MSVC)
    target_compile_options(${target} PRIVATE /utf-8 /W3)
  endif()
endfunction()
add_executable(showpsisi-core core/main.cpp)
configure_showpsisi_core(showpsisi-core)
if(SHOWPSISI_BUILD_CANCELLATION_TESTS)
  add_executable(showpsisi-core-test tests/cancellation_core.cpp)
  configure_showpsisi_core(showpsisi-core-test)
endif()
if(MSVC)
  add_compile_options(/utf-8 /W3)
  target_compile_options(showpsisi-core PRIVATE /utf-8 /W3)
endif()
if(BUILD_QT_UI)
  find_package(Qt6 6.5 REQUIRED COMPONENTS Quick QuickControls2 Network)
  qt_standard_project_setup(REQUIRES 6.5)
  qt_add_executable(showpsisi-qt ui/qt/main.cpp ui/qt/AgentDebug.h
    ui/qt/ReleaseMetadata.cpp ui/qt/ReleaseMetadata.h
    ui/qt/ReleaseUpdater.cpp ui/qt/ReleaseUpdater.h)
  target_compile_definitions(showpsisi-qt PRIVATE SHOWPSISI_VERSION="${PROJECT_VERSION}")
  qt_add_resources(showpsisi-qt "workbench_contract" PREFIX "/shared" BASE "ui/tauri/web" FILES ui/tauri/web/workbench.js)
  # PNG resources avoid introducing a runtime QtSvg/plugin dependency.
  qt_add_resources(showpsisi-qt "application_icons"
    PREFIX "/icons" BASE "assets/icons"
    FILES assets/icons/showpsisi-16.png assets/icons/showpsisi-24.png
          assets/icons/showpsisi-32.png assets/icons/showpsisi-48.png
          assets/icons/showpsisi-64.png assets/icons/showpsisi-128.png
          assets/icons/showpsisi-256.png)
  if(WIN32)
    enable_language(RC)
    target_sources(showpsisi-qt PRIVATE assets/icons/showpsisi.rc)
    target_include_directories(showpsisi-qt PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/assets/icons")
  elseif(UNIX AND NOT APPLE)
    # Desktop integration assets only; this is not a standalone Linux bundle.
    include(GNUInstallDirs)
    install(FILES assets/linux/org.showpsisi.ShowPsiSi.desktop
      DESTINATION "${CMAKE_INSTALL_DATADIR}/applications")
    install(FILES assets/icons/showpsisi.svg
      DESTINATION "${CMAKE_INSTALL_DATADIR}/icons/hicolor/scalable/apps"
      RENAME org.showpsisi.ShowPsiSi.svg)
    foreach(_icon_size IN ITEMS 16 24 32 48 64 128 256)
      install(FILES "assets/icons/showpsisi-${_icon_size}.png"
        DESTINATION "${CMAKE_INSTALL_DATADIR}/icons/hicolor/${_icon_size}x${_icon_size}/apps"
        RENAME org.showpsisi.ShowPsiSi.png)
    endforeach()
  endif()
  qt_add_qml_module(showpsisi-qt URI ShowPsiSi VERSION 1.0 QML_FILES ui/qt/Main.qml ui/qt/UpdateDialog.qml)
  target_link_libraries(showpsisi-qt PRIVATE Qt6::Quick Qt6::QuickControls2 Qt6::Network)
  set_target_properties(showpsisi-qt PROPERTIES WIN32_EXECUTABLE TRUE)
endif()

if(SHOWPSISI_BUILD_UPDATER_TESTS)
  enable_testing()
  add_subdirectory(tests/qt_updates)
endif()
