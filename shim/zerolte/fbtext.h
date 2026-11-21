/* SPDX-License-Identifier: GPL-2.0-only */
#pragma once
#include <stdint.h>

/* S-Boot scanout buffer (uniLoader board-zeroflte.c; the S6 edge uses the
 * same 1440x2560 buffer as the flat S6). */
#define ZERO_FB_BASE 0xe2a00000UL
#define ZERO_FB_WIDTH 1440U
#define ZERO_FB_HEIGHT 2560U

/* Let CPU writes reach the panel (DECON_F HW trigger), returns old value. */
uint32_t zero_fb_enable(void);
void zero_fb_text(unsigned row, const char *s);
void zero_fb_hex(unsigned row, const char *label, uint64_t value);
