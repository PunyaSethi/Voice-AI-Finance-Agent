from __future__ import annotations

from collections import defaultdict
from threading import Lock


class MetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._timings: dict[str, list[float]] = defaultdict(list)

    def increment(self, key: str, amount: float = 1.0) -> None:
        with self._lock:
            self._counters[key] += amount

    def observe(self, key: str, value: float) -> None:
        with self._lock:
            self._timings[key].append(value)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "timings": {
                    key: {
                        "count": len(values),
                        "avg_ms": round(sum(values) / len(values), 2) if values else 0.0,
                        "max_ms": round(max(values), 2) if values else 0.0,
                    }
                    for key, values in self._timings.items()
                },
            }


metrics_store = MetricsStore()

