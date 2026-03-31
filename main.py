"""MLB Live Score Tracker — Main Orchestrator.

Interaction model:
- Device is DORMANT by default (deep sleep, near-zero power).
- Button press on GP16 wakes the device.
- Fetches all MLB games, displays one at a time.
- Button cycles through games while awake.
- Auto-refreshes on a smart timer while games are live.
- Goes dormant once all games are Final or no games today.
"""

import gc
import json
import time
import machine

# Button pin — tactile button between GP16 and GND, internal pull-up
BUTTON_PIN = 16

# Display dimensions
WIDTH = 250
HEIGHT = 122


def load_config():
    """Load configuration from config.json."""
    with open("config.json") as f:
        return json.load(f)


def init_display():
    """Initialize the SPI bus and eInk display."""
    from ssd1680 import SSD1680

    spi = machine.SPI(0, baudrate=4_000_000, polarity=0, phase=0,
                      sck=machine.Pin(18), mosi=machine.Pin(19))
    epd = SSD1680(spi,
                  cs=machine.Pin(17, machine.Pin.OUT),
                  dc=machine.Pin(20, machine.Pin.OUT),
                  rst=machine.Pin(21, machine.Pin.OUT),
                  busy=machine.Pin(22, machine.Pin.IN))
    return epd


def fetch_all_scores(config):
    """Connect WiFi, sync time, fetch scores, disconnect. Returns (games, utc_offset)."""
    from mlb_api import wifi_connect, wifi_disconnect, sync_ntp, get_local_date, fetch_scores

    utc_offset = config.get("utc_offset", 0)

    if not wifi_connect(config["wifi_ssid"], config["wifi_pass"]):
        return None, utc_offset

    sync_ntp()
    date_str = get_local_date(utc_offset)
    games = fetch_scores(date_str)

    wifi_disconnect()
    gc.collect()

    return games, utc_offset


def compute_sleep_ms(games, utc_offset):
    """Determine how long to sleep based on game states.

    Returns milliseconds to sleep, or -1 for dormant (deep sleep indefinitely).
    """
    if not games:
        return -1  # No games — go dormant

    has_live = False
    has_preview = False
    earliest_start_epoch = None

    now = time.time() + utc_offset * 3600

    for game in games:
        state = game["state"]
        if state == "Live":
            has_live = True
        elif state == "Preview":
            has_preview = True
            # Try to compute time to first pitch from start_time (HH:MM UTC)
            st = game.get("start_time", "")
            if st and ":" in st:
                try:
                    parts = st.split(":")
                    h, m = int(parts[0]), int(parts[1])
                    # Build epoch for today's start time (UTC, then offset)
                    t = time.localtime(time.time())
                    start_epoch = time.mktime((t[0], t[1], t[2], h, m, 0, 0, 0))
                    # Adjust for UTC offset
                    start_local = start_epoch + utc_offset * 3600
                    if earliest_start_epoch is None or start_local < earliest_start_epoch:
                        earliest_start_epoch = start_local
                except Exception:
                    pass

    if has_live:
        return 5 * 60 * 1000  # 5 minutes

    if has_preview:
        # Sleep until 15 minutes before first pitch, capped at 30 min
        if earliest_start_epoch is not None:
            ms_to_start = int((earliest_start_epoch - now - 15 * 60) * 1000)
            if ms_to_start > 0:
                return min(ms_to_start, 30 * 60 * 1000)
        return 30 * 60 * 1000  # 30 minutes default

    # All games Final
    return -1  # Go dormant


def go_dormant(epd):
    """Put display and MCU into deep sleep. Only button press wakes."""
    epd.sleep()

    # Configure GP16 as wake source for deep sleep
    wake_pin = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

    # On RP2350, deepsleep with pin wake may need dormant mode.
    # Try deepsleep first; fall back to lightsleep if not supported.
    try:
        machine.deepsleep()
    except Exception:
        # Fallback: lightsleep indefinitely, woken by pin interrupt
        machine.lightsleep()


def run():
    """Main execution loop."""
    gc.collect()
    config = load_config()
    epd = init_display()
    button = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

    from display import render_game, render_no_games

    # Fetch scores
    games, utc_offset = fetch_all_scores(config)

    if games is None:
        # WiFi failed
        render_no_games(epd, "WIFI FAILED", WIDTH, HEIGHT)
        epd.show()
        go_dormant(epd)
        return

    if not games:
        render_no_games(epd, "NO GAMES", WIDTH, HEIGHT)
        epd.show()
        go_dormant(epd)
        return

    # Display first game
    current_index = 0
    render_game(epd, games[current_index], current_index + 1, len(games), WIDTH, HEIGHT)
    epd.show()

    # Main active loop
    while True:
        sleep_ms = compute_sleep_ms(games, utc_offset)

        if sleep_ms < 0:
            # All done — go dormant
            go_dormant(epd)
            return

        # Light sleep with button as interrupt source
        # Set up pin IRQ to wake from lightsleep
        button_pressed = False

        def on_button(pin):
            nonlocal button_pressed
            button_pressed = True

        button.irq(trigger=machine.Pin.IRQ_FALLING, handler=on_button)

        machine.lightsleep(sleep_ms)

        button.irq(handler=None)  # Disable IRQ

        if button_pressed:
            # Cycle to next game
            current_index = (current_index + 1) % len(games)
            epd.wake()
            render_game(epd, games[current_index], current_index + 1, len(games), WIDTH, HEIGHT)
            epd.show()
            # Don't re-fetch, just continue the loop
        else:
            # Timer expired — re-fetch scores
            epd.wake()
            games, utc_offset = fetch_all_scores(config)

            if games is None:
                render_no_games(epd, "WIFI FAILED", WIDTH, HEIGHT)
                epd.show()
                # Retry in 2 minutes
                machine.lightsleep(2 * 60 * 1000)
                epd.wake()
                continue

            if not games:
                render_no_games(epd, "NO GAMES", WIDTH, HEIGHT)
                epd.show()
                go_dormant(epd)
                return

            # Clamp index in case game count changed
            if current_index >= len(games):
                current_index = 0

            render_game(epd, games[current_index], current_index + 1, len(games), WIDTH, HEIGHT)
            epd.show()


# Entry point — MicroPython runs main.py on boot
run()
