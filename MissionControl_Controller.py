import network
import time
import json
from umqtt.simple import MQTTClient
from machine import Pin, PWM
import neopixel
import secrets
from lis3dh import H3LIS331DL  # your accelerometer class file

class MQTTDevice:
    def __init__(self):
        # Wi-Fi credentials
        self.SSID = secrets.SSID
        self.PASSWORD = secrets.PWD

        # MQTT config
        self.MQTT_BROKER = secrets.mqtt_url
        self.MQTT_PORT = 8883
        self.MQTT_USERNAME = secrets.mqtt_username
        self.MQTT_PASSWORD = secrets.mqtt_password
        self.CLIENT_ID = "Liam_2"
        self.TOPIC_PUB = "/ME35/17"
        self.TOPIC_SUB = "/ME35/18"

        # Hardware setup
        self.button_led = Pin(35, Pin.IN, Pin.PULL_UP)
        self.button_buzzer = Pin(34, Pin.IN, Pin.PULL_UP)
        self.buzzer = PWM(Pin(23, Pin.OUT))
        self.buzzer.duty(0)
        self.buzzer.freq(1000)
        self.np = neopixel.NeoPixel(Pin(15), 2)

        # Debounce tracking
        self.last_press_btn1 = 0
        self.last_press_btn2 = 0

        # Initialize accelerometer
        print("Initializing accelerometer...")
        self.accel = H3LIS331DL(sda_pin=21, scl_pin=22)
        print("Accelerometer ready!")

        # Button interrupts
        self.button_led.irq(trigger=Pin.IRQ_RISING, handler=self.button_led_pressed)
        self.button_buzzer.irq(trigger=Pin.IRQ_RISING, handler=self.button_buzzer_pressed)

    # ---------- Button Handlers ----------
    def button_led_pressed(self, pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_press_btn1) < 200:
            return
        self.last_press_btn1 = now

        msg = b'{"color":[0,0,225]}'
        self.client.publish(self.TOPIC_PUB, msg)
        print("Button 1 pressed → sent LED color message")

    def button_buzzer_pressed(self, pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_press_btn2) < 200:
            return
        self.last_press_btn2 = now

        msg = b'{"Buzzer":true}'
        self.client.publish(self.TOPIC_PUB, msg)
        print("Button 2 pressed → sent buzzer message")

    # ---------- MQTT Callback ----------
    def sub_cb(self, topic, msg):
        print(f"Message received on {topic.decode()}: {msg.decode()}")
        try:
            data = json.loads(msg)
            if "color" in data:
                color = data["color"]
                self.np[0] = color
                self.np.write()
                print(f"LED color updated to {color}")
            if "Buzzer" in data and data["Buzzer"]:
                print("Activating buzzer...")
                self.buzzer.duty(512)
                time.sleep(0.5)
                self.buzzer.duty(0)
                print("Buzzer off")
        except Exception as e:
            print("Error handling message:", e)

    # ---------- Connection Methods ----------
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
            print("WiFi Connected! IP:", wlan.ifconfig()[0])
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
            print("MQTT Connected successfully!")
            self.client.subscribe(self.TOPIC_SUB)
            print(f"Subscribed to topic: {self.TOPIC_SUB}")
            return self.client
        except Exception as e:
            print("MQTT Connection failed:", e)
            return None

    # ---------- Accelerometer Publishing Loop ----------
    def send_accel_data(self):
        try:
            data = self.accel.read_accl_g()
            msg = json.dumps({"accel": data})
            self.client.publish(self.TOPIC_PUB, msg)
            print("Accel data sent:", msg)
        except Exception as e:
            print("Error reading/publishing accelerometer:", e)


# ---------- MAIN ----------
mqtt_obj = MQTTDevice()

if mqtt_obj.connect_wifi():
    client = mqtt_obj.mqtt_connect()

# Continuous loop
while True:
    try:
        client.check_msg()  # handle incoming messages
        mqtt_obj.send_accel_data()  # publish accelerometer data
        time.sleep(0.5)  # adjust frequency (5 Hz)
    except Exception as e:
        print("Error in main loop:", e)
        time.sleep(1)
