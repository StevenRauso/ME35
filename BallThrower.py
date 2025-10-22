from machine import Pin, PWM
import time

# ---------------- Motor Setup ----------------
motorA = Pin(13, Pin.OUT)              # Direction pin
motorB = PWM(Pin(12), freq=1000)       # PWM pin
motorA.off()
motorB.duty(0)

# ---------------- Experimental Data ----------------
pwm_values = [100,200,300,400,500,600,700,800,900]
distances  = [7,16,22,31,37,42,49,52,55]  # in inches

# ---------------- Linear Interpolation Function ----------------
def predict_pwm_interp(target_distance):
    # If below minimum or above maximum, clamp
    if target_distance <= distances[0]:
        return pwm_values[0]
    if target_distance >= distances[-1]:
        return pwm_values[-1]

    # Find surrounding points
    for i in range(1, len(distances)):
        if distances[i-1] <= target_distance <= distances[i]:
            d0, d1 = distances[i-1], distances[i]
            p0, p1 = pwm_values[i-1], pwm_values[i]
            # Linear interpolation formula
            pwm = p0 + (target_distance - d0) * (p1 - p0) / (d1 - d0)
            return int(pwm)

# ---------------- Motor Control Function ----------------
def run_motor(pwm_val, duration=1.0):
    print("Running motor at PWM =", pwm_val)
    motorB.duty(pwm_val)
    time.sleep(duration)
    motorB.duty(0)
    print("Motor stopped.\n")

# ---------------- Interactive Loop ----------------
print("Linear Interpolation PWM Predictor — type target distance in inches ('q' to quit)")

try:
    while True:
        user_input = input("Enter target distance: ")
        if user_input.lower() == 'q':
            break
        try:
            target_distance = float(user_input)
        except ValueError:
            print("Invalid input. Enter a number.")
            continue

        pwm_needed = predict_pwm_interp(target_distance)
        print("Predicted PWM ≈", pwm_needed)

        run = input("Run motor at predicted PWM? (y/n): ")
        if run.lower() == 'y':
            run_motor(pwm_needed)

except KeyboardInterrupt:
    motorB.duty(0)
    print("Stopped by user.")
