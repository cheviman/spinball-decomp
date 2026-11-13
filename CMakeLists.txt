# Name:        CMakeLists.txt
# Description: build of Sonic the Hedgehog Spinball's runtime and its development tools
# Version:     0.1.0
# Created:     13-11-2026
# Modified:    13-11-2026
# Author:      Sebastian Toyos
cmake_minimum_required(VERSION 3.20)
project(spinball C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Every executable lands in build/bin (SPINBALL_BIN_DIR), whatever the generator or configuration
set(SPINBALL_BIN_DIR ${CMAKE_SOURCE_DIR}/build/bin CACHE PATH "Where the executables go")
foreach(config IN ITEMS "" _DEBUG _RELEASE _RELWITHDEBINFO _MINSIZEREL)
	set(CMAKE_RUNTIME_OUTPUT_DIRECTORY${config} ${SPINBALL_BIN_DIR})
endforeach()

if(MSVC)
	add_compile_options(/W3 /utf-8)
	add_compile_definitions(_CRT_SECURE_NO_WARNINGS)
endif()

# The shared kits: arcade-decomp (tools/core: the decompiler, the CPUs' frontends, MAME's cores) and
# console-decomp (tools/console: the consoles; this game's is megadrive/)
set(MD_ARCADE_CORE ${CMAKE_SOURCE_DIR}/tools/core)
set(MD_CONSOLE ${CMAKE_SOURCE_DIR}/tools/console/megadrive)
include(${MD_CONSOLE}/runtime/runtime.cmake)

# The reader of the player's cartridge: for the tools that run the original code, never for the game
add_library(spinball_rom_set STATIC runtime/src/rom_set.c)
target_include_directories(spinball_rom_set PUBLIC runtime/include)
target_link_libraries(spinball_rom_set PUBLIC md_cartridge)

find_package(Python3 COMPONENTS Interpreter)

# The reference tools: the original program on MAME's cores (tools/console/megadrive/reference)
option(SPINBALL_REFERENCE_TOOLS "Build the MAME-based reference tools" ON)
if(SPINBALL_REFERENCE_TOOLS)
	if(NOT Python3_FOUND)
		message(FATAL_ERROR "The reference tools need Python 3 (MAME's 68000 and Z80 cores are written by Python scripts)")
	endif()
	set(MD_GAME_DATA spinball_rom_set)
	include(${MD_CONSOLE}/reference/reference.cmake)
endif()
