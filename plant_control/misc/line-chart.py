#!/usr/bin/env python3
"""
Live Line Chart for Modbus Register Values
Reads holding registers and displays real-time data visualization
"""

import time
import threading
from collections import deque
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
import struct

class ModbusLiveChart:
    def __init__(self, host='localhost', port=502, slave_id=1, address=8834, count=2, 
                 max_points=100, update_interval=1.0):
        """
        Initialize the Modbus live chart
        
        Args:
            host: Modbus server IP address
            port: Modbus server port
            slave_id: Slave device ID
            address: Starting register address
            count: Number of registers to read
            max_points: Maximum points to display on chart
            update_interval: Update interval in seconds
        """
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.address = address
        self.count = count
        self.max_points = max_points
        self.update_interval = update_interval
        
        # Data storage
        self.timestamps = deque(maxlen=max_points)  # Will store elapsed seconds
        self.values = deque(maxlen=max_points)
        self.raw_registers = deque(maxlen=max_points)
        self.start_time = None  # Will be set when data collection starts
        
        # Modbus client
        self.client = None
        self.running = False
        
        # Setup plot
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.line, = self.ax.plot([], [], 'b-', linewidth=2, label='Register Value')
        
        # Configure plot
        self.ax.set_xlabel('Time (seconds)')
        self.ax.set_ylabel('Value')
        self.ax.set_title(f'Live Modbus Register Data (Address: {address})')
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        
        # Data reading thread
        self.data_thread = None
        
    def connect_modbus(self):
        """Connect to Modbus server"""
        try:
            self.client = ModbusTcpClient(host=self.host, port=self.port)
            if self.client.connect():
                print(f"Connected to Modbus server at {self.host}:{self.port}")
                return True
            else:
                print("Failed to connect to Modbus server")
                return False
        except Exception as e:
            print(f"Error connecting to Modbus: {e}")
            return False
    
    def read_registers(self):
        """Read holding registers and convert to value"""
        try:
            if not self.client or not self.client.is_socket_open():
                if not self.connect_modbus():
                    return None, None
                    
            # Read holding registers
            response = self.client.read_holding_registers(
                address=self.address,
                count=self.count,
                slave=self.slave_id
            )
            
            if response.isError():
                print(f"Modbus error: {response}")
                return None, None
            
            # Get raw register values
            raw_values = response.registers
            
            # Convert 2 registers to 32-bit float
            # word_order=big, byte_order=big, formatters=float32
            if self.count == 2:
                # Pack two 16-bit registers as big-endian unsigned shorts
                # Then unpack as big-endian 32-bit float
                packed_data = struct.pack('>HH', raw_values[0], raw_values[1])
                value = struct.unpack('>f', packed_data)[0]
            else:
                print(f"Warning: Expected 2 registers, got {self.count}")
                value = raw_values[0] if raw_values else 0
            
            return value, raw_values
            
        except ModbusException as e:
            print(f"Modbus exception: {e}")
            return None, None
        except Exception as e:
            print(f"Error reading registers: {e}")
            return None, None
    
    def data_collection_loop(self):
        """Continuous data collection loop"""
        self.start_time = time.time()  # Record start time
        
        while self.running:
            value, raw_regs = self.read_registers()
            
            if value is not None:
                current_time = time.time()
                elapsed_seconds = current_time - self.start_time
                
                # Store data
                self.timestamps.append(elapsed_seconds)
                self.values.append(value)
                self.raw_registers.append(raw_regs)
                
                print(f"[{elapsed_seconds:.1f}s] "
                      f"Raw: {raw_regs} -> Value: {value:.6f}")
            
            time.sleep(self.update_interval)
    
    def animate(self, frame):
        """Animation function for matplotlib"""
        if len(self.timestamps) > 1:
            # Update line data
            self.line.set_data(self.timestamps, self.values)
            
            # Adjust axes
            self.ax.relim()
            self.ax.autoscale_view()
        
        return self.line,
    
    def start(self):
        """Start the live chart"""
        print("Starting Modbus live chart...")
        
        # Connect to Modbus
        if not self.connect_modbus():
            return
        
        # Start data collection thread
        self.running = True
        self.data_thread = threading.Thread(target=self.data_collection_loop)
        self.data_thread.daemon = True
        self.data_thread.start()
        
        # Start animation
        ani = animation.FuncAnimation(
            self.fig, self.animate, interval=100, blit=False, cache_frame_data=False
        )
        
        try:
            plt.show()
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the chart and cleanup"""
        self.running = False
        if self.client:
            self.client.close()
        if self.data_thread:
            self.data_thread.join(timeout=2)
        print("Chart stopped")

def main():
    """Main function to run the live chart"""
    
    # Configuration - modify these values for your setup
    CONFIG = {
        'host': '192.168.1.254',    # Change to your Modbus server IP
        'port': 502,                # Modbus TCP port
        'slave_id': 1,              # Your slave ID
        'address': 8834,            # Your register address
        'count': 2,                 # Number of registers to read
        'max_points': 100,          # Points to display on chart
        'update_interval': 1.0      # Update interval in seconds
    }
    
    print("Modbus Live Chart Configuration:")
    for key, value in CONFIG.items():
        print(f"  {key}: {value}")
    print()
    
    # Create and start the chart
    chart = ModbusLiveChart(**CONFIG)
    
    try:
        chart.start()
    except Exception as e:
        print(f"Error: {e}")
        chart.stop()

if __name__ == "__main__":
    main()
