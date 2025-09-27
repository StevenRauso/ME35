from machine import Pin, PWM, I2C
import time
from veml6040 import VEML6040
# Initialize I2C and sensor
i2c = I2C(scl=Pin(22), sda=Pin(21))
color_sensor = VEML6040(i2c)
# Set sensor integration time to 40ms for faster measurements
# VEML6040 integration time constants
IT_40MS = 0x00   # 40ms integration time
IT_80MS = 0x01   # 80ms integration time
IT_160MS = 0x02  # 160ms integration time
IT_320MS = 0x03  # 320ms integration time
# Configure sensor for faster measurements
color_sensor.set_integration_time(IT_40MS)
# Motor setup
left_pwm_pin = PWM(Pin(13), freq=1000)
left_dir_pin = Pin(12, Pin.OUT)
right_pwm_pin = PWM(Pin(27), freq=1000)
right_dir_pin = Pin(14, Pin.OUT)
def set_motor(left_speed, right_speed):
    # Clamp speeds to 0-1023
    left_speed = max(min(abs(left_speed), 1023), 0)
    right_speed = max(min(abs(right_speed), 1023), 0)
    # Set direction based on original sign
    left_dir_pin.value(0 if left_speed >= 0 else 1)
    right_dir_pin.value(0 if right_speed >= 0 else 1)
    # Apply PWM duty cycles
    left_pwm_pin.duty(left_speed)
    right_pwm_pin.duty(right_speed)
def set_motor_dir(left_speed, right_speed):
    # A helper that sets direction and duty for signed speeds (positive forward, negative backward)
    if left_speed >= 0:
        left_dir_pin.value(0)
        left_pwm_pin.duty(left_speed)
    else:
        left_dir_pin.value(1)
        left_pwm_pin.duty(-left_speed)
    if right_speed >= 0:
        right_dir_pin.value(0)
        right_pwm_pin.duty(right_speed)
    else:
        right_dir_pin.value(1)
        right_pwm_pin.duty(-right_speed)
def is_on_line():
    r, g, b, c = color_sensor.read()
    return c < 250  # Adjust as needed
# State variables for search pattern
state = None  # None, "searching_right", "searching_left"
state_start_time = 0
right_search_duration = 3000  # Right search duration in milliseconds
left_search_duration = 10000  # Left search duration - double the right duration
# Base values
base_speed = 150
slow_search_speed = 100 # Very slow speed for searching
# Faster measurement loop with reduced sleep time
measurement_interval = 0.01  # 10ms instead of 20ms for more responsive control
print("Starting line following with 40ms color sensor integration time...")
while True:
    try:
        c = color_sensor.read()[3]
        now = time.ticks_ms()
        if is_on_line():
            # Reset and go straight
            state = None
            set_motor_dir(base_speed, base_speed)
            motor_status = "On line, going straight"
        else:
            # Lost line - enter search pattern
            if state is None:
                # Just lost the line, start searching right
                state = "searching_right"
                state_start_time = now
                print("*** STARTING SEARCH - GOING RIGHT FIRST ***")
            # Check if we need to switch search direction
            time_in_state = time.ticks_diff(now, state_start_time)
            # Use different durations based on current state
            current_search_duration = right_search_duration if state == "searching_right" else left_search_duration
            if time_in_state >= current_search_duration:
                # Switch search direction
                if state == "searching_right":
                    state = "searching_left"
                    print("*** SWITCHING TO SEARCH LEFT ***")
                elif state == "searching_left":
                    state = "searching_right"
                    print("*** SWITCHING TO SEARCH RIGHT ***")
                state_start_time = now
                time_in_state = 0  # Reset for immediate use
            # Execute search movement
            if state == "searching_right":
                # Search right: left motor turns very slow, right motor stationary
                left_motor = slow_search_speed
                right_motor = 0
                motor_status = f"Search right: left motor slow, right stationary | time in state: {time_in_state}ms / {right_search_duration}ms"
            elif state == "searching_left":
                # Search left: right motor turns very slow, left motor stationary
                left_motor = 0
                right_motor = 130
                motor_status = f"Search left: right motor slow, left stationary | time in state: {time_in_state}ms / {left_search_duration}ms"
            set_motor_dir(left_motor, right_motor)
        print(f"Sensor C={c} | State: {state} | Motor status: {motor_status}")
        # Reduced sleep time for more frequent measurements
        time.sleep(measurement_interval)
    except KeyboardInterrupt:
        # Stop motors when program is interrupted
        print("Program stopped - stopping motors")
        set_motor_dir(0, 0)
        break
