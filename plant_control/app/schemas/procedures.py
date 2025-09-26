from pydantic import BaseModel
from typing import Any, List, Dict, Optional


class ProcedureListResponse(BaseModel):
    procedures: List[str]
    count: int


class ProcedureDetailResponse(BaseModel):
    name: str
    description: str
    step_count: int
    steps: List[Dict[str, Any]]


class StepResultResponse(BaseModel):
    step_name: str
    step_type: str
    status: str
    data: Optional[Any] = None
    error_message: Optional[str] = None
    execution_time_ms: int


class ProcedureExecutionResponse(BaseModel):
    procedure_name: str
    status: str
    total_steps: int
    successful_steps: int
    failed_steps: int
    execution_time_ms: int
    step_results: List[StepResultResponse]
    error_message: Optional[str] = None
