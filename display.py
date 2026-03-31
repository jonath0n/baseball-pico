"""Display layout rendering for the eInk scoreboard.

All functions draw onto a framebuf.FrameBuffer (250x122, MONO_HLSB).
Convention: 1 = black pixel, 0 = white pixel.
"""

import framebuf
from teams import abbr


def draw_text_scaled(fb, text, x, y, scale=1, color=1):
    """Draw text using the built-in 8x8 font, scaled up by an integer factor.

    For scale=1, uses framebuf.text() directly.
    For scale>1, renders to a tiny buffer then blits pixel-by-pixel.
    """
    if scale <= 1:
        fb.text(text, x, y, color)
        return

    char_w = 8
    char_h = 8
    text_w = len(text) * char_w
    # Render at 1x into a temporary buffer
    tmp_buf = bytearray((text_w + 7) // 8 * char_h)
    tmp = framebuf.FrameBuffer(tmp_buf, text_w, char_h, framebuf.MONO_HLSB)
    tmp.fill(0)
    tmp.text(text, 0, 0, 1)

    # Scale up
    for cy in range(char_h):
        for cx in range(text_w):
            if tmp.pixel(cx, cy):
                fb.fill_rect(x + cx * scale, y + cy * scale, scale, scale, color)


def text_width_scaled(text, scale=1):
    """Calculate pixel width of scaled text."""
    return len(text) * 8 * scale


def draw_inning_arrow(fb, x, y, is_top, size=6):
    """Draw a small triangle indicating top (up) or bottom (down) of inning."""
    if is_top:
        # Upward triangle
        for row in range(size):
            half = row
            fb.hline(x + size - 1 - half, y + size - 1 - row, half * 2 + 1, 1)
    else:
        # Downward triangle
        for row in range(size):
            half = row
            fb.hline(x + size - 1 - half, y + row, half * 2 + 1, 1)


def render_game(fb, game, game_num, total_games, width, height):
    """Render a single game detail view.

    Layout (250x122):
        Row 1: AWAY abbrev (3x) | away score (3x) | inning arrow + num | outs
        Divider line
        Row 2: HOME abbrev (3x) | home score (3x)
        Divider line
        Bottom: "Game N/T" (1x)  |  status (2x)
    """
    fb.fill(0)  # clear to white

    state = game["state"]

    # --- Row 1: Away team ---
    away = abbr(game["away_id"])
    draw_text_scaled(fb, away, 4, 6, scale=3, color=1)

    if state != "Preview":
        score = str(game.get("away_score", 0))
        # Right-align score in a zone around x=130
        sw = text_width_scaled(score, 3)
        draw_text_scaled(fb, score, 130 - sw // 2, 6, scale=3, color=1)

    # Inning and outs (only for live games)
    if state == "Live":
        inning = game.get("inning", 0)
        is_top = game.get("is_top", True)
        outs = game.get("outs", 0)

        # Inning arrow + number
        draw_inning_arrow(fb, 170, 8, is_top, size=7)
        draw_text_scaled(fb, str(inning), 180, 6, scale=3, color=1)

        # Outs indicator: filled/empty circles
        for i in range(3):
            cx = 220 + i * 10
            cy = 14
            if i < outs:
                fb.fill_rect(cx - 3, cy - 3, 7, 7, 1)
            else:
                fb.rect(cx - 3, cy - 3, 7, 7, 1)

    # --- Divider ---
    fb.hline(4, 38, width - 8, 1)

    # --- Row 2: Home team ---
    home = abbr(game["home_id"])
    draw_text_scaled(fb, home, 4, 46, scale=3, color=1)

    if state != "Preview":
        score = str(game.get("home_score", 0))
        sw = text_width_scaled(score, 3)
        draw_text_scaled(fb, score, 130 - sw // 2, 46, scale=3, color=1)

    # --- Divider ---
    fb.hline(4, 78, width - 8, 1)

    # --- Bottom bar ---
    # Game index
    idx_text = "Game {}/{}".format(game_num, total_games)
    fb.text(idx_text, 4, 88, 1)

    # Status
    if state == "Live":
        draw_text_scaled(fb, "LIVE", 194, 84, scale=2, color=1)
    elif state == "Final":
        inning = game.get("inning", 9)
        if inning and inning > 9:
            status = "F/{}".format(inning)
        else:
            status = "FINAL"
        sw = text_width_scaled(status, 2)
        draw_text_scaled(fb, status, width - 4 - sw, 84, scale=2, color=1)
    else:
        # Preview — show start time
        start = game.get("start_time", "")
        if start:
            draw_text_scaled(fb, start, 190, 84, scale=2, color=1)

    # Live indicator dot (blinking effect on refresh)
    if state == "Live":
        fb.fill_rect(182, 86, 8, 8, 1)


def render_no_games(fb, message, width, height):
    """Render a centered message screen (e.g., 'NO GAMES TODAY', 'WIFI FAILED')."""
    fb.fill(0)

    sw = text_width_scaled(message, 2)
    x = (width - sw) // 2
    y = (height - 16) // 2
    draw_text_scaled(fb, message, x, y, scale=2, color=1)
