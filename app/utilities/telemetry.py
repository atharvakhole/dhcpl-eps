import logging
import json
from datetime import datetime

class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Build the log record
        log_record = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
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

# Setup - explicitly use stdout instead of stderr
import sys
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.propagate = False
