"""
Telemetry and logging utilities for the plant control system.

This module provides the main logging interface used throughout the application.
It uses the configurable logging system and maintains backward compatibility.
"""

from plant_control.app.utilities.logging_config import (
    LoggingConfig, 
    LoggingManager, 
    LogLevel, 
    LogFormat, 
    LogDestination,
    configure_logging,
    get_logger as _get_logger,
    set_log_level,
    logging_manager
)

# Global logger instance for backward compatibility
logger = None

def get_logger(name=None):
    """Get a logger instance - wrapper around the logging manager"""
    return _get_logger(name)

def initialize_logging(config=None):
    """Initialize the logging system with optional configuration"""
    global logger
    
    if config is None:
        # Default configuration for development
        config = LoggingConfig(
            level=LogLevel.INFO,
            format_type=LogFormat.JSON_COMPACT,
            enable_console=True,
            console_destination=LogDestination.STDOUT,
            capture_warnings=True
        )
    
    configure_logging(config)
    logger = get_logger()
    
    return logger

# Initialize with default configuration if not already done
if logger is None:
    try:
        logger = get_logger()
    except RuntimeError:
        logger = initialize_logging()

# Re-export important classes and functions for convenience
__all__ = [
    'logger',
    'get_logger', 
    'initialize_logging',
    'LoggingConfig',
    'LogLevel',
    'LogFormat', 
    'LogDestination',
    'configure_logging',
    'set_log_level',
    'logging_manager'
]
