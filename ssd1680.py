"""Minimal SSD1680 eInk display driver for MicroPython.

Drives the Adafruit 2.13" Monochrome eInk (250x122, PID 4197).
Extends framebuf.FrameBuffer so callers can use standard drawing methods
(text, fill_rect, hline, pixel, etc.) then call show() to refresh.
"""

import framebuf
import time
from machine import Pin, SPI


# SSD1680 commands
_SW_RESET = 0x12
_DRIVER_OUTPUT = 0x01
_DATA_ENTRY_MODE = 0x11
_RAM_X_RANGE = 0x44
_RAM_Y_RANGE = 0x45
_RAM_X_COUNT = 0x4E
_RAM_Y_COUNT = 0x4F
_WRITE_RAM_BW = 0x24
_BORDER_WAVEFORM = 0x3C
_TEMP_SENSOR = 0x18
_DISP_UPDATE_CTRL2 = 0x22
_MASTER_ACTIVATE = 0x20
_DEEP_SLEEP = 0x10

# Display update sequence: load temp, load LUT, display
_UPDATE_SEQUENCE = 0xF7


class SSD1680(framebuf.FrameBuffer):
    """Framebuffer-based driver for SSD1680 eInk display (250x122)."""

    def __init__(self, spi, cs, dc, rst, busy, width=250, height=122):
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self.busy = busy
        self.width = width
        self.height = height

        # Byte width for horizontal layout
        self._bw = (width + 7) // 8  # 32 bytes per row

        # Allocate framebuffer: 1 bit per pixel, horizontal bytes MSB first
        self._buf = bytearray(self._bw * height)
        super().__init__(self._buf, width, height, framebuf.MONO_HLSB)

        # Small chunk buffer for bit-inverted SPI writes
        self._chunk = bytearray(64)

        # Init pins
        self.cs.value(1)
        self.dc.value(0)

        # Init display
        self._hw_reset()
        self._init_display()

    def _hw_reset(self):
        """Hardware reset via RST pin."""
        self.rst.value(1)
        time.sleep_ms(10)
        self.rst.value(0)
        time.sleep_ms(10)
        self.rst.value(1)
        time.sleep_ms(10)
        self._wait_busy()

    def _wait_busy(self, timeout_ms=5000):
        """Wait for BUSY pin to go LOW (display ready)."""
        start = time.ticks_ms()
        while self.busy.value() == 1:
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                return
            time.sleep_ms(10)

    def _cmd(self, cmd, data=None):
        """Send a command byte, optionally followed by data bytes."""
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(bytes([cmd]))
        if data is not None:
            self.dc.value(1)
            self.spi.write(bytes(data))
        self.cs.value(1)

    def _init_display(self):
        """SSD1680 initialization sequence for 250x122 display."""
        # Software reset
        self._cmd(_SW_RESET)
        self._wait_busy()

        # Driver output control: MUX = height - 1 = 121 = 0x79
        self._cmd(_DRIVER_OUTPUT, [0x79, 0x00, 0x00])

        # Data entry mode: X increment, Y increment
        self._cmd(_DATA_ENTRY_MODE, [0x03])

        # RAM X address range: 0 to (byte_width - 1)
        self._cmd(_RAM_X_RANGE, [0x00, self._bw - 1])

        # RAM Y address range: 0 to (height - 1)
        self._cmd(_RAM_Y_RANGE, [0x00, 0x00, self.height - 1, 0x00])

        # Border waveform control
        self._cmd(_BORDER_WAVEFORM, [0x05])

        # Use internal temperature sensor
        self._cmd(_TEMP_SENSOR, [0x80])

        # Set RAM counters to origin
        self._set_ram_pointer(0, 0)

    def _set_ram_pointer(self, x, y):
        """Set the RAM address pointer."""
        self._cmd(_RAM_X_COUNT, [x])
        self._cmd(_RAM_Y_COUNT, [y & 0xFF, (y >> 8) & 0xFF])

    def show(self):
        """Write framebuffer to display RAM and trigger a full refresh."""
        self._set_ram_pointer(0, 0)

        # Begin writing to black/white RAM
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(bytes([_WRITE_RAM_BW]))
        self.dc.value(1)

        # Send framebuffer data in chunks, bit-inverted
        # (SSD1680: 0=black, 1=white; framebuf: 1=set=black, 0=clear=white)
        buf = self._buf
        chunk = self._chunk
        chunk_size = len(chunk)
        total = len(buf)
        offset = 0

        while offset < total:
            n = min(chunk_size, total - offset)
            for i in range(n):
                chunk[i] = buf[offset + i] ^ 0xFF
            self.spi.write(memoryview(chunk)[:n])
            offset += n

        self.cs.value(1)

        # Trigger display update
        self._cmd(_DISP_UPDATE_CTRL2, [_UPDATE_SEQUENCE])
        self._cmd(_MASTER_ACTIVATE)
        self._wait_busy(timeout_ms=10000)

    def sleep(self):
        """Put the SSD1680 into deep sleep mode.

        The display retains its image. Call _hw_reset() + _init_display()
        to wake it back up.
        """
        self._cmd(_DEEP_SLEEP, [0x01])

    def wake(self):
        """Wake the display from deep sleep and re-initialize."""
        self._hw_reset()
        self._init_display()
