# test_serial_ports.py
import serial
import time

print("Testing serial port pair...")
print("Make sure socat is running in another terminal!")

try:
    # Open both ports
    print("Opening /tmp/ttyV0...")
    port0 = serial.Serial('/tmp/ttyV0', 19200, timeout=2)
    time.sleep(0.5)  # Give it time to settle
    
    print("Opening /tmp/ttyV1...")
    port1 = serial.Serial('/tmp/ttyV1', 19200, timeout=2)
    time.sleep(0.5)  # Give it time to settle
    
    # Flush any existing data
    port0.reset_input_buffer()
    port1.reset_input_buffer()
    
    # Write from port1
    test_msg = b"HELLO"
    print(f"\nWriting to /tmp/ttyV1: {test_msg}")
    written = port1.write(test_msg)
    print(f"Bytes written: {written}")
    port1.flush()  # Make sure it's sent
    
    time.sleep(0.5)  # Wait for data to arrive
    
    # Check how many bytes are waiting
    waiting = port0.in_waiting
    print(f"Bytes waiting at /tmp/ttyV0: {waiting}")
    
    # Read from port0
    received = port0.read(100)
    print(f"Read from /tmp/ttyV0: {received}")
    
    if received == test_msg:
        print("\n✓ Serial ports working correctly!")
    else:
        print(f"\n✗ Serial ports NOT working!")
        print(f"   Expected: {test_msg}")
        print(f"   Received: {received}")
    
    port0.close()
    port1.close()
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
