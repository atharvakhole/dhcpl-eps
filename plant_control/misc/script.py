from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("192.168.1.254", port=502)
client.connect()

# Read and print values
print("6416:", client.read_holding_registers(6416, 2, slave=1).registers)
print("6418:", client.read_holding_registers(6418, 2, slave=1).registers)
print("60526:", client.read_holding_registers(60526, 2, slave=1).registers)
print("8616:", client.read_holding_registers(8616, 2, slave=1).registers)
print("9008:", client.read_holding_registers(9008, 2, slave=1).registers)
print("9010:", client.read_holding_registers(9010, 2, slave=1).registers)
print("17266:", client.read_holding_registers(17266, 2, slave=1).registers)
print("6746:", client.read_holding_registers(6746, 2, slave=1).registers)

client.close()
