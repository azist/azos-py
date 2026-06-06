"""
Circuit breaker pattern implementation for calling external services.

Copyright (C) 2025 Azist, MIT License
"""

import time
import functools
from enum import Enum, auto
from typing import Callable, Any, TypeVar, ParamSpec

# Type hints for the decorator
P = ParamSpec('P')
R = TypeVar('R')

class CircuitBreakerState(Enum):
    """Enum to represent the state of the circuit breaker"""
    CLOSED = auto()     # Normal operation, requests flow through
    OPEN = auto()       # Tripped, requests are blocked immediately
    HALF_OPEN = auto()  # Testing recovery, single request allowed through


class CircuitBreakerOpenException(Exception):
    """Raised when a call is made but the circuit breaker is OPEN"""
    pass


class CircuitBreaker:
    """Base Circuit Breaker that trips on ANY exception"""

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 10.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time = 0.0

    def call(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        """Proxies the call to the target function and manages state."""
        self._check_state()

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            if self._should_trip(e):
                self._on_failure()
            raise e  # Always re-raise the original exception

    def _check_state(self) -> None:
        """Evaluates if the circuit should transition from OPEN to HALF_OPEN"""
        if self.state == CircuitBreakerState.OPEN:
            time_since_failure = time.time() - self.last_failure_time
            if time_since_failure >= self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise CircuitBreakerOpenException(
                    f"Circuit is OPEN. Try again in {self.recovery_timeout - time_since_failure:.1f}s"
                )

    def _on_success(self) -> None:
        """Resets the circuit breaker on a successful call"""
        if self.state != CircuitBreakerState.CLOSED:
            self.failure_count = 0
            self.state = CircuitBreakerState.CLOSED

    def _on_failure(self) -> None:
        """Increments failure count and trips the circuit if threshold is met"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        # If we fail while HALF_OPEN, or hit the threshold while CLOSED, trip it.
        if self.state == CircuitBreakerState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN

    def _should_trip(self, exception: Exception) -> bool:
        """
        Determines if the exception should count towards tripping the circuit.
        Base implementation trips on ALL exceptions
        """
        return True


class HttpCircuitBreaker(CircuitBreaker):
    """
    HTTP-specific Circuit Breaker.
    Trips on exceptions, but ignores 4xx family status codes (business/client errors)
    """

    def _should_trip(self, exception: Exception) -> bool:
        # Check standard library urllib.error.HTTPError
        if hasattr(exception, 'code') and isinstance(exception.code, int):
            if 400 <= exception.code < 500:
                return False

        # Duck-typing for custom exception classes that use 'status_code'
        if hasattr(exception, 'status_code') and isinstance(exception.status_code, int):
            if 400 <= exception.status_code < 500:
                return False

        # For network timeouts, 5xx errors, or unknown exceptions, trip the circuit
        return True


def with_circuit_breaker(breaker: CircuitBreaker):
    """
    Decorator to attach a specific CircuitBreaker instance to a function
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator