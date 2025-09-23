from dataclasses import dataclass


@dataclass()
class PLCConfig:
    """Configuration for a single PLC with vendor-specific addressing support"""
    plc_id: str
    host: str
    port: int = 502
    unit_id: int = 1 # slave id for operations
    timeout: float = 3.0
    retries: int = 3
    description: str = ""
    vendor: str = "generic"  # "schneider", "siemens", "custom", "raw", etc.
    model: str = ""
    addressing_scheme: str = "absolute"  # "absolute" (holding registers start at 40001) "relative" (all registers start at 1)
    max_concurrent_connections: int = 5
    health_check_interval: int = 30
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60
