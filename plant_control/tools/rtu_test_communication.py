from pymodbus.client import ModbusSerialClient
import time

def test_serial_connection(port, baudrate, slave_id):
    """Test if we can communicate with a slave"""
    
    print(f"\nTesting connection:")
    print(f"  Port: {port}")
    print(f"  Baudrate: {baudrate}")
    print(f"  Slave ID: {slave_id}")
    print("-" * 40)
    
    client = ModbusSerialClient(
        port=port,
        baudrate=baudrate,
        parity='N',      # None, Even, or Odd
        stopbits=1,
        bytesize=8,
        timeout=3
    )
    
    if not client.connect():
        print("✗ Failed to open serial port")
        return False
    
    print("✓ Serial port opened")
    
    # Try reading a register
    try:
        response = client.read_holding_registers(100, 1, slave=slave_id)  # Read register 0
        
        if response.isError():
            print(f"✗ Modbus error: {response}")
            return False
        
        print(f"✓ Successfully read from Slave {slave_id}")
        print(f"  Register 0 value: {response.registers[0]}")  # Should be 17
        return True
        
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False
    finally:
        client.close()

# Test with your settings
test_serial_connection(
    port='/dev/ttyACM0',  # Change for your system
    baudrate=19200,        # Your bus speed
    slave_id=1             # Start with slave 1
)
