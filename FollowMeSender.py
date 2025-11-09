import cv2
import numpy as np
import paho.mqtt.client as mqtt
import json
import secrets_CS  # Make sure you have your secrets_CS file with MQTT credentials

# MQTT Setup
MQTT_BROKER = secrets_CS.mqtt_url
MQTT_PORT = 8883
MQTT_USERNAME = secrets_CS.mqtt_username
MQTT_PASSWORD = secrets_CS.mqtt_password
CLIENT_ID = "opencv_tracker"
TOPIC_PUB = "/ME35/1"  # Same topic as your ESP32, or change as needed

# MQTT Connection
client = mqtt.Client(client_id=CLIENT_ID)
client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
client.tls_set()  # Enable SSL/TLS

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()  # Start background thread for MQTT
    print("MQTT Connected!")
except Exception as e:
    print(f"MQTT Connection failed: {e}")
    exit()

# Open camera
cam = cv2.VideoCapture(0)
if not cam.isOpened():
    print("Error: Could not open camera")
    exit()

while True:
    ret, frame = cam.read()
    if not ret:
        print("Error: Failed to capture frame")
        break
    
    # Convert frame to HSV color space
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Define green color range in HSV
    lower_green = np.array([40, 100, 50])
    upper_green = np.array([85, 255, 255])
    
    # Create mask for green regions
    green_mask = cv2.inRange(hsv, lower_green, upper_green)
    
    # Clean up mask
    kernel = np.ones((1, 1), np.uint8)
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel)
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
    
    # Apply mask: only green visible
    green_only = cv2.bitwise_and(frame, frame, mask=green_mask)
    
    # Find contours for green regions
    contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        biggest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(biggest_contour)
        
        if area > 100:
            x, y, w, h = cv2.boundingRect(biggest_contour)
            cx = x + w // 2
            cy = y + h // 2
            
            # Draw bounding box and center
            cv2.rectangle(green_only, (x, y), (x + w, y + h), (255, 255, 255), 2)
            cv2.circle(green_only, (cx, cy), 5, (255, 255, 255), -1)
            cv2.putText(green_only, f"({cx}, {cy})", (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.putText(green_only, f"Area: {int(area)}", (x, y + h + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            # Send data via MQTT
            mqtt_data = {
                "center": [cx, cy],
                "area": int(area),
                "width": w,
                "height": h
            }
            mqtt_message = json.dumps(mqtt_data)
            client.publish(TOPIC_PUB, mqtt_message)
            print(f"MQTT sent: {mqtt_message}")
    
    # Show result window
    cv2.imshow("green Marker Detection", green_only)
    
    # Press 'q' to quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Cleanup
client.loop_stop()
client.disconnect()
cam.release()
cv2.destroyAllWindows()
