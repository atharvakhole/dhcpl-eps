#!/usr/bin/env python3
"""
Modbus TCP Pump Simulator
Simulates 2 Pumps on port 5020 with different slave IDs, and PLC2 on port 5021
Uses modern pymodbus 3.x API with actual pump register mappings
"""

import asyncio
import logging
from pymodbus.server import StartAsyncTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

def uint32_to_registers(value):
    """Convert a 32-bit unsigned integer to two 16-bit registers (big-endian)"""
    high = (value >> 16) & 0xFFFF
    low = value & 0xFFFF
    return [high, low]

def create_slave_context(name, coils_data=None, discrete_inputs_data=None, 
                        holding_registers_data=None, input_registers_data=None):
    """Create a slave context with register data blocks"""
    
    # Default data if none provided
    coils_data = coils_data or [0] * 100
    discrete_inputs_data = discrete_inputs_data or [0] * 100
    holding_registers_data = holding_registers_data or [0] * 500
    input_registers_data = input_registers_data or [0] * 100
    
    # Create data blocks
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, discrete_inputs_data),    # Discrete Inputs
        co=ModbusSequentialDataBlock(0, coils_data),              # Coils
        hr=ModbusSequentialDataBlock(0, holding_registers_data),  # Holding Registers
        ir=ModbusSequentialDataBlock(0, input_registers_data),    # Input Registers
        zero_mode=True
    )
    
    return store

def create_pump_context(pump_name, pump_id):
    """
    Create Pump context with actual register mappings
    Note: Modbus address 40001 = holding register address 0
          So 40101 = holding register address 100
    """
    
    # Initialize holding registers array
    holding_registers = [0] * 500
    
    # Register address 100 (40101): CURRENT_SETPOINT (actually Actual RPM) - uint16
    holding_registers[100] = 1200  # 1200 RPM actual
    
    # Register address 101 (40102): ACTUAL_RPM (actually RPM Percentage of 1500 max) - uint16
    holding_registers[101] = 80  # 80% of max (1200/1500 * 100)
    
    # Register address 102-103 (40103): MOTOR_POWER - uint32
    motor_power = uint32_to_registers(5240)  # 52.40 kW/h (with 0.01 scaling)
    holding_registers[102] = motor_power[0]
    holding_registers[103] = motor_power[1]
    
    # Register address 104 (40105): MOTOR_INPUT_VOLTAGE - uint16
    holding_registers[104] = 3800  # 380.0 V (with 0.1 scaling)
    
    # Register address 105-106 (40106): MOTOR_INPUT_CURRENT - uint32
    motor_current = uint32_to_registers(14250)  # 142.50 A (with 0.01 scaling)
    holding_registers[105] = motor_current[0]
    holding_registers[106] = motor_current[1]
    
    # Register address 107-108 (40108): SENSORLESS_HEAD - uint32
    sensorless_head = uint32_to_registers(4500)  # 45.00 (with 0.01 scaling)
    holding_registers[107] = sensorless_head[0]
    holding_registers[108] = sensorless_head[1]
    
    # Register address 109-110 (40110): SENSORLESS_FLOW - uint32
    sensorless_flow = uint32_to_registers(18500)  # 185.00 (with 0.01 scaling)
    holding_registers[109] = sensorless_flow[0]
    holding_registers[110] = sensorless_flow[1]
    
    # Register address 111-112 (40112): TOTAL_FLOW - uint32
    total_flow = uint32_to_registers(18200)  # 182.00 m3/hr (with 0.01 scaling)
    holding_registers[111] = total_flow[0]
    holding_registers[112] = total_flow[1]
    
    # Register address 113-114 (40114): TOTAL_POWER - uint32
    total_power = uint32_to_registers(5100)  # 51.00 kW/hr (with 0.01 scaling)
    holding_registers[113] = total_power[0]
    holding_registers[114] = total_power[1]
    
    # Register address 116-117 (40117): MAX_SENSORLESS_FLOW - uint32
    max_flow = uint32_to_registers(20000)  # 200.00 (with 0.01 scaling)
    holding_registers[116] = max_flow[0]
    holding_registers[117] = max_flow[1]
    
    # Register address 118-119 (40119): MAX_SENSORLESS_HEAD - uint32
    max_head = uint32_to_registers(5000)  # 50.00 (with 0.01 scaling)
    holding_registers[118] = max_head[0]
    holding_registers[119] = max_head[1]
    
    # Register address 122 (40123): PUMP_RUNNING_STATUS - uint16
    holding_registers[122] = 1  # 1 = Running
    
    # Register address 301 (40302): MODE - uint16
    holding_registers[301] = 2  # 0=Off, 1=Hand, 2=Auto
    
    # Register address 305 (40306): MANUAL_RPM_SP - uint16
    holding_registers[305] = 10000  # 1000.0 RPM (with 0.1 scaling)
    
    # Register address 306 (40307): AUTO_RPM_SP - uint16
    holding_registers[306] = 12000  # 1200.0 RPM (with 0.1 scaling)
    
    # Register address 308 (40309): START_PUMP - uint16
    holding_registers[308] = 1  # 1 = Start, 0 = Stop
    
    # Coils and discrete inputs (minimal for pumps)
    coils = [0] * 100
    coils[0] = 1    # Pump Running
    coils[1] = 0    # Emergency Stop
    coils[2] = 1    # Main Power
    
    discrete_inputs = [0] * 100
    discrete_inputs[0] = 1   # System Ready
    discrete_inputs[1] = 0   # Fault Condition
    discrete_inputs[2] = 1   # Normal Operation
    
    # Input registers (read-only values)
    input_registers = [0] * 100
    
    return create_slave_context(pump_name, coils, discrete_inputs, holding_registers, input_registers)

def create_plc2_context():
    """Create PLC2 - HVAC System Controller (kept from original)"""
    
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
    
    return create_slave_context("PLC2", coils, discrete_inputs, holding_registers, input_registers)

async def simulate_pump_control(context_5020):
    """Simulate pump start/stop behavior with delay and RPM control"""
    # Track previous states to detect changes
    pump_states = {
        5: {'last_start': 1, 'transitioning': False, 'current_rpm': 1200},   # PUMP1
        10: {'last_start': 1, 'transitioning': False, 'current_rpm': 1200}   # PUMP2
    }
    
    MAX_RPM = 1500
    
    while True:
        try:
            await asyncio.sleep(0.5)  # Check every 0.5 seconds
            
            for slave_id in [5, 10]:
                if context_5020 and slave_id in context_5020.slaves():
                    slave_context = context_5020[slave_id]
                    state = pump_states[slave_id]
                    
                    # Read current status
                    start_pump = slave_context.getValues(3, 308, 1)[0]  # HR 308: START_PUMP
                    running_status = slave_context.getValues(3, 122, 1)[0]  # HR 122: PUMP_RUNNING_STATUS
                    mode = slave_context.getValues(3, 301, 1)[0]  # HR 301: MODE (0=Off, 1=Hand, 2=Auto)
                    
                    # Determine target RPM based on mode
                    if mode == 1:  # Hand/Manual mode
                        manual_sp = slave_context.getValues(3, 305, 1)[0]  # HR 305: MANUAL_RPM_SP (scaled by 0.1)
                        target_rpm = manual_sp / 10.0  # Convert to actual RPM
                    elif mode == 2:  # Auto mode
                        auto_sp = slave_context.getValues(3, 306, 1)[0]  # HR 306: AUTO_RPM_SP (scaled by 0.1)
                        target_rpm = auto_sp / 10.0  # Convert to actual RPM
                    else:  # Off mode
                        target_rpm = 0
                    
                    # Limit target RPM to MAX_RPM
                    target_rpm = min(target_rpm, MAX_RPM)
                    
                    # Update RPM based on running status
                    if running_status == 1:
                        # Pump is running - ramp up/down to target RPM
                        if state['current_rpm'] < target_rpm:
                            state['current_rpm'] = min(state['current_rpm'] + 20, target_rpm)
                        elif state['current_rpm'] > target_rpm:
                            state['current_rpm'] = max(state['current_rpm'] - 20, target_rpm)
                    else:
                        # Pump is stopped - ramp down to 0
                        if state['current_rpm'] > 0:
                            state['current_rpm'] = max(state['current_rpm'] - 50, 0)
                    
                    # Update registers
                    # HR 100: CURRENT_SETPOINT (actually actual RPM)
                    actual_rpm = int(state['current_rpm'])
                    slave_context.setValues(3, 100, [actual_rpm])
                    
                    # HR 101: ACTUAL_RPM (actually RPM percentage of max 1500)
                    rpm_percentage = int((state['current_rpm'] / MAX_RPM) * 100)
                    slave_context.setValues(3, 101, [rpm_percentage])
                    
                    # Check if START_PUMP changed
                    if start_pump != state['last_start'] and not state['transitioning']:
                        state['last_start'] = start_pump
                        state['transitioning'] = True
                        
                        # Create async task to update status after delay
                        asyncio.create_task(
                            update_pump_status(slave_context, slave_id, start_pump, state)
                        )
                        
        except Exception as e:
            log.error(f"Error in pump control simulation: {e}")

async def update_pump_status(slave_context, slave_id, target_status, state):
    """Update pump running status after delay"""
    try:
        # Simulate startup/shutdown delay (3 seconds)
        await asyncio.sleep(3.0)
        
        # Update PUMP_RUNNING_STATUS register (HR 122)
        slave_context.setValues(3, 122, [target_status])
        
        status_text = "RUNNING" if target_status == 1 else "STOPPED"
        log.info(f"Pump {slave_id}: Status changed to {status_text}")
        
    except Exception as e:
        log.error(f"Error updating pump {slave_id} status: {e}")
    finally:
        state['transitioning'] = False

async def run_server_5020(context):
    """Run server on port 5020 with multiple slaves (PUMP1 and PUMP2)"""
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'PyModbus Simulator'
    identity.ProductCode = 'Multi-Slave-5020'
    identity.VendorUrl = 'https://github.com/pymodbus-dev/pymodbus/'
    identity.ProductName = 'Pump Simulator Port 5020'
    identity.ModelName = 'Multi-Pump Server'
    identity.MajorMinorRevision = '1.0'
    
    log.info("Starting Multi-Pump server on port 5020 (PUMP1=SlaveID:5, PUMP2=SlaveID:10)")
    
    await StartAsyncTcpServer(
        context=context,
        identity=identity,
        address=("localhost", 5020),
    )

async def run_server_5021(context):
    """Run server on port 5021"""
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'PyModbus Simulator'
    identity.ProductCode = 'PLC2-HVAC'
    identity.VendorUrl = 'https://github.com/pymodbus-dev/pymodbus/'
    identity.ProductName = 'PLC Simulator Port 5021'
    identity.ModelName = 'HVAC Controller'
    identity.MajorMinorRevision = '1.0'
    
    log.info("Starting PLC2 server on port 5021 (SlaveID:1)")
    
    await StartAsyncTcpServer(
        context=context,
        identity=identity,
        address=("localhost", 5021),
    )

async def main_async():
    """Async main function to start all simulators"""
    
    # Create slave contexts
    pump1_slave = create_pump_context("PUMP1", 1)
    pump2_slave = create_pump_context("PUMP2", 2)
    plc2_slave = create_plc2_context()
    
    # Create server contexts
    # Port 5020: Multiple slaves (PUMP1 and PUMP2)
    context_5020 = ModbusServerContext(slaves={
        5: pump1_slave,   # PUMP1
        10: pump2_slave   # PUMP2
    }, single=False)
    
    # Port 5021: Single slave (PLC2)
    context_5021 = ModbusServerContext(slaves={
        1: plc2_slave    # PLC2 - HVAC
    }, single=False)
    
    # Create tasks for both servers and pump control simulation
    server1_task = asyncio.create_task(run_server_5020(context_5020))
    server2_task = asyncio.create_task(run_server_5021(context_5021))
    pump_control_task = asyncio.create_task(simulate_pump_control(context_5020))
    
    print("\nModbus simulators are running!")
    print("Press Ctrl+C to stop...")
    
    try:
        # Wait for all tasks
        await asyncio.gather(server1_task, server2_task, pump_control_task)
    except KeyboardInterrupt:
        print("\nShutting down simulators...")
        server1_task.cancel()
        server2_task.cancel()
        pump_control_task.cancel()

def main():
    """Main function to start all simulators"""
    print("=" * 80)
    print("Modbus TCP Pump Simulator - Multi-Slave Configuration")
    print("=" * 80)
    print("\nPort 5020 (Multi-Slave Server - Pumps):")
    print("  PUMP1 - Slave ID: 5")
    print("    Key Registers (Holding Registers):")
    print("      HR 100 (40101): CURRENT_SETPOINT - Actually Actual RPM (1200 RPM)")
    print("      HR 101 (40102): ACTUAL_RPM - Actually RPM % of max 1500 (80%)")
    print("      HR 102-103 (40103): MOTOR_POWER - 52.40 kW/h (uint32)")
    print("      HR 104 (40105): MOTOR_INPUT_VOLTAGE - 380.0 V")
    print("      HR 105-106 (40106): MOTOR_INPUT_CURRENT - 142.50 A (uint32)")
    print("      HR 111-112 (40112): TOTAL_FLOW - 182.00 m3/hr (uint32)")
    print("      HR 122 (40123): PUMP_RUNNING_STATUS - 1 (Running)")
    print("      HR 301 (40302): MODE - 2 (Auto)")
    print("      HR 305 (40306): MANUAL_RPM_SP - 1000.0 RPM")
    print("      HR 306 (40307): AUTO_RPM_SP - 1200.0 RPM")
    print("      HR 308 (40309): START_PUMP - 1 (Start)")
    print()
    print("  PUMP2 - Slave ID: 10")
    print("    Same register mappings as PUMP1")
    print()
    print("Port 5021 (Single-Slave Server - HVAC):")
    print("  PLC2 (HVAC) - Slave ID: 1")
    print("    - Simulates HVAC system with temperature, humidity control")
    print("    - Key registers: TempSP(HR0), Humidity(IR1), Efficiency(IR11)")
    print()
    print("Register Types:")
    print("  - Coils (FC01/05): Digital outputs")
    print("  - Discrete Inputs (FC02): Digital inputs") 
    print("  - Holding Registers (FC03/06/16): Read/write values")
    print("  - Input Registers (FC04): Read-only values")
    print()
    print("Note: 32-bit values (uint32) occupy TWO consecutive registers")
    print("      Register addressing: 40001 = HR address 0, 40101 = HR address 100")
    print()
    print("Pump Control Behavior:")
    print("  - When START_PUMP (HR 308) is set to 1, PUMP_RUNNING_STATUS (HR 122)")
    print("    will change to 1 after a 3-second delay (simulating pump startup)")
    print("  - When START_PUMP is set to 0, PUMP_RUNNING_STATUS will change to 0")
    print("    after a 3-second delay (simulating pump shutdown)")
    print()
    print("RPM Behavior:")
    print("  - HR 100 (CURRENT_SETPOINT) shows the actual current RPM")
    print("  - HR 101 (ACTUAL_RPM) shows RPM as percentage of max (1500 RPM)")
    print("  - Target RPM determined by MODE:")
    print("    * MODE 1 (Hand): Uses MANUAL_RPM_SP (HR 305) / 10")
    print("    * MODE 2 (Auto): Uses AUTO_RPM_SP (HR 306) / 10")
    print("  - RPM ramps up/down gradually when pump is running")
    print("  - RPM ramps down to 0 when pump is stopped")
    print()
    print("To test pumps on same port:")
    print("  Connect to localhost:5020 and specify slave ID 5 (PUMP1) or 10 (PUMP2)")
    print("=" * 80)
    
    try:
        # Run the async main function
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
        
if __name__ == "__main__":
    main()
