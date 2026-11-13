/**
 *    Name:        rom_set.c
 *    Description: Sonic the Hedgehog Spinball's cartridge into the board's memory (game/data.h)
 *    Version:     0.1.0
 *    Created:     13-11-2026
 *    Modified:    13-11-2026
 *    Author:      Sebastian Toyos
 *
 *    license:BSD-3-Clause
 *    The USA cartridge (GM MK-1537 -00), known by its CRC32 and size through the console's reader
 *    (tools/console/megadrive/runtime: md/cartridge.h). Only the tools that run the original code read it.
 */
#include "game/extract.h"

#include "game/data.h"
#include "md/cartridge.h"

#define CARTRIDGE_CRC       0x677206CBu    /* Sonic the Hedgehog Spinball (USA) */

uint8_t game_program[GAME_PROGRAM_SIZE];

const char *game_rom_set_load(const char *source)
{
	if (md_cartridge_load(source, CARTRIDGE_CRC, GAME_PROGRAM_SIZE, game_program))
		return 0;
	return "the cartridge (Sonic the Hedgehog Spinball, USA: 1 MiB, CRC32 677206CB) is not there";
}
