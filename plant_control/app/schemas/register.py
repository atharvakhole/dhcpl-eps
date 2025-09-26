from pydantic import BaseModel, Field
from typing import Any, List, Dict, Optional


class WriteTagRequest(BaseModel):
    data: Any = Field(..., description="Data to write to the tag")


class BulkReadRequest(BaseModel):
    tag_names: List[str] = Field(..., description="List of tag names to read", min_items=1)


class BulkWriteRequest(BaseModel):
    tag_data: Dict[str, Any] = Field(..., description="Dictionary mapping tag names to values")


class TagReadResponse(BaseModel):
    plc_id: str
    tag_name: str
    status: str
    data: Optional[Any] = None
    registers: Optional[List[Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: float


class TagWriteResponse(BaseModel):
    plc_id: str
    tag_name: str
    status: str
    data: Optional[Any] = None
    result: Optional[Any] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: float


class BulkReadResponseModel(BaseModel):
    plc_id: str
    summary: Dict[str, int]  # total_requested, successful, failed
    overall_status: str  # "success", "partial_success", "failed"
    results: List[TagReadResponse]
    timestamp: float


class BulkWriteResponseModel(BaseModel):
    plc_id: str
    summary: Dict[str, int]  # total_requested, successful, failed
    overall_status: str  # "success", "partial_success", "failed"
    results: List[TagWriteResponse]
    timestamp: float
