/**
 *    Name:        frame.c
 *    Description: where Sonic Spinball waits for its next frame (md/frames.h), for the console's frame timing:
 *                 the translated and the decompiled program, and mdref --timing frames
 *    Version:     0.1.0
 *    Created:     20-11-2026
 *    Modified:    20-11-2026
 *    Author:      Sebastian Toyos
 *
 *    license:BSD-3-Clause
 *    The program waits in loops that only read and test, until an interrupt changes what they read (the rule and
 *    the list: tools/frame_waits.py, which checks this list and tools/game_profile.py's FRAME_WAIT against the
 *    listing). Each is named by its branch back: when the program takes it, it has nothing to do until the next
 *    frame. They wait for the VBLANK's count of the frames at FF0000 (the main loop's 0D54C2, the demo's 0D47B6,
 *    0D3E0C, and 0D3E20, which no scenario runs), for the front end's VBLANK to clear FFF2C9 (0F38CE), for the
 *    VBLANK to serve the requests at FF559E (0D41DA, 0D4328, 0D84D6, 0FF59C, 0FF7DA, 0FF808) and the palette's
 *    command at FF0058 (0D86C4, 0D86E2, 0D86FE, 0D871A, 0D8736), for the Z80's bus (0F5FBC, 0F600E, 0F60B6), and
 *    at the boot (00024C).
 *
 *    And one loop that does work: the state machine 0D48E2 runs between the balls goes round (0D4EE0 "bra
 *    $d4932") while its state, at FF55A0, is 3, 6 or 9, whose handlers wait for the timer at FFF1FA, which the
 *    VBLANK counts down (0D3D66), to run out ("tst.w $fff1fa.l", "bgt $d4ed0"); states from 10 on leave (0D4ED8).
 *    Each round clears the same flags (0DE996): nothing changes until the timer does.
 */
#include "md/frames.h"
#include "md/machine.h"

#define ROUND_STATE     0xFF55A0u    /* the state of 0D48E2's machine */
#define TIMER           0xFFF1FAu    /* the timer the VBLANK counts down */

const uint32_t md_game_frame_waits[] =
{
	0x00024Cu, 0x0D3E0Cu, 0x0D3E20u, 0x0D41DAu, 0x0D4328u, 0x0D47B6u, 0x0D54C2u, 0x0D84D6u, 0x0D86C4u, 0x0D86E2u,
	0x0D86FEu, 0x0D871Au, 0x0D8736u, 0x0F38CEu, 0x0F5FBCu, 0x0F600Eu, 0x0F60B6u, 0x0FF59Cu, 0x0FF7DAu, 0x0FF808u,
	0x0D4EE0u,
};
const unsigned md_game_frame_wait_count = sizeof(md_game_frame_waits) / sizeof(md_game_frame_waits[0]);

int md_game_frame_idle(uint32_t pc)
{
	if (pc == 0x0D4EE0u)
	{
		const uint16_t state = md_peek16(ROUND_STATE);

		return (state == 3 || state == 6 || state == 9) && (int16_t)md_peek16(TIMER) > 0;
	}
	return 1;
}
