import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Collects and tracks analysis metrics."""

    def __init__(self) -> None:
        self._metrics: Dict[str, Any] = {}
        self._timers: Dict[str, float] = {}

    def start_timer(self, name: str) -> None:
        """Start a named timer."""
        self._timers[name] = time.monotonic()

    def stop_timer(self, name: str) -> float:
        """Stop a named timer and return elapsed milliseconds."""
        if name not in self._timers:
            logger.warning("Timer '%s' was never started.", name)
            return 0.0
        elapsed = (time.monotonic() - self._timers.pop(name)) * 1000
        self._metrics[f"{name}_ms"] = elapsed
        return elapsed

    def record(self, key: str, value: Any) -> None:
        """Record an arbitrary metric value."""
        self._metrics[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a recorded metric."""
        return self._metrics.get(key, default)

    def all(self) -> Dict[str, Any]:
        """Return all recorded metrics."""
        return dict(self._metrics)

    @contextmanager
    def timer(self, name: str) -> Generator[None, None, None]:
        """Context manager that times the enclosed block."""
        self.start_timer(name)
        try:
            yield
        finally:
            elapsed = self.stop_timer(name)
            logger.debug("'%s' took %.2f ms", name, elapsed)
