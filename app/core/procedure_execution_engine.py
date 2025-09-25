import asyncio
import time
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.tag_service import TagService, ReadStatus, WriteStatus
from app.core.procedure_loader import ProcedureDefinition, ProcedureStep
from app.utilities.telemetry import logger


class ExecutionStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class StepResult:
    """Result of executing a single step"""
    step_name: str
    step_type: str
    status: str  # "success" or "error"
    data: Optional[Any] = None
    error_message: Optional[str] = None
    execution_time_ms: int = 0


@dataclass
class ExecutionState:
    """Current state of procedure execution"""
    procedure_name: str
    status: ExecutionStatus = ExecutionStatus.RUNNING
    current_step: Optional[str] = None
    executed_steps: List[StepResult] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)  # For storing read values
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    error_message: Optional[str] = None


@dataclass 
class ExecutionResult:
    """Final execution result for API consumption"""
    procedure_name: str
    status: str
    total_steps: int
    successful_steps: int
    failed_steps: int
    execution_time_ms: int
    step_results: List[StepResult]
    error_message: Optional[str] = None


class ProcedureExecutor:
    """Simple procedure execution engine"""
    
    def __init__(self, tag_service: TagService):
        self.tag_service = tag_service
    
    async def execute_procedure(self, procedure: ProcedureDefinition) -> ExecutionResult:
        """Execute a complete procedure"""
        
        logger.info(f"Starting procedure execution: {procedure.name}")
        
        execution_state = ExecutionState(procedure_name=procedure.name)
        
        try:
            # Execute steps sequentially
            current_step_index = 0
            
            while current_step_index < len(procedure.steps):
                step = procedure.steps[current_step_index]
                execution_state.current_step = step.name
                
                step_result = await self._execute_step(step, execution_state)
                execution_state.executed_steps.append(step_result)
                
                if step_result.status == "error":
                    execution_state.status = ExecutionStatus.FAILED
                    execution_state.error_message = step_result.error_message
                    break
                
                # Handle step flow control
                next_step_index = self._get_next_step_index(
                    step, step_result, procedure.steps, current_step_index
                )
                
                if next_step_index is None:
                    break  # Procedure complete
                
                current_step_index = next_step_index
            
            if execution_state.status == ExecutionStatus.RUNNING:
                execution_state.status = ExecutionStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"Procedure execution failed: {procedure.name}: {str(e)}")
            execution_state.status = ExecutionStatus.FAILED
            execution_state.error_message = str(e)
        
        execution_state.end_time = time.time()
        
        logger.info(f"Procedure execution completed: {procedure.name} - {execution_state.status.value}")
        
        return self._build_execution_result(execution_state)
    
    async def _execute_step(self, step: ProcedureStep, state: ExecutionState) -> StepResult:
        """Execute a single step"""
        
        start_time = time.time()
        
        try:
            if step.type == "read":
                return await self._execute_read_step(step, state, start_time)
            elif step.type == "write":
                return await self._execute_write_step(step, state, start_time)
            elif step.type == "condition":
                return await self._execute_condition_step(step, state, start_time)
            elif step.type == "wait":
                return await self._execute_wait_step(step, state, start_time)
            elif step.type == "loop":
                return await self._execute_loop_step(step, state, start_time)
            else:
                raise ValueError(f"Unknown step type: {step.type}")
        
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            logger.error(f"Step execution failed: {step.name}: {str(e)}")
            return StepResult(
                step_name=step.name,
                step_type=step.type,
                status="error",
                error_message=str(e),
                execution_time_ms=execution_time
            )
    
    async def _execute_read_step(self, step: ProcedureStep, state: ExecutionState, start_time: float) -> StepResult:
        """Execute read step using TagService"""
        
        plc_id = step.data['plc_id']
        register = step.data['register']
        
        result = await self.tag_service.read_tag(plc_id, register)
        execution_time = int((time.time() - start_time) * 1000)
        
        if result.status == ReadStatus.SUCCESS:
            # Store value if requested
            store_as = step.data.get('store_as')
            if store_as:
                state.variables[store_as] = result.data
            
            return StepResult(
                step_name=step.name,
                step_type=step.type,
                status="success",
                data=result.data,
                execution_time_ms=execution_time
            )
        else:
            return StepResult(
                step_name=step.name,
                step_type=step.type,
                status="error",
                error_message=result.error_message,
                execution_time_ms=execution_time
            )
    
    async def _execute_write_step(self, step: ProcedureStep, state: ExecutionState, start_time: float) -> StepResult:
        """Execute write step using TagService"""
        
        plc_id = step.data['plc_id']
        register = step.data['register']
        value = step.data['value']
        
        result = await self.tag_service.write_tag(plc_id, register, value)
        execution_time = int((time.time() - start_time) * 1000)
        
        if result.status == WriteStatus.SUCCESS:
            return StepResult(
                step_name=step.name,
                step_type=step.type,
                status="success",
                data=value,
                execution_time_ms=execution_time
            )
        else:
            return StepResult(
                step_name=step.name,
                step_type=step.type,
                status="error",
                error_message=result.error_message,
                execution_time_ms=execution_time
            )
    
    async def _execute_condition_step(self, step: ProcedureStep, state: ExecutionState, start_time: float) -> StepResult:
        """Execute condition step - reads register and evaluates condition"""
        
        plc_id = step.data['plc_id']
        condition = step.data['condition']
        
        # Parse condition to get register name
        match = re.match(r'^(\w+)\s*(==|!=|<=|>=|<|>)\s*(.+)$', condition)
        if not match:
            raise ValueError(f"Invalid condition format: {condition}")
        
        register_name = match.group(1)
        operator = match.group(2)
        compare_value = match.group(3).strip()
        
        # Read the register value
        read_result = await self.tag_service.read_tag(plc_id, register_name)
        execution_time = int((time.time() - start_time) * 1000)
        
        if read_result.status != ReadStatus.SUCCESS:
            return StepResult(
                step_name=step.name,
                step_type=step.type,
                status="error",
                error_message=f"Failed to read register for condition: {read_result.error_message}",
                execution_time_ms=execution_time
            )
        
        # Evaluate condition
        condition_result = self._evaluate_condition(read_result.data, operator, compare_value)
        
        return StepResult(
            step_name=step.name,
            step_type=step.type,
            status="success",
            data=condition_result,  # True or False
            execution_time_ms=execution_time
        )
    
    async def _execute_wait_step(self, step: ProcedureStep, state: ExecutionState, start_time: float) -> StepResult:
        """Execute wait step"""
        
        seconds = step.data['seconds']
        await asyncio.sleep(seconds)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return StepResult(
            step_name=step.name,
            step_type=step.type,
            status="success",
            data=seconds,
            execution_time_ms=execution_time
        )
    
    async def _execute_loop_step(self, step: ProcedureStep, state: ExecutionState, start_time: float) -> StepResult:
        """Execute loop step - keeps checking condition until true or max iterations"""
        
        plc_id = step.data['plc_id']
        condition = step.data['condition']
        max_iterations = step.data['max_iterations']
        delay_seconds = step.data.get('delay_seconds', 1)
        
        # Parse condition
        match = re.match(r'^(\w+)\s*(==|!=|<=|>=|<|>)\s*(.+)$', condition)
        if not match:
            raise ValueError(f"Invalid loop condition format: {condition}")
        
        register_name = match.group(1)
        operator = match.group(2)
        compare_value = match.group(3).strip()
        
        # Loop until condition is true or max iterations reached
        for iteration in range(max_iterations):
            read_result = await self.tag_service.read_tag(plc_id, register_name)
            
            if read_result.status != ReadStatus.SUCCESS:
                execution_time = int((time.time() - start_time) * 1000)
                return StepResult(
                    step_name=step.name,
                    step_type=step.type,
                    status="error",
                    error_message=f"Failed to read register in loop: {read_result.error_message}",
                    execution_time_ms=execution_time
                )
            
            if self._evaluate_condition(read_result.data, operator, compare_value):
                execution_time = int((time.time() - start_time) * 1000)
                return StepResult(
                    step_name=step.name,
                    step_type=step.type,
                    status="success",
                    data=f"Condition met after {iteration + 1} iterations",
                    execution_time_ms=execution_time
                )
            
            if iteration < max_iterations - 1:  # Don't wait after last iteration
                await asyncio.sleep(delay_seconds)
        
        # Max iterations reached without condition being met
        execution_time = int((time.time() - start_time) * 1000)
        return StepResult(
            step_name=step.name,
            step_type=step.type,
            status="error",
            error_message=f"Loop condition not met after {max_iterations} iterations",
            execution_time_ms=execution_time
        )
    
    def _evaluate_condition(self, register_value: Any, operator: str, compare_value: str) -> bool:
        """Evaluate a simple condition"""
        
        # Try to convert values to numbers for numeric comparison
        try:
            reg_val = float(register_value)
            comp_val = float(compare_value)
            
            if operator == "==":
                return reg_val == comp_val
            elif operator == "!=":
                return reg_val != comp_val
            elif operator == "<":
                return reg_val < comp_val
            elif operator == ">":
                return reg_val > comp_val
            elif operator == "<=":
                return reg_val <= comp_val
            elif operator == ">=":
                return reg_val >= comp_val
        
        except ValueError:
            # String comparison
            if operator == "==":
                return str(register_value) == compare_value
            elif operator == "!=":
                return str(register_value) != compare_value
            else:
                raise ValueError(f"Non-numeric values cannot use operator: {operator}")
        
        raise ValueError(f"Unknown operator: {operator}")
    
    def _get_next_step_index(self, current_step: ProcedureStep, step_result: StepResult, 
                           all_steps: List[ProcedureStep], current_index: int) -> Optional[int]:
        """Determine the next step to execute based on current step result"""
        
        if current_step.type == "condition":
            condition_result = step_result.data
            next_step_name = current_step.data['if_true'] if condition_result else current_step.data['if_false']
            
            # Find the step index by name
            for i, step in enumerate(all_steps):
                if step.name == next_step_name:
                    return i
            
            raise ValueError(f"Step '{next_step_name}' not found")
        
        # For all other step types, proceed to next step
        next_index = current_index + 1
        return next_index if next_index < len(all_steps) else None
    
    def _build_execution_result(self, state: ExecutionState) -> ExecutionResult:
        """Build final execution result for API consumption"""
        
        successful_steps = sum(1 for step in state.executed_steps if step.status == "success")
        failed_steps = len(state.executed_steps) - successful_steps
        execution_time = int((state.end_time - state.start_time) * 1000) if state.end_time else 0
        
        return ExecutionResult(
            procedure_name=state.procedure_name,
            status=state.status.value,
            total_steps=len(state.executed_steps),
            successful_steps=successful_steps,
            failed_steps=failed_steps,
            execution_time_ms=execution_time,
            step_results=state.executed_steps,
            error_message=state.error_message
        )
