import pygame
import socket
import json
import sys
# Configuration
PI_IP = "10.247.137.191"
PI_PORT = 5005
MAX_LINEAR_SPEED = 0.5  # m/s
MAX_ANGULAR_SPEED = 2.0  # rad/s
DEADZONE = 0.1  # Ignore stick movements smaller than this
UPDATE_RATE = 20  # Hz
class PS5Controller:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            print("No controller found! Please connect your PS5 controller.")
            sys.exit(1)
        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()
        print(f"Connected to: {self.joystick.get_name()}")
        # Setup TCP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        print(f"Connecting to {PI_IP}:{PI_PORT}...")
        try:
            self.sock.connect((PI_IP, PI_PORT))
            print(f"Successfully connected to Pi!")
        except Exception as e:
            print(f"Failed to connect to Pi: {e}")
            print("Make sure ros2_bridge.py is running on the Pi first!")
            sys.exit(1)
    def apply_deadzone(self, value, deadzone=DEADZONE):
        """Apply deadzone to joystick values"""
        if abs(value) < deadzone:
            return 0.0
        # Scale the remaining range
        sign = 1 if value > 0 else -1
        return sign * (abs(value) - deadzone) / (1.0 - deadzone)
    def get_twist_command(self):
        """Read controller and return velocity command"""
        pygame.event.pump()
        # Left stick vertical (axis 1) - forward/backward
        # Note: axis values are -1 (up) to 1 (down), so we negate
        linear_raw = -self.joystick.get_axis(1)
        linear_x = self.apply_deadzone(linear_raw) * MAX_LINEAR_SPEED
        # Right stick horizontal (axis 2) - rotation
        # Negative because left should be positive rotation
        angular_raw = -self.joystick.get_axis(2)
        angular_z = self.apply_deadzone(angular_raw) * MAX_ANGULAR_SPEED
        return {
            "linear": {"x": linear_x, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": angular_z}
        }
    def send_command(self, twist_msg):
        """Send twist command to Pi"""
        try:
            data = json.dumps(twist_msg) + '\n'  # Add newline delimiter
            self.sock.sendall(data.encode('utf-8'))
        except BrokenPipeError:
            print("\nConnection lost to Pi!")
            return False
        except Exception as e:
            print(f"\nError sending command: {e}")
            return False
        return True
    def run(self):
        """Main control loop"""
        print("\nController ready!")
        print("Left stick: Forward/Backward")
        print("Right stick: Rotate Left/Right")
        print("Press Ctrl+C to exit\n")
        clock = pygame.time.Clock()
        try:
            while True:
                twist = self.get_twist_command()
                if not self.send_command(twist):
                    break
                # Display current command
                linear = twist["linear"]["x"]
                angular = twist["angular"]["z"]
                print(f"\rLinear: {linear:+.2f} m/s | Angular: {angular:+.2f} rad/s", end="", flush=True)
                clock.tick(UPDATE_RATE)
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            # Send stop command
            stop_cmd = {
                "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
                "angular": {"x": 0.0, "y": 0.0, "z": 0.0}
            }
            self.send_command(stop_cmd)
        finally:
            self.sock.close()
            pygame.quit()
if __name__ == "__main__":
    controller = PS5Controller()
    controller.run()