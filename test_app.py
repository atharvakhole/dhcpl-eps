import asyncio
import logging
import sys
from pathlib import Path

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder

from app.core.connection_manager import connection_manager
from app.core.tag_service import TagService
from app.utilities.registers import convert_modbus_address

# Add app to path
sys.path.append(str(Path(__file__).parent))

from app.core.connection_manager import (
    connection_manager,
    initialize_connections, shutdown_connections, 
    read_register, write_register, read_registers, 
    get_health_status, get_connection_status
)
from app.config import config_manager

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


async def test_app():
    """Test app with existing configurations"""
    
    print("🔧 Testing App")
    print("-" * 40)
    
    try:
        # Load your existing configurations
        print("Loading configurations...")
        plc_configs = config_manager.load_plc_configs()
        register_maps = config_manager.load_register_maps()

        print(f"Found {len(plc_configs)} PLCs:")
        for config in plc_configs:
            print(f"  - {config.plc_id}: {config.host}:{config.port} :{config.vendor}: {config.addressing_scheme}")

        print(f"Found {len(register_maps)} registers:")
        for plc_name, register_map in register_maps.items():
            print(plc_name, register_map)

        # print("Testing convert_modbus_address")
        # print(convert_modbus_address(6879, config_manager.get_plc_config("EPS01").addressing_scheme, register_config=config_manager.get_register_config("EPS01", 6879)))
        #
        #
        # print("Testing connection_manager")
        # await connection_manager.initialize(plc_configs, config_manager)
        #
        # try:
        #     result = await connection_manager.read_registers('EPS01', 7449, 2)
        #     print(f"result: {result}")
        #
        # except Exception as e:
        #     print(e)
        #
        #
        # builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
        # builder.add_32bit_float(17.59)
        # payload = builder.to_registers()
        # for register in payload:
        #     print(register)
        #
        # try:
        #     result = await connection_manager.write_registers('EPS01', 6879, payload)
        #     print(result)
        #
        # except Exception as e:
        #     print(e)
        #
        #
        # builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
        # builder.add_bits([True])
        # payload = builder.to_registers()
        # for register in payload:
        #     print(register)
        #
        # try:
        #     result = await connection_manager.write_registers('EPS01', 7449, payload)
        #     print(result)
        #
        # except Exception as e:
        #     print(e)
        #
        #
        # print(connection_manager.get_connection_status())

        tag_service = TagService()
        print(tag_service._construct_payload("EPS01", 7449, 1))
        print(tag_service._construct_payload("EPS01", 6879, 1))


    except Exception as e:
        print(e)


if __name__ == "__main__":
    asyncio.run(test_app())
