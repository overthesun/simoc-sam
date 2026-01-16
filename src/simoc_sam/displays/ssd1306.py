import os
import json
import time
import board
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
from datetime import datetime

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
LOG_DIR = "/home/pi/logs"
MAX_ROWS = 9  # Max total sensor rows displayed (excluding header)

FILES = {
    "SCD30": "SRS_SRS_SCD-30.jsonl",        # 2 rows: CO2, RH
    "SGP30": "SRS_SRS_SGP30.jsonl",         # 1 row: TVOC
    "BME688": "SRS_SRS_BME688.jsonl",       # 1 row: Pressure
    "TSL": "SRS_SRS_TSL2591.jsonl",         # 1 row: TTL LIGHT
    "BNO045": "sam_samrpi1_MockAccelerometer.jsonl",  # 3 rows: A-x, A-y, A-z
}

DISPLAY_ORDER = ["SCD30", "SGP30", "BME688", "TSL", "BNO045"]

# =================== OLED INIT ===================
oled_reset = digitalio.DigitalInOut(board.D4)
oled = adafruit_ssd1306.SSD1306_I2C(
    WIDTH, HEIGHT, board.I2C(), addr=0x3D, reset=oled_reset
)
<<<<<<< Updated upstream

# Fonts
font_small = ImageFont.load_default()
font_header = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14
)

=======
font = ImageFont.load_default()
START_TIME = time.monotonic()

# =================== HELPERS ===================
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
def format_values(data_scd, data_bme, data_bno):
    co2 = data_scd.get("co2", "--")
    temp = data_scd.get("temperature", "--")
    hum = data_scd.get("humidity", "--")
    pres = data_bme.get("pressure", "--")
    accx = data_bno.get("accel_x", "--")
    accy = data_bno.get("accel_y", "--")
    accz = data_bno.get("accel_z", "--")
    return [
        "CO2: " + f"{co2:.0f}" if isinstance(co2, float) else str(co2),
        "Tmp: " + f"{temp:.1f}" if isinstance(temp, float) else str(temp),
        "Hum: " + f"{hum:.1f}" if isinstance(hum, float) else str(hum),
        "Prs: " + f"{pres:.1f}" if isinstance(pres, float) else str(pres),
        "A-x: " + f"{accx:.2f}" if isinstance(accx, float) else str(accx),
        "A-y: " + f"{accy:.2f}" if isinstance(accy, float) else str(accy),
        "A-z: " + f"{accz:.2f}" if isinstance(accz, float) else str(accz),
    ]

def format_uptime():
    t = int(time.monotonic())
    hm, s = divmod(t, 60)
    h, m = divmod(hm, 60)
    return f"Rt: {h:02}:{m:02}:{s:02}"
=======
def uptime():
    t = int(time.monotonic() - START_TIME)
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"Up {h:02}:{m:02}:{s:02}"
>>>>>>> Stashed changes

# =================== SENSOR VALUE COLLECTION ===================
# def get_sensor_values():
#     values = []
#     now = time.time()  # current real time in seconds

#     for sensor in DISPLAY_ORDER:
#         data = read_latest_entry(os.path.join(LOG_DIR, FILES[sensor]))
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
        data = read_latest_entry(os.path.join(LOG_DIR, FILES[sensor]))
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
