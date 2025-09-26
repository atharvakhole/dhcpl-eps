# Custom Exception Classes
class TagServiceError(Exception):
    """Base exception for tag service operations"""
    def __init__(self, message: str, plc_id: str = None, tag_name: str = None, address: int = None):
        super().__init__(message)
        self.plc_id = plc_id
        self.tag_name = tag_name
        self.address = address


class ConfigurationError(TagServiceError):
    """Raised when configuration is missing or invalid"""
    pass


class ValidationError(TagServiceError):
    """Raised when data validation fails"""
    pass


class AddressResolutionError(TagServiceError):
    """Raised when tag name cannot be resolved to address"""
    pass


class EncodingError(TagServiceError):
    """Raised when data encoding/decoding fails"""
    pass


class ConnectionError(TagServiceError):
    """Raised when PLC connection fails - should rarely happen due to connection_manager handling"""
    pass
