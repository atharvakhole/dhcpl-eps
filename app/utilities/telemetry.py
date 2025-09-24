import logging
import json
from datetime import datetime
import sys

class JsonFormatter(logging.Formatter):
    """Compact JSON formatter - single line output"""
    def format(self, record):
        # Build the log record
        log_record = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Reserved attributes we don't want duplicated (get them dynamically)
        reserved = set(vars(logging.LogRecord('', 0, '', 0, '', (), None)).keys())
        reserved.add('getMessage')  # Add this method name too
        
        # Add extras (anything that isn't reserved)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in reserved and not key.startswith('_')
        }
        if extras:
            log_record["extra"] = extras
        
        # Output compact JSON (single line)
        return json.dumps(log_record, ensure_ascii=False, separators=(',', ':'))


class JsonPrettyFormatter(logging.Formatter):
    """Pretty-printed JSON formatter - multi-line indented output"""
    def format(self, record):
        # Build the log record
        log_record = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Reserved attributes we don't want duplicated (get them dynamically)
        reserved = set(vars(logging.LogRecord('', 0, '', 0, '', (), None)).keys())
        reserved.add('getMessage')  # Add this method name too
        
        # Add extras (anything that isn't reserved)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in reserved and not key.startswith('_')
        }
        if extras:
            log_record["extra"] = extras
        
        # Output pretty-printed JSON (multi-line with indentation)
        return json.dumps(log_record, ensure_ascii=False, indent=2)

# Compact formatter setup
def setup_compact_logger(name="compact_logger"):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False
    return logger

# Pretty formatter setup
def setup_pretty_logger(name="pretty_logger"):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonPrettyFormatter())
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False
    return logger

logger = setup_pretty_logger()

# Example usage
if __name__ == "__main__":
    # Compact logger
    compact_logger = setup_compact_logger("app.compact")
    print("=== Compact JSON Logging ===")
    compact_logger.info("This is a compact log message", extra={
        "user_id": 123,
        "action": "login",
        "ip_address": "192.168.1.1"
    })
    
    print("\n=== Pretty JSON Logging ===")
    # Pretty logger  
    pretty_logger = setup_pretty_logger("app.pretty")
    pretty_logger.info("This is a pretty log message", extra={
        "user_id": 456,
        "action": "logout", 
        "ip_address": "192.168.1.2",
        "session_duration": 3600
    })
