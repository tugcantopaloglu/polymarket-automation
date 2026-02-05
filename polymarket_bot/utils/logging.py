import sys
import logging
import structlog
from pathlib import Path
from datetime import datetime
from typing import Optional

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    json_format: bool = False
):
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)

def get_logger(name: str = None):
    return structlog.get_logger(name)

class MetricsCollector:
    def __init__(self):
        self._metrics = {}
        self._counters = {}
        self._timers = {}
    
    def increment(self, name: str, value: int = 1, tags: dict = None):
        key = (name, frozenset((tags or {}).items()))
        self._counters[key] = self._counters.get(key, 0) + value
    
    def gauge(self, name: str, value: float, tags: dict = None):
        key = (name, frozenset((tags or {}).items()))
        self._metrics[key] = value
    
    def timer_start(self, name: str):
        self._timers[name] = datetime.utcnow()
    
    def timer_stop(self, name: str) -> Optional[float]:
        if name in self._timers:
            elapsed = (datetime.utcnow() - self._timers[name]).total_seconds()
            del self._timers[name]
            return elapsed
        return None
    
    def get_all(self) -> dict:
        return {
            "counters": {f"{k[0]}:{dict(k[1])}": v for k, v in self._counters.items()},
            "gauges": {f"{k[0]}:{dict(k[1])}": v for k, v in self._metrics.items()}
        }
    
    def reset(self):
        self._counters.clear()

metrics = MetricsCollector()
