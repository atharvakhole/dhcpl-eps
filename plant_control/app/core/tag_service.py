from typing import Any, Dict, List
import time
import asyncio
from plant_control.app.models.connection_manager import ModbusOperation
from plant_control.app.core.connection_manager import connection_manager
from plant_control.app.utilities.telemetry import logger

from plant_control.app.schemas.tag_service import (
    ReadStatus, WriteStatus, TagReadResult, TagWriteResult, 
    BulkReadResponse, BulkWriteResponse
)
from plant_control.app.core.tag_exceptions import (
    TagServiceError, ValidationError
)
from plant_control.app.utilities.tag_helpers import (
    TagServiceHelper
)


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

    def __init__(self):
        self.helper = TagServiceHelper()

    async def read_tag(self, plc_id: str, tag_name: str) -> TagReadResult:
        """Reads data from the register corresponding to the given tag."""
        start_time = time.time()
        timestamp = start_time
        context = {"plc_id": plc_id, "tag_name": tag_name}
        
        try:
            logger.debug(f"Reading tag {tag_name} from PLC {plc_id}")
            
            # Validate inputs
            if not plc_id or not isinstance(plc_id, str):
                raise ValidationError("PLC ID must be a non-empty string", plc_id=plc_id, tag_name=tag_name)
            if not tag_name or not isinstance(tag_name, str):
                raise ValidationError("Tag name must be a non-empty string", plc_id=plc_id, tag_name=tag_name)
            
            # Resolve tag configuration
            original_address = self.helper.get_address_from_tagname(plc_id, tag_name)
            context["address"] = original_address
            
            converted_modbus_address = self.helper.convert_modbus_address(plc_id, original_address)
            register_type = self.helper.get_register_type(plc_id, original_address)
            data_type = self.helper.get_data_type(plc_id, original_address)
            decode_type = self.helper.get_decode_type(plc_id, original_address)
            register_count = self.helper.determine_register_count(data_type)
            
            # Build and execute operation
            operation = self.helper.build_modbus_operation("read", converted_modbus_address, original_address, register_type, register_count)
            registers = await connection_manager.execute_operation(plc_id, operation)
            
            # Decode result
            decoded_data = self.helper.decode_registers(registers, decode_type)
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.debug(f"Tag read completed in {duration_ms}ms")
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
            logger.debug(f"Writing {data} to tag {tag_name} on PLC {plc_id}")
            
            # Validate inputs
            if not plc_id or not isinstance(plc_id, str):
                raise ValidationError("PLC ID must be a non-empty string", plc_id=plc_id, tag_name=tag_name)
            if not tag_name or not isinstance(tag_name, str):
                raise ValidationError("Tag name must be a non-empty string", plc_id=plc_id, tag_name=tag_name)
            if data is None:
                raise ValidationError("Data cannot be None", plc_id=plc_id, tag_name=tag_name)
            
            # Resolve tag configuration
            original_address = self.helper.get_address_from_tagname(plc_id, tag_name)
            context["address"] = original_address
            
            converted_modbus_address = self.helper.convert_modbus_address(plc_id, original_address)
            payload = self.helper.construct_payload(plc_id, original_address, data)
            register_type = self.helper.get_register_type(plc_id, original_address)

            # Build and execute operation
            operation = self.helper.build_modbus_operation("write", converted_modbus_address, original_address, register_type, 0, payload)
            result = await connection_manager.execute_operation(plc_id, operation)
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.debug(f"Tag write completed in {duration_ms}ms", extra={
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
            logger.debug(f"Reading {len(tag_names)} tags from PLC {plc_id}")
        
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
                logger.debug(f"Bulk read PLC {plc_id} completed in {duration_ms}ms: {successful_count} successful, {failed_count} failed")
            
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
            logger.debug(f"Writing {len(tag_data)} tags to PLC {plc_id}")
        
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
                logger.debug(f"Bulk write PLC {plc_id} completed in {duration_ms}ms: {successful_count} successful, {failed_count} failed")
            
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
                original_address = self.helper.get_address_from_tagname(plc_id, tag_name)
                converted_modbus_address = self.helper.convert_modbus_address(plc_id, original_address)
                register_type = self.helper.get_register_type(plc_id, original_address)
                data_type = self.helper.get_data_type(plc_id, original_address)
                decode_type = self.helper.get_decode_type(plc_id, original_address)
                register_count = self.helper.determine_register_count(data_type)
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
                operation = self.helper.build_modbus_operation("read", converted_modbus_address, original_address, register_type, register_count)
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
                decoded_data = self.helper.decode_registers_minimal_logging(registers, decode_type, verbose_logging)
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
                original_address = self.helper.get_address_from_tagname(plc_id, tag_name)
                converted_modbus_address = self.helper.convert_modbus_address(plc_id, original_address)
                payload = self.helper.construct_payload(plc_id, original_address, data)
                register_type = self.helper.get_register_type(plc_id, original_address)
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
                operation = self.helper.build_modbus_operation("write", converted_modbus_address, original_address, register_type, 0, payload)
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
