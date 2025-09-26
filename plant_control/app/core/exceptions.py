from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
import time

from plant_control.app.core.tag_exceptions import (
    TagServiceError, ConfigurationError, ValidationError, 
    AddressResolutionError, EncodingError, ConnectionError
)
from plant_control.app.utilities.telemetry import logger

from plant_control.app.schemas.common import ErrorDetail, ErrorResponse


def setup_exception_handlers(app: FastAPI):
    """Setup custom exception handlers for the FastAPI app"""
    
    @app.exception_handler(TagServiceError)
    async def tag_service_exception_handler(request: Request, exc: TagServiceError):
        """Handle custom TagService exceptions with appropriate HTTP status codes"""
        
        # Map exception types to HTTP status codes
        status_code_map = {
            ConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            ValidationError: status.HTTP_400_BAD_REQUEST,
            AddressResolutionError: status.HTTP_404_NOT_FOUND,
            EncodingError: status.HTTP_422_UNPROCESSABLE_ENTITY,
            ConnectionError: status.HTTP_503_SERVICE_UNAVAILABLE,
            TagServiceError: status.HTTP_500_INTERNAL_SERVER_ERROR,  # Generic fallback
        }
        
        status_code = status_code_map.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        error_detail = ErrorDetail(
            error_type=type(exc).__name__,
            message=str(exc),
            plc_id=getattr(exc, 'plc_id', None),
            tag_name=getattr(exc, 'tag_name', None),
            address=getattr(exc, 'address', None),
            timestamp=time.time()
        )
        
        logger.error(f"TagService error: {error_detail.error_type} - {error_detail.message}", extra={
            "error_type": error_detail.error_type,
            "plc_id": error_detail.plc_id,
            "tag_name": error_detail.tag_name,
            "address": error_detail.address,
            "status_code": status_code
        })
        
        return JSONResponse(
            status_code=status_code,
            content=ErrorResponse(detail=error_detail).dict()
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions gracefully"""
        error_detail = ErrorDetail(
            error_type="InternalServerError",
            message="An unexpected error occurred",
            timestamp=time.time()
        )
        
        logger.error(f"Unexpected error: {str(exc)}", extra={
            "error": str(exc),
            "request_path": request.url.path,
            "request_method": request.method
        }, exc_info=True)
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(detail=error_detail).dict()
        )
