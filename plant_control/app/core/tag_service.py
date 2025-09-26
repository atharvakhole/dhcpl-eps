from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder, BinaryPayloadDecoder
from typing import Any, Dict, List, Optional, Tuple
import time
import asyncio
from plant_control.app.models.connection_manager import ModbusOperation
from plant_control.app.core.connection_manager import connection_manager
from plant_control.app.utilities.telemetry import logger
from plant_control.app.config import config_manager
from dataclasses import dataclass
from enum import Enum


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


class TagService:
    """
    Provides a high level interface to read from and write to registers

    Handles the following:
    1. Address Translation: Convert logical tag names to physical addresses using vendor mapping rules
    2. Data Type Handling: Determine register count needed based on data types (e.g., float32 = 2 registers)
    3. Encoding/Decoding: Convert between application values and raw register data
    4. Payload Construction: Build proper byte arrays for writes
    5. Validation: Check value ranges, readonly flags, data type compatibility

    Note: All connection handling, retries, and communication reliability is handled by connection_manager
    """

    async def read_tag(self, plc_id: str, tag_name: str) -> TagReadResult:
        """Reads data from the register corresponding to the given tag."""
        start_time = time.time()
        timestamp = start_time
        context = {"plc_id": plc_id, "tag_name": tag_name}
        
        try:
            logger.info(f"Reading tag {tag_name} from PLC {plc_id}")
            
            # Validate inputs
            if not plc_id or not isinstance(plc_id, str):
                raise ValidationError("PLC ID must be a non-empty string", plc_id=plc_id, tag_name=tag_name)
            if not tag_name or not isinstance(tag_name, str):
                raise ValidationError("Tag name must be a non-empty string", plc_id=plc_id, tag_name=tag_name)
            
            # Resolve tag configuration
            original_address = self._get_address_from_tagname(plc_id, tag_name)
            context["address"] = original_address
            
            converted_modbus_address = self._convert_modbus_address(plc_id, original_address)
            register_type = self._get_register_type(plc_id, original_address)
            data_type = self._get_data_type(plc_id, original_address)
            decode_type = self._get_decode_type(plc_id, original_address)
            register_count = self._determine_register_count(data_type)
            
            # Build and execute operation
            operation = self._build_modbus_operation("read", converted_modbus_address, original_address, register_type, register_count)
            registers = await connection_manager.execute_operation(plc_id, operation)
            
            # Decode result
            decoded_data = self._decode_registers(registers, decode_type)
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Tag read completed in {duration_ms}ms")
            logger.debug(f"Tag read completed", extra={
                "operation": "read_tag", **context, "duration_ms": duration_ms,
                "registers": registers, "result": decoded_data
            })

            return TagReadResult(
                tag_name=tag_name,
                status=ReadStatus.SUCCESS,
                data=decoded_data,
                registers=registers,
                timestamp=timestamp
            )
            
        except TagServiceError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"Tag read failed: {type(e).__name__}: {str(e)}", extra={
                "operation": "read_tag", **context, "duration_ms": duration_ms
            })
            return TagReadResult(
                tag_name=tag_name,
                status=ReadStatus.ERROR,
                error_type=type(e).__name__,
                error_message=str(e),
                timestamp=timestamp
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Unexpected error reading tag {tag_name} from PLC {plc_id}: {str(e)}"
            logger.error(error_msg, extra={
                "operation": "read_tag", **context, "error": str(e), "duration_ms": duration_ms
            })
            return TagReadResult(
                tag_name=tag_name,
                status=ReadStatus.ERROR,
                error_type="UnknownError",
                error_message=error_msg,
                timestamp=timestamp
            )

    async def write_tag(self, plc_id: str, tag_name: str, data: Any) -> TagWriteResult:
        """Writes data to the register corresponding to the given tag."""
        start_time = time.time()
        timestamp = start_time
        context = {"plc_id": plc_id, "tag_name": tag_name, "data": data}
        
        try:
            logger.info(f"Writing {data} to tag {tag_name} on PLC {plc_id}")
            
            # Validate inputs
            if not plc_id or not isinstance(plc_id, str):
                raise ValidationError("PLC ID must be a non-empty string", plc_id=plc_id, tag_name=tag_name)
            if not tag_name or not isinstance(tag_name, str):
                raise ValidationError("Tag name must be a non-empty string", plc_id=plc_id, tag_name=tag_name)
            if data is None:
                raise ValidationError("Data cannot be None", plc_id=plc_id, tag_name=tag_name)
            
            # Resolve tag configuration
            original_address = self._get_address_from_tagname(plc_id, tag_name)
            context["address"] = original_address
            
            converted_modbus_address = self._convert_modbus_address(plc_id, original_address)
            payload = self._construct_payload(plc_id, original_address, data)
            register_type = self._get_register_type(plc_id, original_address)

            # Build and execute operation
            operation = self._build_modbus_operation("write", converted_modbus_address, original_address, register_type, 0, payload)
            result = await connection_manager.execute_operation(plc_id, operation)
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Tag write completed in {duration_ms}ms", extra={
                "operation": "write_tag", **context, "address": original_address,
                "convert_modbus_address": converted_modbus_address, "duration_ms": duration_ms
            })

            return TagWriteResult(
                tag_name=tag_name,
                status=WriteStatus.SUCCESS,
                data=data,
                result=result,
                timestamp=timestamp
            )
            
        except TagServiceError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"Tag write failed: {type(e).__name__}: {str(e)}", extra={
                "operation": "write_tag", **context, "duration_ms": duration_ms
            })
            return TagWriteResult(
                tag_name=tag_name,
                status=WriteStatus.ERROR,
                data=data,
                error_type=type(e).__name__,
                error_message=str(e),
                timestamp=timestamp
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Unexpected error writing to tag {tag_name} on PLC {plc_id}: {str(e)}"
            logger.error(error_msg, extra={
                "operation": "write_tag", **context, "error": str(e), "duration_ms": duration_ms
            })
            return TagWriteResult(
                tag_name=tag_name,
                status=WriteStatus.ERROR,
                data=data,
                error_type="UnknownError",
                error_message=error_msg,
                timestamp=timestamp
            )

    async def read_multiple_tags(self, plc_id: str, tag_names: List[str], verbose_logging: bool = False) -> BulkReadResponse:
        """
        Read multiple tags from a single PLC concurrently with minimal logging for high-frequency operations
        
        Args:
            plc_id: The PLC identifier
            tag_names: List of tag names to read
            verbose_logging: Enable detailed logging (default: False for performance)
            
        Returns:
            BulkReadResponse containing results for all tag reads
        """
        start_time = time.time()
        timestamp = start_time
        
        # Only log at INFO level for bulk operations summary, not individual tags
        if verbose_logging:
            logger.info(f"Reading {len(tag_names)} tags from PLC {plc_id}")
        
        try:
            # Input validation (errors always logged)
            if not plc_id or not isinstance(plc_id, str):
                logger.error(f"Invalid PLC ID for bulk read: {plc_id}")
                raise ValidationError("PLC ID must be a non-empty string", plc_id=plc_id)
            if not tag_names or not isinstance(tag_names, list) or len(tag_names) == 0:
                logger.error(f"Invalid tag names for bulk read: {tag_names}")
                raise ValidationError("Tag names must be a non-empty list", plc_id=plc_id)
            
            # Filter valid tag names (no logging for individual invalid tags unless verbose)
            valid_tag_names = []
            invalid_count = 0
            for tag_name in tag_names:
                if not tag_name or not isinstance(tag_name, str):
                    invalid_count += 1
                    if verbose_logging:
                        logger.warning(f"Skipping invalid tag name: {tag_name}")
                    continue
                valid_tag_names.append(tag_name)
            
            if not valid_tag_names:
                logger.error(f"No valid tag names provided for bulk read on PLC {plc_id}")
                raise ValidationError("No valid tag names provided", plc_id=plc_id)
            
            # Only log invalid count if there were any and not in verbose mode
            if invalid_count > 0 and not verbose_logging:
                logger.warning(f"Skipped {invalid_count} invalid tag names in bulk read for PLC {plc_id}")
            
            # Create tasks for concurrent execution
            tasks = []
            for tag_name in valid_tag_names:
                task = asyncio.create_task(
                    self._optimized_read_single_tag(plc_id, tag_name, timestamp, verbose_logging),
                    name=f"read_tag_{plc_id}_{tag_name}"
                )
                tasks.append(task)
            
            # Execute all reads concurrently - no debug logging here
            results = await asyncio.gather(*tasks, return_exceptions=False)
            
            # Analyze results
            successful_count = sum(1 for r in results if r.status == ReadStatus.SUCCESS)
            failed_count = len(results) - successful_count
            
            # Determine overall status
            if failed_count == 0:
                overall_status = "success"
            elif successful_count == 0:
                overall_status = "failed"
            else:
                overall_status = "partial_success"
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Only log summary info, not individual tag details
            if failed_count > 0 or verbose_logging:
                # Always log if there are failures, or if verbose logging is enabled
                logger.info(f"Bulk read PLC {plc_id} completed in {duration_ms}ms: {successful_count} successful, {failed_count} failed")
            
            return BulkReadResponse(
                plc_id=plc_id,
                total_requested=len(valid_tag_names),
                successful_count=successful_count,
                failed_count=failed_count,
                results=results,
                overall_status=overall_status,
                timestamp=timestamp
            )
            
        except TagServiceError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            # Always log validation errors
            logger.error(f"Bulk read validation failed for PLC {plc_id}: {str(e)} (duration: {duration_ms}ms)")
            
            # Return error response for all requested tags
            error_results = [
                TagReadResult(
                    tag_name=tag_name,
                    status=ReadStatus.ERROR,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    timestamp=timestamp
                ) for tag_name in tag_names
            ]
            return BulkReadResponse(
                plc_id=plc_id,
                total_requested=len(tag_names),
                successful_count=0,
                failed_count=len(tag_names),
                results=error_results,
                overall_status="failed",
                timestamp=timestamp
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Unexpected error during bulk read from PLC {plc_id}: {str(e)}"
            # Always log unexpected errors
            logger.error(f"{error_msg} (duration: {duration_ms}ms)", exc_info=True)
            
            # Return error response for all requested tags
            error_results = [
                TagReadResult(
                    tag_name=tag_name,
                    status=ReadStatus.ERROR,
                    error_type="UnknownError",
                    error_message=error_msg,
                    timestamp=timestamp
                ) for tag_name in tag_names
            ]
            return BulkReadResponse(
                plc_id=plc_id,
                total_requested=len(tag_names),
                successful_count=0,
                failed_count=len(tag_names),
                results=error_results,
                overall_status="failed",
                timestamp=timestamp
            )

    async def write_multiple_tags(self, plc_id: str, tag_data: Dict[str, Any], verbose_logging: bool = False) -> BulkWriteResponse:
        """
        Write multiple tags to a single PLC concurrently with minimal logging for high-frequency operations
        """
        start_time = time.time()
        timestamp = start_time
        
        if verbose_logging:
            logger.info(f"Writing {len(tag_data)} tags to PLC {plc_id}")
        
        try:
            # Input validation (errors always logged)
            if not plc_id or not isinstance(plc_id, str):
                logger.error(f"Invalid PLC ID for bulk write: {plc_id}")
                raise ValidationError("PLC ID must be a non-empty string", plc_id=plc_id)
            if not tag_data or not isinstance(tag_data, dict):
                logger.error(f"Invalid tag data for bulk write: {tag_data}")
                raise ValidationError("Tag data must be a non-empty dictionary", plc_id=plc_id)
            
            # Create tasks for concurrent execution
            tasks = []
            invalid_count = 0
            for tag_name, data in tag_data.items():
                if not tag_name or not isinstance(tag_name, str):
                    invalid_count += 1
                    if verbose_logging:
                        logger.warning(f"Skipping invalid tag name: {tag_name}")
                    continue
                
                task = asyncio.create_task(
                    self._optimized_write_single_tag(plc_id, tag_name, data, timestamp, verbose_logging),
                    name=f"write_tag_{plc_id}_{tag_name}"
                )
                tasks.append(task)
            
            if not tasks:
                logger.error(f"No valid tag write operations for PLC {plc_id}")
                raise ValidationError("No valid tag write operations to perform", plc_id=plc_id)
            
            if invalid_count > 0 and not verbose_logging:
                logger.warning(f"Skipped {invalid_count} invalid tag operations in bulk write for PLC {plc_id}")
            
            # Execute all writes concurrently
            results = await asyncio.gather(*tasks, return_exceptions=False)
            
            # Analyze results
            successful_count = sum(1 for r in results if r.status == WriteStatus.SUCCESS)
            failed_count = len(results) - successful_count
            
            # Determine overall status
            if failed_count == 0:
                overall_status = "success"
            elif successful_count == 0:
                overall_status = "failed"
            else:
                overall_status = "partial_success"
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Only log summary if there are failures or verbose logging is enabled
            if failed_count > 0 or verbose_logging:
                logger.info(f"Bulk write PLC {plc_id} completed in {duration_ms}ms: {successful_count} successful, {failed_count} failed")
            
            return BulkWriteResponse(
                plc_id=plc_id,
                total_requested=len(tasks),
                successful_count=successful_count,
                failed_count=failed_count,
                results=results,
                overall_status=overall_status,
                timestamp=timestamp
            )
            
        except TagServiceError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Bulk write validation failed for PLC {plc_id}: {str(e)} (duration: {duration_ms}ms)")
            
            # Return error response for all requested tags
            error_results = [
                TagWriteResult(
                    tag_name=tag_name,
                    status=WriteStatus.ERROR,
                    data=data,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    timestamp=timestamp
                ) for tag_name, data in tag_data.items()
            ]
            return BulkWriteResponse(
                plc_id=plc_id,
                total_requested=len(tag_data),
                successful_count=0,
                failed_count=len(tag_data),
                results=error_results,
                overall_status="failed",
                timestamp=timestamp
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Unexpected error during bulk write to PLC {plc_id}: {str(e)}"
            logger.error(f"{error_msg} (duration: {duration_ms}ms)", exc_info=True)
            
            # Return error response for all requested tags
            error_results = [
                TagWriteResult(
                    tag_name=tag_name,
                    status=WriteStatus.ERROR,
                    data=data,
                    error_type="UnknownError",
                    error_message=error_msg,
                    timestamp=timestamp
                ) for tag_name, data in tag_data.items()
            ]
            return BulkWriteResponse(
                plc_id=plc_id,
                total_requested=len(tag_data),
                successful_count=0,
                failed_count=len(tag_data),
                results=error_results,
                overall_status="failed",
                timestamp=timestamp
            )

    async def _optimized_read_single_tag(self, plc_id: str, tag_name: str, timestamp: float, verbose_logging: bool = False) -> TagReadResult:
        """
        Optimized single tag read with minimal logging for high-frequency bulk operations
        
        This method contains the same logic as read_tag() but with minimal logging for performance.
        Use verbose_logging=True for debugging or troubleshooting.
        """
        try:
            # Core business logic (same as read_tag but without excessive logging)
            
            # Resolve tag configuration (errors logged, success not logged unless verbose)
            try:
                original_address = self._get_address_from_tagname(plc_id, tag_name)
                converted_modbus_address = self._convert_modbus_address(plc_id, original_address)
                register_type = self._get_register_type(plc_id, original_address)
                data_type = self._get_data_type(plc_id, original_address)
                decode_type = self._get_decode_type(plc_id, original_address)
                register_count = self._determine_register_count(data_type)
            except Exception as e:
                # Configuration/resolution errors are always important to log
                logger.error(f"Tag resolution failed for {plc_id}.{tag_name}: {str(e)}")
                return TagReadResult(
                    tag_name=tag_name,
                    status=ReadStatus.ERROR,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    timestamp=timestamp
                )
            
            # Build and execute operation (no debug logging unless verbose)
            try:
                operation = self._build_modbus_operation("read", converted_modbus_address, original_address, register_type, register_count)
                registers = await connection_manager.execute_operation(plc_id, operation)
            except Exception as e:
                # Connection errors are always important to log
                logger.error(f"Operation execution failed for {plc_id}.{tag_name}: {str(e)}")
                return TagReadResult(
                    tag_name=tag_name,
                    status=ReadStatus.ERROR,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    timestamp=timestamp
                )
            
            # Decode result (encoding errors logged, success not logged unless verbose)
            try:
                decoded_data = self._decode_registers_minimal_logging(registers, decode_type, verbose_logging)
            except Exception as e:
                # Decoding errors are always important to log
                logger.error(f"Decoding failed for {plc_id}.{tag_name}: {str(e)}")
                return TagReadResult(
                    tag_name=tag_name,
                    status=ReadStatus.ERROR,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    timestamp=timestamp
                )
            
            # Success - no individual tag success logging unless verbose
            if verbose_logging:
                logger.debug(f"Tag read successful: {plc_id}.{tag_name} = {decoded_data}")
                
            return TagReadResult(
                tag_name=tag_name,
                status=ReadStatus.SUCCESS,
                data=decoded_data,
                registers=registers,
                timestamp=timestamp
            )
            
        except TagServiceError as e:
            # Our custom exceptions - already have specific error messages
            if verbose_logging:
                logger.warning(f"TagService error reading {plc_id}.{tag_name}: {type(e).__name__}: {str(e)}")
            return TagReadResult(
                tag_name=tag_name,
                status=ReadStatus.ERROR,
                error_type=type(e).__name__,
                error_message=str(e),
                timestamp=timestamp
            )
        except Exception as e:
            # Unexpected errors are always logged
            logger.error(f"Unexpected error reading {plc_id}.{tag_name}: {str(e)}", exc_info=verbose_logging)
            return TagReadResult(
                tag_name=tag_name,
                status=ReadStatus.ERROR,
                error_type="UnknownError",
                error_message=f"Unexpected error: {str(e)}",
                timestamp=timestamp
            )

    async def _optimized_write_single_tag(self, plc_id: str, tag_name: str, data: Any, timestamp: float, verbose_logging: bool = False) -> TagWriteResult:
        """Optimized single tag write with minimal logging"""
        try:
            # Core write logic (same as write_tag but minimal logging)
            try:
                original_address = self._get_address_from_tagname(plc_id, tag_name)
                converted_modbus_address = self._convert_modbus_address(plc_id, original_address)
                payload = self._construct_payload(plc_id, original_address, data)
                register_type = self._get_register_type(plc_id, original_address)
            except Exception as e:
                logger.error(f"Tag resolution/validation failed for write {plc_id}.{tag_name}: {str(e)}")
                return TagWriteResult(
                    tag_name=tag_name,
                    status=WriteStatus.ERROR,
                    data=data,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    timestamp=timestamp
                )

            try:
                operation = self._build_modbus_operation("write", converted_modbus_address, original_address, register_type, 0, payload)
                result = await connection_manager.execute_operation(plc_id, operation)
            except Exception as e:
                logger.error(f"Write operation failed for {plc_id}.{tag_name}: {str(e)}")
                return TagWriteResult(
                    tag_name=tag_name,
                    status=WriteStatus.ERROR,
                    data=data,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    timestamp=timestamp
                )

            # Success
            if verbose_logging:
                logger.debug(f"Tag write successful: {plc_id}.{tag_name} = {data}")

            return TagWriteResult(
                tag_name=tag_name,
                status=WriteStatus.SUCCESS,
                data=data,
                result=result,
                timestamp=timestamp
            )
            
        except TagServiceError as e:
            if verbose_logging:
                logger.warning(f"TagService error writing {plc_id}.{tag_name}: {type(e).__name__}: {str(e)}")
            return TagWriteResult(
                tag_name=tag_name,
                status=WriteStatus.ERROR,
                data=data,
                error_type=type(e).__name__,
                error_message=str(e),
                timestamp=timestamp
            )
        except Exception as e:
            logger.error(f"Unexpected error writing {plc_id}.{tag_name}: {str(e)}", exc_info=verbose_logging)
            return TagWriteResult(
                tag_name=tag_name,
                status=WriteStatus.ERROR,
                data=data,
                error_type="UnknownError",
                error_message=f"Unexpected error: {str(e)}",
                timestamp=timestamp
            )

    # Convenience methods for specific logging needs
    async def read_multiple_tags_silent(self, plc_id: str, tag_names: List[str]) -> BulkReadResponse:
        """Ultra-minimal logging version for very high-frequency operations (sub-second polling)"""
        return await self.read_multiple_tags(plc_id, tag_names, verbose_logging=False)

    async def read_multiple_tags_verbose(self, plc_id: str, tag_names: List[str]) -> BulkReadResponse:
        """Full logging version for debugging and troubleshooting"""
        return await self.read_multiple_tags(plc_id, tag_names, verbose_logging=True)

    def _decode_registers(self, registers: List[Any], decode_as: str) -> Any:
        """Decode register values to application data type."""
        if not registers:
            raise EncodingError("No registers provided for decoding")
        
        if not isinstance(registers, list):
            raise EncodingError(f"Registers must be a list, got {type(registers)}")

        try:
            decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.BIG, wordorder=Endian.BIG)
            
            logger.debug("Decoding registers", extra={
                "registers": registers,
                "decode_as": decode_as,
            })
            
            if decode_as == "uint16":
                result = decoder.decode_16bit_uint()
            elif decode_as == "float32":
                result = decoder.decode_32bit_float()
            elif decode_as == "int16":
                result = decoder.decode_16bit_int()
            elif decode_as == "uint32":
                result = decoder.decode_32bit_uint()
            elif decode_as == "int32":
                result = decoder.decode_32bit_int()
            else:
                logger.warning(f"Unknown decode type '{decode_as}', defaulting to uint16")
                result = decoder.decode_16bit_uint()
                
            logger.debug("Decoded registers", extra={
                "registers": registers,
                "decode_as": decode_as,
                "result": result,
            })
            return result
            
        except Exception as e:
            error_msg = f"Failed to decode {len(registers)} registers as {decode_as}: {str(e)}"
            logger.error(error_msg, extra={
                "registers": registers,
                "decode_as": decode_as,
            })
            raise EncodingError(error_msg) from e

    def _decode_registers_minimal_logging(self, registers: List[Any], decode_as: str, verbose_logging: bool = False) -> Any:
        """Decode register values with minimal logging for bulk operations"""
        if not registers:
            raise EncodingError("No registers provided for decoding")
        
        if not isinstance(registers, list):
            raise EncodingError(f"Registers must be a list, got {type(registers)}")

        try:
            decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.BIG, wordorder=Endian.BIG)
            
            # Only log debug info if verbose logging is enabled
            if verbose_logging:
                logger.debug(f"Decoding {len(registers)} registers as {decode_as}")
            
            if decode_as == "uint16":
                result = decoder.decode_16bit_uint()
            elif decode_as == "float32":
                result = decoder.decode_32bit_float()
            elif decode_as == "int16":
                result = decoder.decode_16bit_int()
            elif decode_as == "uint32":
                result = decoder.decode_32bit_uint()
            elif decode_as == "int32":
                result = decoder.decode_32bit_int()
            else:
                # Always log unknown decode types
                logger.warning(f"Unknown decode type '{decode_as}', defaulting to uint16")
                result = decoder.decode_16bit_uint()
                
            if verbose_logging:
                logger.debug(f"Decoded result: {result}")
                
            return result
            
        except Exception as e:
            error_msg = f"Failed to decode {len(registers)} registers as {decode_as}: {str(e)}"
            # Always log decoding errors with register details for debugging
            logger.error(f"{error_msg} (registers: {registers})")
            raise EncodingError(error_msg) from e

    def _get_register_type(self, plc_id: str, original_address: int) -> str:
        """Get register type from register config"""
        try:
            register_config = config_manager.get_register_config(plc_id, original_address)
            if not register_config:
                raise ConfigurationError(f"No register configuration found", 
                                       plc_id=plc_id, address=original_address)

            register_type = register_config.get("register_type", "holding_register")
            
            # Validate register type
            valid_types = ["holding_register", "input_register", "discrete_input", "coil"]
            if register_type not in valid_types:
                logger.warning(f"Invalid register type '{register_type}', defaulting to holding_register")
                register_type = "holding_register"

            return register_type
            
        except Exception as e:
            raise ConfigurationError(f"Failed to get register type for address {original_address}: {str(e)}", 
                                   plc_id=plc_id, address=original_address) from e

    def _get_decode_type(self, plc_id: str, original_address: int) -> str:
        """Get decode type from register config"""
        try:
            register_config = config_manager.get_register_config(plc_id, original_address)
            if not register_config:
                raise ConfigurationError(f"No register configuration found", 
                                       plc_id=plc_id, address=original_address)

            return register_config.get("decode_as", "uint16")
            
        except Exception as e:
            raise ConfigurationError(f"Failed to get decode type for address {original_address}: {str(e)}", 
                                   plc_id=plc_id, address=original_address) from e

    def _get_data_type(self, plc_id: str, original_address: int) -> str:
        """Get data type of stored data from register config"""
        try:
            register_config = config_manager.get_register_config(plc_id, original_address)
            if not register_config:
                raise ConfigurationError(f"No register configuration found", 
                                       plc_id=plc_id, address=original_address)

            return register_config.get("stored_as", "uint16")
            
        except Exception as e:
            raise ConfigurationError(f"Failed to get data type for address {original_address}: {str(e)}", 
                                   plc_id=plc_id, address=original_address) from e

    def _build_modbus_operation(self, read_write: str, address: int, original_address: int, 
                               register_type: str, count: int, payload: Optional[List[Any]] = None, 
                               unit_id: int = 1) -> ModbusOperation:
        """Construct the modbus operation to be executed"""
        try:
            if read_write == "read":
                read_operation_type_map = {
                    "holding_register": "read_holding",
                    "input_register": "read_input", 
                    "discrete_input": "read_discrete",
                    "coil": "read_coil"
                }
                operation_type = read_operation_type_map.get(register_type, "read_holding")
            elif read_write == "write":
                operation_type = "write_coil" if register_type == "coil" else "write_registers"
            else:
                raise ValidationError(f"Invalid operation type: {read_write}")

            logger.debug(f"Constructed modbus operation", extra={
                "operation_type": operation_type,
                "address": address,
                "original_address": original_address,
                "values": payload,
                "count": count,
                "unit_id": unit_id
            })
            
            return ModbusOperation(
                operation_type=operation_type,
                address=address,
                original_address=original_address,
                values=payload,
                count=count,
                unit_id=unit_id
            )
            
        except Exception as e:
            raise ValidationError(f"Failed to build modbus operation: {str(e)}") from e

    def _is_valid_data(self, plc_id: str, address: int, data: Any) -> bool:
        """Validates data against register configuration rules."""
        try:
            # Check PLC configuration exists
            plc_config = config_manager.get_plc_config(plc_id)
            if not plc_config:
                raise ConfigurationError(f"No PLC configuration found", plc_id=plc_id)

            # Check register configuration exists
            register_config = config_manager.get_register_config(plc_id, address)
            if not register_config:
                raise ConfigurationError(f"No register configuration found", 
                                       plc_id=plc_id, address=address)

            # Check readonly protection
            if register_config.get('readonly', False):
                raise ValidationError(f"Cannot write to readonly register", 
                                    plc_id=plc_id, address=address)

            # Validate data exists
            if data is None:
                raise ValidationError("Data cannot be None", plc_id=plc_id, address=address)

            # Convert data to numeric format
            try:
                if isinstance(data, bool):
                    numeric_data = float(data)
                elif isinstance(data, (int, float)):
                    numeric_data = float(data)
                else:
                    numeric_data = float(data)
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Cannot convert data '{data}' to numeric value", 
                                    plc_id=plc_id, address=address) from e

            # Range validation
            min_value = register_config.get('min_value')
            max_value = register_config.get('max_value')
            
            if min_value is not None and numeric_data < min_value:
                raise ValidationError(f"Value {numeric_data} below minimum {min_value}", 
                                    plc_id=plc_id, address=address)
                
            if max_value is not None and numeric_data > max_value:
                raise ValidationError(f"Value {numeric_data} above maximum {max_value}", 
                                    plc_id=plc_id, address=address)

            # Digital tag validation
            tag_type = register_config.get('tag_type', '').lower()
            if tag_type == 'digital' and numeric_data not in [0.0, 1.0]:
                raise ValidationError(f"Digital tag requires 0 or 1, got {numeric_data}", 
                                    plc_id=plc_id, address=address)

            # Integer type validation
            stored_as = register_config.get('stored_as', 'uint16')
            if tag_type == 'digital' or stored_as in ['int16', 'int32', 'uint16', 'uint32']:
                if numeric_data != int(numeric_data):
                    raise ValidationError(f"Integer type {stored_as} requires whole number, got {numeric_data}", 
                                        plc_id=plc_id, address=address)

            return True
            
        except TagServiceError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            raise ValidationError(f"Data validation failed: {str(e)}", 
                                plc_id=plc_id, address=address) from e

    def _construct_payload(self, plc_id: str, address: int, data: Any) -> List[Any]:
        """Constructs binary payload for Modbus register write operation."""
        try:
            # Validate data first
            self._is_valid_data(plc_id, address, data)

            register_config = config_manager.get_register_config(plc_id, address)
            if not register_config:
                raise ConfigurationError(f"No register configuration found", 
                                       plc_id=plc_id, address=address)
            
            stored_as = register_config.get('stored_as', 'uint16')
            encode_as = register_config.get('encode_as', 'uint16')
            
            # Build payload using pymodbus
            builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
            
            if encode_as == 'uint16':
                builder.add_16bit_uint(int(data))
            elif encode_as == 'int16':
                builder.add_16bit_int(int(data))
            elif encode_as == 'uint32':
                builder.add_32bit_uint(int(data))
            elif encode_as == 'int32':
                builder.add_32bit_int(int(data))
            elif encode_as == 'float32':
                builder.add_32bit_float(float(data))
            else:
                raise EncodingError(f"Unsupported encoding type: {encode_as}", 
                                  plc_id=plc_id, address=address)

            payload = builder.to_registers()
            logger.debug(f"Constructed payload for {plc_id}:{address} - {len(payload)} registers")
            return payload
            
        except TagServiceError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            raise EncodingError(f"Failed to construct payload: {str(e)}", 
                              plc_id=plc_id, address=address) from e

    def _get_address_from_tagname(self, plc_id: str, tag_name: str) -> int:
        """Resolves logical tag name to physical register address."""
        try:
            if plc_id not in config_manager.plc_configs:
                raise ConfigurationError(f"No PLC configuration found", plc_id=plc_id)

            registers = config_manager.register_maps.get(plc_id)
            if not registers:
                raise ConfigurationError(f"No register map found", plc_id=plc_id)

            # Search for tag name in register configurations
            for register_address, config in registers.items():
                if config.get('name') == tag_name:
                    logger.debug(f"Resolved tag {tag_name} to address {register_address} on PLC {plc_id}")
                    return register_address

            # Provide helpful error with available tags
            available_tags = [cfg.get('name') for cfg in registers.values() if cfg.get('name')]
            if available_tags:
                error_msg = f"Tag '{tag_name}' not found. Available tags: {', '.join(sorted(available_tags[:10]))}"
                if len(available_tags) > 10:
                    error_msg += f" (and {len(available_tags) - 10} more)"
            else:
                error_msg = f"No tags configured for PLC {plc_id}"
            
            raise AddressResolutionError(error_msg, plc_id=plc_id, tag_name=tag_name)
            
        except TagServiceError:
            raise
        except Exception as e:
            raise AddressResolutionError(f"Failed to resolve tag name: {str(e)}", 
                                       plc_id=plc_id, tag_name=tag_name) from e

    def _determine_register_count(self, data_type: str) -> int:
        """Determines number of Modbus registers required for given data type."""
        type_map = {
            'float32': 2, 'uint32': 2, 'int32': 2,
            'uint64': 4, 'int64': 4, 'float64': 4
        }
        count = type_map.get(data_type, 1)  # Default to 1 register
        
        if count != type_map.get(data_type, 1):
            logger.debug(f"Using {count} registers for data type {data_type}")
            
        return count

    def _convert_modbus_address(self, plc_id: str, address: int) -> int:
        """Converts 1-based data model address to 0-based Modbus PDU address."""
        try:
            plc_config = config_manager.get_plc_config(plc_id)
            if not plc_config:
                raise ConfigurationError(f"No PLC configuration found", plc_id=plc_id)
            
            addressing_scheme = plc_config.addressing_scheme        
            
            # Handle vendor-specific relative addressing
            if addressing_scheme.lower() == 'relative':
                return address - 1
            
            # Standard Modbus addressing ranges
            elif 40001 <= address <= 49999:
                return address - 40001
            elif 30001 <= address <= 39999:
                return address - 30001
            elif 10001 <= address <= 19999:
                return address - 10001
            elif 1 <= address <= 9999:
                return address - 1
            else:
                logger.warning(f"Address {address} outside standard ranges, using as-is")
                return address
                
        except TagServiceError:
            raise
        except Exception as e:
            raise ConfigurationError(f"Failed to convert address {address}: {str(e)}", 
                                   plc_id=plc_id, address=address) from e

