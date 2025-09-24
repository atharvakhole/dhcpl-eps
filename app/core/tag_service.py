from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder
from app.config import config_manager
import logging
from typing import Any, Dict, List, Optional, Tuple
import time
from app.models.connection_manager import ModbusOperation
from app.core.connection_manager import connection_manager
from app.utilities.telemetry import logger


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

    async def read_tag(self, plc_id: str, tag_name: str) -> Tuple[Any, List[Any]]:
        """Reads data from the register corresponding to the given tag."""
        start_time = time.time()
        logger.info(f"Reading tag {tag_name} from PLC {plc_id}")
        
        try:
            original_address = self._get_address_from_tagname(plc_id, tag_name)
            converted_modbus_address = self._convert_modbus_address(plc_id, original_address)
            register_type = self._get_register_type(plc_id, original_address)
            data_type = self._get_data_type(plc_id, original_address)
            decode_type = self._get_decode_type(plc_id, original_address)
            register_count = self._determine_register_count(data_type)
            operation = self._build_modbus_operation("read", converted_modbus_address, original_address, register_type, register_count)
            registers = await connection_manager.execute_operation(plc_id, operation)
            
            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(f"Tag read completed in {duration_ms}ms")
            logger.debug(f"Tag read completed", extra={
                "operation": "read_tag", "plc_id": plc_id, "tag_name": tag_name, "duration_ms": duration_ms,
                "registers": registers,
            })

            result = self._decode_registers(registers, decode_type)
            return result, registers
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Tag read failed: {e}", extra={
                "operation": "read_tag", "plc_id": plc_id, "tag_name": tag_name, "error": str(e), "duration_ms": duration_ms
            })
            raise

    async def write_tag(self, plc_id: str, tag_name: str, data: Any):
        """Writes data to the register corresponding to the given tag."""
        start_time = time.time()
        logger.info(f"Writing {data} to tag {tag_name} on PLC {plc_id}")
        
        try:
            original_address = self._get_address_from_tagname(plc_id, tag_name)
            converted_modbus_address = self._convert_modbus_address(plc_id, original_address)
            payload = self._construct_payload(plc_id, original_address, data)
            register_type = self._get_register_type(plc_id, original_address)

            operation = self._build_modbus_operation("write", converted_modbus_address, original_address, register_type, 0, payload)
            result = await connection_manager.execute_operation(plc_id, operation)
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Tag write completed in {duration_ms}ms", extra={
                "operation": "write_tag", "plc_id": plc_id, "tag_name": tag_name, "address": original_address,
                "convert_modbus_address": converted_modbus_address, "duration_ms": duration_ms
            })

            return result
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Tag write failed: {e}", extra={
                "operation": "write_tag", "plc_id": plc_id, "tag_name": tag_name, 
                "data": data, "error": str(e), "duration_ms": duration_ms
            })
            raise

    def _decode_registers(self, registers, decode_as):
        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.BIG, wordorder=Endian.BIG)
        logger.debug("Decoding registers", extra={
            "registers": registers,
            "decode_as": decode_as,
        })
        try:
            if decode_as == "uint16":
                result = decoder.decode_16bit_uint()
            elif decode_as == "float32":
                result = decoder.decode_32bit_float()
            else:
                result = decoder.decode_16bit_uint()
            logger.debug("Decoded registers", extra={
                "registers": registers,
                "decode_as": decode_as,
                "result": result,
            })
            return result
        except Exception as e:
            logger.error(f"Failed to decode registers: {e}", extra={
                "registers": registers,
                "decode_as": decode_as,
            })
            raise

    def _get_register_type(self, plc_id, original_address) -> str:
        """Get register type from regsiter config"""
        # Check register configuration exists
        register_config = config_manager.get_register_config(plc_id, original_address)
        if not register_config:
            logger.error(f"No register config found for {plc_id}:{original_address}")
            raise ValueError(f"No register config for {plc_id} register: {original_address}")

        register_type = register_config.get("register_type", "holding_register")

        return register_type

    def _get_decode_type(self, plc_id, original_address) -> str:
        """Get register type from regsiter config"""
        # Check register configuration exists
        register_config = config_manager.get_register_config(plc_id, original_address)
        if not register_config:
            logger.error(f"No register config found for {plc_id}:{original_address}")
            raise ValueError(f"No register config for {plc_id} register: {original_address}")

        decode_type = register_config.get("decode_as", "uint16")

        return decode_type

    def _get_data_type(self, plc_id, original_address) -> str:
        """Get data type of stored data from regsiter config"""
        # Check register configuration exists
        register_config = config_manager.get_register_config(plc_id, original_address)
        if not register_config:
            logger.error(f"No register config found for {plc_id}:{original_address}")
            raise ValueError(f"No register config for {plc_id} register: {original_address}")

        data_type = register_config.get("stored_as", "uint16")

        return data_type


    def _build_modbus_operation(self, read_write: str, address, original_address, register_type: str, count, payload: Optional[List[Any]]=None, unit_id=1) -> ModbusOperation: 
        """
        Construct the modbus operation to be executed
        """

        if read_write == "read":
            read_operation_type_map = {
                "holding_register": "read_holding",
                "input_register": "read_input", 
                "discrete_input": "read_discrete",
                "coil": "read_coil"
            }
            operation_type = read_operation_type_map.get(register_type, "read_holding")
        elif read_write == "write":
            # Determine operation type based on register type
            operation_type = "write_coil" if register_type == "coil" else "write_register"
            operation_type = "write_registers"
        else:
            operation_type = "read_holding"


        logger.debug(f"Constructed modbus operation", extra={
            "operation_type":operation_type,
            "address":address,
            "original_address":original_address,
            "values":payload,
            "count":count,
            "unit_id":unit_id
        })
        operation = ModbusOperation(
            operation_type=operation_type,
            address=address,
            original_address=original_address,
            values=payload,
            count=count,
            unit_id=unit_id
        )

        return operation


    def _is_valid_data(self, plc_id: str, address: int, data: Any) -> bool:
        """Validates data against register configuration rules."""
        
        # Check PLC configuration exists
        plc_config = config_manager.get_plc_config(plc_id)
        if not plc_config:
            logger.error(f"No PLC config found for {plc_id}")
            raise ValueError(f"No plc config for {plc_id}")

        # Check register configuration exists
        register_config = config_manager.get_register_config(plc_id, address)
        if not register_config:
            logger.error(f"No register config found for {plc_id}:{address}")
            raise ValueError(f"No register config for {plc_id} register: {address}")

        # Check readonly protection
        if register_config.get('readonly', False):
            logger.error(f"Attempted write to readonly register {plc_id}:{address}")
            raise ValueError(f"Cannot write to readonly register {address} on PLC {plc_id}")

        # Validate data
        if data is None:
            return False

        # Convert data to numeric format
        try:
            if isinstance(data, bool):
                numeric_data = float(data)
            elif isinstance(data, (int, float)):
                numeric_data = float(data)
            else:
                numeric_data = float(data)
        except (ValueError, TypeError):
            logger.warning(f"Failed to convert data {data} to numeric for {plc_id}:{address}")
            return False

        # Range validation
        min_value = register_config.get('min_value')
        max_value = register_config.get('max_value')
        
        if min_value is not None and numeric_data < min_value:
            logger.warning(f"Data {numeric_data} below minimum {min_value} for {plc_id}:{address}")
            return False
            
        if max_value is not None and numeric_data > max_value:
            logger.warning(f"Data {numeric_data} above maximum {max_value} for {plc_id}:{address}")
            return False

        # Digital tag validation
        tag_type = register_config.get('tag_type', '').lower()
        if tag_type == 'digital' and numeric_data not in [0.0, 1.0]:
            logger.warning(f"Invalid digital value {numeric_data} for {plc_id}:{address}")
            return False

        # Integer type validation
        stored_as = register_config.get('stored_as', 'uint16')
        if tag_type == 'digital' or stored_as in ['int16', 'int32', 'uint16', 'uint32']:
            if numeric_data != int(numeric_data):
                logger.warning(f"Non-integer value {numeric_data} for integer type {stored_as} at {plc_id}:{address}")
                return False

        return True

    def _construct_payload(self, plc_id: str, address: int, data: Any) -> List[Any]:
        """Constructs binary payload for Modbus register write operation."""
        
        if not self._is_valid_data(plc_id, address, data):
            raise ValueError(f"Invalid data {data} for {plc_id} register: {address}")

        register_config = config_manager.get_register_config(plc_id, address)
        stored_as = register_config.get('stored_as', 'uint16') if register_config else 'uint16'
        encode_as = register_config.get('encode_as', 'uint16') if register_config else 'uint16'
        
        # Build payload using pymodbus
        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
        
        try:
            if encode_as == 'uint16':
                builder.add_16bit_uint(int(data))
            elif encode_as == 'float32':
                builder.add_32bit_float(float(data))
            else:
                logger.error(f"Unsupported encoding type: {encode_as}")
                raise ValueError(f'Unknown encoding {encode_as}')

            payload = builder.to_registers()
            logger.debug(f"Constructed payload for {plc_id}:{address} - {len(payload)} registers")
            return payload
            
        except Exception as e:
            logger.error(f"Failed to construct payload for {plc_id}:{address}: {e}")
            raise

    def _get_address_from_tagname(self, plc_id: str, tag_name: str) -> int:
        """Resolves logical tag name to physical register address."""
        
        if plc_id not in config_manager.plc_configs:
            raise ValueError(f"No plc config for {plc_id}")

        registers = config_manager.register_maps.get(plc_id)
        if not registers:
            raise ValueError(f"No registers found for plc {plc_id}")

        # Search for tag name in register configurations
        for register_address, config in registers.items():
            if config.get('name') == tag_name:
                logger.debug(f"Resolved tag {tag_name} to address {register_address} on PLC {plc_id}")
                return register_address

        available_tags = [cfg.get('name') for cfg in registers.values() if cfg.get('name')]
        logger.error(f"Tag {tag_name} not found in PLC {plc_id}. Available: {available_tags[:5]}...")
        raise ValueError(f"No Address found for tag {tag_name}")
        
    def _determine_register_count(self, data_type: str) -> int:
        """Determines number of Modbus registers required for given data type."""
        type_map = {
            'float32': 2, 'uint32': 2, 'int32': 2,
            'uint64': 4, 'int64': 4, 'float64': 4
        }
        return type_map.get(data_type, 1)  # Default to 1 register

    def _convert_modbus_address(self, plc_id: str, address: int) -> int:
        """Converts 1-based data model address to 0-based Modbus PDU address."""
        plc_config = config_manager.get_plc_config(plc_id)
        addressing_scheme = plc_config.addressing_scheme        
        
        # Handle vendor-specific relative addressing
        if addressing_scheme.lower() == 'relative':
            return address - 1
        
        # Standard Modbus addressing ranges
        elif 40001 <= address <= 49999:
            return address - 40001
        elif 30001 <= address <= 39999:
            return address - 30001
        elif 10001 <= address <= 19999:
            return address - 10001
        elif 1 <= address <= 9999:
            return address - 1
        else:
            logger.warning(f"Address {address} outside standard ranges, using as-is")
            return address
