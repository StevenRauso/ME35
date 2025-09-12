import time
from machine import Pin
import urequests
import servo   # Cytron servo library

# ---- Servo Setup ----
servo1 = servo.Servo(Pin(19), angle=180)

# ---- Button Setup ----
button = Pin(35, Pin.IN, Pin.PULL_UP)
mode = "clock"   # start in clock mode
last_button = 1  # track previous button state

# ---- Clock State ----
current_hours = 0
current_minutes = 0
current_seconds = 0

# ---- Function to fetch real world time ----
def fetch_world_time():
    global current_hours, current_minutes, current_seconds
    try:
        url = "http://worldtimeapi.org/api/timezone/America/New_York"
        response = urequests.get(url)
        data = response.json()
        response.close()

        datetime_str = data["datetime"]  # e.g., "2025-09-08T20:01:05.123456-04:00"
        time_part = datetime_str.split("T")[1].split(".")[0]  # "20:01:05"
        h, m, s = map(int, time_part.split(":"))
        current_hours = h
        current_minutes = m
        current_seconds = s
        print("Synced world time:", f"{h:02d}:{m:02d}:{s:02d}")
    except Exception as e:
        print("Error fetching world time:", e)

# ---- Temperature Function ----
def update_temp_servo_nonblocking():
    latitude = 42.3601
    longitude = -71.0589
    url = f"http://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"

    try:
        response = urequests.get(url)
        data = response.json()
        response.close()

        temp_c = data["current_weather"]["temperature"]
        temp_f = (temp_c * 9/5) + 32
        print("Temp: {:.1f}°F".format(temp_f))

        # Map Fahrenheit temp (32–100F → 0–180°)
        if temp_f <= 0:
            angle = 0
        elif temp_f >= 100:
            angle = 180
        else:
            angle = 180 - ((temp_f / 100) * 180)

        print("Servo angle (temp mode):", round(angle))
        servo1.write_angle(round(angle))

    except Exception as e:
        print("Temp error:", e)

    # Wait up to 60s, checking button every 0.1s
    for _ in range(600):
        if button.value() == 0:  # button pressed
            return True
        time.sleep(0.1)
    return False

# ---- Clock Mode Function ----
def update_clock_servo():
    global current_seconds, current_minutes, current_hours

    # Map seconds to servo angle: 0s → 0°, 60s → 180° (3° per sec)
    angle = 180 - (current_seconds * 3)
    servo1.write_angle(angle)

    print(f"Clock Time: {current_hours:02d}:{current_minutes:02d}:{current_seconds:02d}, Servo angle: {angle}°")

    # Increment time manually
    current_seconds += 1
    if current_seconds >= 60:
        current_seconds = 0
        current_minutes += 1
        if current_minutes >= 60:
            current_minutes = 0
            current_hours = (current_hours + 1) % 24

# ---- Main Loop ----
print("Starting... initial mode:", mode)
fetch_world_time()  # Initial sync

while True:
    # --- Button Handling for Mode Toggle ---
    button_state = button.value()
    if button_state == 0 and last_button == 1:
        mode = "temp" if mode == "clock" else "clock"
        print("Mode changed to:", mode)
        last_button = 0
        time.sleep(0.3)  # debounce

        # Resync when switching back to clock
        if mode == "clock":
            fetch_world_time()

    elif button_state == 1:
        last_button = 1

    # --- Mode Execution ---
    if mode == "clock":
        update_clock_servo()
        time.sleep(1)  # jump once per second
    else:
        if update_temp_servo_nonblocking():
            mode = "clock"
            print("Mode changed to:", mode)
            fetch_world_time()