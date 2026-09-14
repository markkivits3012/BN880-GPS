from machine import Pin, SPI, UART
import time
import st7789py as st7789  # Ensure st7789py.py is uploaded to your ESP32

# 1. Initialize Display Pins (Standard IdeaSpark 1.9" setup)
# Resolution: 170x320 pixels
BL_PIN  = 7   # Backlight pin
DC_PIN  = 3   # Data/Command pin
RST_PIN = 6   # Reset pin
SCL_PIN = 8   # SPI Clock
SDA_PIN = 10  # SPI MOSI/Data

# Enable the display backlight
backlight = Pin(BL_PIN, Pin.OUT)
backlight.value(1)

# Initialize Hardware SPI for the display
spi = SPI(1, baudrate=40000000, sck=Pin(SCL_PIN), mosi=Pin(SDA_PIN))

# Initialize the ST7789 Display Driver
display = st7789.ST7789(
    spi,
    170,
    320,
    reset=Pin(RST_PIN, Pin.OUT),
    dc=Pin(DC_PIN, Pin.OUT),
    rotation=1  # 1 = Landscape mode
)

# Clear screen with a black background
display.fill(st7789.BLACK)
display.text(st7789.sysfont, "BN-880 GPS Status", 10, 10, st7789.WHITE)
display.text(st7789.sysfont, "Waiting for fix...", 10, 30, st7789.YELLOW)

# 2. Initialize UART2 for Beitian BN-880 GPS
# Connect GPS TX -> ESP32 RX (GPIO 16)
uart = UART(2, baudrate=9600, tx=17, rx=16, timeout=10)

def parse_gga(nmea_sentence):
    parts = nmea_sentence.split(',')
    if len(parts) > 10 and ('GGA' in parts[0]):
        try:
            utc_time   = parts[1]
            lat        = parts[2]
            lat_dir    = parts[3]
            lon        = parts[4]
            lon_dir    = parts[5]
            satellites = parts[7]
            altitude   = parts[9]
            
            if lat and lon:  # Valid data available
                return {
                    "time": utc_time[:2] + ":" + utc_time[2:4] + ":" + utc_time[4:6],
                    "lat": f"{lat[:2]}*{lat[2:]}' {lat_dir}",
                    "lon": f"{lon[:3]}*{lon[3:]}' {lon_dir}",
                    "sats": satellites,
                    "alt": f"{altitude} M"
                }
        except IndexError:
            pass
    return None

print("System active. Displaying GPS output...")

# Variables to avoid flickering the screen unnecessarily
last_sats = ""
last_lat = ""

while True:
    if uart.any():
        line = uart.readline()
        try:
            line_str = line.decode('utf-8').strip()
            if line_str.startswith('$'):
                data = parse_gga(line_str)
                
                # Update screen only if new coordinate or satellite updates occur
                if data and (data['lat'] != last_lat or data['sats'] != last_sats):
                    last_lat = data['lat']
                    last_sats = data['sats']
                    
                    # Refresh active section of the layout
                    display.fill_rect(0, 30, 320, 140, st7789.BLACK)
                    
                    # Output structured metrics to the 1.9 inch IPS layout
                    display.text(st7789.sysfont, f"UTC Time: {data['time']}", 10, 35, st7789.GREEN)
                    display.text(st7789.sysfont, f"Latitude: {data['lat']}", 10, 60, st7789.WHITE)
                    display.text(st7789.sysfont, f"Longitude:{data['lon']}", 10, 85, st7789.WHITE)
                    display.text(st7789.sysfont, f"Satellites: {data['sats']}", 10, 110, st7789.CYAN)
                    display.text(st7789.sysfont, f"Altitude: {data['alt']}", 10, 135, st7789.MAGENTA)
                    
        except UnicodeError:
            pass  # Drop corrupted bytes cleanly
            
    time.sleep(0.05)
