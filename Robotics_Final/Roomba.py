#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import socket
import json
import select
class SocketToCmdVel(Node):
    def _init_(self):
        super()._init_('socket_to_cmd_vel')
        
        # Create publisher
        self.publisher = self.create_publisher(Twist, 'cmd_vel', 10)
        
        # Setup TCP socket
        self.port = 5005
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(('', self.port))
        self.server_sock.listen(1)
        self.server_sock.setblocking(False)  # Non-blocking
        
        self.client_sock = None
        self.buffer = ""
        
        self.get_logger().info(f'Waiting for controller connection on port {self.port}...')
        
        # Timer for publishing (in case we need to timeout)
        self.last_command_time = self.get_clock().now()
        self.timer = self.create_timer(0.1, self.check_timeout)
        
    def check_timeout(self):
        """Stop robot if no commands received for 1 second"""
        if self.client_sock:
            time_since_last = (self.get_clock().now() - self.last_command_time).nanoseconds / 1e9
            if time_since_last > 1.0:
                twist = Twist()
                self.publisher.publish(twist)
    
    def accept_connection(self):
        """Accept new client connection"""
        try:
            self.client_sock, addr = self.server_sock.accept()
            self.client_sock.setblocking(False)
            self.get_logger().info(f'Controller connected from {addr[0]}:{addr[1]}')
            self.buffer = ""
        except BlockingIOError:
            pass
    
    def receive_commands(self):
        """Receive and process commands from client"""
        try:
            ready = select.select([self.client_sock], [], [], 0)
            if ready[0]:
                data = self.client_sock.recv(4096)
                if not data:
                    # Connection closed
                    self.get_logger().info('Controller disconnected')
                    self.client_sock.close()
                    self.client_sock = None
                    self.buffer = ""
                    return
                
                # Add to buffer
                self.buffer += data.decode('utf-8')
                
                # Process complete messages (separated by newlines)
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    if line.strip():
                        try:
                            cmd_dict = json.loads(line)
                            
                            # Create Twist message
                            twist = Twist()
                            twist.linear.x = cmd_dict['linear']['x']
                            twist.linear.y = cmd_dict['linear']['y']
                            twist.linear.z = cmd_dict['linear']['z']
                            twist.angular.x = cmd_dict['angular']['x']
                            twist.angular.y = cmd_dict['angular']['y']
                            twist.angular.z = cmd_dict['angular']['z']
                            
                            # Publish
                            # Publish
                            self.publisher.publish(twist)
                            self.last_command_time = self.get_clock().now()
                            self.get_logger().info(f'Published: linear.x={twist.linear.x:.2f}, angular.z={twist.angular.z:.2f}')  # ADD THIS
                        except json.JSONDecodeError as e:
                            self.get_logger().error(f'JSON decode error: {e}')
                        except KeyError as e:
                            self.get_logger().error(f'Missing key in command: {e}')
        except Exception as e:
            self.get_logger().error(f'Error receiving data: {e}')
            if self.client_sock:
                self.client_sock.close()
                self.client_sock = None
    
    def run(self):
        """Main loop to receive and publish commands"""
        while rclpy.ok():
            if self.client_sock is None:
                self.accept_connection()
            else:
                self.receive_commands()
            
            # Spin once to process callbacks
            rclpy.spin_once(self, timeout_sec=0.01)
def main():
    rclpy.init()
    node = SocketToCmdVel()
    
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        # Stop the robot
        twist = Twist()
        node.publisher.publish(twist)
        node.destroy_node()
        rclpy.shutdown()
if _name_ == '_main_':
    main()