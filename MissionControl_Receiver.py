import network
import time
import json
from umqtt.simple import MQTTClient
from machine import Pin, PWM
import neopixel
import secrets


class MotorReceiver:
    def __init__(self):
        # Wi-Fi & MQTT configuration
        self.SSID = secrets.SSID
        self.PASSWORD = secrets.PWD
        self.MQTT_BROKER = secrets.mqtt_url
        self.MQTT_PORT = 8883
        self.MQTT_USERNAME = secrets.mqtt_username
        self.MQTT_PASSWORD = secrets.mqtt_password
        self.CLIENT_ID = "ESP32_MotorReceiver"
        self.TOPIC_SUB = "/ME35/17"  # listens for accelerometer and control messages
        self.TOPIC_PUB = "/ME35/18"  # can respond with status or debug info

        # NeoPixel and buzzer
        self.np = neopixel.NeoPixel(Pin(15), 2)
        self.buzzer = PWM(Pin(23, Pin.OUT))
        self.buzzer.duty(0)
        self.buzzer.freq(1000)

        # Motor PWM frequency and current limiting
        self.MAX_DUTY = 300  # limit PWM output to reduce current draw

        # Motors setup
        self.motorA_pwm = PWM(Pin(12), freq=100)
        self.motorA_in1 = Pin(12, Pin.OUT)
        self.motorA_in2 = Pin(13, Pin.OUT)
        self.motorB_pwm = PWM(Pin(14), freq=100)
        self.motorB_in1 = Pin(14, Pin.OUT)
        self.motorB_in2 = Pin(27, Pin.OUT)

    # ---------- MOTOR CONTROL ----------
    def set_motor(self, motor, speed):
        """Set one motor's direction and speed based on signed value."""
        pwm = self.motorA_pwm if motor == 'A' else self.motorB_pwm
        in1 = self.motorA_in1 if motor == 'A' else self.motorB_in1
        in2 = self.motorA_in2 if motor == 'A' else self.motorB_in2

        # limit PWM duty
        duty = min(abs(int(speed)), self.MAX_DUTY)

        if speed > 0:
            in1.value(1)
            in2.value(0)
            pwm.duty(duty)
        elif speed < 0:
            in1.value(0)
            in2.value(1)
            pwm.duty(duty)
        else:
            in1.value(0)
            in2.value(0)
            pwm.duty(0)

    def drive_from_tilt(self, x_val):
        """Drive both motors based on received X tilt value."""
        scale = 100  # sensitivity (adjust as needed)
        raw_speed = int(x_val * scale)

        # small dead zone
        if abs(raw_speed) < 10:
            raw_speed = 0

        self.set_motor('A', raw_speed)
        self.set_motor('B', raw_speed)
        print(f"Motors set with x={x_val:.2f} → speed={raw_speed}")

    # ---------- MQTT CALLBACK ----------
    def sub_cb(self, topic, msg):
        try:
            message = msg.decode()
            data = json.loads(message)
            print(f"Received on {topic.decode()}: {message}")

            # --- Check for accelerometer data ---
            if "accel" in data:
                x = data["accel"]["x"]
                self.drive_from_tilt(x)

            # --- LED flash command ---
            if "color" in data:
                color = data["color"]
                self.np[0] = color
                self.np.write()
                print(f"LED color updated to {color}")
                time.sleep(0.5)  # flash duration
                self.np[0] = [0, 0, 0]
                self.np.write()

            # --- Optional buzzer command ---
            if "Buzzer" in data and data["Buzzer"]:
                print("Activating buzzer...")
                self.buzzer.duty(512)
                time.sleep(0.5)
                self.buzzer.duty(0)

        except Exception as e:
            print("Error parsing message:", e)

    # ---------- CONNECTION ----------
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
            print("WiFi connected! IP:", wlan.ifconfig()[0])
            return True
        else:
            print("WiFi connection failed!")
            return False

    def mqtt_connect(self):
        try:
            self.client = MQTTClient(
                client_id=self.CLIENT_ID,
                server=self.MQTT_BROKER,
                port=self.MQTT_PORT,
                user=self.MQTT_USERNAME,
                password=self.MQTT_PASSWORD,
                ssl=True,
                ssl_params={'server_hostname': self.MQTT_BROKER}
            )
            self.client.set_callback(self.sub_cb)
            self.client.connect()
            print("MQTT connected successfully!")
            self.client.subscribe(self.TOPIC_SUB)
            print(f"Subscribed to topic: {self.TOPIC_SUB}")
            return self.client
        except Exception as e:
            print("MQTT connection failed:", e)
            return None


# ---------- MAIN ----------
receiver = MotorReceiver()

if receiver.connect_wifi():
    client = receiver.mqtt_connect()

while True:
    try:
        client.check_msg()
        time.sleep(0.05)  # check for messages ~20Hz
    except Exception as e:
        print("Error in main loop:", e)
        time.sleep(1)
