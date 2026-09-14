from machine import Pin, SPI, UART, I2C
import time
import math
import st7789py as st7789  # Ensure st7789py.py is uploaded to your ESP32

# ==========================================
# 1. INITIALIZE DISPLAY (IdeaSpark 1.9" TFT)
# ==========================================
BL_PIN, DC_PIN, RST_PIN, SCL_PIN, SDA_PIN = 7, 3, 6, 8, 10
backlight = Pin(BL_PIN, Pin.OUT)
backlight.value(1)

spi = SPI(1, baudrate=40000000, sck=Pin(SCL_PIN), mosi=Pin(SDA_PIN))
display = st7789.ST7789(spi, 170, 320, reset=Pin(RST_PIN, Pin.OUT), dc=Pin(DC_PIN, Pin.OUT), rotation=1)

display.fill(st7789.BLACK)
display.text(st7789.sysfont, "BN-880 Dashboard", 10, 10, st7789.WHITE)

# ==========================================
# 2. INITIALIZE COMPASS (HMC5883L via I2C)
# ==========================================
I2C_ADDR = 0x1E
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000)

def init_compass():
    try:
        # Write to Configuration Register A: Set sample averaging to 8, 15Hz default
        i2c.writeto_mem(I2C_ADDR, 0x00, b'\x70')
        # Write to Configuration Register B: Set Gain setup
        i2c.writeto_mem(I2C_ADDR, 0x01, b'\x20')
        # Write to Mode Register: Set to Continuous-Measurement Mode
        i2c.writeto_mem(I2C_ADDR, 0x02, b'\x00')
        return True
    except Exception:
        return False

compass_ready = init_compass()

def read_heading():
    if not compass_ready:
        return "No Device"
    try:
        # Read 6 bytes starting from Data Output X MSB Register (0x03)
        data = i2c.readfrom_mem(I2C_ADDR, 0x03, 6)
        
        # Parse 16-bit signed integers (HMC5883L uses Big-Endian layout: X, Z, Y)
        x = int.from_bytes(data[0:2], 'big')
        z = int.from_bytes(data[2:4], 'big')
        y = int.from_bytes(data[4:6], 'big')
        
        # Handle 2's complement manually for signed data
        if x > 32767: x -= 65536
        if y > 32767: y -= 65536
        
        # Calculate Heading in Radians and convert to Degrees
        heading_rad = math.atan2(y, x)
        heading_deg = math.degrees(heading_rad)
        
        # Adjust for negative angles
        if heading_deg < 0:
            heading_deg += 360
            
        return f"{int(heading_deg)} DEG"
    except Exception:
        return "Read Error"

# ==========================================
# 3. INITIALIZE GPS (UART2)
# ==========================================
uart = UART(2, baudrate=9600, tx=17, rx=16, timeout=10)

def parse_gga(nmea_sentence):
    parts = nmea_sentence.split(',')
    if len(parts) > 10 and ('GGA' in parts):
        try:
            utc_time = parts[1]
            lat, lat_dir = parts[2], parts[3]
            lon, lon_dir = parts[4], parts[5]
            satellites = parts[7]
            
            if lat and lon:
                return {
                    "time": f"{utc_time[:2]}:{utc_time[2:4]}:{utc_time[4:6]}",
                    "lat": f"{lat[:2]}*{lat[2:]}' {lat_dir}",
                    "lon": f"{lon[:3]}*{lon[3:]}' {lon_dir}",
                    "sats": satellites
                }
        except IndexError:
            pass
    return None

# ==========================================
# 4. MAIN RUNTIME LOOP
# ==========================================
last_lat = ""
last_heading = ""
last_compass_tick = time.ticks_ms()

while True:
    # Read and refresh the compass data every 200ms
    if time.ticks_diff(time.ticks_ms(), last_compass_tick) > 200:
        current_heading = read_heading()
        if current_heading != last_heading:
            last_heading = current_heading
            # Clear and redraw the compass metric block at the bottom
            display.fill_rect(0, 125, 320, 30, st7789.BLACK)
            display.text(st7789.sysfont, f"Compass Heading: {current_heading}", 10, 130, st7789.CYAN)
        last_compass_tick = time.ticks_ms()

    # Read and parse streaming GPS data
    if uart.any():
        line = uart.readline()
        try:
            line_str = line.decode('utf-8').strip()
            if line_str.startswith('$'):
                gps_data = parse_gga(line_str)
                
                if gps_data and (gps_data['lat'] != last_lat):
                    last_lat = gps_data['lat']
                    
                    # Clear and refresh the mid-screen GPS canvas fields
                    display.fill_rect(0, 35, 320, 85, st7789.BLACK)
                    display.text(st7789.sysfont, f"UTC Time:  {gps_data['time']}", 10, 40, st7789.GREEN)
                    display.text(st7789.sysfont, f"Latitude:  {gps_data['lat']}", 10, 65, st7789.WHITE)
                    display.text(st7789.sysfont, f"Longitude: {gps_data['lon']}", 10, 90, st7789.WHITE)
                    display.text(st7789.sysfont, f"Satellites: {gps_data['sats']}", 10, 110, st7789.YELLOW)
        except UnicodeError:
            pass

    time.sleep(0.02)
