from pydantic import BaseModel
from typing import Optional


class RootResponse(BaseModel):
    message: str
    version: str


class ErrorDetail(BaseModel):
    error_type: str
    message: str
    plc_id: Optional[str] = None
    tag_name: Optional[str] = None
    address: Optional[int] = None
    timestamp: float


class ErrorResponse(BaseModel):
    detail: ErrorDetail
