from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import time

from plant_control.app.config import config_manager
from plant_control.app.utilities.telemetry import logger

from plant_control.app.schemas.procedures import (
    ProcedureListResponse, 
    ProcedureDetailResponse,
    ProcedureExecutionResponse,
    StepResultResponse
)
from plant_control.app.dependencies import get_procedure_executor

router = APIRouter(prefix="/procedures", tags=["procedures"])


@router.get("", response_model=ProcedureListResponse)
async def list_procedures():
    """
    Get list of available procedures
    
    Returns:
        List of procedure names and count
    """
    try:
        procedure_names = config_manager.list_procedures()
        
        return ProcedureListResponse(
            procedures=sorted(procedure_names),
            count=len(procedure_names)
        )
        
    except Exception as e:
        logger.error(f"Failed to list procedures: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list procedures: {str(e)}"
        )


@router.get("/{procedure_name}", response_model=ProcedureDetailResponse)  
async def get_procedure_details(procedure_name: str):
    """
    Get details of a specific procedure
    
    Args:
        procedure_name: Name of the procedure
        
    Returns:
        Procedure definition with steps
    """
    try:
        procedure = config_manager.get_procedure(procedure_name)
        
        if not procedure:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure '{procedure_name}' not found"
            )
        
        # Convert steps to API format
        steps_data = []
        for step in procedure.steps:
            steps_data.append({
                "name": step.name,
                "type": step.type,
                **step.data
            })
        
        return ProcedureDetailResponse(
            name=procedure.name,
            description=procedure.description,
            step_count=len(procedure.steps),
            steps=steps_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get procedure details: {procedure_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get procedure details: {str(e)}"
        )


@router.post("/{procedure_name}/execute", response_model=ProcedureExecutionResponse)
async def execute_procedure(procedure_name: str, procedure_executor=get_procedure_executor):
    """
    Execute a procedure
    
    Args:
        procedure_name: Name of the procedure to execute
        
    Returns:
        Execution result with step details and status
    """
    if not procedure_executor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Procedure executor not initialized"
        )
    
    start_time = time.time()
    
    try:
        # Get procedure definition
        procedure = config_manager.get_procedure(procedure_name)
        
        if not procedure:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procedure '{procedure_name}' not found"
            )
        
        logger.info(f"API executing procedure: {procedure_name}")
        
        # Execute the procedure
        result = await procedure_executor.execute_procedure(procedure)
        
        # Convert to API response format
        step_responses = []
        for step_result in result.step_results:
            step_responses.append(StepResultResponse(
                step_name=step_result.step_name,
                step_type=step_result.step_type,
                status=step_result.status,
                data=step_result.data,
                error_message=step_result.error_message,
                execution_time_ms=step_result.execution_time_ms
            ))
        
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"API procedure execution completed: {procedure_name} - {result.status} in {duration_ms}ms")
        
        response = ProcedureExecutionResponse(
            procedure_name=result.procedure_name,
            status=result.status,
            total_steps=result.total_steps,
            successful_steps=result.successful_steps,
            failed_steps=result.failed_steps,
            execution_time_ms=result.execution_time_ms,
            step_results=step_responses,
            error_message=result.error_message
        )
        
        # Return appropriate HTTP status based on execution result
        if result.status == "completed":
            return response
        elif result.status == "failed":
            return JSONResponse(
                content=response.dict(),
                status_code=status.HTTP_200_OK  # Still return 200 with error details
            )
        else:  # aborted or other status
            return JSONResponse(
                content=response.dict(),
                status_code=status.HTTP_200_OK
            )
        
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"API procedure execution failed: {procedure_name}: {str(e)} in {duration_ms}ms")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Procedure execution failed: {str(e)}"
        )
