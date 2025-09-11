#!/usr/bin/env python3
"""
Modbus TCP PLC Simulator
Simulates 2 PLCs with different register configurations for testing
Uses modern pymodbus 3.x API
"""

import asyncio
import threading
import time
import logging
import random
from pymodbus.server import StartAsyncTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

class PLCSimulator:
    def __init__(self, name, port, slave_id=1):
        self.name = name
        self.port = port
        self.slave_id = slave_id
        self.context = None
        self.server_task = None
        
    def setup_registers(self, coils_data=None, discrete_inputs_data=None, 
                       holding_registers_data=None, input_registers_data=None):
        """Setup the register data blocks for the PLC"""
        
        # Default data if none provided
        coils_data = coils_data or [0] * 100
        discrete_inputs_data = discrete_inputs_data or [0] * 100
        holding_registers_data = holding_registers_data or [0] * 100
        input_registers_data = input_registers_data or [0] * 100
        
        # Create data blocks
        store = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, discrete_inputs_data),    # Discrete Inputs
            co=ModbusSequentialDataBlock(0, coils_data),              # Coils
            hr=ModbusSequentialDataBlock(0, holding_registers_data),  # Holding Registers
            ir=ModbusSequentialDataBlock(0, input_registers_data),    # Input Registers
            zero_mode=True
        )
        
        self.context = ModbusServerContext(slaves={self.slave_id: store}, single=False)
        
    async def start_server(self):
        """Start the Modbus TCP server"""
        # Device identification
        identity = ModbusDeviceIdentification()
        identity.VendorName = 'PyModbus Simulator'
        identity.ProductCode = f'{self.name}'
        identity.VendorUrl = 'https://github.com/pymodbus-dev/pymodbus/'
        identity.ProductName = f'PLC Simulator {self.name}'
        identity.ModelName = f'Simulated PLC {self.name}'
        identity.MajorMinorRevision = '1.0'
        
        log.info(f"Starting {self.name} on port {self.port}")
        
        # Start async server
        await StartAsyncTcpServer(
            context=self.context,
            identity=identity,
            address=("localhost", self.port),
        )

def create_plc1():
    """Create PLC1 - Manufacturing Line Controller"""
    plc1 = PLCSimulator("PLC1-Manufacturing", 5020, slave_id=1)
    
    # Coils (Digital Outputs) - Equipment control
    coils = [0] * 100
    coils[0] = 1    # Conveyor Motor Running
    coils[1] = 0    # Emergency Stop
    coils[2] = 1    # Main Power
    coils[10] = 1   # Station 1 Active
    coils[11] = 0   # Station 2 Active
    
    # Discrete Inputs (Digital Inputs) - Sensors
    discrete_inputs = [0] * 100
    discrete_inputs[0] = 1   # Safety Door Closed
    discrete_inputs[1] = 0   # Part Present Sensor
    discrete_inputs[2] = 1   # Limit Switch 1
    discrete_inputs[3] = 0   # Limit Switch 2
    discrete_inputs[10] = 1  # Temperature OK
    
    # Holding Registers (Read/Write) - Setpoints and parameters
    holding_registers = [0] * 100
    holding_registers[0] = 1500   # Conveyor Speed Setpoint (RPM)
    holding_registers[1] = 250    # Temperature Setpoint (°C * 10)
    holding_registers[2] = 5      # Production Rate Target
    holding_registers[10] = 100   # Motor Current Limit
    holding_registers[11] = 85    # Pressure Setpoint
    holding_registers[20] = 12345 # Part Counter
    holding_registers[21] = 67    # Good Parts Count
    holding_registers[22] = 3     # Rejected Parts Count
    
    # Input Registers (Read Only) - Process values
    input_registers = [0] * 100
    input_registers[0] = 1480     # Actual Conveyor Speed
    input_registers[1] = 248      # Actual Temperature (°C * 10)
    input_registers[2] = 95       # Motor Current (A * 10)
    input_registers[3] = 82       # System Pressure
    input_registers[10] = 4500    # Production Time (minutes)
    input_registers[11] = 99      # System Efficiency %
    input_registers[12] = 45      # Vibration Level
    
    plc1.setup_registers(coils, discrete_inputs, holding_registers, input_registers)
    return plc1

def create_plc2():
    """Create PLC2 - HVAC System Controller"""
    plc2 = PLCSimulator("PLC2-HVAC", 5021, slave_id=1)
    
    # Coils (Digital Outputs) - HVAC control
    coils = [0] * 100
    coils[0] = 1    # Heating System On
    coils[1] = 0    # Cooling System On
    coils[2] = 1    # Fan 1 Running
    coils[3] = 1    # Fan 2 Running
    coils[4] = 0    # Damper 1 Open
    coils[5] = 1    # Damper 2 Open
    coils[10] = 0   # Alarm Active
    
    # Discrete Inputs (Digital Inputs) - HVAC sensors
    discrete_inputs = [0] * 100
    discrete_inputs[0] = 1   # Filter OK
    discrete_inputs[1] = 0   # High Temperature Alarm
    discrete_inputs[2] = 0   # Low Temperature Alarm
    discrete_inputs[3] = 1   # Airflow OK
    discrete_inputs[4] = 1   # System Ready
    discrete_inputs[10] = 0  # Maintenance Required
    
    # Holding Registers (Read/Write) - HVAC setpoints
    holding_registers = [0] * 100
    holding_registers[0] = 220    # Temperature Setpoint (°C * 10)
    holding_registers[1] = 450    # Humidity Setpoint (% * 10)
    holding_registers[2] = 75     # Fan Speed %
    holding_registers[3] = 50     # Damper Position %
    holding_registers[10] = 30    # Filter Change Interval (days)
    holding_registers[11] = 15    # Maintenance Interval (days)
    holding_registers[20] = 8760  # Operating Hours
    holding_registers[21] = 156   # Days Since Filter Change
    
    # Input Registers (Read Only) - HVAC measurements
    input_registers = [0] * 100
    input_registers[0] = 218      # Actual Temperature (°C * 10)
    input_registers[1] = 445      # Actual Humidity (% * 10)
    input_registers[2] = 73       # Actual Fan Speed %
    input_registers[3] = 48       # Actual Damper Position %
    input_registers[10] = 1250    # Airflow CFM
    input_registers[11] = 85      # System Efficiency %
    input_registers[12] = 245     # Power Consumption (W)
    input_registers[13] = 180     # Outdoor Temperature (°C * 10)
    
    plc2.setup_registers(coils, discrete_inputs, holding_registers, input_registers)
    return plc2

async def simulate_dynamic_values(plc1, plc2):
    """Simulate changing values in the PLCs"""
    while True:
        try:
            # Update PLC1 values (Manufacturing)
            if plc1.context:
                slave_context = plc1.context[1]
                
                # Simulate temperature fluctuation
                current_temp = slave_context.getValues(4, 1, 1)[0]  # Input register 1
                new_temp = max(240, min(260, current_temp + random.randint(-2, 2)))
                slave_context.setValues(4, 1, [new_temp])
                
                # Simulate production counter increment
                counter = slave_context.getValues(3, 20, 1)[0]  # Holding register 20
                slave_context.setValues(3, 20, [counter + 1])
                
                # Simulate motor current fluctuation
                current_amps = slave_context.getValues(4, 2, 1)[0]  # Input register 2
                new_amps = max(90, min(110, current_amps + random.randint(-2, 2)))
                slave_context.setValues(4, 2, [new_amps])
                
            # Update PLC2 values (HVAC)
            if plc2.context:
                slave_context = plc2.context[1]
                
                # Simulate temperature fluctuation
                current_temp = slave_context.getValues(4, 0, 1)[0]  # Input register 0
                new_temp = max(215, min(225, current_temp + random.randint(-1, 1)))
                slave_context.setValues(4, 0, [new_temp])
                
                # Simulate humidity changes
                current_humidity = slave_context.getValues(4, 1, 1)[0]  # Input register 1
                new_humidity = max(400, min(500, current_humidity + random.randint(-5, 5)))
                slave_context.setValues(4, 1, [new_humidity])
                
                # Simulate power consumption changes
                current_power = slave_context.getValues(4, 12, 1)[0]  # Input register 12
                new_power = max(200, min(300, current_power + random.randint(-10, 10)))
                slave_context.setValues(4, 12, [new_power])
                
        except Exception as e:
            log.error(f"Error in simulation: {e}")
            
        await asyncio.sleep(2)  # Update every 2 seconds

async def run_plc_server(plc):
    """Run a single PLC server"""
    await plc.start_server()

async def main_async():
    """Async main function to start both PLC simulators"""
    
    # Create PLCs
    plc1 = create_plc1()
    plc2 = create_plc2()
    
    # Create tasks for both servers and simulation
    plc1_task = asyncio.create_task(run_plc_server(plc1))
    plc2_task = asyncio.create_task(run_plc_server(plc2))
    sim_task = asyncio.create_task(simulate_dynamic_values(plc1, plc2))
    
    print("PLC simulators are running!")
    print("Press Ctrl+C to stop...")
    
    try:
        # Wait for all tasks
        await asyncio.gather(plc1_task, plc2_task, sim_task)
    except KeyboardInterrupt:
        print("\nShutting down PLC simulators...")
        plc1_task.cancel()
        plc2_task.cancel()
        sim_task.cancel()

def main():
    """Main function to start both PLC simulators"""
    print("=" * 60)
    print("Modbus TCP PLC Simulator")
    print("=" * 60)
    print("PLC1 (Manufacturing): localhost:5020")
    print("  - Slave ID: 1")
    print("  - Simulates manufacturing line with conveyors, sensors")
    print("  - Key registers: Speed(HR0), Temp(IR1), Counter(HR20)")
    print()
    print("PLC2 (HVAC): localhost:5021") 
    print("  - Slave ID: 1")
    print("  - Simulates HVAC system with temperature, humidity control")
    print("  - Key registers: TempSP(HR0), Humidity(IR1), Efficiency(IR11)")
    print()
    print("Register Types:")
    print("  - Coils (FC01/05): Digital outputs")
    print("  - Discrete Inputs (FC02): Digital inputs") 
    print("  - Holding Registers (FC03/06/16): Read/write values")
    print("  - Input Registers (FC04): Read-only values")
    print("=" * 60)
    
    try:
        # Run the async main function
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
        
if __name__ == "__main__":
    main()
