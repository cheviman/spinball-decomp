/**
 *    Name:        data.h
 *    Description: the cartridge's program as the board has it, for the tools that run the original code
 *    Version:     0.1.0
 *    Created:     13-11-2026
 *    Modified:    13-11-2026
 *    Author:      Sebastian Toyos
 *
 *    license:BSD-3-Clause
 *    The reference (tools/core/megadrive/reference) runs the original code, so it fills this from the
 *    player's ROM when it starts (game/extract.h). The game itself never opens the ROM.
 */
#ifndef GAME_DATA_H
#define GAME_DATA_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GAME_PROGRAM_SIZE   0x100000     /* the cartridge: 8 Mbit, the 68000's program and its data */

extern uint8_t game_program[GAME_PROGRAM_SIZE];

#ifdef __cplusplus
}
#endif

#endif
