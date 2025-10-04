#!/usr/bin/env python3
"""
Simple Modbus RTU Simulator - Fixed for pymodbus 3.x
"""
from pymodbus.server import StartSerialServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.framer import ModbusRtuFramer
import logging
import sys

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger()

def run_modbus_simulator():
    """Run the Modbus RTU simulator"""
    
    # Initialize data store with some default values
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0] * 100),  # Discrete Inputs
        co=ModbusSequentialDataBlock(0, [0] * 100),  # Coils
        hr=ModbusSequentialDataBlock(0, [17] * 100), # Holding Registers
        ir=ModbusSequentialDataBlock(0, [45] * 100)  # Input Registers
    )
    
    # Create context with slave ID 1
    context = ModbusServerContext(slaves={1: store}, single=False)
    
    # Device identification
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'Pymodbus'
    identity.ProductCode = 'PM'
    identity.VendorUrl = 'http://github.com/pymodbus-dev/pymodbus/'
    identity.ProductName = 'Pymodbus RTU Simulator'
    identity.ModelName = 'RTU Simulator'
    identity.MajorMinorRevision = '1.0'
    
    # Serial configuration - MUST MATCH CLIENT
    port = '/tmp/ttyV0'
    baudrate = 19200
    
    print("\n" + "="*60)
    print("Modbus RTU Simulator Starting")
    print("="*60)
    print(f"Serial Port: {port}")
    print(f"Baudrate: {baudrate}")
    print(f"Parity: N")
    print(f"Slave ID: 1")
    print("\nData Store:")
    print("  - Holding Registers (0-99): Value = 17")
    print("  - Input Registers (0-99): Value = 45")
    print("\nDebug logging enabled")
    print("Waiting for requests...")
    print("="*60 + "\n")
    
    # Verify port exists
    import os
    if not os.path.exists(port):
        print(f"\n⚠ WARNING: Port {port} does not exist!")
        print("Make sure socat is running:")
        print("  socat -d -d pty,raw,echo=0,link=/tmp/ttyV0 pty,raw,echo=0,link=/tmp/ttyV1")
        sys.exit(1)
    
    # Start the RTU server with explicit framer
    try:
        StartSerialServer(
            context=context,
            framer=ModbusRtuFramer,  # Explicitly specify RTU framer
            identity=identity,
            port=port,
            baudrate=baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=1
        )
    except KeyboardInterrupt:
        print("\n\nSimulator stopped by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    run_modbus_simulator()
