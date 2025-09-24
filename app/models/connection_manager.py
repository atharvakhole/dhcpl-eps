from dataclasses import dataclass, field
from datetime import datetime 
from enum import Enum
from typing import Any, List, Optional, Union
from collections import deque

class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    CIRCUIT_OPEN = "circuit_open"

class Priority(Enum):
    EMERGENCY = 1
    CRITICAL = 2
    NORMAL = 3
    BACKGROUND = 4


@dataclass()
class ConnectionMetrics:
    """Connection performance and reliability metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    last_successful_connection: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    connection_uptime_start: Optional[datetime] = None
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))

@dataclass
class ModbusOperation:
    """
    Modbus operation request with official addressing
    
    Stores both Data Model address (from YAML) and PDU Protocol address (for wire)
    to maintain full traceability per Modbus specification
    """
    operation_type: str      # PDU function type: 'read_holding', 'read_input', etc.
    address: int             # PDU Protocol address (0-based, for wire)
    original_address: int    # Data Model address (1-based, from YAML/user)
    values: Optional[List[Any]] = None
    count: Optional[int] = None
    unit_id: Optional[int] = None
    priority: Priority = Priority.NORMAL
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
