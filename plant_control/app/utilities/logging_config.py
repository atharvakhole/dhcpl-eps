import logging
import logging.handlers
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from enum import Enum


class LogLevel(Enum):
    """Enumeration for log levels"""
    CRITICAL = logging.CRITICAL
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    INFO = logging.INFO
    DEBUG = logging.DEBUG


class LogFormat(Enum):
    """Enumeration for log output formats"""
    JSON_COMPACT = "json_compact"
    JSON_PRETTY = "json_pretty"
    STANDARD = "standard"
    DETAILED = "detailed"


class LogDestination(Enum):
    """Enumeration for log destinations"""
    STDOUT = "stdout"
    STDERR = "stderr"
    FILE = "file"
    ROTATING_FILE = "rotating_file"
    SYSLOG = "syslog"


class JsonFormatter(logging.Formatter):
    """Compact JSON formatter - single line output"""
    
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        # Reserved attributes we don't want duplicated
        reserved = set(vars(logging.LogRecord('', 0, '', 0, '', (), None)).keys())
        reserved.update(['getMessage', 'exc_text', 'stack_info'])
        
        # Add extras (anything that isn't reserved)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in reserved and not key.startswith('_')
        }
        if extras:
            log_record["extra"] = extras
        
        return json.dumps(log_record, ensure_ascii=False, separators=(',', ':'))


class JsonPrettyFormatter(logging.Formatter):
    """Pretty-printed JSON formatter - multi-line indented output"""
    
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        # Reserved attributes we don't want duplicated
        reserved = set(vars(logging.LogRecord('', 0, '', 0, '', (), None)).keys())
        reserved.update(['getMessage', 'exc_text', 'stack_info'])
        
        # Add extras (anything that isn't reserved)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in reserved and not key.startswith('_')
        }
        if extras:
            log_record["extra"] = extras
        
        return json.dumps(log_record, ensure_ascii=False, indent=2)


class StandardFormatter(logging.Formatter):
    """Standard text formatter"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


class DetailedFormatter(logging.Formatter):
    """Detailed text formatter with more context"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


class LoggingConfig:
    """Configuration class for logging setup"""
    
    def __init__(
        self,
        level: Union[LogLevel, str] = LogLevel.INFO,
        format_type: Union[LogFormat, str] = LogFormat.JSON_COMPACT,
        destinations: Optional[List[Dict]] = None,
        logger_name: str = "plant_control",
        enable_console: bool = True,
        console_destination: Union[LogDestination, str] = LogDestination.STDOUT,
        # File logging options
        log_file_path: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        # Filtering options
        component_filters: Optional[Dict[str, Union[LogLevel, str]]] = None,
        exclude_components: Optional[List[str]] = None,
        # Production options
        capture_warnings: bool = True,
        disable_existing_loggers: bool = False,
        # Performance options
        queue_handler: bool = False,
        queue_size: int = 1000
    ):
        self.level = LogLevel(level) if isinstance(level, str) else level
        self.format_type = LogFormat(format_type) if isinstance(format_type, str) else format_type
        self.destinations = destinations or []
        self.logger_name = logger_name
        self.enable_console = enable_console
        self.console_destination = LogDestination(console_destination) if isinstance(console_destination, str) else console_destination
        
        # File options
        self.log_file_path = log_file_path
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        
        # Filtering
        self.component_filters = component_filters or {}
        self.exclude_components = exclude_components or []
        
        # Production options
        self.capture_warnings = capture_warnings
        self.disable_existing_loggers = disable_existing_loggers
        
        # Performance options
        self.queue_handler = queue_handler
        self.queue_size = queue_size


class ComponentFilter(logging.Filter):
    """Filter logs based on component (logger name)"""
    
    def __init__(self, component_filters: Dict[str, LogLevel], exclude_components: List[str]):
        super().__init__()
        self.component_filters = component_filters
        self.exclude_components = exclude_components
    
    def filter(self, record):
        # Exclude specific components
        for exclude in self.exclude_components:
            if record.name.startswith(exclude):
                return False
        
        # Apply component-specific log levels
        for component, min_level in self.component_filters.items():
            if record.name.startswith(component):
                return record.levelno >= min_level.value
        
        return True


class LoggingManager:
    """Central logging manager for the plant control system"""
    
    def __init__(self):
        self._loggers: Dict[str, logging.Logger] = {}
        self._config: Optional[LoggingConfig] = None
        self._is_configured = False
        
    def configure(self, config: LoggingConfig) -> None:
        """Configure the logging system"""
        self._config = config
        
        # Clear existing handlers if requested
        if config.disable_existing_loggers:
            logging.getLogger().handlers.clear()
        
        # Configure warnings capture
        if config.capture_warnings:
            logging.captureWarnings(True)
        
        # Get or create the main logger
        logger = logging.getLogger(config.logger_name)
        logger.setLevel(config.level.value)
        
        # Clear existing handlers for clean setup
        logger.handlers.clear()
        logger.propagate = False
        
        # Setup handlers
        handlers = []
        
        # Console handler
        if config.enable_console:
            handlers.append(self._create_console_handler(config))
        
        # File handler
        if config.log_file_path:
            handlers.append(self._create_file_handler(config))
        
        # Custom destination handlers
        for dest_config in config.destinations:
            handlers.append(self._create_custom_handler(dest_config, config))
        
        # Apply filters and add handlers
        for handler in handlers:
            if config.component_filters or config.exclude_components:
                handler.addFilter(ComponentFilter(
                    {k: LogLevel(v) if isinstance(v, str) else v 
                     for k, v in config.component_filters.items()},
                    config.exclude_components
                ))
            
            logger.addHandler(handler)
        
        self._loggers[config.logger_name] = logger
        self._is_configured = True
    
    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """Get a logger instance"""
        if not self._is_configured:
            raise RuntimeError("Logging not configured. Call configure() first.")
        
        logger_name = name or self._config.logger_name
        
        if logger_name not in self._loggers:
            # Create child logger
            parent_logger = self._loggers[self._config.logger_name]
            child_logger = logging.getLogger(logger_name)
            child_logger.parent = parent_logger
            self._loggers[logger_name] = child_logger
        
        return self._loggers[logger_name]
    
    def set_level(self, level: Union[LogLevel, str], component: Optional[str] = None) -> None:
        """Dynamically change log level"""
        if not self._is_configured:
            raise RuntimeError("Logging not configured. Call configure() first.")
        
        log_level = LogLevel(level) if isinstance(level, str) else level
        
        if component:
            if component in self._loggers:
                self._loggers[component].setLevel(log_level.value)
        else:
            # Set for main logger
            main_logger = self._loggers[self._config.logger_name]
            main_logger.setLevel(log_level.value)
    
    def add_file_handler(self, file_path: str, level: Union[LogLevel, str] = LogLevel.INFO) -> None:
        """Add a new file handler at runtime"""
        if not self._is_configured:
            raise RuntimeError("Logging not configured. Call configure() first.")
        
        log_level = LogLevel(level) if isinstance(level, str) else level
        main_logger = self._loggers[self._config.logger_name]
        
        # Create file handler
        handler = logging.FileHandler(file_path)
        handler.setLevel(log_level.value)
        handler.setFormatter(self._create_formatter(self._config.format_type))
        
        main_logger.addHandler(handler)
    
    def _create_console_handler(self, config: LoggingConfig) -> logging.Handler:
        """Create console handler based on configuration"""
        if config.console_destination == LogDestination.STDOUT:
            handler = logging.StreamHandler(sys.stdout)
        else:
            handler = logging.StreamHandler(sys.stderr)
        
        handler.setLevel(config.level.value)
        handler.setFormatter(self._create_formatter(config.format_type))
        return handler
    
    def _create_file_handler(self, config: LoggingConfig) -> logging.Handler:
        """Create file handler based on configuration"""
        # Ensure directory exists
        file_path = Path(config.log_file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use rotating file handler for production
        handler = logging.handlers.RotatingFileHandler(
            filename=config.log_file_path,
            maxBytes=config.max_file_size,
            backupCount=config.backup_count
        )
        
        handler.setLevel(config.level.value)
        handler.setFormatter(self._create_formatter(config.format_type))
        return handler
    
    def _create_custom_handler(self, dest_config: Dict, config: LoggingConfig) -> logging.Handler:
        """Create custom handler from destination configuration"""
        dest_type = LogDestination(dest_config.get('type', LogDestination.FILE))
        
        if dest_type == LogDestination.SYSLOG:
            handler = logging.handlers.SysLogHandler()
        elif dest_type == LogDestination.ROTATING_FILE:
            handler = logging.handlers.RotatingFileHandler(
                filename=dest_config['path'],
                maxBytes=dest_config.get('max_size', config.max_file_size),
                backupCount=dest_config.get('backup_count', config.backup_count)
            )
        else:
            handler = logging.FileHandler(dest_config['path'])
        
        level = dest_config.get('level', config.level)
        if isinstance(level, str):
            level = LogLevel(level)
        
        handler.setLevel(level.value)
        
        format_type = dest_config.get('format', config.format_type)
        if isinstance(format_type, str):
            format_type = LogFormat(format_type)
        
        handler.setFormatter(self._create_formatter(format_type))
        return handler
    
    def _create_formatter(self, format_type: LogFormat) -> logging.Formatter:
        """Create formatter based on format type"""
        if format_type == LogFormat.JSON_COMPACT:
            return JsonFormatter()
        elif format_type == LogFormat.JSON_PRETTY:
            return JsonPrettyFormatter()
        elif format_type == LogFormat.STANDARD:
            return StandardFormatter()
        elif format_type == LogFormat.DETAILED:
            return DetailedFormatter()
        else:
            return JsonFormatter()  # Default fallback


# Global logging manager instance
logging_manager = LoggingManager()

# Convenience functions for backward compatibility
def configure_logging(config: LoggingConfig) -> None:
    """Configure the global logging system"""
    logging_manager.configure(config)

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance"""
    return logging_manager.get_logger(name)

def set_log_level(level: Union[LogLevel, str], component: Optional[str] = None) -> None:
    """Set log level dynamically"""
    logging_manager.set_level(level, component)

# Default logger for backward compatibility
logger = None

def _ensure_default_logger():
    """Ensure default logger is available"""
    global logger
    if logger is None:
        try:
            logger = get_logger()
        except RuntimeError:
            # Fallback to basic configuration if not configured
            default_config = LoggingConfig()
            configure_logging(default_config)
            logger = get_logger()

# Initialize with basic configuration for immediate use
try:
    default_config = LoggingConfig(
        level=LogLevel.INFO,
        format_type=LogFormat.JSON_COMPACT,
        enable_console=True
    )
    configure_logging(default_config)
    logger = get_logger()
except Exception:
    # Fallback if initialization fails
    logger = logging.getLogger("plant_control")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
