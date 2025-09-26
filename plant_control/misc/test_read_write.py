from pymodbus.client import ModbusTcpClient
from pymodbus.pdu import ModbusExceptions

client = ModbusTcpClient("192.168.1.254", port=502)
client.connect()

# Read
result = client.read_holding_registers(0, 20)
print(result.registers[0])

# # Write
# try:
#     response = client.write_registers(9100, [16256,0])
#     print("Wrote to register 9100", response)
# except ModbusExceptio as e:
#     print(e)

# Read
result = client.read_holding_registers(0, 20)
print(result.registers[0])

client.close()
