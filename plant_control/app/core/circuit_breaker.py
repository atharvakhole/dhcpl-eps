from datetime import datetime
from plant_control.app.models.connection_manager import ConnectionState
from plant_control.app.utilities.telemetry import logger


class CircuitBreaker:
    """Circuit breaker for PLC connection protection"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = ConnectionState.CONNECTED
    
    def record_success(self):
        """Record successful operation and potentially close circuit"""
        self.failure_count = 0
        if self.state == ConnectionState.CIRCUIT_OPEN:
            self.state = ConnectionState.CONNECTED
            logger.info("Circuit breaker recovered", extra={
                "component": "circuit_breaker",
                "action": "circuit_closed",
                "previous_failure_count": self.failure_count
            })
    
    def record_failure(self):
        """Record failed operation and potentially open circuit"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        logger.debug("Circuit breaker failure recorded", extra={
            "component": "circuit_breaker", 
            "failure_count": self.failure_count,
            "threshold": self.failure_threshold
        })
        
        if self.failure_count >= self.failure_threshold:
            self.state = ConnectionState.CIRCUIT_OPEN
            logger.warning("Circuit breaker opened due to failures", extra={
                "component": "circuit_breaker",
                "failure_count": self.failure_count,
                "threshold": self.failure_threshold,
                "timeout_seconds": self.timeout
            })
    
    def can_attempt(self) -> bool:
        """Check if connection attempts are allowed"""
        if self.state != ConnectionState.CIRCUIT_OPEN:
            return True
        
        if self.last_failure_time is None:
            return True
        
        if self._is_timeout_expired():
            logger.info("Circuit breaker timeout expired", extra={
                "component": "circuit_breaker",
                "action": "attempting_reconnection",
                "timeout_seconds": self.timeout
            })
            return True
        
        return False
    
    def _is_timeout_expired(self) -> bool:
        """Check if circuit breaker timeout has expired"""
        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() > self.timeout
