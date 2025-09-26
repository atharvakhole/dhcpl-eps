from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder
from typing import Any, List, Optional
from plant_control.app.models.connection_manager import ModbusOperation
from plant_control.app.utilities.telemetry import logger
from plant_control.app.config import config_manager

from plant_control.app.core.tag_exceptions import (
    ConfigurationError, ValidationError, AddressResolutionError, 
    EncodingError
)


class TagServiceHelper:
    """Helper class containing utility methods for tag operations"""

    def decode_registers(self, registers: List[Any], decode_as: str) -> Any:
        """Decode register values to application data type."""
        if not registers:
            raise EncodingError("No registers provided for decoding")
        
        if not isinstance(registers, list):
            raise EncodingError(f"Registers must be a list, got {type(registers)}")

        try:
            decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.BIG, wordorder=Endian.BIG)
            
            logger.debug("Decoding registers", extra={
                "registers": registers,
                "decode_as": decode_as,
            })
            
            if decode_as == "uint16":
                result = decoder.decode_16bit_uint()
            elif decode_as == "float32":
                result = decoder.decode_32bit_float()
            elif decode_as == "int16":
                result = decoder.decode_16bit_int()
            elif decode_as == "uint32":
                result = decoder.decode_32bit_uint()
            elif decode_as == "int32":
                result = decoder.decode_32bit_int()
            else:
                logger.warning(f"Unknown decode type '{decode_as}', defaulting to uint16")
                result = decoder.decode_16bit_uint()
                
            logger.debug("Decoded registers", extra={
                "registers": registers,
                "decode_as": decode_as,
                "result": result,
            })
            return result
            
        except Exception as e:
            error_msg = f"Failed to decode {len(registers)} registers as {decode_as}: {str(e)}"
            logger.error(error_msg, extra={
                "registers": registers,
                "decode_as": decode_as,
            })
            raise EncodingError(error_msg) from e

    def decode_registers_minimal_logging(self, registers: List[Any], decode_as: str, verbose_logging: bool = False) -> Any:
        """Decode register values with minimal logging for bulk operations"""
        if not registers:
            raise EncodingError("No registers provided for decoding")
        
        if not isinstance(registers, list):
            raise EncodingError(f"Registers must be a list, got {type(registers)}")

        try:
            decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.BIG, wordorder=Endian.BIG)
            
            # Only log debug info if verbose logging is enabled
            if verbose_logging:
                logger.debug(f"Decoding {len(registers)} registers as {decode_as}")
            
            if decode_as == "uint16":
                result = decoder.decode_16bit_uint()
            elif decode_as == "float32":
                result = decoder.decode_32bit_float()
            elif decode_as == "int16":
                result = decoder.decode_16bit_int()
            elif decode_as == "uint32":
                result = decoder.decode_32bit_uint()
            elif decode_as == "int32":
                result = decoder.decode_32bit_int()
            else:
                # Always log unknown decode types
                logger.warning(f"Unknown decode type '{decode_as}', defaulting to uint16")
                result = decoder.decode_16bit_uint()
                
            if verbose_logging:
                logger.debug(f"Decoded result: {result}")
                
            return result
            
        except Exception as e:
            error_msg = f"Failed to decode {len(registers)} registers as {decode_as}: {str(e)}"
            # Always log decoding errors with register details for debugging
            logger.error(f"{error_msg} (registers: {registers})")
            raise EncodingError(error_msg) from e

    def get_register_type(self, plc_id: str, original_address: int) -> str:
        """Get register type from register config"""
        try:
            register_config = config_manager.get_register_config(plc_id, original_address)
            if not register_config:
                raise ConfigurationError(f"No register configuration found", 
                                       plc_id=plc_id, address=original_address)

            register_type = register_config.get("register_type", "holding_register")
            
            # Validate register type
            valid_types = ["holding_register", "input_register", "discrete_input", "coil"]
            if register_type not in valid_types:
                logger.warning(f"Invalid register type '{register_type}', defaulting to holding_register")
                register_type = "holding_register"

            return register_type
            
        except Exception as e:
            raise ConfigurationError(f"Failed to get register type for address {original_address}: {str(e)}", 
                                   plc_id=plc_id, address=original_address) from e

    def get_decode_type(self, plc_id: str, original_address: int) -> str:
        """Get decode type from register config"""
        try:
            register_config = config_manager.get_register_config(plc_id, original_address)
            if not register_config:
                raise ConfigurationError(f"No register configuration found", 
                                       plc_id=plc_id, address=original_address)

            return register_config.get("decode_as", "uint16")
            
        except Exception as e:
            raise ConfigurationError(f"Failed to get decode type for address {original_address}: {str(e)}", 
                                   plc_id=plc_id, address=original_address) from e

    def get_data_type(self, plc_id: str, original_address: int) -> str:
        """Get data type of stored data from register config"""
        try:
            register_config = config_manager.get_register_config(plc_id, original_address)
            if not register_config:
                raise ConfigurationError(f"No register configuration found", 
                                       plc_id=plc_id, address=original_address)

            return register_config.get("stored_as", "uint16")
            
        except Exception as e:
            raise ConfigurationError(f"Failed to get data type for address {original_address}: {str(e)}", 
                                   plc_id=plc_id, address=original_address) from e

    def build_modbus_operation(self, read_write: str, address: int, original_address: int, 
                               register_type: str, count: int, payload: Optional[List[Any]] = None, 
                               unit_id: int = 1) -> ModbusOperation:
        """Construct the modbus operation to be executed"""
        try:
            if read_write == "read":
                read_operation_type_map = {
                    "holding_register": "read_holding",
                    "input_register": "read_input", 
                    "discrete_input": "read_discrete",
                    "coil": "read_coil"
                }
                operation_type = read_operation_type_map.get(register_type, "read_holding")
            elif read_write == "write":
                operation_type = "write_coil" if register_type == "coil" else "write_registers"
            else:
                raise ValidationError(f"Invalid operation type: {read_write}")

            logger.debug(f"Constructed modbus operation", extra={
                "operation_type": operation_type,
                "address": address,
                "original_address": original_address,
                "values": payload,
                "count": count,
                "unit_id": unit_id
            })
            
            return ModbusOperation(
                operation_type=operation_type,
                address=address,
                original_address=original_address,
                values=payload,
                count=count,
                unit_id=unit_id
            )
            
        except Exception as e:
            raise ValidationError(f"Failed to build modbus operation: {str(e)}") from e

    def is_valid_data(self, plc_id: str, address: int, data: Any) -> bool:
        """Validates data against register configuration rules."""
        try:
            # Check PLC configuration exists
            plc_config = config_manager.get_plc_config(plc_id)
            if not plc_config:
                raise ConfigurationError(f"No PLC configuration found", plc_id=plc_id)

            # Check register configuration exists
            register_config = config_manager.get_register_config(plc_id, address)
            if not register_config:
                raise ConfigurationError(f"No register configuration found", 
                                       plc_id=plc_id, address=address)

            # Check readonly protection
            if register_config.get('readonly', False):
                raise ValidationError(f"Cannot write to readonly register", 
                                    plc_id=plc_id, address=address)

            # Validate data exists
            if data is None:
                raise ValidationError("Data cannot be None", plc_id=plc_id, address=address)

            # Convert data to numeric format
            try:
                if isinstance(data, bool):
                    numeric_data = float(data)
                elif isinstance(data, (int, float)):
                    numeric_data = float(data)
                else:
                    numeric_data = float(data)
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Cannot convert data '{data}' to numeric value", 
                                    plc_id=plc_id, address=address) from e

            # Range validation
            min_value = register_config.get('min_value')
            max_value = register_config.get('max_value')
            
            if min_value is not None and numeric_data < min_value:
                raise ValidationError(f"Value {numeric_data} below minimum {min_value}", 
                                    plc_id=plc_id, address=address)
                
            if max_value is not None and numeric_data > max_value:
                raise ValidationError(f"Value {numeric_data} above maximum {max_value}", 
                                    plc_id=plc_id, address=address)

            # Digital tag validation
            tag_type = register_config.get('tag_type', '').lower()
            if tag_type == 'digital' and numeric_data not in [0.0, 1.0]:
                raise ValidationError(f"Digital tag requires 0 or 1, got {numeric_data}", 
                                    plc_id=plc_id, address=address)

            # Integer type validation
            stored_as = register_config.get('stored_as', 'uint16')
            if tag_type == 'digital' or stored_as in ['int16', 'int32', 'uint16', 'uint32']:
                if numeric_data != int(numeric_data):
                    raise ValidationError(f"Integer type {stored_as} requires whole number, got {numeric_data}", 
                                        plc_id=plc_id, address=address)

            return True
            
        except Exception as e:
            if hasattr(e, 'plc_id'):
                # Re-raise our custom exceptions
                raise
            else:
                raise ValidationError(f"Data validation failed: {str(e)}", 
                                    plc_id=plc_id, address=address) from e

    def construct_payload(self, plc_id: str, address: int, data: Any) -> List[Any]:
        """Constructs binary payload for Modbus register write operation."""
        try:
            # Validate data first
            self.is_valid_data(plc_id, address, data)

            register_config = config_manager.get_register_config(plc_id, address)
            if not register_config:
                raise ConfigurationError(f"No register configuration found", 
                                       plc_id=plc_id, address=address)
            
            stored_as = register_config.get('stored_as', 'uint16')
            encode_as = register_config.get('encode_as', 'uint16')
            
            # Build payload using pymodbus
            builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
            
            if encode_as == 'uint16':
                builder.add_16bit_uint(int(data))
            elif encode_as == 'int16':
                builder.add_16bit_int(int(data))
            elif encode_as == 'uint32':
                builder.add_32bit_uint(int(data))
            elif encode_as == 'int32':
                builder.add_32bit_int(int(data))
            elif encode_as == 'float32':
                builder.add_32bit_float(float(data))
            else:
                raise EncodingError(f"Unsupported encoding type: {encode_as}", 
                                  plc_id=plc_id, address=address)

            payload = builder.to_registers()
            logger.debug(f"Constructed payload for {plc_id}:{address} - {len(payload)} registers")
            return payload
            
        except Exception as e:
            if hasattr(e, 'plc_id'):
                # Re-raise our custom exceptions
                raise
            else:
                raise EncodingError(f"Failed to construct payload: {str(e)}", 
                                  plc_id=plc_id, address=address) from e

    def get_address_from_tagname(self, plc_id: str, tag_name: str) -> int:
        """Resolves logical tag name to physical register address."""
        try:
            if plc_id not in config_manager.plc_configs:
                raise ConfigurationError(f"No PLC configuration found", plc_id=plc_id)

            registers = config_manager.register_maps.get(plc_id)
            if not registers:
                raise ConfigurationError(f"No register map found", plc_id=plc_id)

            # Search for tag name in register configurations
            for register_address, config in registers.items():
                if config.get('name') == tag_name:
                    logger.debug(f"Resolved tag {tag_name} to address {register_address} on PLC {plc_id}")
                    return register_address

            # Provide helpful error with available tags
            available_tags = [cfg.get('name') for cfg in registers.values() if cfg.get('name')]
            if available_tags:
                error_msg = f"Tag '{tag_name}' not found. Available tags: {', '.join(sorted(available_tags[:10]))}"
                if len(available_tags) > 10:
                    error_msg += f" (and {len(available_tags) - 10} more)"
            else:
                error_msg = f"No tags configured for PLC {plc_id}"
            
            raise AddressResolutionError(error_msg, plc_id=plc_id, tag_name=tag_name)
            
        except Exception as e:
            if hasattr(e, 'plc_id'):
                raise
            else:
                raise AddressResolutionError(f"Failed to resolve tag name: {str(e)}", 
                                           plc_id=plc_id, tag_name=tag_name) from e

    def determine_register_count(self, data_type: str) -> int:
        """Determines number of Modbus registers required for given data type."""
        type_map = {
            'float32': 2, 'uint32': 2, 'int32': 2,
            'uint64': 4, 'int64': 4, 'float64': 4
        }
        count = type_map.get(data_type, 1)  # Default to 1 register
        
        if count != type_map.get(data_type, 1):
            logger.debug(f"Using {count} registers for data type {data_type}")
            
        return count

    def convert_modbus_address(self, plc_id: str, address: int) -> int:
        """Converts 1-based data model address to 0-based Modbus PDU address."""
        try:
            plc_config = config_manager.get_plc_config(plc_id)
            if not plc_config:
                raise ConfigurationError(f"No PLC configuration found", plc_id=plc_id)
            
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
                
        except Exception as e:
            if hasattr(e, 'plc_id'):
                raise
            else:
                raise ConfigurationError(f"Failed to convert address {address}: {str(e)}", 
                                       plc_id=plc_id, address=address) from e
