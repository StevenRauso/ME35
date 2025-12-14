from machine import Pin
import time
from machine import PWM
import math

# -------------------------
# Your Servo Class
# -------------------------
class Servo:
    def __init__(self, pin, freq=50, min_us=600, max_us=2400, angle=180):
        self.min_us = min_us
        self.max_us = max_us
        self.us = 0
        self.freq = freq
        self.angle = angle
        self.pwm = PWM(pin, freq=freq, duty=0)

    def write_us(self, us):
        if us == 0:
            self.pwm.duty(0)
            return
        us = min(self.max_us, max(self.min_us, us))
        duty = us * 1024 * self.freq // 1_000_000
        self.pwm.duty(duty)

    def write_angle(self, degrees=None, radians=None):
        if degrees is None:
            degrees = math.degrees(radians)
        degrees = degrees % 360
        total_range = self.max_us - self.min_us
        us = self.min_us + total_range * degrees // self.angle
        self.write_us(us)


# -------------------------
# Hardware Setup
# -------------------------

button = Pin(34, Pin.IN)     # D34 input-only pin, no pullups inside
servo_pin = Pin(19)          # pick your servo signal pin (example: GPIO15)

servo = Servo(servo_pin)

# Optional: if button needs pull-up
# button = Pin(34, Pin.IN, Pin.PULL_UP)

last_state = 0

# -------------------------
# Main Loop
# -------------------------

while True:
    state = button.value()

    # Detect button press (LOW if using pull-up, HIGH if using external pull-down)
    if state == 1 and last_state == 0:   # adjust if using pull-up
        print("Button pressed")

        # Move servo 0 → 90 degrees
        servo.write_angle(0)
        time.sleep_ms(200)
        servo.write_angle(90)

        time.sleep(1)

        # Return to 0
        servo.write_angle(0)

    last_state = state
    time.sleep_ms(20)
