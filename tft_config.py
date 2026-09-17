"""Known-good ST7789 configuration for the 1.9" TFT used in this project.

This matches the proven wiring in the working example: SPI1, pins 8/10 for
SCL/SDA, reset on GPIO6, DC on GPIO3, and a 170x320 TFT panel.
"""

from machine import Pin, SPI
import st7789py as st7789

TFA = 40
BFA = 40
WIDE = 1
TALL = 0
SCROLL = 0      # orientation for scroll.py
FEATHERS = 1    # orientation for feathers.py


def config(rotation=1):
    """
    Configures and returns an instance of the ST7789 display driver.

    Args:
        rotation (int): The rotation of the display (default: 1).

    Returns:
        ST7789: An instance of the ST7789 display driver.
    """
    backlight = Pin(7, Pin.OUT)
    backlight.value(1)

    return st7789.ST7789(
        SPI(1, baudrate=40000000, sck=Pin(8), mosi=Pin(10), miso=None),
        170,
        320,
        reset=Pin(6, Pin.OUT),
        dc=Pin(3, Pin.OUT),
        rotation=rotation,
    )