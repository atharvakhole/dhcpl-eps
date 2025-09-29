from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
import time

from plant_control.app.utilities.telemetry import logger

from plant_control.app.schemas.register import (
    WriteTagRequest,
    BulkReadRequest, 
    BulkWriteRequest,
    TagReadResponse,
    TagWriteResponse,
    BulkReadResponseModel,
    BulkWriteResponseModel
)
from plant_control.app.dependencies import get_plc_handler
from plant_control.app.utilities.converters import convert_read_result_to_response, convert_write_result_to_response

router = APIRouter(prefix="/registers", tags=["registers"])


@router.post("/bulk-read/{plc_id}", response_model=BulkReadResponseModel)
async def read_multiple_tags_endpoint(plc_id: str, request: BulkReadRequest, plc_handler=get_plc_handler) -> BulkReadResponseModel:
    """
    Read multiple tags from a PLC concurrently.
    
    Args:
        plc_id: The PLC identifier
        request: Request body containing list of tag names to read
        
    Returns:
        JSON object containing results for all tag reads, including both successful and failed operations
        
    Response includes:
        - summary: counts of total requested, successful, and failed reads
        - overall_status: "success" (all succeeded), "partial_success" (mixed), or "failed" (all failed)  
        - results: detailed results for each tag including data or error information
        
    Note:
        This endpoint uses different status codes based on results:
        - 200: Complete success or complete failure (check overall_status)
        - 207: Partial success (some tags succeeded, some failed)
    """
    if not plc_handler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is initializing, please try again later"
        )
    
    start_time = time.time()
    context = {
        "plc_id": plc_id, 
        "tag_count": len(request.tag_names),
        "operation": "read_multiple_tags_api"
    }
    
    # Log the request (without full tag list for brevity)
    logger.debug(f"Bulk read request for {len(request.tag_names)} tags from PLC {plc_id}")
    logger.debug(f"Bulk read tag names: {request.tag_names[:10]}{'...' if len(request.tag_names) > 10 else ''}")
    
    try:
        # Call the tag service - it always returns BulkReadResponse
        bulk_result = await plc_handler.read_multiple_tags(plc_id, request.tag_names)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Convert internal result format to API response format
        api_results = []
        for result in bulk_result.results:
            api_result = convert_read_result_to_response(result, plc_id)
            api_results.append(api_result)
        
        # Determine HTTP status code based on results
        if bulk_result.overall_status == "success":
            response_status = status.HTTP_200_OK
        elif bulk_result.overall_status == "partial_success":
            response_status = status.HTTP_207_MULTI_STATUS  # Some succeeded, some failed
        else:  # "failed"
            response_status = status.HTTP_200_OK  # Still return 200, but with error details in response
        
        logger.debug(f"Bulk read API completed", extra={
            **context, 
            "successful_count": bulk_result.successful_count,
            "failed_count": bulk_result.failed_count,
            "overall_status": bulk_result.overall_status,
            "duration_ms": duration_ms
        })
        
        response_data = BulkReadResponseModel(
            plc_id=bulk_result.plc_id,
            summary={
                "total_requested": bulk_result.total_requested,
                "successful": bulk_result.successful_count,
                "failed": bulk_result.failed_count
            },
            overall_status=bulk_result.overall_status,
            results=api_results,
            timestamp=bulk_result.timestamp
        )
        
        # Return with appropriate status code
        return JSONResponse(
            content=response_data.dict(),
            status_code=response_status
        )
        
    except Exception as e:
        # This should rarely happen now since TagService handles its own errors
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Unexpected error in bulk read API: {str(e)}", extra={
            **context, "error": str(e), "duration_ms": duration_ms
        })
        
        # Return error response for all requested tags
        error_results = []
        for tag_name in request.tag_names:
            error_result = TagReadResponse(
                plc_id=plc_id,
                tag_name=tag_name,
                status="error",
                error_type="UnknownError",
                error_message=f"Internal server error: {str(e)}",
                timestamp=time.time()
            )
            error_results.append(error_result)
        
        return BulkReadResponseModel(
            plc_id=plc_id,
            summary={
                "total_requested": len(request.tag_names),
                "successful": 0,
                "failed": len(request.tag_names)
            },
            overall_status="failed",
            results=error_results,
            timestamp=time.time()
        )


@router.post("/bulk-write/{plc_id}", response_model=BulkWriteResponseModel)
async def write_multiple_tags_endpoint(plc_id: str, request: BulkWriteRequest, plc_handler=get_plc_handler) -> BulkWriteResponseModel:
    """
    Write multiple tags to a PLC concurrently.
    
    Args:
        plc_id: The PLC identifier
        request: Request body containing dictionary of tag names to values
        
    Returns:
        JSON object containing results for all tag writes, including both successful and failed operations
        
    Response includes:
        - summary: counts of total requested, successful, and failed writes
        - overall_status: "success" (all succeeded), "partial_success" (mixed), or "failed" (all failed)  
        - results: detailed results for each tag including success confirmation or error information
        
    Note:
        This endpoint uses different status codes based on results:
        - 200: Complete success or complete failure (check overall_status)
        - 207: Partial success (some tags succeeded, some failed)
    """
    if not plc_handler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is initializing, please try again later"
        )
    
    start_time = time.time()
    context = {
        "plc_id": plc_id, 
        "tag_count": len(request.tag_data),
        "operation": "write_multiple_tags_api"
    }
    
    logger.info(f"Bulk write request for {len(request.tag_data)} tags to PLC {plc_id}")
    
    try:
        # Call the tag service - it always returns BulkWriteResponse
        bulk_result = await plc_handler.write_multiple_tags(plc_id, request.tag_data)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Convert internal result format to API response format
        api_results = []
        for result in bulk_result.results:
            api_result = convert_write_result_to_response(result, plc_id)
            api_results.append(api_result)
        
        # Determine HTTP status code based on results
        if bulk_result.overall_status == "success":
            response_status = status.HTTP_200_OK
        elif bulk_result.overall_status == "partial_success":
            response_status = status.HTTP_207_MULTI_STATUS  # Some succeeded, some failed
        else:  # "failed"
            response_status = status.HTTP_200_OK  # Still return 200, but with error details in response
        
        logger.info(f"Bulk write API completed", extra={
            **context, 
            "successful_count": bulk_result.successful_count,
            "failed_count": bulk_result.failed_count,
            "overall_status": bulk_result.overall_status,
            "duration_ms": duration_ms
        })
        
        response_data = BulkWriteResponseModel(
            plc_id=bulk_result.plc_id,
            summary={
                "total_requested": bulk_result.total_requested,
                "successful": bulk_result.successful_count,
                "failed": bulk_result.failed_count
            },
            overall_status=bulk_result.overall_status,
            results=api_results,
            timestamp=bulk_result.timestamp
        )
        
        # Return with appropriate status code
        return JSONResponse(
            content=response_data.dict(),
            status_code=response_status
        )
        
    except Exception as e:
        # This should rarely happen now since TagService handles its own errors
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Unexpected error in bulk write API: {str(e)}", extra={
            **context, "error": str(e), "duration_ms": duration_ms
        })
        
        # Return error response for all requested tags
        error_results = []
        for tag_name, data in request.tag_data.items():
            error_result = TagWriteResponse(
                plc_id=plc_id,
                tag_name=tag_name,
                status="error",
                data=data,
                error_type="UnknownError",
                error_message=f"Internal server error: {str(e)}",
                timestamp=time.time()
            )
            error_results.append(error_result)
        
        return BulkWriteResponseModel(
            plc_id=plc_id,
            summary={
                "total_requested": len(request.tag_data),
                "successful": 0,
                "failed": len(request.tag_data)
            },
            overall_status="failed",
            results=error_results,
            timestamp=time.time()
        )


@router.get("/read/{plc_id}/{tag_name}", response_model=TagReadResponse)
async def read_tag_endpoint(plc_id: str, tag_name: str, plc_handler=get_plc_handler) -> TagReadResponse:
    """
    Read data from a PLC tag.
    
    Args:
        plc_id: The PLC identifier
        tag_name: The name of the tag to read
        
    Returns:
        JSON object containing the tag data and metadata or error information
        
    Note:
        This endpoint always returns 200 OK, but the response includes a status field
        indicating whether the operation was successful or failed, along with error details.
    """
    if not plc_handler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is initializing, please try again later"
        )
    
    start_time = time.time()
    context = {"plc_id": plc_id, "tag_name": tag_name, "operation": "read_tag_api"}
    
    try:
        # Call the tag service - it now returns TagReadResult always
        result = await plc_handler.read_tag(plc_id, tag_name)
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.debug(f"Tag read API completed with status: {result.status.value}", extra={
            **context, "duration_ms": duration_ms, "status": result.status.value
        })
        
        return convert_read_result_to_response(result, plc_id)
        
    except Exception as e:
        # This should rarely happen now since TagService handles its own errors
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Unexpected error in read tag API: {str(e)}", extra={
            **context, "error": str(e), "duration_ms": duration_ms
        })
        # Return error response instead of raising exception
        return TagReadResponse(
            plc_id=plc_id,
            tag_name=tag_name,
            status="error",
            error_type="UnknownError",
            error_message=f"Internal server error: {str(e)}",
            timestamp=time.time()
        )


@router.post("/write/{plc_id}/{tag_name}", response_model=TagWriteResponse)
async def write_tag_endpoint(plc_id: str, tag_name: str, request: WriteTagRequest, plc_handler=get_plc_handler) -> TagWriteResponse:
    """
    Write data to a PLC tag.
    
    Args:
        plc_id: The PLC identifier
        tag_name: The name of the tag to write
        request: Request body containing the data to write
        
    Returns:
        JSON object with operation details or error information
        
    Note:
        This endpoint always returns 200 OK, but the response includes a status field
        indicating whether the operation was successful or failed, along with error details.
    """
    if not plc_handler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is initializing, please try again later"
        )
    
    start_time = time.time()
    context = {
        "plc_id": plc_id, 
        "tag_name": tag_name, 
        "data": request.data,
        "operation": "write_tag_api"
    }
    
    try:
        # Call the tag service - it now returns TagWriteResult always
        result = await plc_handler.write_tag(plc_id, tag_name, request.data)
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.debug(f"Tag write API completed with status: {result.status.value}", extra={
            **context, "duration_ms": duration_ms, "status": result.status.value
        })
        
        return convert_write_result_to_response(result, plc_id)
        
    except Exception as e:
        # This should rarely happen now since TagService handles its own errors
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Unexpected error in write tag API: {str(e)}", extra={
            **context, "error": str(e), "duration_ms": duration_ms
        })
        # Return error response instead of raising exception
        return TagWriteResponse(
            plc_id=plc_id,
            tag_name=tag_name,
            status="error",
            data=request.data,
            error_type="UnknownError",
            error_message=f"Internal server error: {str(e)}",
            timestamp=time.time()
        )
