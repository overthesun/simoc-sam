import os
import json
import time

from datetime import datetime

import board
import digitalio
import adafruit_ssd1306

from PIL import Image, ImageDraw, ImageFont

from simoc_sam.sensors.basesensor import get_log_path


def parse_timestamp(ts_str):
    """Convert ISO string timestamp to float seconds since epoch."""
    try:
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
        return dt.timestamp()
    except Exception:
        return time.time()  # fallback if parsing fails

# =================== CONFIG ===================
WIDTH = 128
HEIGHT = 64
MAX_ROWS = 9  # Max total sensor rows displayed (excluding header)

FILES = {
    'SCD30': get_log_path('scd30'),               # 2 rows: CO2, RH
    'SGP30': get_log_path('sgp30'),               # 1 row: TVOC
    'BME688': get_log_path('bme688'),             # 1 row: Pressure
    'TSL': get_log_path('tsl2591'),               # 1 row: TTL LIGHT
    'BNO045': get_log_path('mockaccelerometer'),  # 3 rows: A-x, A-y, A-z
}

DISPLAY_ORDER = ["SCD30", "SGP30", "BME688", "TSL", "BNO045"]

# =================== OLED INIT ===================
oled_reset = digitalio.DigitalInOut(board.D4)
oled = adafruit_ssd1306.SSD1306_I2C(
    WIDTH, HEIGHT, board.I2C(), addr=0x3D, reset=oled_reset
)
font = ImageFont.load_default()
START_TIME = time.monotonic()

# =================== HELPERS ===================
def read_latest_entry(filepath):
    """Return the latest JSON entry from a file, or empty dict."""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r") as f:
            for line in reversed(f.read().splitlines()):
                if line.strip():
                    return json.loads(line)
    except Exception:
        pass
    return {}

def uptime():
    t = int(time.monotonic() - START_TIME)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"Up {h:02}:{m:02}:{s:02}"

# =================== SENSOR VALUE COLLECTION ===================
# def get_sensor_values():
#     values = []
#     now = time.time()  # current real time in seconds

#     for sensor in DISPLAY_ORDER:
#         data = read_latest_entry(FILES[sensor])
#         if not data:
#             continue

#         # ------------------------------
#         # SCD30: CO2 and RH, independent timestamps
#         # ------------------------------
#         if sensor == "SCD30":

#             ts = parse_timestamp(data.get("timestamp", now))
#             if now - ts <= 1:
#                 values.append(f"CO2: {data.get('co2', 0):.2f}")
#                 values.append(f"RH: {data.get('humidity', 0):.2f}")

#         # ------------------------------
#         # SGP30: TVOC
#         # ------------------------------
#         elif sensor == "SGP30":
#             ts = parse_timestamp(data.get("timestamp", now))
#             if now - ts <= 1:
#                 values.append(f"TVOC: {data.get('tvoc', 0)}")

#         # ------------------------------
#         # BME688: Pressure
#         # ------------------------------
#         elif sensor == "BME688":
#             ts = parse_timestamp(data.get("timestamp", now))
#             if now - ts <= 2:
#                 values.append(f"Pr: {data.get('pressure', 0):.2f}")

#         # ------------------------------
#         # TSL: Light
#         # ------------------------------
#         elif sensor == "TSL":
#             ts = parse_timestamp(data.get("timestamp", now))
#             if now - ts <= 1:
#                 values.append(f"Lt: {data.get('light', 0):.2f}")

#         # ------------------------------
#         # BNO045: Accelerometer, 3 rows
#         # ------------------------------
#         elif sensor == "BNO045":
#             for axis in ["accx", "accy", "accz"]:
#                 val = data.get(axis, {})
#                 if isinstance(val, dict):
#                     ts = parse_timestamp(val.get("ts", now))
#                     if now - ts <= 1:
#                         values.append(f"{axis.replace('acc','A-')}: {val.get('value',0):.2f}")

#         # Limit total rows
#         if len(values) >= MAX_ROWS:
#             values = values[:MAX_ROWS]
#             break

#     return values

def get_sensor_values():
    values = []

    for sensor in DISPLAY_ORDER:
        data = read_latest_entry(FILES[sensor])
        if not data:
            continue  # skip if no data at all

        # SCD30: CO2 and RH
        if sensor == "SCD30":
            values.append(f"CO2: {data.get('co2', 0):.2f}")
            values.append(f"RH: {data.get('humidity', 0):.2f}")

        # SGP30: TVOC
        elif sensor == "SGP30":
            values.append(f"TVOC: {data.get('tvoc', 0)}")

        # BME688: Pressure
        elif sensor == "BME688":
            values.append(f"Pr: {data.get('pressure', 0):.2f}")

        # TSL: Light
        elif sensor == "TSL":
            values.append(f"Lt: {data.get('light', 0):.2f}")

        # BNO045: Accelerometer, 3 rows
        elif sensor == "BNO045":
            for axis in ["accx", "accy", "accz"]:
                val = data.get(axis, 0)
                if isinstance(val, dict):
                    val = val.get("value", 0)
                values.append(f"{axis.replace('acc','A-')}: {val:.2f}")

        # Limit total rows
        if len(values) >= MAX_ROWS:
            values = values[:MAX_ROWS]
            break

    return values

# =================== PAGE RENDER ===================
def draw_page(sensor_values):
    """
    Draw OLED page with dynamic spacing.
    Header (SIMOC LIVE + uptime) always on top.
    Sensor rows below, dynamic spacing.
    """
    image = Image.new("1", (oled.height, oled.width))
    draw = ImageDraw.Draw(image)

    # Header
    draw.text((0, 0), "SIMOC LIVE", font=font, fill=255)
    draw.text((0, 12), uptime(), font=font, fill=255)

    num_rows = len(sensor_values)
    if num_rows == 0:
        oled.image(image.rotate(90, expand=True))
        oled.show()
        return

    header_height = 30  # 2 lines of header
    usable_height = WIDTH - header_height
    spacing = max(8, usable_height // num_rows)

    y = header_height
    for row in sensor_values:
        draw.text((0, y), row, font=font, fill=255)
        y += spacing

    oled.image(image.rotate(90, expand=True))
    oled.show()

# =================== MAIN LOOP ===================
def main():
    oled.fill(0)
    oled.show()

    while True:
        sensor_values = get_sensor_values()
        draw_page(sensor_values)
        #time.sleep(0.2)  # fast refresh for near real-time readings

if __name__ == "__main__":
    main()
