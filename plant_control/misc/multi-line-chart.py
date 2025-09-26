#!/usr/bin/env python3
"""
Live Line Chart for Multiple Modbus Registers
Reads multiple holding registers and displays real-time data visualization
"""

import time
import threading
from collections import deque
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
import struct
import math
import signal
import sys

class ModbusMultiChart:
    def __init__(self, host='localhost', port=502, slave_id=1, registers=None, 
                 max_points=100, update_interval=1.0, charts_per_row=2):
        """
        Initialize the Modbus multi-register live chart
        
        Args:
            host: Modbus server IP address
            port: Modbus server port
            slave_id: Slave device ID
            registers: List of register configurations
            max_points: Maximum points to display on each chart
            update_interval: Update interval in seconds
            charts_per_row: Number of charts per row in subplot grid
        """
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.registers = registers or []
        self.max_points = max_points
        self.update_interval = update_interval
        self.charts_per_row = charts_per_row
        
        # Data storage for each register
        self.data = {}
        for i, reg_config in enumerate(self.registers):
            self.data[i] = {
                'timestamps': deque(maxlen=max_points),
                'values': deque(maxlen=max_points),
                'raw_registers': deque(maxlen=max_points)
            }
        
        self.start_time = None
        
        # Modbus client
        self.client = None
        self.running = False
        
        # Setup plots
        self.setup_plots()
        
        # Data reading thread
        self.data_thread = None
        self.animation = None
        
        # Signal handler for clean shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def setup_plots(self):
        """Setup matplotlib subplots for multiple registers"""
        num_registers = len(self.registers)
        if num_registers == 0:
            return
            
        # Calculate subplot grid
        rows = math.ceil(num_registers / self.charts_per_row)
        cols = min(num_registers, self.charts_per_row)
        
        # Create figure and subplots
        self.fig, self.axes = plt.subplots(rows, cols, figsize=(6*cols, 4*rows))
        
        # Handle single subplot case
        if num_registers == 1:
            self.axes = [self.axes]
        elif rows == 1:
            self.axes = list(self.axes) if hasattr(self.axes, '__iter__') else [self.axes]
        else:
            self.axes = self.axes.flatten()
        
        # Remove extra subplots if any
        for i in range(num_registers, len(self.axes)):
            self.fig.delaxes(self.axes[i])
        
        # Setup each subplot
        self.lines = []
        for i, reg_config in enumerate(self.registers):
            ax = self.axes[i]
            
            # Create line plot
            line, = ax.plot([], [], 'b-', linewidth=2, 
                           label=f"Register {reg_config['address']}")
            self.lines.append(line)
            
            # Configure subplot
            ax.set_xlabel('Time (seconds)')
            ax.set_ylabel(reg_config.get('unit', 'Value'))
            # Get the name or default
            chart_name = reg_config.get('name', f"Register {reg_config['address']}")
            ax.set_title(chart_name)
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
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
    
    def decode_register_value(self, raw_values, reg_config):
        """Decode register value based on configuration"""
        data_type = reg_config.get('data_type', 'float32')
        count = reg_config.get('count', 2)
        
        if data_type == 'float32' and count == 2:
            # 32-bit float: word_order=big, byte_order=big
            packed_data = struct.pack('>HH', raw_values[0], raw_values[1])
            value = struct.unpack('>f', packed_data)[0]
        elif data_type == 'int32' and count == 2:
            # 32-bit signed integer
            packed_data = struct.pack('>HH', raw_values[0], raw_values[1])
            value = struct.unpack('>i', packed_data)[0]
        elif data_type == 'uint32' and count == 2:
            # 32-bit unsigned integer
            value = (raw_values[0] << 16) | raw_values[1]
        elif data_type == 'int16' and count == 1:
            # 16-bit signed integer
            value = struct.unpack('>h', struct.pack('>H', raw_values[0]))[0]
        elif data_type == 'uint16' and count == 1:
            # 16-bit unsigned integer
            value = raw_values[0]
        else:
            # Default: use first register as is
            value = raw_values[0] if raw_values else 0
            
        # Apply scaling if specified
        scale = reg_config.get('scale', 1.0)
        offset = reg_config.get('offset', 0.0)
        value = (value * scale) + offset
        
        return value
    
    def read_register(self, reg_config):
        """Read a single register configuration"""
        try:
            if not self.client or not self.client.is_socket_open():
                if not self.connect_modbus():
                    return None, None
                    
            # Read holding registers
            response = self.client.read_holding_registers(
                address=reg_config['address'],
                count=reg_config.get('count', 2),
                slave=self.slave_id
            )
            
            if response.isError():
                print(f"Modbus error for register {reg_config['address']}: {response}")
                return None, None
            
            # Get raw register values
            raw_values = response.registers
            
            # Decode based on configuration
            value = self.decode_register_value(raw_values, reg_config)
            
            return value, raw_values
            
        except ModbusException as e:
            print(f"Modbus exception for register {reg_config['address']}: {e}")
            return None, None
        except Exception as e:
            print(f"Error reading register {reg_config['address']}: {e}")
            return None, None
    
    def data_collection_loop(self):
        """Continuous data collection loop for all registers"""
        self.start_time = time.time()
        
        while self.running:
            current_time = time.time()
            elapsed_seconds = current_time - self.start_time
            
            # Read all registers
            for i, reg_config in enumerate(self.registers):
                value, raw_regs = self.read_register(reg_config)
                
                if value is not None:
                    # Store data
                    self.data[i]['timestamps'].append(elapsed_seconds)
                    self.data[i]['values'].append(value)
                    self.data[i]['raw_registers'].append(raw_regs)
                    
                    print(f"[{elapsed_seconds:.1f}s] "
                          f"Reg {reg_config['address']}: {raw_regs} -> {value:.6f} "
                          f"{reg_config.get('unit', '')}")
            
            time.sleep(self.update_interval)
    
    def signal_handler(self, signum, frame):
        """Handle keyboard interrupt signal"""
        print("\nReceived interrupt signal, stopping chart...")
        self.stop()
        plt.close('all')
        sys.exit(0)
    
    def animate(self, frame):
        """Animation function for matplotlib"""
        updated_lines = []
        
        for i, (line, reg_config) in enumerate(zip(self.lines, self.registers)):
            if len(self.data[i]['timestamps']) > 1:
                # Update line data
                line.set_data(self.data[i]['timestamps'], self.data[i]['values'])
                updated_lines.append(line)
                
                # Adjust axes
                ax = self.axes[i]
                ax.relim()
                ax.autoscale_view()
        
        return updated_lines
    
    def start(self):
        """Start the live chart"""
        print("Starting Modbus multi-register live chart...")
        print(f"Monitoring {len(self.registers)} registers:")
        for reg_config in self.registers:
            print(f"  - Address {reg_config['address']}: {reg_config.get('name', 'Unnamed')}")
        print("Press Ctrl+C to stop")
        print()
        
        # Connect to Modbus
        if not self.connect_modbus():
            return
        
        # Start data collection thread
        self.running = True
        self.data_thread = threading.Thread(target=self.data_collection_loop)
        self.data_thread.daemon = True
        self.data_thread.start()
        
        # Start animation
        self.animation = animation.FuncAnimation(
            self.fig, self.animate, interval=100, blit=False, cache_frame_data=False
        )
        
        try:
            # Use non-blocking show to avoid Tkinter issues
            plt.ion()  # Turn on interactive mode
            plt.show(block=True)
        except Exception as e:
            print(f"Error in plot display: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the chart and cleanup"""
        print("Stopping chart...")
        self.running = False
        
        # Stop animation
        if self.animation:
            self.animation.event_source.stop()
        
        # Close Modbus connection
        if self.client:
            self.client.close()
        
        # Wait for data thread to finish
        if self.data_thread and self.data_thread.is_alive():
            self.data_thread.join(timeout=2)
        
        # Close all matplotlib figures
        plt.close('all')
        print("Chart stopped")

def main():
    """Main function to run the live chart"""
    
    # Register configurations - modify these for your setup
    REGISTERS = [
        {
            'address': 8834,
            'count': 2,
            'data_type': 'float32',
            'name': 'Temperature',
            'unit': '°C',
            'scale': 1.0,
            'offset': 0.0
        },
        {
            'address': 8836,
            'count': 2,
            'data_type': 'float32',
            'name': 'Pressure',
            'unit': 'bar',
            'scale': 1.0,
            'offset': 0.0
        },
        {
            'address': 8838,
            'count': 2,
            'data_type': 'float32',
            'name': 'Flow Rate',
            'unit': 'L/min',
            'scale': 1.0,
            'offset': 0.0
        },
        {
            'address': 8840,
            'count': 2,
            'data_type': 'float32',
            'name': 'Level',
            'unit': '%',
            'scale': 1.0,
            'offset': 0.0
        }
        # Add more registers as needed...
    ]
    
    # Connection configuration
    CONFIG = {
        'host': '192.168.1.254',    # Change to your Modbus server IP
        'port': 502,                # Modbus TCP port
        'slave_id': 1,              # Your slave ID
        'registers': REGISTERS,     # Register configurations
        'max_points': 100,          # Points to display on each chart
        'update_interval': 1.0,     # Update interval in seconds
        'charts_per_row': 2         # Charts per row in grid
    }
    
    print("Modbus Multi-Register Live Chart Configuration:")
    print(f"  Host: {CONFIG['host']}:{CONFIG['port']}")
    print(f"  Slave ID: {CONFIG['slave_id']}")
    print(f"  Update interval: {CONFIG['update_interval']}s")
    print(f"  Max points per chart: {CONFIG['max_points']}")
    print(f"  Charts per row: {CONFIG['charts_per_row']}")
    print()
    
    # Create and start the chart
    chart = ModbusMultiChart(**CONFIG)
    
    try:
        chart.start()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received")
        chart.stop()
    except Exception as e:
        print(f"Error: {e}")
        chart.stop()

if __name__ == "__main__":
    main()
