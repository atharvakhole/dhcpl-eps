from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional


# Enums
class ReadStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"

class WriteStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"


# Structured Response Classes
@dataclass
class TagReadResult:
    tag_name: str
    status: ReadStatus
    data: Optional[Any] = None
    registers: Optional[List[Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: Optional[float] = None

@dataclass
class TagWriteResult:
    tag_name: str
    status: WriteStatus
    data: Optional[Any] = None
    result: Optional[Any] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: Optional[float] = None

@dataclass
class BulkReadResponse:
    plc_id: str
    total_requested: int
    successful_count: int
    failed_count: int
    results: List[TagReadResult]
    overall_status: str
    timestamp: float

@dataclass
class BulkWriteResponse:
    plc_id: str
    total_requested: int
    successful_count: int
    failed_count: int
    results: List[TagWriteResult]
    overall_status: str
    timestamp: float
