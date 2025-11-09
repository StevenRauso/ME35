import network
import time
import json
from umqtt.simple import MQTTClient
import secrets_CS
from machine import Pin, PWM
import math


class Motor:
    def __init__(self, m1, m2):
        self.M1 = PWM(Pin(m1), freq=100, duty_u16=0)
        self.M2 = PWM(Pin(m2), freq=100, duty_u16=0)
        self.stop()

    def stop(self):
        self.M1.duty_u16(0)
        self.M2.duty_u16(0)

    def start(self, direction=0, speed=99):
        """Start motor in given direction and speed (0–100)."""
        duty = int(speed * 65535 / 100)
        if direction:
            self.M1.duty_u16(duty)
            self.M2.duty_u16(0)
        else:
            self.M1.duty_u16(0)
            self.M2.duty_u16(duty)


class Follower:
    def __init__(self):
        # Motors
        self.left_motor = Motor(27, 14)
        self.right_motor = Motor(12, 13)

        # Wi-Fi credentials
        self.SSID = secrets_CS.SSID
        self.PASSWORD = secrets_CS.PWD
        self.wifi_connect()

        # MQTT config
        self.MQTT_BROKER = secrets_CS.mqtt_url
        self.MQTT_PORT = 8883
        self.MQTT_USERNAME = secrets_CS.mqtt_username
        self.MQTT_PASSWORD = secrets_CS.mqtt_password
        self.CLIENT_ID = "ESP32_Reader"
        self.TOPIC_SUB = "/ME35/1"

        print("Connecting to MQTT...")
        self.client = MQTTClient(
            client_id=self.CLIENT_ID,
            server=self.MQTT_BROKER,
            port=self.MQTT_PORT,
            user=self.MQTT_USERNAME,
            password=self.MQTT_PASSWORD,
            ssl=True,
            ssl_params={'server_hostname': self.MQTT_BROKER}
        )
        self.client.set_callback(self.message_callback)
        self.client.connect()
        print("MQTT Connected!")
        self.client.subscribe(self.TOPIC_SUB)
        print(f"Subscribed to: {self.TOPIC_SUB}")
        print("\nListening for messages...\n")

        # PID variables
        self.TARGET_SIZE = 1 / 25
        self.FREQ = 100  # sample rate in Hz

        # Distance control gains
        self.kp_D = 2000
        self.ki_D = 0.5

        # Position control gains
        self.kp_P = 0.4
        self.ki_P = 0.1

        # Error terms
        self.total_dist_e = 0
        self.total_pos_e = 0

    def wifi_connect(self):
        """Connect to Wi-Fi network."""
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(self.SSID, self.PASSWORD)
        print("Connecting to Wi-Fi...", end="")
        while not wlan.isconnected():
            print(".", end="")
            time.sleep(0.5)
        print("\nWi-Fi connected:", wlan.ifconfig())

    def get_direction(self, num):
        """Return direction (1 for forward, 0 for backward)."""
        return 1 if num >= 0 else 0

    def message_callback(self, topic, msg):
        """Handle incoming MQTT messages."""
        try:
            data = json.loads(msg)
            dist_e = data.get("distance_error", 0)
            pos_e = data.get("position_error", 0)
            self.calc_motion(dist_e, pos_e)
        except Exception as e:
            print("Error parsing message:", e)

    def calc_motion(self, dist_e, pos_e):
        """Compute PI control for distance and position and drive motors."""
        print(f"Object Size: {dist_e} | Center: {pos_e}")

        # Distance PI
        kp_D_term = self.kp_D * dist_e
        self.total_dist_e += dist_e
        ki_D_term = self.ki_D * self.total_dist_e
        speed = kp_D_term + ki_D_term

        # Position PI
        kp_P_term = self.kp_P * pos_e
        self.total_pos_e += pos_e * (1 / self.FREQ)
        ki_P_term = self.ki_P * self.total_pos_e
        turn_rate = kp_P_term + ki_P_term

        # Clamp turn rate
        turn_rate = max(min(turn_rate, 29), -29)
        # Clamp speed
        speed = max(min(speed, 70), -70)

        print(f"Dist -> kp: {kp_D_term:.2f}, ki: {ki_D_term:.2f}, speed: {speed:.2f}")
        print(f"Pos  -> kp: {kp_P_term:.2f}, ki: {ki_P_term:.2f}, turn_rate: {turn_rate:.2f}")

        # Motor commands
        left_motor = speed - turn_rate
        right_motor = speed + turn_rate

        self.left_motor.start(self.get_direction(left_motor), abs(left_motor))
        self.right_motor.start(self.get_direction(right_motor), abs(right_motor))
