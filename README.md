# Baseball Pico — MLB Live Score Tracker

A battery-powered MLB scoreboard that fits in your hand. Press a button to see every live game, cycle through them, and let it auto-refresh while games are in progress. When the last game ends, it goes to sleep until you press the button again.

## Parts List

| Part | Notes |
|------|-------|
| [Raspberry Pi Pico 2W with Headers](https://www.adafruit.com/product/6315) | RP2350, pre-soldered headers |
| [Adafruit 2.13" Monochrome eInk Display](https://www.adafruit.com/product/4197) | 250x122, SSD1680, with SRAM |
| [Pimoroni Pico LiPo SHIM](https://www.adafruit.com/product/5612) | Sandwiches under the Pico |
| [3.7V 1200mAh LiPo Battery](https://www.adafruit.com/product/258) | JST connector |
| Tactile push button (6mm) | [20-pack from Adafruit](https://www.adafruit.com/product/1119) or any momentary switch |
| Breadboard jumper wires | Female-to-female recommended for display header |

## Assembly

### Step 1: Stack the LiPo SHIM

The Pimoroni LiPo SHIM sandwiches between the Pico 2W and whatever it's mounted on. Align the SHIM's castellated pads with the Pico's header pins and press it onto the underside of the Pico. The USB-C port on the SHIM should face the same direction as the Pico's micro-USB port. The JST battery connector will stick out one side.

### Step 2: Wire the eInk Display

Connect the Pico 2W to the eInk display's header using jumper wires:

```
Pico 2W          eInk Display
────────          ────────────
3V3 (pin 36) ──→ VIN
GND (pin 38) ──→ GND
GP18         ──→ SCK
GP19         ──→ MOSI
GP17         ──→ CS
GP20         ──→ DC
GP21         ──→ RST
GP22         ──→ BUSY
```

Leave the display's other pins (MISO, SRAM CS) unconnected — they're not needed.

### Step 3: Wire the Button

Connect a tactile push button between **GP16** and **GND**. That's it — two wires, no resistor needed (the Pico uses an internal pull-up).

If you're using a breadboard, just plug the button across the center gap and run wires from each leg to GP16 and any GND pin.

### Step 4: Connect the Battery

Plug the LiPo battery's JST connector into the Pimoroni LiPo SHIM. The SHIM handles charging (via USB-C) and power management automatically.

## Installing the Firmware

### Step 1: Flash MicroPython

1. Download the **RP2350W** MicroPython firmware (`.uf2` file) from [micropython.org/download/RPI_PICO2_W](https://micropython.org/download/RPI_PICO2_W/).
   - Make sure it says RP2350 / Pico 2W — not the RP2040 version.
2. Hold the **BOOTSEL** button on the Pico 2W and plug it into your computer via USB.
3. It will appear as a USB drive called `RPI-RP2`. Drag the `.uf2` file onto it.
4. The Pico will reboot automatically. The USB drive will disappear — that's normal.

### Step 2: Upload the Code

Use [Thonny](https://thonny.org/) (easiest) or `mpremote` (command line).

**Option A: Thonny**

1. Open Thonny and select **Run → Configure interpreter → MicroPython (Raspberry Pi Pico)**.
2. You should see the MicroPython REPL at the bottom.
3. For each file (`config.json`, `teams.py`, `ssd1680.py`, `mlb_api.py`, `display.py`, `main.py`):
   - Open the file in Thonny.
   - **File → Save as → Raspberry Pi Pico** and save with the same filename.

**Option B: mpremote**

```bash
pip install mpremote
mpremote cp config.json teams.py ssd1680.py mlb_api.py display.py main.py :
```

### Step 3: Configure WiFi

Before uploading (or after, by editing on-device), open `config.json` and fill in your WiFi credentials:

```json
{
    "wifi_ssid": "MyNetwork",
    "wifi_pass": "MyPassword",
    "utc_offset": -5
}
```

Set `utc_offset` to your timezone's offset from UTC:
- Eastern: `-5` (or `-4` during daylight saving)
- Central: `-6` (or `-5`)
- Mountain: `-7` (or `-6`)
- Pacific: `-8` (or `-7`)

## Usage

### Wake Up

Press the **button**. The device will:
1. Connect to WiFi (~3-5 seconds)
2. Fetch today's MLB scores
3. Display the first game on the eInk screen

### Cycle Through Games

Press the **button** again to see the next game. It wraps around after the last game.

The bottom of the screen shows `Game 3/15` so you know where you are in the list.

### Auto-Refresh

You don't need to do anything — the device handles this automatically:

- **Live games**: Refreshes every **5 minutes**
- **Games haven't started yet**: Checks every **30 minutes** (or wakes up closer to first pitch)
- **All games finished**: Goes dormant automatically
- **No games today**: Shows "NO GAMES" and goes dormant

### Go Back to Sleep

You don't need to turn it off. Once every game for the day is final, the device goes dormant on its own. The eInk screen keeps showing the last score even with no power — that's how eInk works.

To wake it up the next day (or whenever), just press the button again.

### Charging

Plug a USB-C cable into the Pimoroni LiPo SHIM. It charges the battery while the device continues to work normally. You can leave it plugged in indefinitely.

## Display Layout

```
 NYY        5       ▲ 7     ■ ■ □
 ─────────────────────────────────
 BOS        3
 ─────────────────────────────────
 Game 3/15                   LIVE
```

- **Top row**: Away team, score, inning (▲ = top, ▼ = bottom), outs (■ = out recorded)
- **Bottom row**: Home team, score
- **Status bar**: Game position in today's schedule + status (LIVE / FINAL / start time)

For games that haven't started, scores are hidden and the start time is shown instead.

## Troubleshooting

**Screen shows "WIFI FAILED"**: Check your SSID and password in `config.json`. Make sure your router is within range. The device will go to sleep — press the button to try again.

**Screen shows "NO GAMES"**: There are no MLB games scheduled today (off-day, All-Star break, or off-season). Press the button on a game day.

**Display looks inverted or mirrored**: The SSD1680 init sequence may need adjustment for your exact display revision. In `ssd1680.py`, try changing the data entry mode byte in `_init_display()` from `0x03` to `0x00`, `0x01`, or `0x02` to fix orientation.

**Display shows garbled pixels**: Double-check your SPI wiring, especially SCK/MOSI order. Also confirm the SPI baudrate — try lowering it from `4_000_000` to `1_000_000` in `main.py`.

**Device doesn't wake from button press**: Verify the button is wired between GP16 and GND. Test in Thonny's REPL:
```python
from machine import Pin
btn = Pin(16, Pin.IN, Pin.PULL_UP)
print(btn.value())  # Should print 1, then 0 when pressed
```

**Scores seem wrong or stale**: The device fetches from the MLB Stats API which updates in near-real-time. If scores look stale, check that `utc_offset` in `config.json` is correct — a wrong offset means it might be fetching yesterday's or tomorrow's games.
