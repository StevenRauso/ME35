# OpenMV color tracking + UART command sender 
# Replaces PC+OpenCV+MQTT pipeline

import sensor, time
from pyb import UART

# --- USER SETTINGS ---
FIRST_COLOR   = "green"    # starting color
SECOND_COLOR  = "purple"   # goal color to find and center
MIN_AREA      = 50         # minimum blob area to consider valid
NEAR_AREA     = 4000       # area threshold for "CLOSE"
DEADBAND_PCT  = 0.06       # center deadband as % of image width
COOLDOWN_SEC  = 0.5        # min time between UART sends
# ----------------------

# NOTE: These LAB thresholds are *starting points*.
# You WILL need to tune them using the OpenMV IDE Tools → Threshold Editor.
COLOR_THRESHOLDS = {
    # (Lmin, Lmax, Amin, Amax, Bmin, Bmax)
    "orange": (40, 80, 10, 40, 10, 60),
    "purple": (20, 60, 15, 60, -60, -10),
    "yellow": (50, 100, -10, 10, 40, 80),
    "blue":   (0, 40, 0, 64, -128, 0),
    "green":  (30, 100, -64, -35, -32, 60),
    "red":    (30, 80, 15, 127, 15, 127)
}

if FIRST_COLOR not in COLOR_THRESHOLDS:
    raise ValueError("Unknown FIRST_COLOR '%s'" % FIRST_COLOR)
if SECOND_COLOR not in COLOR_THRESHOLDS:
    raise ValueError("Unknown SECOND_COLOR '%s'" % SECOND_COLOR)

tracking_color = FIRST_COLOR
searching_second_color = False  # True after FIRST_COLOR is CENTER_CLOSE

# --- GOAL HOLD LOGIC (NEW) ---
goal_mode = False               # True while we're holding GOAL_FOUND
goal_start_ms = 0               # when we first sent GOAL_FOUND
GOAL_HOLD_MS = 5000             # how long to stay in GOAL mode (5s)

# --- Helper functions ---
def decide_direction(cx, img_width):
    if cx is None:
        return "NONE"
    thirds1, thirds2 = img_width / 3, 2 * img_width / 3
    deadband = DEADBAND_PCT * img_width
    center_left = (img_width / 2) - deadband
    center_right = (img_width / 2) + deadband

    if center_left <= cx <= center_right:
        return "CENTER"
    if cx < thirds1:
        return "LEFT"
    if cx > thirds2:
        return "RIGHT"
    return "CENTER"

def decide_distance(area):
    if area is None or area <= 0:
        return "NONE"
    if area >= NEAR_AREA:
        return "CLOSE"
    else:
        return "FAR"

# --- Camera setup ---
sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QQVGA)  # 160x120; can increase if needed
sensor.skip_frames(time=2000)
clock = time.clock()

# --- UART setup ---
# On many OpenMV boards, UART(3) is P4 (TX) / P5 (RX).
uart = UART(3, 115200, timeout_char=1000)

print("Tracking FIRST color:", FIRST_COLOR, "then SECOND color:", SECOND_COLOR)

last_msg = None
last_send_ms = 0  # ms since boot

while True:
    clock.tick()
    img = sensor.snapshot()
    img_w = img.width()
    img_h = img.height()

    # current time in ms (for cooldown + goal timer)
    now_ms = time.ticks_ms()

    thresh = COLOR_THRESHOLDS[tracking_color]
    blobs = img.find_blobs(
        [thresh],
        pixels_threshold=MIN_AREA,
        area_threshold=MIN_AREA,
        merge=True
    )

    cx = None
    cy = None
    blob_area = None
    have_blob = False

    if blobs:
        # find largest blob
        biggest = max(blobs, key=lambda b: b.pixels())
        if biggest.pixels() > MIN_AREA:
            have_blob = True
            blob_area = biggest.pixels()
            cx = biggest.cx()
            cy = biggest.cy()

            # draw for debugging
            img.draw_rectangle(biggest.rect(), color=(0, 255, 0))
            img.draw_cross(cx, cy, color=(255, 0, 0))

    dir_cmd = decide_direction(cx, img_w)
    dist_cmd = decide_distance(blob_area)

    # -------------------- STATE MACHINE --------------------

    # --- PHASE 1: FIRST_COLOR ---
    if (not searching_second_color) and (tracking_color == FIRST_COLOR) and (not goal_mode):
        if dir_cmd == "CENTER" and dist_cmd == "CLOSE":
            # We reached FIRST_COLOR in center & close:
            # switch to SECOND_COLOR and start spin-search
            print("FIRST_COLOR reached (CENTER_CLOSE). Switching to SECOND_COLOR and spin search.")
            tracking_color = SECOND_COLOR
            searching_second_color = True
            have_blob = False  # next frame will use SECOND_COLOR threshold

    # Decide message
    msg = None
    ui_text = ""

    if searching_second_color and (not goal_mode):
        # --- SEARCH FOR SECOND_COLOR: spin right until seen ---
        if not have_blob:
            msg = "RIGHT_FAR"  # keep robot spinning right
            ui_text = "SEARCH SECOND | MSG: %s" % msg
        else:
            # SECOND_COLOR first detected anywhere in frame:
            # stop search and start normal centering
            print("SECOND_COLOR detected - exiting spin search, now centering.")
            searching_second_color = False
            # we don't send a special msg here; next block will compute normal msg
            msg = None
            ui_text = ""
    else:
        msg = None
        ui_text = ""

    # --- NORMAL TRACKING (FIRST or SECOND) ---
    if not searching_second_color:
        if goal_mode:
            # While in goal_mode, keep sending GOAL_FOUND
            msg = "GOAL_FOUND"
            ui_text = "TRACK: %s | MSG: %s | GOAL HOLD" % (tracking_color.upper(), msg)
        else:
            if tracking_color == SECOND_COLOR and have_blob and dir_cmd == "CENTER":
                # SECOND_COLOR in middle third -> GOAL_FOUND (start goal_mode)
                msg = "GOAL_FOUND"
                goal_mode = True
                goal_start_ms = now_ms
                print("GOAL_FOUND - entering GOAL HOLD for 5 seconds.")
            else:
                msg = "%s_%s" % (dir_cmd, dist_cmd)

            ui_text = "TRACK: %s | MSG: %s" % (tracking_color.upper(), msg)
            if tracking_color == SECOND_COLOR and have_blob and dir_cmd == "CENTER":
                ui_text += " | GOAL FOUND (CENTER)"

    # --- UART Publish (with cooldown / dedupe) ---
    if (msg is not None) and (
        (msg != last_msg) or (time.ticks_diff(now_ms, last_send_ms) > int(COOLDOWN_SEC * 1000))
    ):
        try:
            uart.write(msg + "\n")
            print("Sent:", msg, "(area:", blob_area, ", tracking:", tracking_color, ")")
        except Exception as e:
            print("UART write failed:", e)
        last_msg = msg
        last_send_ms = now_ms

    # --- GOAL HOLD TIMEOUT: reset back to FIRST_COLOR search after 5s ---
    if goal_mode and (time.ticks_diff(now_ms, goal_start_ms) > GOAL_HOLD_MS):
        print("5s elapsed since GOAL_FOUND – resetting to FIRST_COLOR search.")
        goal_mode = False
        tracking_color = FIRST_COLOR
        searching_second_color = False
        last_msg = None  # force a new command on next loop

    # --- Debug text overlay ---
    img.draw_string(2, 2, ui_text, mono_space=False, color=(255, 255, 0))
    if blob_area is not None:
        img.draw_string(2, 14, "Area: %d" % blob_area, mono_space=False, color=(0, 255, 0))