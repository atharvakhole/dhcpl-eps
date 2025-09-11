"""
Configuration management for Plant Control API
"""

import os
import yaml
from typing import Dict, List, Any
from pathlib import Path
from pydantic_settings import BaseSettings
from app.core.connection_manager import PLCConfig

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
    
    # Logging
    log_level: str = "INFO"
    
    # Safety Settings
    enable_safety_interlocks: bool = True
    emergency_stop_timeout: int = 5  # seconds
    
    class Config:
        env_file = ".env"

settings = Settings()

class ConfigManager:
    """Manages loading of PLC and register configurations"""
    
    def __init__(self):
        self.plc_configs: Dict[str, PLCConfig] = {}
        self.register_maps: Dict[str, Dict[int, Dict[str, Any]]] = {}
    
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
        
        print(plc_configs)
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
    
    def get_register_config(self, plc_id: str, register_address: int) -> Dict[str, Any]:
        """Get configuration for a specific register"""
        if plc_id not in self.register_maps:
            raise ValueError(f"No register map found for PLC: {plc_id}")
        
        if register_address not in self.register_maps[plc_id]:
            raise ValueError(f"Register {register_address} not found in PLC {plc_id}")
        
        return self.register_maps[plc_id][register_address]
    
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
