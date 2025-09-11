#!/usr/bin/env python3
"""
Modbus TCP PLC Monitor
Monitors all registers from both PLCs every second
"""

import time
import threading
from datetime import datetime
from pymodbus.client.tcp import ModbusTcpClient
from pymodbus.exceptions import ModbusException
import os
import sys

# Register definitions (copy from the register map)
PLC1_REGISTERS = [
    # Coils (Digital Outputs)
    {"name": "PLC1_CONVEYOR_MOTOR_RUN", "address": 0x0000, "variable_id": 1, "data_type": "bool", "description": "Conveyor motor running status"},
    {"name": "PLC1_EMERGENCY_STOP", "address": 0x0001, "variable_id": 2, "data_type": "bool", "description": "Emergency stop activated"},
    {"name": "PLC1_MAIN_POWER", "address": 0x0002, "variable_id": 3, "data_type": "bool", "description": "Main power on/off"},
    {"name": "PLC1_STATION_1_ACTIVE", "address": 0x000A, "variable_id": 4, "data_type": "bool", "description": "Station 1 active status"},
    {"name": "PLC1_STATION_2_ACTIVE", "address": 0x000B, "variable_id": 5, "data_type": "bool", "description": "Station 2 active status"},
    
    # Discrete Inputs
    {"name": "PLC1_SAFETY_DOOR_CLOSED", "address": 0x10000, "variable_id": 6, "data_type": "bool", "description": "Safety door closed sensor"},
    {"name": "PLC1_PART_PRESENT_SENSOR", "address": 0x10001, "variable_id": 7, "data_type": "bool", "description": "Part present detection sensor"},
    {"name": "PLC1_LIMIT_SWITCH_1", "address": 0x10002, "variable_id": 8, "data_type": "bool", "description": "Limit switch 1 status"},
    {"name": "PLC1_LIMIT_SWITCH_2", "address": 0x10003, "variable_id": 9, "data_type": "bool", "description": "Limit switch 2 status"},
    {"name": "PLC1_TEMPERATURE_OK", "address": 0x1000A, "variable_id": 10, "data_type": "bool", "description": "Temperature within acceptable range"},
    
    # Holding Registers
    {"name": "PLC1_CONVEYOR_SPEED_SP", "address": 0x40000, "variable_id": 11, "data_type": "uint16", "description": "Conveyor speed setpoint (RPM)"},
    {"name": "PLC1_TEMPERATURE_SP", "address": 0x40001, "variable_id": 12, "data_type": "uint16", "description": "Temperature setpoint (°C * 10)"},
    {"name": "PLC1_PRODUCTION_RATE_TARGET", "address": 0x40002, "variable_id": 13, "data_type": "uint16", "description": "Production rate target"},
    {"name": "PLC1_MOTOR_CURRENT_LIMIT", "address": 0x4000A, "variable_id": 14, "data_type": "uint16", "description": "Motor current limit setting"},
    {"name": "PLC1_PRESSURE_SP", "address": 0x4000B, "variable_id": 15, "data_type": "uint16", "description": "System pressure setpoint"},
    {"name": "PLC1_PART_COUNTER", "address": 0x40014, "variable_id": 16, "data_type": "uint32", "description": "Total parts produced counter"},
    {"name": "PLC1_GOOD_PARTS_COUNT", "address": 0x40015, "variable_id": 17, "data_type": "uint16", "description": "Good parts count"},
    {"name": "PLC1_REJECTED_PARTS_COUNT", "address": 0x40016, "variable_id": 18, "data_type": "uint16", "description": "Rejected parts count"},
    
    # Input Registers
    {"name": "PLC1_CONVEYOR_SPEED_ACTUAL", "address": 0x30000, "variable_id": 19, "data_type": "uint16", "description": "Actual conveyor speed (RPM)"},
    {"name": "PLC1_TEMPERATURE_ACTUAL", "address": 0x30001, "variable_id": 20, "data_type": "uint16", "description": "Actual temperature (°C * 10) - Dynamic"},
    {"name": "PLC1_MOTOR_CURRENT_ACTUAL", "address": 0x30002, "variable_id": 21, "data_type": "uint16", "description": "Actual motor current (A * 10) - Dynamic"},
    {"name": "PLC1_SYSTEM_PRESSURE", "address": 0x30003, "variable_id": 22, "data_type": "uint16", "description": "Actual system pressure"},
    {"name": "PLC1_PRODUCTION_TIME", "address": 0x3000A, "variable_id": 23, "data_type": "uint16", "description": "Total production time (minutes)"},
    {"name": "PLC1_SYSTEM_EFFICIENCY", "address": 0x3000B, "variable_id": 24, "data_type": "uint16", "description": "System efficiency percentage"},
    {"name": "PLC1_VIBRATION_LEVEL", "address": 0x3000C, "variable_id": 25, "data_type": "uint16", "description": "Vibration level measurement"}
]

PLC2_REGISTERS = [
    # Coils (Digital Outputs)
    {"name": "PLC2_HEATING_SYSTEM_ON", "address": 0x0000, "variable_id": 26, "data_type": "bool", "description": "Heating system on/off"},
    {"name": "PLC2_COOLING_SYSTEM_ON", "address": 0x0001, "variable_id": 27, "data_type": "bool", "description": "Cooling system on/off"},
    {"name": "PLC2_FAN_1_RUNNING", "address": 0x0002, "variable_id": 28, "data_type": "bool", "description": "Fan 1 running status"},
    {"name": "PLC2_FAN_2_RUNNING", "address": 0x0003, "variable_id": 29, "data_type": "bool", "description": "Fan 2 running status"},
    {"name": "PLC2_DAMPER_1_OPEN", "address": 0x0004, "variable_id": 30, "data_type": "bool", "description": "Damper 1 open/closed"},
    {"name": "PLC2_DAMPER_2_OPEN", "address": 0x0005, "variable_id": 31, "data_type": "bool", "description": "Damper 2 open/closed"},
    {"name": "PLC2_ALARM_ACTIVE", "address": 0x000A, "variable_id": 32, "data_type": "bool", "description": "System alarm active"},
    
    # Discrete Inputs
    {"name": "PLC2_FILTER_OK", "address": 0x10000, "variable_id": 33, "data_type": "bool", "description": "Air filter status OK"},
    {"name": "PLC2_HIGH_TEMP_ALARM", "address": 0x10001, "variable_id": 34, "data_type": "bool", "description": "High temperature alarm"},
    {"name": "PLC2_LOW_TEMP_ALARM", "address": 0x10002, "variable_id": 35, "data_type": "bool", "description": "Low temperature alarm"},
    {"name": "PLC2_AIRFLOW_OK", "address": 0x10003, "variable_id": 36, "data_type": "bool", "description": "Airflow within acceptable range"},
    {"name": "PLC2_SYSTEM_READY", "address": 0x10004, "variable_id": 37, "data_type": "bool", "description": "HVAC system ready status"},
    {"name": "PLC2_MAINTENANCE_REQUIRED", "address": 0x1000A, "variable_id": 38, "data_type": "bool", "description": "Maintenance required indicator"},
    
    # Holding Registers
    {"name": "PLC2_TEMPERATURE_SP", "address": 0x40000, "variable_id": 39, "data_type": "uint16", "description": "Temperature setpoint (°C * 10)"},
    {"name": "PLC2_HUMIDITY_SP", "address": 0x40001, "variable_id": 40, "data_type": "uint16", "description": "Humidity setpoint (% * 10)"},
    {"name": "PLC2_FAN_SPEED_SP", "address": 0x40002, "variable_id": 41, "data_type": "uint16", "description": "Fan speed setpoint (%)"},
    {"name": "PLC2_DAMPER_POSITION_SP", "address": 0x40003, "variable_id": 42, "data_type": "uint16", "description": "Damper position setpoint (%)"},
    {"name": "PLC2_FILTER_CHANGE_INTERVAL", "address": 0x4000A, "variable_id": 43, "data_type": "uint16", "description": "Filter change interval (days)"},
    {"name": "PLC2_MAINTENANCE_INTERVAL", "address": 0x4000B, "variable_id": 44, "data_type": "uint16", "description": "Maintenance interval (days)"},
    {"name": "PLC2_OPERATING_HOURS", "address": 0x40014, "variable_id": 45, "data_type": "uint16", "description": "Total operating hours"},
    {"name": "PLC2_DAYS_SINCE_FILTER_CHANGE", "address": 0x40015, "variable_id": 46, "data_type": "uint16", "description": "Days since last filter change"},
    
    # Input Registers
    {"name": "PLC2_TEMPERATURE_ACTUAL", "address": 0x30000, "variable_id": 47, "data_type": "uint16", "description": "Actual temperature (°C * 10) - Dynamic"},
    {"name": "PLC2_HUMIDITY_ACTUAL", "address": 0x30001, "variable_id": 48, "data_type": "uint16", "description": "Actual humidity (% * 10) - Dynamic"},
    {"name": "PLC2_FAN_SPEED_ACTUAL", "address": 0x30002, "variable_id": 49, "data_type": "uint16", "description": "Actual fan speed (%)"},
    {"name": "PLC2_DAMPER_POSITION_ACTUAL", "address": 0x30003, "variable_id": 50, "data_type": "uint16", "description": "Actual damper position (%)"},
    {"name": "PLC2_AIRFLOW_CFM", "address": 0x3000A, "variable_id": 51, "data_type": "uint16", "description": "Airflow measurement (CFM)"},
    {"name": "PLC2_SYSTEM_EFFICIENCY", "address": 0x3000B, "variable_id": 52, "data_type": "uint16", "description": "System efficiency percentage"},
    {"name": "PLC2_POWER_CONSUMPTION", "address": 0x3000C, "variable_id": 53, "data_type": "uint16", "description": "Power consumption (W) - Dynamic"},
    {"name": "PLC2_OUTDOOR_TEMPERATURE", "address": 0x3000D, "variable_id": 54, "data_type": "uint16", "description": "Outdoor temperature (°C * 10)"}
]

# Dynamic registers that change during simulation
DYNAMIC_REGISTERS = [
    "PLC1_TEMPERATURE_ACTUAL",
    "PLC1_MOTOR_CURRENT_ACTUAL", 
    "PLC1_PART_COUNTER",
    "PLC2_TEMPERATURE_ACTUAL",
    "PLC2_HUMIDITY_ACTUAL",
    "PLC2_POWER_CONSUMPTION"
]

# PLC Connection info
PLC_CONFIGS = {
    "PLC1": {"host": "localhost", "port": 5020, "registers": PLC1_REGISTERS},
    "PLC2": {"host": "localhost", "port": 5021, "registers": PLC2_REGISTERS}
}

class ModbusMonitor:
    def __init__(self):
        self.clients = {}
        self.previous_values = {}
        self.running = False
        
    def connect_to_plcs(self):
        """Connect to both PLCs"""
        for plc_name, config in PLC_CONFIGS.items():
            try:
                client = ModbusTcpClient(config["host"], port=config["port"])
                if client.connect():
                    self.clients[plc_name] = client
                    print(f"✓ Connected to {plc_name} at {config['host']}:{config['port']}")
                else:
                    print(f"✗ Failed to connect to {plc_name}")
            except Exception as e:
                print(f"✗ Error connecting to {plc_name}: {e}")
    
    def get_register_type_and_address(self, address):
        """Determine register type based on address"""
        if 0x0000 <= address <= 0x0FFF:
            return "coil", address
        elif 0x10000 <= address <= 0x1FFFF:
            return "discrete_input", address - 0x10000
        elif 0x30000 <= address <= 0x3FFFF:
            return "input_register", address - 0x30000
        elif 0x40000 <= address <= 0x4FFFF:
            return "holding_register", address - 0x40000
        else:
            return "unknown", address
    
    def read_register(self, client, register):
        """Read a single register"""
        try:
            reg_type, modbus_address = self.get_register_type_and_address(register["address"])
            
            if reg_type == "coil":
                response = client.read_coils(modbus_address, 1, slave=1)
            elif reg_type == "discrete_input":
                response = client.read_discrete_inputs(modbus_address, 1, slave=1)
            elif reg_type == "input_register":
                response = client.read_input_registers(modbus_address, 1, slave=1)
            elif reg_type == "holding_register":
                response = client.read_holding_registers(modbus_address, 1, slave=1)
            else:
                return None, f"Unknown register type for address {register['address']:04X}"
            
            if response.isError():
                return None, f"Modbus Error: {response}"
            
            if reg_type in ["coil", "discrete_input"]:
                return response.bits[0], None
            else:
                return response.registers[0], None
                
        except Exception as e:
            return None, str(e)
    
    def format_value(self, register, value):
        """Format value based on register description"""
        if value is None:
            return "ERROR"
        
        if register["data_type"] == "bool":
            return "ON" if value else "OFF"
        
        # Handle temperature values (scaled by 10)
        if "temperature" in register["description"].lower() and "* 10" in register["description"]:
            return f"{value/10:.1f}°C"
        
        # Handle humidity values (scaled by 10)
        if "humidity" in register["description"].lower() and "* 10" in register["description"]:
            return f"{value/10:.1f}%"
        
        # Handle current values (scaled by 10)
        if "current" in register["description"].lower() and "* 10" in register["description"]:
            return f"{value/10:.1f}A"
        
        # Handle percentage values
        if "%" in register["description"] and "* 10" not in register["description"]:
            return f"{value}%"
        
        # Handle RPM values
        if "RPM" in register["description"]:
            return f"{value} RPM"
        
        # Handle power values
        if "power" in register["description"].lower() and "W" in register["description"]:
            return f"{value}W"
        
        # Default formatting
        return str(value)
    
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def display_values(self, values):
        """Display all register values"""
        self.clear_screen()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("=" * 100)
        print(f"MODBUS PLC MONITOR - {timestamp}")
        print("=" * 100)
        
        for plc_name in ["PLC1", "PLC2"]:
            if plc_name in values:
                print(f"\n{plc_name} - {'Manufacturing Line' if plc_name == 'PLC1' else 'HVAC System'}")
                print("-" * 90)
                
                # Group by register type
                register_types = {
                    "Coils (Digital Outputs)": [],
                    "Discrete Inputs": [], 
                    "Holding Registers": [],
                    "Input Registers": []
                }
                
                for reg_name, (value, error, register) in values[plc_name].items():
                    reg_type, _ = self.get_register_type_and_address(register["address"])
                    
                    if reg_type == "coil":
                        register_types["Coils (Digital Outputs)"].append((reg_name, value, error, register))
                    elif reg_type == "discrete_input":
                        register_types["Discrete Inputs"].append((reg_name, value, error, register))
                    elif reg_type == "holding_register":
                        register_types["Holding Registers"].append((reg_name, value, error, register))
                    elif reg_type == "input_register":
                        register_types["Input Registers"].append((reg_name, value, error, register))
                
                # Display each type
                for type_name, registers in register_types.items():
                    if registers:
                        print(f"\n  {type_name}:")
                        for reg_name, value, error, register in registers:
                            if error:
                                status = f"ERROR: {error}"
                                indicator = "✗"
                            else:
                                formatted_value = self.format_value(register, value)
                                
                                # Check if value changed
                                changed = ""
                                if reg_name in self.previous_values:
                                    if self.previous_values[reg_name] != value:
                                        changed = " 🔄" if reg_name in DYNAMIC_REGISTERS else " ⚠️"
                                
                                status = formatted_value + changed
                                indicator = "✓"
                            
                            # Truncate long names for better formatting
                            short_name = reg_name.replace(f"{plc_name}_", "")
                            print(f"    {indicator} {short_name:<25} [{register['address']:05X}] = {status}")
                            
                            # Store current value for change detection
                            if not error:
                                self.previous_values[reg_name] = value
        
        print("\n" + "=" * 100)
        print("Legend: ✓=OK ✗=Error 🔄=Dynamic(Expected) ⚠️=Changed")
        print("Press Ctrl+C to stop monitoring...")
    
    def monitor_loop(self):
        """Main monitoring loop"""
        self.running = True
        
        while self.running:
            try:
                all_values = {}
                
                # Read from all PLCs
                for plc_name, client in self.clients.items():
                    plc_values = {}
                    registers = PLC_CONFIGS[plc_name]["registers"]
                    
                    for register in registers:
                        value, error = self.read_register(client, register)
                        plc_values[register["name"]] = (value, error, register)
                    
                    all_values[plc_name] = plc_values
                
                # Display results
                self.display_values(all_values)
                
                # Wait 1 second
                time.sleep(1)
                
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(1)
    
    def disconnect(self):
        """Disconnect from all PLCs"""
        for plc_name, client in self.clients.items():
            try:
                client.close()
                print(f"Disconnected from {plc_name}")
            except:
                pass

def main():
    """Main function"""
    print("Modbus PLC Monitor")
    print("================")
    print("This script will monitor all registers from both PLCs every second.")
    print("Make sure the PLC simulator is running first!")
    print()
    
    monitor = ModbusMonitor()
    
    try:
        # Connect to PLCs
        print("Connecting to PLCs...")
        monitor.connect_to_plcs()
        
        if not monitor.clients:
            print("No PLCs connected. Make sure the simulator is running.")
            return
        
        print(f"Connected to {len(monitor.clients)} PLC(s)")
        print("Starting monitoring in 3 seconds...")
        time.sleep(3)
        
        # Start monitoring
        monitor.monitor_loop()
        
    except KeyboardInterrupt:
        print("\nShutting down monitor...")
    finally:
        monitor.disconnect()
        print("Monitor stopped.")

if __name__ == "__main__":
    main()
