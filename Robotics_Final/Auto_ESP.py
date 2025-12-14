import time
import network
from machine import Pin, PWM, UART
import neopixel
from umqtt.simple import MQTTClient
import secrets

class RobotDevice:
    def __init__(self):
        # --- NeoPixel: 2 LEDs on pin 15 ---
        self.np = neopixel.NeoPixel(Pin(15), 2)

        # --- Buzzer ---
        self.buz = Pin(23, Pin.OUT)
        self.buz.value(0)

        # --- Motor PWM pins ---
        self.L_IN1 = PWM(Pin(12), freq=20000, duty=0)
        self.L_IN2 = PWM(Pin(13), freq=20000, duty=0)
        self.R_IN1 = PWM(Pin(27), freq=20000, duty=0)
        self.R_IN2 = PWM(Pin(14), freq=20000, duty=0)
        self.S_IN1 = Pin(25, Pin.OUT) #D25
        self.S_IN2 = Pin(26, Pin.OUT) #D26
        self.SPEED = 400  # adjust as needed (0–1023 for ESP32)

        # --- UART setup (from camera/OpenMV) ---
        # Example: UART(1) on GPIO16 (RX) and GPIO17 (TX).
        self.uart = UART(1, baudrate=115200, tx=Pin(17), rx=Pin(16), timeout=100)

        # --- WiFi + MQTT setup ---
        self.SSID = secrets.SSID
        self.PASSWORD = secrets.PWD

        self.MQTT_BROKER = secrets.mqtt_url
        self.MQTT_PORT = 8883
        self.MQTT_USERNAME = secrets.mqtt_username
        self.MQTT_PASSWORD = secrets.mqtt_password
        self.MQTT_CLIENT_ID = "Liam_goal_bot"
        # Topic where we listen for "GOAL"
        self.TOPIC_GOAL = b"/ME35/goal"

        self.mqtt_client = None

        # --- State machine ---
        # SEARCHING: normal UART control
        # WAITING_GOAL_RESET: got GOAL_FOUND, waiting for MQTT "GOAL" or timeout
        self.state = "SEARCHING"

        # --- GOAL timeout system ---
        self.GOAL_RESET_TIMEOUT = 20.0  # seconds
        self.goal_found_time = None     # timestamp when GOAL_FOUND was received

        print("RobotDevice initialized. Waiting for UART + MQTT commands...")

    # ---------- WiFi + MQTT ----------
    def connect_wifi(self):
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            print("Connecting to WiFi...")
            wlan.connect(self.SSID, self.PASSWORD)
            timeout = 10
            while not wlan.isconnected() and timeout > 0:
                time.sleep(1)
                timeout -= 1
        if wlan.isconnected():
            print("WiFi Connected:", wlan.ifconfig()[0])
            return True
        print("WiFi failed.")
        return False

    def mqtt_connect(self):
        try:
            self.mqtt_client = MQTTClient(
                client_id=self.MQTT_CLIENT_ID,
                server=self.MQTT_BROKER,
                port=self.MQTT_PORT,
                user=self.MQTT_USERNAME,
                password=self.MQTT_PASSWORD,
                ssl=True,
                ssl_params={'server_hostname': self.MQTT_BROKER}  # SNI
            )
            self.mqtt_client.set_callback(self._mqtt_cb)
            self.mqtt_client.connect()
            self.mqtt_client.subscribe(self.TOPIC_GOAL)
            print("Connected to MQTT broker and subscribed to", self.TOPIC_GOAL)
        except Exception as e:
            print("MQTT connect failed:", e)
            self.mqtt_client = None

    def _mqtt_cb(self, topic, msg):
        """
        MQTT callback – when we get 'GOAL' on TOPIC_GOAL,
        and we are in WAITING_GOAL_RESET state, reset search pattern.
        """
        try:
            text = msg.decode().strip().upper()
        except:
            text = ""
        print("MQTT received on", topic, ":", text)

        if text == "GOAL":
            if self.state == "WAITING_GOAL_RESET":
                print("GOAL ACK received – resetting to SEARCHING state.")
                # Optional celebration
                self.celebrate_goal(duration=2.0)
                # Reset state so we accept UART search commands again
                self.state = "SEARCHING"
                self.goal_found_time = None
                # Clear outputs
                self.set_led((0, 0, 0), (0, 0, 0))
                self.stop()

    def celebrate_goal(self, duration=3.0):
        """
        Spin in place and repeatedly beep the buzzer
        for 'duration' seconds.
        """
        print("Celebration: spinning + beeping!")
        start = time.time()
        while time.time() - start < duration:
            # Spin (e.g., spin left) and short beep
            self.spin_left()
            self.buz.value(1)
            time.sleep(0.1)
            self.buz.value(0)
            time.sleep(0.1)
        # Stop everything at the end
        self.stop()
        self.buz.value(0)

    # ---------- UART Command handling ----------
    def handle_cmd(self, cmd):
        """Interpret commands like LEFT_FAR, RIGHT_CLOSE, GOAL_FOUND, NONE_NONE."""
        print("Received:", cmd)

        # If we're waiting for MQTT GOAL reset, ignore movement commands
        if self.state == "WAITING_GOAL_RESET":
            print("Ignoring movement cmd while waiting for GOAL MQTT.")
            return

        if cmd == "LEFT_FAR":
            self.set_led((255, 0, 0), (0, 0, 0))   # red
            self.spin_left()
        elif cmd == "LEFT_CLOSE":
            self.set_led((255, 0, 0), (0, 0, 255)) # red + blue
            self.spin_left()
        elif cmd == "RIGHT_FAR":
            self.set_led((255, 0, 0), (0, 0, 0))   # red
            self.spin_right()
        elif cmd == "RIGHT_CLOSE":
            self.set_led((255, 0, 0), (0, 0, 255)) # red + blue
            self.spin_right()
        elif cmd == "CENTER_FAR":
            self.set_led((0, 255, 0), (0, 0, 0))   # green
            self.forward()
        elif cmd == "CENTER_CLOSE":
            self.set_led((0, 255, 0), (0, 0, 255)) # green + blue
            self.forward()
            time.sleep(2)
            self.stop()
        elif "NONE" in cmd:
            # e.g., NONE_NONE, LEFT_NONE, NONE_FAR, etc.
            self.set_led((0, 0, 0), (0, 0, 0))     # off
            self.stop()
        elif cmd == "GOAL_FOUND":
            # We reached the ball → stop & beep once,
            # then enter WAITING_GOAL_RESET state and start timeout
            print("GOAL_FOUND received – entering WAITING_GOAL_RESET state.")
            self.set_led((0, 255, 0), (0, 0, 255)) # green + blue
            self.buzzer_beep()
            self.forward()
            time.sleep(1)
            self.shoot()
            self.stop()
            self.state = "WAITING_GOAL_RESET"
            self.goal_found_time = time.time()     # start 20s timer
        else:
            print("Unknown command:", cmd)

    def set_led(self, color_1, color_2):
        """Set both NeoPixels to given RGB color tuples."""
        self.np[0] = color_1
        self.np[1] = color_2
        self.np.write()

    def buzzer_beep(self, duration=0.1):
        self.buz.value(1)
        time.sleep(duration)
        self.buz.value(0)

    # ---------- Motor controls ----------
    def spin_left(self):
        self.L_IN1.duty(self.SPEED);          self.L_IN2.duty(0)
        self.R_IN1.duty(0); self.R_IN2.duty(self.SPEED)

    def spin_right(self):
        self.L_IN1.duty(0); self.L_IN2.duty(self.SPEED)
        self.R_IN1.duty(self.SPEED);          self.R_IN2.duty(0)

    def forward(self):
        self.L_IN1.duty(self.SPEED); self.L_IN2.duty(0)
        self.R_IN1.duty(self.SPEED); self.R_IN2.duty(0)

    def stop(self):
        self.L_IN1.duty(0); self.L_IN2.duty(0)
        self.R_IN1.duty(0); self.R_IN2.duty(0)
        
    def shoot(self):
        # spin forward
        self.S_IN1.value(0)
        self.S_IN2.value(1)
        time.sleep(0.25)

        # stop
        self.S_IN1.value(0)
        self.S_IN2.value(0)
        time.sleep(0.5)

        # spin backward
        self.S_IN1.value(1)
        self.S_IN2.value(0)
        time.sleep(0.25)

        # final stop
        self.S_IN1.value(0)
        self.S_IN2.value(0)
    
    # ---------- Main polling loop ----------
    def loop(self):
        while True:
            try:
                # --- AUTO RESET AFTER TIMEOUT IF NO MQTT GOAL RECEIVED ---
                if self.state == "WAITING_GOAL_RESET" and self.goal_found_time is not None:
                    if time.time() - self.goal_found_time > self.GOAL_RESET_TIMEOUT:
                        print("Timeout expired – auto-resetting to SEARCHING.")
                        self.state = "SEARCHING"
                        self.goal_found_time = None
                        self.set_led((0, 0, 0), (0, 0, 0))
                        self.stop()

                # Check MQTT (non-blocking)
                if self.mqtt_client is not None:
                    try:
                        self.mqtt_client.check_msg()
                    except Exception as e:
                        print("MQTT error in loop:", e)
                        time.sleep(0.1)

                # ---------- UART DRAIN LOGIC (Fix 1) ----------
                # Read ALL waiting lines and keep only the most recent one
                last_line = None
                while self.uart.any():
                    line = self.uart.readline()
                    if line:
                        last_line = line  # overwrite each time -> newest wins

                if last_line:
                    try:
                        cmd = last_line.decode().strip().upper()
                        if cmd:
                            self.handle_cmd(cmd)
                    except Exception as e:
                        print("UART decode error:", e)

                # Slow down the loop a bit
                time.sleep(0.3)

            except Exception as e:
                print("Error in loop:", e)
                time.sleep(1)

# ---------- MAIN ----------
time.sleep(2)  # you can lower/remove this if you want faster startup
robot = RobotDevice()

# Connect WiFi + MQTT (if available)
if robot.connect_wifi():
    robot.mqtt_connect()

robot.loop(