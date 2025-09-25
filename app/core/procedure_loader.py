import yaml
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from pathlib import Path
import re

from app.utilities.telemetry import logger


@dataclass
class ProcedureStep:
    """Single procedure step - ready for execution"""
    name: str
    type: str  # "read", "write", "condition", "wait", "loop"
    data: Dict[str, Any]  # All the step-specific data


@dataclass
class ProcedureDefinition:
    """Complete procedure definition with validated steps"""
    name: str
    description: str
    steps: List[ProcedureStep]


class ProcedureLoader:
    """Loads and validates procedure definitions - ready for TagService execution"""
    
    VALID_STEP_TYPES = {"read", "write", "condition", "wait", "loop"}
    
    def __init__(self, plc_configs=None, register_maps=None):
        self.procedures: Dict[str, ProcedureDefinition] = {}
        self.plc_configs = plc_configs or {}
        self.register_maps = register_maps or {}
        
    def load_procedures_file(self, file_path: str) -> Dict[str, ProcedureDefinition]:
        """Load procedures from a single YAML file"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"Procedure file not found: {file_path}")
            raise FileNotFoundError(f"Procedure file not found: {file_path}")
        
        logger.info(f"Loading procedures from {file_path}")
        
        try:
            with open(file_path, 'r') as file:
                data = yaml.safe_load(file)
                
            if not data or 'procedures' not in data:
                raise ValueError(f"YAML file must contain 'procedures' section")
            
            procedures = {}
            for procedure_name, procedure_data in data['procedures'].items():
                procedure_def = self._parse_procedure(procedure_name, procedure_data)
                procedures[procedure_name] = procedure_def
                self.procedures[procedure_name] = procedure_def
                
                logger.debug(f"Loaded procedure: {procedure_name} with {len(procedure_def.steps)} steps")
            
            logger.info(f"Loaded {len(procedures)} procedures from {file_path}")
            return procedures
            
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {file_path}: {e}")
            raise ValueError(f"Invalid YAML in procedure file: {e}")
        except Exception as e:
            logger.error(f"Error loading procedure file {file_path}: {e}")
            raise
    
    def get_procedure(self, name: str) -> Optional[ProcedureDefinition]:
        """Get a specific procedure definition by name"""
        return self.procedures.get(name)
    
    def list_procedures(self) -> List[str]:
        """Get list of all loaded procedure names"""
        return list(self.procedures.keys())
    
    def _parse_procedure(self, name: str, data: Dict[str, Any]) -> ProcedureDefinition:
        """Parse individual procedure data into ProcedureDefinition"""
        
        if not isinstance(data, dict):
            raise ValueError(f"Procedure '{name}' must be a dictionary")
        
        description = data.get('description', f'Procedure {name}')
        
        # Parse steps
        steps_data = data.get('steps', [])
        if not isinstance(steps_data, list):
            raise ValueError(f"Procedure '{name}' steps must be a list")
        
        if not steps_data:
            raise ValueError(f"Procedure '{name}' must have at least one step")
        
        steps = []
        step_names = set()
        
        # First pass: parse all steps and collect names
        for i, step_data in enumerate(steps_data):
            step = self._parse_step(name, i, step_data)
            steps.append(step)
            
            if step.name in step_names:
                raise ValueError(f"Duplicate step name '{step.name}' in procedure '{name}'")
            step_names.add(step.name)
        
        # Second pass: validate step references
        self._validate_step_references(name, steps, step_names)
        
        return ProcedureDefinition(
            name=name,
            description=description,
            steps=steps
        )
    
    def _parse_step(self, procedure_name: str, step_index: int, step_data: Dict[str, Any]) -> ProcedureStep:
        """Parse individual step data"""
        
        if not isinstance(step_data, dict):
            raise ValueError(f"Step {step_index} in procedure '{procedure_name}' must be a dictionary")
        
        # Required fields
        step_name = step_data.get('name')
        step_type = step_data.get('type')
        
        if not step_name:
            raise ValueError(f"Step {step_index} in procedure '{procedure_name}' missing 'name'")
        
        if not step_type:
            raise ValueError(f"Step '{step_name}' in procedure '{procedure_name}' missing 'type'")
        
        if step_type not in self.VALID_STEP_TYPES:
            raise ValueError(f"Step '{step_name}' has invalid type '{step_type}'. Valid types: {self.VALID_STEP_TYPES}")
        
        # Validate step-specific requirements
        self._validate_step_data(procedure_name, step_name, step_type, step_data)
        
        return ProcedureStep(
            name=step_name,
            type=step_type,
            data=step_data
        )
    
    def _validate_step_data(self, procedure_name: str, step_name: str, step_type: str, step_data: Dict[str, Any]):
        """Validate step data based on step type - ensures execution readiness"""
        
        if step_type == "read":
            if 'register' not in step_data:
                raise ValueError(f"Read step '{step_name}' missing 'register'")
            if 'plc_id' not in step_data:
                raise ValueError(f"Read step '{step_name}' missing 'plc_id'")
            self._validate_register_access(step_name, step_data['plc_id'], step_data['register'])
        
        elif step_type == "write":
            if 'register' not in step_data:
                raise ValueError(f"Write step '{step_name}' missing 'register'")
            if 'plc_id' not in step_data:
                raise ValueError(f"Write step '{step_name}' missing 'plc_id'")
            if 'value' not in step_data:
                raise ValueError(f"Write step '{step_name}' missing 'value'")
            self._validate_register_access(step_name, step_data['plc_id'], step_data['register'])
            self._validate_register_writable(step_name, step_data['plc_id'], step_data['register'])
        
        elif step_type == "condition":
            if 'condition' not in step_data:
                raise ValueError(f"Condition step '{step_name}' missing 'condition'")
            if 'plc_id' not in step_data:
                raise ValueError(f"Condition step '{step_name}' missing 'plc_id' - needed to read register for condition")
            if 'if_true' not in step_data:
                raise ValueError(f"Condition step '{step_name}' missing 'if_true'")
            if 'if_false' not in step_data:
                raise ValueError(f"Condition step '{step_name}' missing 'if_false'")
            self._validate_condition(step_name, step_data['plc_id'], step_data['condition'])
        
        elif step_type == "wait":
            if 'seconds' not in step_data:
                raise ValueError(f"Wait step '{step_name}' missing 'seconds'")
            if not isinstance(step_data['seconds'], (int, float)) or step_data['seconds'] <= 0:
                raise ValueError(f"Wait step '{step_name}' seconds must be positive number")
        
        elif step_type == "loop":
            if 'condition' not in step_data:
                raise ValueError(f"Loop step '{step_name}' missing 'condition'")
            if 'plc_id' not in step_data:
                raise ValueError(f"Loop step '{step_name}' missing 'plc_id' - needed to read register for condition")
            if 'max_iterations' not in step_data:
                raise ValueError(f"Loop step '{step_name}' missing 'max_iterations'")
            if not isinstance(step_data['max_iterations'], int) or step_data['max_iterations'] <= 0:
                raise ValueError(f"Loop step '{step_name}' max_iterations must be positive integer")
            self._validate_condition(step_name, step_data['plc_id'], step_data['condition'])
    
    def _validate_register_access(self, step_name: str, plc_id: str, register_name: str):
        """Validate that register exists in the specified PLC"""
        
        # Check PLC exists
        if plc_id not in self.plc_configs:
            available_plcs = list(self.plc_configs.keys())
            raise ValueError(f"Step '{step_name}' references unknown PLC: {plc_id}. Available: {available_plcs}")
        
        # Check register exists in PLC
        if plc_id not in self.register_maps:
            raise ValueError(f"Step '{step_name}' PLC '{plc_id}' has no register map")
        
        # Find register by name
        register_found = False
        for register_addr, register_config in self.register_maps[plc_id].items():
            if register_config.get('name') == register_name:
                register_found = True
                break
        
        if not register_found:
            available_registers = [
                config.get('name') for config in self.register_maps[plc_id].values() 
                if config.get('name')
            ]
            raise ValueError(
                f"Step '{step_name}' register '{register_name}' not found in PLC '{plc_id}'. "
                f"Available registers: {available_registers[:10]}"
            )
    
    def _validate_register_writable(self, step_name: str, plc_id: str, register_name: str):
        """Validate that register is writable for write operations"""
        
        # Find the register config
        register_config = None
        for register_addr, config in self.register_maps[plc_id].items():
            if config.get('name') == register_name:
                register_config = config
                break
        
        if register_config and register_config.get('readonly', False):
            raise ValueError(f"Write step '{step_name}' cannot write to readonly register '{register_name}' in PLC '{plc_id}'")
    
    def _validate_condition(self, step_name: str, plc_id: str, condition: str):
        """Validate condition syntax and register access"""
        
        # Simple regex for register comparison: REGISTER_NAME operator value
        # Supports: ==, !=, <, >, <=, >=
        condition_pattern = r'^(\w+)\s*(==|!=|<=|>=|<|>)\s*(.+)$'
        
        if not re.match(condition_pattern, condition):
            raise ValueError(
                f"Step '{step_name}' condition '{condition}' invalid. "
                f"Must be format: REGISTER_NAME operator value (e.g., 'TEMP_01 > 50')"
            )
        
        # Extract register name and validate it exists in the specified PLC
        match = re.match(condition_pattern, condition)
        register_name = match.group(1)
        operator = match.group(2)
        value = match.group(3).strip()
        
        # Validate register exists in the specified PLC
        self._validate_register_access(step_name, plc_id, register_name)
        
        # Validate the comparison value is reasonable
        try:
            # Try to convert value to number for numeric comparisons
            if operator in ['<', '>', '<=', '>=']:
                float(value)  # Must be numeric for these operators
        except ValueError:
            if operator in ['<', '>', '<=', '>=']:
                raise ValueError(
                    f"Step '{step_name}' condition uses numeric operator '{operator}' "
                    f"but value '{value}' is not numeric"
                )
        
        logger.debug(f"Validated condition: {plc_id}.{register_name} {operator} {value}")
    
    def _validate_step_references(self, procedure_name: str, steps: List[ProcedureStep], step_names: set):
        """Validate that step references point to existing steps"""
        
        for step in steps:
            if step.type == "condition":
                if_true = step.data['if_true']
                if_false = step.data['if_false']
                
                if if_true not in step_names:
                    raise ValueError(
                        f"Procedure '{procedure_name}' step '{step.name}' if_true references "
                        f"unknown step: {if_true}. Available steps: {sorted(step_names)}"
                    )
                
                if if_false not in step_names:
                    raise ValueError(
                        f"Procedure '{procedure_name}' step '{step.name}' if_false references "
                        f"unknown step: {if_false}. Available steps: {sorted(step_names)}"
                    )
    
    def get_execution_ready_steps(self, procedure_name: str) -> List[ProcedureStep]:
        """Get steps ready for execution - all registers have plc_id and are validated"""
        procedure = self.get_procedure(procedure_name)
        if not procedure:
            raise ValueError(f"Procedure '{procedure_name}' not found")
        
        return procedure.steps
