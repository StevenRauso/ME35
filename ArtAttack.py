import math
import time
from machine import Pin, PWM

# ---------------- Servo setup ----------------
servo_base = PWM(Pin(19), freq=50)    # Base servo (θ1)
servo_arm  = PWM(Pin(18), freq=50)    # Shoulder servo (θ2)

def set_angle(servo, angle):
    """Convert angle (0–180°) to PWM duty cycle."""
    duty = int(26 + (angle / 180) * 102)
    servo.duty(duty)

# ---------------- Arm geometry ----------------
L2 = 11.0     # Length of second link in cm
OFFSET_Z = 8  # Vertical offset in cm

# ---------------- LED setup ----------------
led = Pin(13, Pin.OUT)
led.on()
# ---------------- Inverse Kinematics ----------------
def ik_from_xyz(x, y, z):
    """
    Given a desired (x, y, z), return (θ1, θ2) in degrees.
    """
    r = math.sqrt(x**2 + y**2)
    theta1 = math.degrees(math.atan2(y, x))
    theta2 = math.degrees(math.atan2(z - OFFSET_Z, r))

    # Clamp within servo limits
    theta1 = max(0, min(180, theta1))
    theta2 = max(0, min(180, theta2))
    return theta1, theta2

# ---------------- Manual Path Array ----------------
# Each point is (x, y, z) in cm
# You can edit these to make shapes (circle, letters, etc.)
# Notes: z != <8 as the motors have configureds to have 90 elbow = 0 degrees on encoder, max z = 17cm,...
# any Z = 8 is not going to have any elevation
path = [
    (11,0,8), #fill in with any values in range (11,0,8) is the base position where both thetas = 0
]

# ---------------- Motion Function ----------------
def follow_path(path, delay=0.1):
    for (x, y, z) in path:
        a1, a2 = ik_from_xyz(x, y, z)
        print("XYZ(%.1f, %.1f, %.1f) -> θ1=%.1f°, θ2=%.1f°" % (x, y, z, a1, a2))
        set_angle(servo_base, a1)
        set_angle(servo_arm, a2)
        time.sleep(delay)

# ---------------- Main Loop ----------------
while True:
    follow_path(path, delay=0.1)
    time.sleep(5)
