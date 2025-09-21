from typing import Dict


def convert_modbus_address(address: int, plc_vendor: str = "generic", register_config: Dict[str, Any] = None) -> tuple[int, str]:
    """
    Convert address with register type detection for vendor-specific addressing
    
    Enhanced to determine correct register type for custom addressing schemes
    """
    
    # Handle vendor-specific addressing with type detection
    if plc_vendor.lower() in ["custom", "raw", "direct"]:
        if register_config:
            # Use register configuration to determine type
            register_type = determine_register_type_from_config(register_config)
            return address, register_type
        else:
            # Default to holding register if no config available
            logger.warning(f"No register config for address {address} - defaulting to holding_register")
            return address, "holding_register"
    
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
    
    # If address doesn't match standard ranges, assume vendor-specific
    else:
        if register_config:
            register_type = determine_register_type_from_config(register_config)
            logger.info(f"Non-standard address {address} detected as {register_type}")
            return address, register_type
        else:
            logger.warning(f"Non-standard address {address} - treating as holding_register")
            return address, "holding_register"
