import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def convert_modbus_address(address: int, addressing_scheme='absolute', *, register_config: Dict[str, Any] = None) -> tuple[int, str]:
    """
    Convert address with register type detection for vendor-specific addressing
    
    Enhanced to determine correct register type for custom addressing schemes
    """
    
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
