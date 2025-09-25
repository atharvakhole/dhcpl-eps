"""
Configuration management for Plant Control API
"""

import yaml
from typing import Dict, List, Any
from pathlib import Path
from pydantic_settings import BaseSettings
from app.models.plc_config import PLCConfig

class Settings(BaseSettings):
    """Application settings"""
    
    # API Settings
    api_title: str = "EPS Plant Control API"
    api_version: str = "1.0.0"
    api_description: str = "Industrial Plant Control and Monitoring API"
    
    # Database Settings
    database_url: str = "postgresql://user:password@localhost/plant_control"
    
    # Redis Settings  
    redis_url: str = "redis://localhost:6379"
    
    # Security Settings
    secret_key: str = "your-secret-key-change-this-in-production"
    access_token_expire_minutes: int = 30
    
    # PLC Configuration
    plc_config_dir: str = "config/plc_configs"
    register_map_dir: str = "config/register_maps"
    procedure_config_dir: str = "config/procedures"  # Add procedure config directory
    
    # Logging
    log_level: str = "INFO"
    
    # Safety Settings
    enable_safety_interlocks: bool = True
    emergency_stop_timeout: int = 5  # seconds
    
    class Config:
        env_file = ".env"

settings = Settings()

class ConfigManager:
    """Manages loading of PLC, register, and procedure configurations"""
    
    def __init__(self):
        self.plc_configs: Dict[str, PLCConfig] = {}
        self.register_maps: Dict[str, Dict[int, Dict[str, Any]]] = {}
        self.procedures: Dict[str, Any] = {}  # Will store ProcedureDefinition objects
    
    def load_plc_configs(self) -> List[PLCConfig]:
        """Load all PLC configurations from YAML files"""
        config_dir = Path(settings.plc_config_dir)
        plc_configs = []
        
        for config_file in config_dir.glob("*.yaml"):
            with open(config_file, 'r') as f:
                data = yaml.safe_load(f)
                
            for plc_id, config_data in data.get('plcs', {}).items():
                plc_config = PLCConfig(
                    plc_id=plc_id,
                    **config_data
                )
                plc_configs.append(plc_config)
                self.plc_configs[plc_id] = plc_config
        
        return plc_configs
    
    def load_register_maps(self) -> Dict[str, Dict[int, Dict[str, Any]]]:
        """Load all register mappings from YAML files"""
        config_dir = Path(settings.register_map_dir)
        
        for config_file in config_dir.glob("*.yaml"):
            with open(config_file, 'r') as f:
                data = yaml.safe_load(f)
            
            for plc_id, registers in data.get('registers', {}).items():
                if plc_id not in self.register_maps:
                    self.register_maps[plc_id] = {}
                
                # Convert string keys to integers
                for register_addr, register_config in registers.items():
                    self.register_maps[plc_id][int(register_addr)] = register_config
        
        return self.register_maps
    
    def load_procedures(self) -> Dict[str, Any]:
        """
        Load and validate all procedure configurations from YAML files
        
        This must be called AFTER load_plc_configs() and load_register_maps()
        since procedures reference PLCs and registers.
        
        Returns:
            Dictionary of procedure name -> ProcedureDefinition
        """
        if not self.plc_configs:
            raise ValueError("Must load PLC configs before loading procedures")
        
        if not self.register_maps:
            raise ValueError("Must load register maps before loading procedures")
        
        from app.core.procedure_loader import ProcedureLoader
        
        # Create procedure loader with loaded configs
        procedure_loader = ProcedureLoader(
            plc_configs=self.plc_configs,
            register_maps=self.register_maps
        )
        
        config_dir = Path(settings.procedure_config_dir)
        
        if not config_dir.exists():
            from app.utilities.telemetry import logger
            logger.warning(f"Procedure config directory not found: {config_dir}")
            return {}
        
        all_procedures = {}
        
        # Load all YAML files in the procedures directory
        for config_file in config_dir.glob("*.yaml"):
            try:
                procedures = procedure_loader.load_procedures_file(str(config_file))
                all_procedures.update(procedures)
                
            except Exception as e:
                from app.utilities.telemetry import logger
                logger.error(f"Failed to load procedure file {config_file}: {e}")
                raise ValueError(f"Failed to load procedures from {config_file}: {e}")
        
        # Store loaded procedures
        self.procedures = all_procedures
        
        from app.utilities.telemetry import logger
        logger.info(f"Loaded {len(all_procedures)} procedures with full validation")
        
        return all_procedures
    
    def get_register_config(self, plc_id: str, register_address: int) -> Dict[str, Any]:
        """Get configuration for a specific register"""
        if plc_id not in self.register_maps:
            raise ValueError(f"No register map found for PLC: {plc_id}")
        
        if register_address not in self.register_maps[plc_id]:
            raise ValueError(f"Register {register_address} not found in PLC {plc_id}")
        
        return self.register_maps[plc_id][register_address]

    def get_plc_config(self, plc_id: str) -> PLCConfig:
        """Get configuration for a specific PLC"""
        if plc_id not in self.plc_configs:
            raise ValueError(f"Configuration for PLC {plc_id} not found")
        
        return self.plc_configs[plc_id]
    
    def get_procedure(self, procedure_name: str):
        """Get a specific procedure definition"""
        if procedure_name not in self.procedures:
            available_procedures = list(self.procedures.keys())
            raise ValueError(f"Procedure '{procedure_name}' not found. Available: {available_procedures}")
        
        return self.procedures[procedure_name]
    
    def list_procedures(self) -> List[str]:
        """Get list of all loaded procedure names"""
        return list(self.procedures.keys())
    
    def is_register_readonly(self, plc_id: str, register_address: int) -> bool:
        """Check if a register is read-only"""
        try:
            config = self.get_register_config(plc_id, register_address)
            return config.get('readonly', False)
        except ValueError:
            # If register not found in config, assume it's writable
            return False
    
    def is_register_critical(self, plc_id: str, register_address: int) -> bool:
        """Check if a register is critical (requires special permissions)"""
        try:
            config = self.get_register_config(plc_id, register_address)
            return config.get('critical', False)
        except ValueError:
            # If register not found in config, assume it's not critical
            return False

# Global config manager instance
config_manager = ConfigManager()


if __name__ == "__main__":
    config_manager.load_plc_configs()
    config_manager.load_register_maps()
    config_manager.load_procedures()  # Must be last - validates against PLCs/registers

    procedure = config_manager.get_procedure("START_HEATING_REACTOR_04")
