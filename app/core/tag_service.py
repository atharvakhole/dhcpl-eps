from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder
from app.config import config_manager
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)
class TagService:
    """
    Provides a high level interface to read from and write to registers

    Handles the following:
    1. Address Translation: Convert logical tag names to physical addresses using vendor mapping rules
    2. Data Type Handling: Determine register count needed based on data types (e.g., float32 = 2 registers)
    3. Encoding/Decoding: Convert between application values and raw register data
    4. Payload Construction: Build proper byte arrays for writes
    5. Validation: Check value ranges, readonly flags, data type compatibility
    """

    def read_tag(self, plc_id, tag_name):
        pass


    def write_tag(self, plc_id):
        pass

    def _is_valid_data(self, plc_id, address, data) -> bool:
        register_config: Dict[str, Any] | None = config_manager.get_register_config(plc_id, address)
        if not register_config:
            raise ValueError(f"No register config for {plc_id} register: {address}")

        logger.debug(f"Validating data for PLC {plc_id}, register {address}: {data}")

        # Check if register is readonly
        if register_config.get('readonly', False):
            logger.error(f"Attempt to write to readonly register {address} on PLC {plc_id}")
            raise ValueError(f"Cannot write to readonly register {address} on PLC {plc_id}")

        # Check if data is None
        if data is None:
            logger.warning(f"Received None data for register {address} on PLC {plc_id}")
            return False

        # Get validation parameters
        min_value = register_config.get('min_value')
        max_value = register_config.get('max_value')
        tag_type = register_config.get('tag_type', '').lower()

        logger.debug(f"Validation parameters - min: {min_value}, max: {max_value}, tag_type: {tag_type}")

        # Convert data to numeric if possible
        try:
            if isinstance(data, bool):
                numeric_data = float(data)
            elif isinstance(data, (int, float)):
                numeric_data = float(data)
            else:
                # Try to convert string to float
                numeric_data = float(data)

            logger.debug(f"Converted data to numeric: {numeric_data}")
        except (ValueError, TypeError):
            logger.warning(f"Failed to convert data '{data}' to numeric for register {address} on PLC {plc_id}")
            return False

        # Validate range if min/max values are specified
        if min_value is not None and numeric_data < min_value:
            logger.warning(f"Data {numeric_data} below minimum {min_value} for register {address} on PLC {plc_id}")
            return False

        if max_value is not None and numeric_data > max_value:
            logger.warning(f"Data {numeric_data} above maximum {max_value} for register {address} on PLC {plc_id}")
            return False

        # Additional validation for digital tags
        if tag_type == 'digital':
            # Digital tags should only accept 0, 1, True, or False
            if numeric_data not in [0.0, 1.0]:
                logger.warning(f"Digital register {address} on PLC {plc_id} received invalid value {numeric_data} (must be 0 or 1)")
                return False

        # Check for integer values where expected
        if tag_type == 'digital' or register_config.get('stored_as') in ['int16', 'int32', 'uint16', 'uint32']:
            if numeric_data != int(numeric_data):
                logger.warning(f"Integer register {address} on PLC {plc_id} received non-integer value {numeric_data}")
                return False

        logger.debug(f"Data validation successful for register {address} on PLC {plc_id}")
        return True


    def _construct_payload(self, plc_id, address, data) -> List[Any]:
        logger.debug(f"Constructing payload for {plc_id}: {address} with data {data}")
        if not self._is_valid_data(plc_id, address, data):
            raise ValueError(f"Invalid data {data} for {plc_id} register: {address}")

        register_config = config_manager.get_register_config(plc_id, address) or None

        stored_as = 'uint16'
        encode_as = 'uint16'
        if register_config:
            stored_as = register_config.get('stored_as', 'uint16')
            encode_as = register_config.get('encode_as', 'uint16')
        
        register_count = self._determine_register_count(stored_as)
        logger.debug(f"Determined register count {register_count}")
        pdu_address = self._convert_modbus_address(plc_id, address)
        logger.debug(f"Converted model address to PDU address {address} -> {pdu_address}")

        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
        if encode_as == 'uint16':
            builder.add_16bit_uint(data)
        elif encode_as == 'float32':
            builder.add_32bit_float(data)
        else:
            raise ValueError(f'Unknown encoding {encode_as}')

        payload = builder.to_registers()
        return payload



    def _get_address_from_tagname(self, plc_id, tag_name) -> int:
        """
        Get data model (yaml) register address from tag name
        * Data model is 1-based unlike Modbus PDU which is 0-based
        """
        registers = config_manager.register_maps[plc_id]

        address = None
        for register_address, config in registers.items():
            if config.get('name') == tag_name:
                address = register_address

        if not address:
            raise ValueError(f"No Address found for tag {tag_name}")

        return address
        

    def _determine_register_count(self, data_type) -> int:
        """
        Determine register count needed based on data types (e.g., float32 = 2 registers)
        """

        if data_type == 'float32':
            return 2
        else:
        # default to uint16 (1 register) if no config available
            return 1


    def _convert_modbus_address(self, plc_id, address: int) -> tuple[int, str]:
        """
        Convert address with register type detection for vendor-specific addressing
        
        Enhanced to determine correct register type for custom addressing schemes
        """
        
        addressing_scheme = config_manager.get_plc_config(plc_id).addressing_scheme

        register_config = config_manager.get_register_config(plc_id, address) or None
        # Handle vendor-specific addressing with type detection
        if addressing_scheme.lower() == 'relative':
            if register_config:
                # Use register configuration to determine type
                register_type = register_config.get('register_type', 'holding_register')
                return address - 1, register_type
            else:
                # default to holding register if no config available
                logger.warning(f"No register config for address {address} - defaulting to holding_register")
                return address - 1, "holding_register"
        
        # Standard Modbus addressing (per official specification)
        elif 40001 <= address <= 49999:
            return address - 40001, "holding_register"
        elif 30001 <= address <= 39999:
            return address - 30001, "input_register"
        elif 10001 <= address <= 19999:
            return address - 10001, "discrete_input"
        elif 1 <= address <= 9999:
            return address - 1, "coil"
        elif address == 0:
            return 0, "holding_register"
        
        # default to holding register
        return address, "holding_register"
