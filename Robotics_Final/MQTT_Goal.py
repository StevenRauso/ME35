import cv2
import numpy as np
import time
import json
import paho.mqtt.client as mqtt
import secrets
import sys  # only if you want to exit on failure

# ---------------- MOUSE-DRAGGABLE BOUNDING BOX ----------------
last_goal_time = 0
goal_cooldown = 10
drawing = False
ix, iy = -1, -1
bbox = None   # (x1,y1,x2,y2)

def draw_bbox(event, x, y, flags, param):
    global ix, iy, drawing, bbox

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
        bbox = None

    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        bbox = (ix, iy, x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        bbox = (ix, iy, x, y)

# --------------------- MQTT CLASS ---------------------
class BallDetectorMQTT:
    def __init__(self):
        self.MQTT_BROKER = secrets.mqtt_url
        self.MQTT_PORT = 8883
        self.MQTT_USERNAME = secrets.mqtt_username
        self.MQTT_PASSWORD = secrets.mqtt_password
        self.TOPIC_PUB = "/ME35/goal

        self.client = mqtt.Client(client_id="Liam_2")
        self.client.username_pw_set(self.MQTT_USERNAME, self.MQTT_PASSWORD)
        self.client.tls_set()  # basic SSL
        
        try:
            self.client.connect(self.MQTT_BROKER, self.MQTT_PORT)
            print("MQTT connected successfully!")
        except Exception as e:
            print("ERROR: Unable to connect to MQTT broker!")
            print("Details:", e)
            # exit program
            sys.exit(1)

        self.ball_detected_last = False

    def publish_goal(self):
        try:
            msg = "GOAL"
            self.client.publish(self.TOPIC_PUB, msg)
            print("GOAL message published!")
        except Exception as e:
            print("Error publishing GOAL:", e)

# --------------- INIT CAMERA + MQTT ----------------

mqtt_device = BallDetectorMQTT()

cap = cv2.VideoCapture(0) #adjust as necessary usually 0 or 1
if not cap.isOpened():
    print("Error: Could not open camera.")
    exit()

cv2.namedWindow("Camera")
cv2.setMouseCallback("Camera", draw_bbox)

# HSV range for green ball
lower_color = np.array([66, 60, 150])
upper_color = np.array([76, 155, 230])

print("Starting ball + bounding box goal detector...")

# ---------------- MAIN LOOP ----------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_color, upper_color)

    mask = cv2.GaussianBlur(mask, (9, 9), 2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    ball_detected = False
    ball_center = None

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 300 or area > 10000:
            continue

        (x, y), radius = cv2.minEnclosingCircle(cnt)
        center = (int(x), int(y))
        radius = int(radius)

        if radius < 10 or radius > 80:
            continue

        circle_area = np.pi * radius**2
        roundness = area / circle_area

        if roundness < 0.6:
            continue

        # Ball passes filters
        ball_detected = True
        ball_center = center

        cv2.circle(frame, center, radius, (255, 0, 0), 2)

    # ---------------- CHECK IF BALL IS IN BOUNDING BOX ----------------
# ---------------- STATE MACHINE FOR GOAL DETECTION ----------------

    ball_inside_box_now = False

# ALWAYS draw bounding box if one exists
    if bbox is not None:
        x1, y1, x2, y2 = bbox
        x_min, x_max = sorted([x1, x2])
        y_min, y_max = sorted([y1, y2])
        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 255), 3)

    # Check if ball center is inside the box
    if ball_center is not None:
        bx, by = ball_center
        if x_min <= bx <= x_max and y_min <= by <= y_max:
            ball_inside_box_now = True
            cv2.putText(frame, "GOAL!", (bx - 30, by - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

# ------------- MQTT SEND ON FIRST ENTRY ONLY -------------
    current_time = time.time()

    if ball_inside_box_now:
        if (not mqtt_device.ball_detected_last) and (current_time - last_goal_time > goal_cooldown):
            mqtt_device.publish_goal()
            last_goal_time = current_time

# Update last state
    mqtt_device.ball_detected_last = ball_inside_box_now


    # -------- SHOW WINDOWS --------
    cv2.imshow("Camera", frame)
    cv2.imshow("Mask", mask)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Program terminated.")