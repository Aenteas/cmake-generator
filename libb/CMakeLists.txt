cmake_minimum_required (VERSION 3.22.0)

project(downstream)

include(GNUInstallDirs)

add_executable(main apps/main.cpp)

find_package(liba CONFIG REQUIRED)

message("${CMAKE_INSTALL_PREFIX}/lib")
message("install prefix for liba: ${liba_DIR}")

# link liba libraries

target_link_libraries(main liba.A.AA.AAA.aaa)

if (TARGET B_BA_Targets)
    message("B_BA")
    target_link_libraries(main liba.B.BA.ba)
endif()