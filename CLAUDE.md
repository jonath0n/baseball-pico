# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Battery-powered MLB live score tracker built with MicroPython on a Raspberry Pi Pico 2W (RP2350). The device is **dormant by default** — a button press wakes it, it fetches all live MLB scores and displays one game at a time. The button cycles through games. Auto-refreshes while games are live, then returns to dormancy.

## Hardware

- **MCU**: Raspberry Pi Pico 2W (RP2350, 520KB RAM, WiFi)
- **Display**: Adafruit 2.13" Monochrome eInk, SSD1680 driver, 250x122px (PID 4197)
- **Power**: Pimoroni Pico LiPo SHIM + 3.7V 1200mAh LiPo
- **Button**: Tactile button on GP16 → GND (internal pull-up, wakes from deep sleep)

### Pin Assignments

| Pin  | Function       |
|------|----------------|
| GP16 | Button (pull-up, active low) |
| GP17 | eInk CS        |
| GP18 | SPI0 SCK       |
| GP19 | SPI0 MOSI      |
| GP20 | eInk DC        |
| GP21 | eInk RST       |
| GP22 | eInk BUSY      |

## Architecture

```
main.py      — Orchestrator: button wake → fetch → render → smart sleep loop
ssd1680.py   — eInk driver (extends framebuf.FrameBuffer, standalone, no dependencies)
mlb_api.py   — WiFi connect/disconnect, NTP sync, MLB Stats API fetch + parse
display.py   — Layout rendering with scaled built-in font (8x8 × scale factor)
teams.py     — Team ID → abbreviation lookup (30 MLB teams)
config.json  — WiFi credentials and UTC offset
```

### Interaction Flow

1. **Dormant**: `machine.deepsleep()`, near-zero draw, button on GP16 is the only wake source
2. **Wake**: Fetch all games → show game 1 on eInk
3. **Button press**: Cycle to next game (no network, just re-render)
4. **Smart sleep**: `machine.lightsleep()` (preserves RAM, button can interrupt)
   - Live games → 5 min refresh
   - Pre-game → 30 min or until near first pitch
   - All Final / no games → go dormant
5. **Timer wake**: Re-fetch scores from API, update display

### Key Design Decisions

- `lightsleep` for active polling (preserves state, button-interruptible), `deepsleep` only for dormancy
- SSD1680 driver is standalone (no nano-gui dependency), ~4.5KB total RAM
- Font rendering uses built-in 8×8 framebuf font scaled up via pixel doubling/tripling
- Full eInk refresh only (no partial update) to avoid ghosting
- WiFi disconnected immediately after data fetch to save power

## Language & Runtime

MicroPython targeting RP2350. Use RP2350-specific firmware (not RP2040).

## Data Source

MLB Stats API (`statsapi.mlb.com`) — no API key required.
- Schedule endpoint: `/api/v1/schedule?sportId=1&date=YYYY-MM-DD&hydrate=linescore`
- Team abbreviations are hardcoded in `teams.py` (not in API schedule response)

## Key Constraints

- **Memory**: 520KB RAM — parse only needed JSON fields, `gc.collect()` after discarding parsed JSON
- **SPI**: Use standard `machine.SPI` (not PIO-based) for RP2350 compatibility
- **eInk**: Display retains image during sleep/power-off; full refresh takes ~3 seconds
