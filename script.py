#!/usr/bin/env python3
"""
Simple Modbus TCP test script for monitoring PLC registers
"""

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
import time
import sys

# PLC Configuration
PLC_HOST = "192.168.1.254"
PLC_PORT = 502
UNIT_ID = 1  # Try 1 first, then 255 if that doesn't work
TIMEOUT = 5

def test_modbus_connection():
    """Test basic connectivity to the PLC"""
    print(f"Testing connection to {PLC_HOST}:{PLC_PORT}")
    
    try:
        client = ModbusTcpClient(host=PLC_HOST, port=PLC_PORT, timeout=TIMEOUT)
        
        if client.connect():
            print("✓ Successfully connected to PLC")
            
            # Test reading device identification (if supported)
            try:
                device_info = client.read_device_information(unit=UNIT_ID)
                if not device_info.isError():
                    print("Device Information:")
                    for key, value in device_info.information.items():
                        print(f"  {key}: {value}")
            except:
                print("  Device identification not supported")
            
            client.close()
            return True
        else:
            print("✗ Failed to connect to PLC")
            return False
            
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False

def read_register_range(client, register_type, start_addr, count, description=""):
    """Read a range of registers and display results"""
    print(f"\n--- {description} ---")
    print(f"Reading {register_type} registers {start_addr} to {start_addr + count - 1}")
    
    try:
        if register_type == "holding":
            result = client.read_holding_registers(start_addr, count, unit=UNIT_ID)
        elif register_type == "input":
            result = client.read_input_registers(start_addr, count, unit=UNIT_ID)
        elif register_type == "coil":
            result = client.read_coils(start_addr, count, unit=UNIT_ID)
        elif register_type == "discrete":
            result = client.read_discrete_inputs(start_addr, count, unit=UNIT_ID)
        else:
            print(f"Unknown register type: {register_type}")
            return
        
        if result.isError():
            print(f"  Error reading registers: {result}")
            return
        
        # Display results
        if register_type in ["holding", "input"]:
            values = result.registers
            for i, value in enumerate(values):
                addr = start_addr + i
                print(f"  Register {addr}: {value} (0x{value:04X})")
        else:  # coils or discrete inputs
            values = result.bits
            for i, value in enumerate(values):
                addr = start_addr + i
                print(f"  Bit {addr}: {value}")
                
    except ModbusException as e:
        print(f"  Modbus error: {e}")
    except Exception as e:
        print(f"  Error: {e}")

def scan_for_active_registers(client):
    """Scan common register ranges to find active/non-zero values"""
    print("\n=== Scanning for Active Registers ===")
    
    # Common register ranges to check
    scan_ranges = [
        ("holding", 0, 20, "Holding 0-19"),
        ("holding", 40000, 20, "Holding 40000-40019 (4x format)"),
        ("holding", 1, 20, "Holding 1-20"),
        ("input", 0, 20, "Input 0-19"),
        ("input", 30000, 20, "Input 30000-30019 (3x format)"),
        ("coil", 0, 20, "Coils 0-19"),
        ("discrete", 0, 20, "Discrete Inputs 0-19"),
    ]
    
    active_registers = []
    
    for reg_type, start_addr, count, description in scan_ranges:
        try:
            if reg_type == "holding":
                result = client.read_holding_registers(start_addr, count, unit=UNIT_ID)
                if not result.isError():
                    for i, value in enumerate(result.registers):
                        if value != 0:
                            active_registers.append((reg_type, start_addr + i, value))
                            
            elif reg_type == "input":
                result = client.read_input_registers(start_addr, count, unit=UNIT_ID)
                if not result.isError():
                    for i, value in enumerate(result.registers):
                        if value != 0:
                            active_registers.append((reg_type, start_addr + i, value))
                            
            elif reg_type == "coil":
                result = client.read_coils(start_addr, count, unit=UNIT_ID)
                if not result.isError():
                    for i, value in enumerate(result.bits):
                        if value:
                            active_registers.append((reg_type, start_addr + i, value))
                            
            elif reg_type == "discrete":
                result = client.read_discrete_inputs(start_addr, count, unit=UNIT_ID)
                if not result.isError():
                    for i, value in enumerate(result.bits):
                        if value:
                            active_registers.append((reg_type, start_addr + i, value))
        except:
            continue  # Skip ranges that fail
    
    if active_registers:
        print("\nActive (non-zero) registers found:")
        for reg_type, addr, value in active_registers[:20]:  # Show first 20
            print(f"  {reg_type.capitalize()} {addr}: {value}")
        if len(active_registers) > 20:
            print(f"  ... and {len(active_registers) - 20} more")
    else:
        print("\nNo active registers found in scanned ranges")
    
    return active_registers

def monitor_registers(client, registers_to_monitor, interval=2):
    """Continuously monitor specific registers"""
    if not registers_to_monitor:
        print("No registers specified for monitoring")
        return
    
    print(f"\n=== Monitoring Registers (every {interval} seconds) ===")
    print("Press Ctrl+C to stop monitoring")
    
    try:
        while True:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{timestamp}]")
            
            for reg_type, addr, _ in registers_to_monitor[:5]:  # Monitor first 5
                try:
                    if reg_type == "holding":
                        result = client.read_holding_registers(addr, 1, unit=UNIT_ID)
                        value = result.registers[0] if not result.isError() else "Error"
                    elif reg_type == "input":
                        result = client.read_input_registers(addr, 1, unit=UNIT_ID)
                        value = result.registers[0] if not result.isError() else "Error"
                    elif reg_type == "coil":
                        result = client.read_coils(addr, 1, unit=UNIT_ID)
                        value = result.bits[0] if not result.isError() else "Error"
                    elif reg_type == "discrete":
                        result = client.read_discrete_inputs(addr, 1, unit=UNIT_ID)
                        value = result.bits[0] if not result.isError() else "Error"
                    
                    print(f"  {reg_type.capitalize()} {addr}: {value}")
                    
                except Exception as e:
                    print(f"  {reg_type.capitalize()} {addr}: Error - {e}")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped")

def main():
    print("Modbus PLC Test Script")
    print("=" * 50)
    
    # Test connection first
    if not test_modbus_connection():
        print("\nCannot proceed - connection failed")
        sys.exit(1)
    
    # Create client for register operations
    client = ModbusTcpClient(host=PLC_HOST, port=PLC_PORT, timeout=TIMEOUT)
    
    if not client.connect():
        print("Failed to connect for register testing")
        sys.exit(1)
    
    try:
        # Scan for active registers
        # active_registers = scan_for_active_registers(client)
        active_registers = None
        
        # Ask user if they want to monitor
        if active_registers:
            response = input(f"\nFound {len(active_registers)} active registers. Monitor them? (y/n): ")
            if response.lower() == 'y':
                monitor_registers(client, active_registers)
        else:
            # Test some common ranges anyway
            print("\n=== Testing Common Register Ranges ===")
            read_register_range(client, "holding", 0, 10, "Holding Registers 0-9")
            read_register_range(client, "input", 0, 10, "Input Registers 0-9")
            read_register_range(client, "coil", 0, 16, "Coils 0-15")
            read_register_range(client, "discrete", 0, 16, "Discrete Inputs 0-15")
            
            # Try 4x and 3x addressing if PLCs use that convention
            read_register_range(client, "holding", 40000, 10, "Holding 40000-40009 (4x addressing)")
            read_register_range(client, "input", 30000, 10, "Input 30000-30009 (3x addressing)")
    
    finally:
        client.close()
        print("\nConnection closed")

if __name__ == "__main__":
    main()
