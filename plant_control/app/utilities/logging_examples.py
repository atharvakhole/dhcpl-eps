"""
Example configurations for the plant control logging system.

This file demonstrates various logging configurations for different use cases:
- Development
- Production 
- Testing
- Debugging specific components
"""

from plant_control.app.utilities.logging_config import (
    LoggingConfig, LogLevel, LogFormat, LogDestination
)
from plant_control.app.utilities.telemetry import configure_logging, get_logger

# Development Configuration
def setup_development_logging():
    """Setup logging for development environment"""
    config = LoggingConfig(
        level=LogLevel.DEBUG,
        format_type=LogFormat.JSON_PRETTY,  # Pretty for readability
        enable_console=True,
        console_destination=LogDestination.STDOUT,
        # Enable detailed component filtering for debugging
        component_filters={
            "plant_control.app.core.connection_manager": LogLevel.DEBUG,
            "plant_control.app.core.plc_connection": LogLevel.DEBUG,
            "plant_control.app.api": LogLevel.INFO,
        },
        capture_warnings=True
    )
    
    configure_logging(config)
    logger = get_logger()
    logger.info("Development logging configured", extra={
        "environment": "development",
        "log_level": "DEBUG"
    })
    return logger

def setup_file_logging(file_path: str, enable_console: bool):
    """Setup logging for development environment"""
    config = LoggingConfig(
        level=LogLevel.DEBUG,
        format_type=LogFormat.JSON_PRETTY,  # Pretty for readability
        enable_console=enable_console,
        console_destination=LogDestination.FILE,
        log_file_path=file_path,
        # Enable detailed component filtering for debugging
        component_filters={
            "plant_control.app.core.connection_manager": LogLevel.DEBUG,
            "plant_control.app.core.plc_connection": LogLevel.DEBUG,
            "plant_control.app.api": LogLevel.INFO,
        },
        capture_warnings=True
    )
    
    configure_logging(config)
    logger = get_logger()
    logger.info("File logging configured", extra={
        "environment": "development",
        "log_level": "DEBUG"
    })
    return logger


# Production Configuration
def setup_production_logging():
    """Setup logging for production environment"""
    config = LoggingConfig(
        level=LogLevel.INFO,
        format_type=LogFormat.JSON_COMPACT,  # Compact for log aggregation
        enable_console=True,
        console_destination=LogDestination.STDOUT,
        # Production file logging with rotation
        log_file_path="/var/log/plant_control/app.log",
        max_file_size=50 * 1024 * 1024,  # 50MB
        backup_count=10,
        # Additional destinations for different log types
        destinations=[
            {
                "type": LogDestination.ROTATING_FILE,
                "path": "/var/log/plant_control/errors.log",
                "level": LogLevel.ERROR,
                "format": LogFormat.JSON_COMPACT,
                "max_size": 10 * 1024 * 1024,
                "backup_count": 5
            },
            {
                "type": LogDestination.ROTATING_FILE,
                "path": "/var/log/plant_control/plc_operations.log",
                "level": LogLevel.INFO,
                "format": LogFormat.JSON_COMPACT,
                "max_size": 100 * 1024 * 1024,
                "backup_count": 20
            }
        ],
        # Filter out noisy components in production
        exclude_components=[
            "urllib3.connectionpool",
            "asyncio"
        ],
        # Component-specific levels
        component_filters={
            "plant_control.app.core": LogLevel.INFO,
            "plant_control.app.api": LogLevel.WARNING,
            "plant_control.app.safety": LogLevel.DEBUG,  # Always debug safety
        },
        capture_warnings=True,
        disable_existing_loggers=False
    )
    
    configure_logging(config)
    logger = get_logger()
    logger.info("Production logging configured", extra={
        "environment": "production",
        "log_level": "INFO",
        "file_logging": True
    })
    return logger

# Testing Configuration
def setup_testing_logging():
    """Setup logging for testing environment"""
    config = LoggingConfig(
        level=LogLevel.WARNING,  # Reduce noise during tests
        format_type=LogFormat.STANDARD,  # Simple format for test output
        enable_console=True,
        console_destination=LogDestination.STDERR,  # Don't interfere with test output
        # Exclude components that are noisy during testing
        exclude_components=[
            "plant_control.app.core.connection_manager",
            "asyncio",
            "urllib3"
        ],
        capture_warnings=False  # Let test framework handle warnings
    )
    
    configure_logging(config)
    logger = get_logger()
    logger.warning("Testing logging configured", extra={
        "environment": "testing",
        "log_level": "WARNING"
    })
    return logger

# Debugging Configuration
def setup_debug_logging(debug_component=None):
    """Setup logging for debugging a specific component"""
    component_filters = {
        "plant_control.app.core": LogLevel.DEBUG,
        "plant_control.app.api": LogLevel.INFO,
    }
    
    # Enable verbose logging for specific component
    if debug_component:
        component_filters[debug_component] = LogLevel.DEBUG
    
    config = LoggingConfig(
        level=LogLevel.DEBUG,
        format_type=LogFormat.JSON_PRETTY,
        enable_console=True,
        console_destination=LogDestination.STDOUT,
        # Debug file for detailed analysis
        log_file_path=f"/tmp/plant_control_debug_{debug_component or 'all'}.log",
        component_filters=component_filters,
        capture_warnings=True
    )
    
    configure_logging(config)
    logger = get_logger()
    logger.debug("Debug logging configured", extra={
        "environment": "debug",
        "debug_component": debug_component or "all",
        "log_level": "DEBUG"
    })
    return logger

# HTTP API Server Configuration
def setup_api_server_logging():
    """Setup logging specifically for the HTTP API server"""
    config = LoggingConfig(
        level=LogLevel.INFO,
        format_type=LogFormat.JSON_COMPACT,
        enable_console=True,
        console_destination=LogDestination.STDOUT,
        # Separate log files for different concerns
        destinations=[
            {
                "type": LogDestination.ROTATING_FILE,
                "path": "/var/log/plant_control/api_access.log",
                "level": LogLevel.INFO,
                "format": LogFormat.JSON_COMPACT,
                "max_size": 20 * 1024 * 1024,
                "backup_count": 7
            },
            {
                "type": LogDestination.ROTATING_FILE,
                "path": "/var/log/plant_control/api_errors.log", 
                "level": LogLevel.ERROR,
                "format": LogFormat.JSON_PRETTY,  # Pretty for error analysis
                "max_size": 10 * 1024 * 1024,
                "backup_count": 10
            }
        ],
        # API-specific filtering
        component_filters={
            "plant_control.app.api": LogLevel.INFO,
            "plant_control.app.auth": LogLevel.WARNING,
            "plant_control.app.core": LogLevel.WARNING,
            "uvicorn": LogLevel.INFO,
            "fastapi": LogLevel.WARNING
        },
        # Exclude noisy HTTP libraries
        exclude_components=[
            "urllib3.connectionpool"
        ],
        capture_warnings=True
    )
    
    configure_logging(config)
    logger = get_logger()
    logger.info("API server logging configured", extra={
        "environment": "api_server",
        "log_level": "INFO"
    })
    return logger

# Minimal Configuration for Library Usage
def setup_library_logging():
    """Setup minimal logging when used as a library"""
    config = LoggingConfig(
        level=LogLevel.WARNING,  # Only warnings and errors
        format_type=LogFormat.STANDARD,  # Simple format
        enable_console=False,  # Don't interfere with host application
        # Only log to file if specified
        log_file_path=None,
        capture_warnings=False,  # Let host handle warnings
        disable_existing_loggers=False  # Don't interfere with other loggers
    )
    
    configure_logging(config)
    logger = get_logger()
    return logger

# Example usage function
def configure_logging_from_environment():
    """Configure logging based on environment variables"""
    import os
    
    environment = os.getenv("PLANT_CONTROL_ENV", "development").lower()
    debug_component = os.getenv("PLANT_CONTROL_DEBUG_COMPONENT")
    
    if environment == "production":
        return setup_production_logging()
    elif environment == "testing":
        return setup_testing_logging()
    elif environment == "api_server":
        return setup_api_server_logging()
    elif environment == "library":
        return setup_library_logging()
    elif environment == "debug":
        return setup_debug_logging(debug_component)
    else:
        return setup_development_logging()

# Example of runtime configuration changes
def example_runtime_changes():
    """Example of changing logging configuration at runtime"""
    from plant_control.app.utilities.telemetry import set_log_level, logging_manager
    
    # Change overall log level
    set_log_level(LogLevel.DEBUG)
    
    # Change log level for specific component
    set_log_level(LogLevel.ERROR, "plant_control.app.api")
    
    # Add a new file handler at runtime
    logging_manager.add_file_handler(
        "/tmp/runtime_debug.log", 
        LogLevel.DEBUG
    )

if __name__ == "__main__":
    # Example usage
    print("=== Development Logging ===")
    logger = setup_development_logging()
    logger.info("This is a development log", extra={
        "component": "example",
        "action": "test_logging"
    })
    
    print("\n=== Production Logging ===")
    logger = setup_production_logging()
    logger.info("This is a production log", extra={
        "component": "example", 
        "action": "test_logging",
        "metrics": {"response_time": 0.1, "success": True}
    })
    
    print("\n=== Environment-based Configuration ===")
    logger = configure_logging_from_environment()
    logger.info("Environment-based logging configured")
