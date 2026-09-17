# main.py
from machine import Pin, SPI, UART # type: ignore
import time
import st7789py as st7789
import vga1_16x32 as largefont
import vga1_8x16 as smallfont



try:
    from machine import WDT # type: ignore
    wdt_available = True
except ImportError:
    wdt_available = False

# Match the known-good TFT configuration from tft_config.py
BL_PIN = 32
DC_PIN = 2
RST_PIN = 4
SCL_PIN = 18
SDA_PIN = 23
CS_PIN = 15

# GPS UART pins
GPS_TX = 17
GPS_RX = 16

wdt = None


def safe_display_text(display, text, x, y, color, font=None):
    if display is None:
        return
    try:
        # Match the working example: pass a font object and a background color.
        if font is None:
            font = largefont
        display.text(font, text, x, y, color, st7789.BLACK)
    except Exception as exc:
        print("Display text failed:", exc)


def safe_display_fill(display, x, y, w, h, color):
    if display is None:
        return
    try:
        display.fill_rect(x, y, w, h, color)
    except Exception as exc:
        print("Display fill failed:", exc)


def init_display():
    backlight = Pin(BL_PIN, Pin.OUT)
    backlight.value(1)

    spi = SPI(2, baudrate=40000000, sck=Pin(SCL_PIN), mosi=Pin(SDA_PIN), miso=None)

    display = st7789.ST7789(
        spi,
        240,
        320,
        reset=Pin(RST_PIN, Pin.OUT),
        cs=Pin(CS_PIN, Pin.OUT),
        dc=Pin(DC_PIN, Pin.OUT),
        backlight=backlight,
        rotation=1,
    )

    display.fill(st7789.BLACK)
    display.text(largefont, "BN-880 GPS", 10, 10, st7789.WHITE, st7789.BLACK)
    display.text(smallfont, "Booting...", 10, 40, st7789.YELLOW, st7789.BLACK)
    return display


def init_gps_uart():
    return UART(2, baudrate=9600, tx=GPS_TX, rx=GPS_RX, timeout=100)


def parse_gga(nmea_sentence):
    parts = nmea_sentence.split(',')
    if len(parts) > 10 and (parts[0].startswith('$GPGGA') or parts[0].startswith('$GNGGA')):
        try:
            utc_time = parts[1]
            lat = parts[2]
            lat_dir = parts[3]
            lon = parts[4]
            lon_dir = parts[5]
            fix_quality = parts[6]
            satellites = parts[7]
            hdop = parts[8]
            altitude = parts[9]

            if lat and lon:
                return {
                    "time": utc_time[:2] + ":" + utc_time[2:4] + ":" + utc_time[4:6],
                    "lat": f"{lat[:2]}*{lat[2:]} {lat_dir}",
                    "lon": f"{lon[:3]}*{lon[3:]} {lon_dir}",
                    "sats": satellites,
                    "alt": f"{altitude} M",
                    "fix_quality": fix_quality,
                    "hdop": hdop,
                    "raw": nmea_sentence,
                }
        except (IndexError, ValueError):
            pass
    return None


print("Starting GPS display")

display = None
uart = None
last_lat = ""
last_sats = ""
last_fix_quality = ""
last_sentence = ""
startup_ok = False

try:
    display = init_display()
    print("Display OK")
    uart = init_gps_uart()
    print("GPS UART OK")
    startup_ok = True
    display.text(smallfont, "GPS: waiting for data...", 10, 40, st7789.YELLOW, st7789.BLACK)
except Exception as exc:
    print("Startup failure:", exc)
    startup_ok = False

if wdt_available and startup_ok:
    # Keep the watchdog disabled while debugging reset behavior. Re-enable later only
    # after the ESP32 is stable and the GPS UART/display loop is proven reliable.
    print("Watchdog disabled for debug stability")
    wdt = None

loop_counter = 0
loop_heartbeat = 0
last_debug_print = 0

while True:
    try:
        if wdt is not None:
            wdt.feed()

        loop_counter += 1
        if loop_counter % 250 == 0:
            loop_heartbeat += 1
            print("Heartbeat:", loop_heartbeat, "Last sentence:", last_sentence, "Fix quality:", last_fix_quality)
            if display is not None:
                safe_display_fill(display, 0, 180, 240, 30, st7789.BLACK)
                display.text(smallfont, f"Alive {loop_heartbeat}", 10, 180, st7789.WHITE, st7789.BLACK)

        if uart is not None and uart.any():
            line = uart.readline()
            if line:
                line_str = line.decode('utf-8', 'ignore').strip()
                if line_str.startswith('$'):
                    sentence_name = line_str.split(',')[0]
                    last_sentence = sentence_name
                    data = parse_gga(line_str)

                    if data:
                        if data['fix_quality'] == '0':
                            fix_status = "NO FIX"
                            fix_color = st7789.RED
                        elif data['fix_quality'] in ('1', '2'):
                            fix_status = "FIX OK"
                            fix_color = st7789.GREEN
                        else:
                            fix_status = f"Q{data['fix_quality']}"
                            fix_color = st7789.YELLOW

                        if data['lat'] != last_lat or data['sats'] != last_sats or data['fix_quality'] != last_fix_quality:
                            last_lat = data['lat']
                            last_sats = data['sats']
                            last_fix_quality = data['fix_quality']

                            safe_display_fill(display, 0, 30, 240, 200, st7789.BLACK)
                            display.text(smallfont, f"GPS: {fix_status}", 10, 35, fix_color, st7789.BLACK)
                            display.text(smallfont, f"Msg: {sentence_name}", 10, 55, st7789.YELLOW, st7789.BLACK)
                            display.text(smallfont, f"UTC: {data['time']}", 10, 75, st7789.GREEN, st7789.BLACK)
                            display.text(smallfont, f"Lat: {data['lat']}", 10, 95, st7789.WHITE, st7789.BLACK)
                            display.text(smallfont, f"Lon: {data['lon']}", 10, 115, st7789.WHITE, st7789.BLACK)
                            display.text(smallfont, f"Sats: {data['sats']}  HDOP: {data['hdop']}", 10, 135, st7789.CYAN, st7789.BLACK)
                            display.text(smallfont, f"Alt: {data['alt']}", 10, 155, st7789.MAGENTA, st7789.BLACK)
                    else:
                        safe_display_fill(display, 0, 30, 240, 80, st7789.BLACK)
                        display.text(smallfont, "GPS: receiving NMEA", 10, 35, st7789.YELLOW, st7789.BLACK)
                        display.text(smallfont, f"Last sentence: {sentence_name}", 10, 55, st7789.WHITE, st7789.BLACK)
                        display.text(smallfont, "Waiting for GGA with valid fix...", 10, 75, st7789.RED, st7789.BLACK)

        time.sleep_ms(20)
    except Exception as exc:
        print("Runtime fault:", exc)
        time.sleep_ms(100)
