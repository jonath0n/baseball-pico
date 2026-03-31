"""WiFi connection, NTP time sync, and MLB Stats API fetching."""

import gc
import json
import time
import network
import ntptime


def wifi_connect(ssid, password, timeout_s=15):
    """Connect to WiFi. Returns True on success."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return True
    wlan.connect(ssid, password)
    start = time.time()
    while not wlan.isconnected():
        if time.time() - start > timeout_s:
            wlan.active(False)
            return False
        time.sleep(0.5)
    return True


def wifi_disconnect():
    """Disconnect WiFi and deactivate the interface to save power."""
    wlan = network.WLAN(network.STA_IF)
    try:
        wlan.disconnect()
    except Exception:
        pass
    wlan.active(False)


def sync_ntp():
    """Set RTC from NTP. Non-fatal on failure."""
    try:
        ntptime.settime()
    except Exception:
        pass


def get_local_date(utc_offset):
    """Get today's date string as YYYY-MM-DD, adjusted by UTC offset (hours)."""
    t = time.localtime(time.time() + utc_offset * 3600)
    return "{:04d}-{:02d}-{:02d}".format(t[0], t[1], t[2])


def get_local_time_str(utc_offset):
    """Get current local time as H:MM AM/PM string."""
    t = time.localtime(time.time() + utc_offset * 3600)
    hour = t[3]
    minute = t[4]
    ampm = "AM" if hour < 12 else "PM"
    hour = hour % 12
    if hour == 0:
        hour = 12
    return "{}:{:02d} {}".format(hour, minute, ampm)


def fetch_scores(date_str):
    """Fetch all MLB games for a given date.

    Returns a list of game dicts with keys:
        away_id, home_id, away_score, home_score,
        state ("Preview"/"Live"/"Final"),
        inning, is_top, outs, start_time
    Returns empty list on any error.
    """
    try:
        # Use urequests if available, otherwise raw socket
        try:
            import urequests
            url = "http://statsapi.mlb.com/api/v1/schedule?sportId=1&date={}&hydrate=linescore".format(date_str)
            resp = urequests.get(url)
            data = resp.json()
            resp.close()
        except ImportError:
            data = _fetch_raw(date_str)

        games = _parse_schedule(data)
        del data
        gc.collect()
        return games

    except Exception:
        gc.collect()
        return []


def _fetch_raw(date_str):
    """Fetch schedule JSON using raw sockets (fallback if urequests unavailable)."""
    import usocket
    host = "statsapi.mlb.com"
    path = "/api/v1/schedule?sportId=1&date={}&hydrate=linescore".format(date_str)

    addr = usocket.getaddrinfo(host, 80)[0][-1]
    sock = usocket.socket()
    sock.settimeout(10)
    sock.connect(addr)
    sock.send("GET {} HTTP/1.0\r\nHost: {}\r\n\r\n".format(path, host).encode())

    # Read full response
    chunks = []
    while True:
        chunk = sock.recv(2048)
        if not chunk:
            break
        chunks.append(chunk)
    sock.close()

    # Split headers from body
    raw = b"".join(chunks)
    del chunks
    idx = raw.find(b"\r\n\r\n")
    if idx < 0:
        return {}
    body = raw[idx + 4:]
    del raw
    return json.loads(body)


def _parse_schedule(data):
    """Extract minimal game info from the schedule API response."""
    games = []
    dates = data.get("dates", [])
    if not dates:
        return games

    for game in dates[0].get("games", []):
        teams = game.get("teams", {})
        away = teams.get("away", {})
        home = teams.get("home", {})
        status = game.get("status", {})
        linescore = game.get("linescore", {})

        # Parse start time from ISO gameDate (e.g. "2026-03-24T19:05:00Z")
        game_date = game.get("gameDate", "")
        start_time = ""
        if "T" in game_date:
            start_time = game_date.split("T")[1][:5]  # "19:05"

        games.append({
            "away_id": away.get("team", {}).get("id", 0),
            "home_id": home.get("team", {}).get("id", 0),
            "away_score": away.get("score", 0),
            "home_score": home.get("score", 0),
            "state": status.get("abstractGameState", "Preview"),
            "inning": linescore.get("currentInning", 0),
            "is_top": linescore.get("isTopInning", True),
            "outs": linescore.get("outs", 0),
            "start_time": start_time,
        })

    return games
