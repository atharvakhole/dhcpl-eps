"""
Simple Connection Manager Test
Tests the connection manager with your existing PLC and register configurations
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add app to path
sys.path.append(str(Path(__file__).parent))

from app.core.connection_manager import (
    initialize_connections, shutdown_connections, 
    read_register, write_register, read_registers, 
    get_health_status, get_connection_status
)
from app.config import config_manager

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def test_connection_manager():
    """Test connection manager with existing configurations"""
    
    print("🔧 Testing Connection Manager")
    print("-" * 40)
    
    try:
        # Load your existing configurations
        print("Loading configurations...")
        plc_configs = config_manager.load_plc_configs()
        register_maps = config_manager.load_register_maps()
        
        print(f"Found {len(plc_configs)} PLCs:")
        for config in plc_configs:
            print(f"  - {config.plc_id}: {config.host}:{config.port}")
        
        # Initialize connection manager
        print("\nInitializing connections...")
        await initialize_connections(plc_configs, redis_url=None)
        
        print("Testing PLC connectivity...")
        plc_statuses = {}

        for config in plc_configs:
            try:
                # Force connection attempt
                value = await read_register(config.plc_id, 40001)
                plc_statuses[config.plc_id] = "connected"
                print(f"  🟢 {config.plc_id}: Connected (read value: {value})")
            except Exception as e:
                plc_statuses[config.plc_id] = "failed" 
                print(f"  🔴 {config.plc_id}: Failed ({e})")

        # Check health
        print("\nChecking PLC health...")
        health = await get_health_status()
        print(f"Status: {health['status']} ({health['connected_plcs']}/{health['total_plcs']} connected)")
        
        # Show connection details
        for plc_id, status in health['plc_status'].items():
            icon = "🟢" if status['state'] == 'connected' else "🔴"
            print(f"  {icon} {plc_id}: {status['state']}")
        
        # Test register operations on connected PLCs
        connected_plcs = [plc_id for plc_id, status in health['plc_status'].items() 
                         if status['state'] == 'connected']
        
        if connected_plcs:
            print(f"\nTesting register operations on {connected_plcs[0]}...")
            plc_id = connected_plcs[0]
            
            # Test single register read
            try:
                value = await read_register(plc_id, 40001)
                print(f"  ✅ Read register 40001: {value}")
            except Exception as e:
                print(f"  ❌ Read register 40001: {e}")
            
            # Test batch read
            try:
                values = await read_registers(plc_id, 40001, 3)
                print(f"  ✅ Batch read 40001-40003: {values}")
            except Exception as e:
                print(f"  ❌ Batch read: {e}")
            
            # Show register configuration if available
            if plc_id in register_maps:
                registers = register_maps[plc_id]
                print(f"\n  Configured registers for {plc_id}:")
                for addr, config in list(registers.items())[:5]:  # Show first 5
                    readonly = "R/O" if config.get('readonly') else "R/W"
                    critical = "CRITICAL" if config.get('critical') else ""
                    name = config.get('name', 'unnamed')
                    print(f"    {addr}: {name} [{readonly}] {critical}")
        
        else:
            print("\n❌ No PLCs connected")
            print("Check:")
            print("  - PLC IP addresses are correct")
            print("  - PLCs are powered and accessible")
            print("  - Modbus TCP is enabled on PLCs")
            print("  - Network connectivity")
        
        # Show connection metrics
        print(f"\nConnection metrics:")
        all_status = get_connection_status()
        for plc_id, status in all_status.items():
            metrics = status['metrics']
            print(f"  {plc_id}:")
            print(f"    Requests: {metrics['total_requests']} (Success rate: {metrics['success_rate']:.1f}%)")
            if metrics['avg_response_time'] > 0:
                print(f"    Avg response: {metrics['avg_response_time']:.3f}s")
            if metrics['last_error']:
                print(f"    Last error: {metrics['last_error']}")
    
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nShutting down...")
        await shutdown_connections()
        print("✅ Test complete")

if __name__ == "__main__":
    asyncio.run(test_connection_manager())
