# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import contextvars
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

_current_trace_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_trace_id", default=None)
_current_span: contextvars.ContextVar[Optional["Span"]] = contextvars.ContextVar("current_span", default=None)


@dataclass
class Span:
    span_id: str
    trace_id: str
    name: str
    start_time: float = field(default_factory=time.perf_counter)
    end_time: Optional[float] = None
    status: str = "RUNNING"  # "OK", "ERROR", "RUNNING"
    error: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.perf_counter()
        return (end - self.start_time) * 1000.0

    def add_event(self, name: str, data: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "data": data or {},
        })

    def finish(self, status: str = "OK", error: Optional[str] = None) -> None:
        self.end_time = time.perf_counter()
        self.status = status
        if error:
            self.error = error


class ExecutionTracer:
    """
    In-memory correlated distributed tracer with circular ring buffer.
    Enables instant inspection of recent operations without log clutter.
    """

    def __init__(self, max_retained_spans: int = 1000):
        self.max_retained_spans = max_retained_spans
        self._spans_ring: Deque[Span] = deque(maxlen=max_retained_spans)
        self._traces: Dict[str, List[Span]] = {}

    def new_trace_id(self) -> str:
        return secrets.token_hex(8)

    def new_span_id(self) -> str:
        return secrets.token_hex(6)

    def start_span(self, name: str, trace_id: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None) -> Span:
        current_t = trace_id or _current_trace_id.get() or self.new_trace_id()
        _current_trace_id.set(current_t)

        span = Span(
            span_id=self.new_span_id(),
            trace_id=current_t,
            name=name,
            attributes=attributes or {},
        )
        _current_span.set(span)
        return span

    def finish_span(self, span: Span, status: str = "OK", error: Optional[str] = None) -> None:
        span.finish(status=status, error=error)
        self._spans_ring.append(span)

        if span.trace_id not in self._traces:
            if len(self._traces) > 200:
                # Remove oldest trace
                oldest_key = next(iter(self._traces))
                self._traces.pop(oldest_key, None)
            self._traces[span.trace_id] = []
        self._traces[span.trace_id].append(span)

    def get_trace(self, trace_id: str) -> List[Span]:
        return self._traces.get(trace_id, [])

    def get_recent_spans(self, count: int = 20) -> List[Span]:
        spans = list(self._spans_ring)
        return spans[-count:]


tracer = ExecutionTracer()


class trace_context:
    """Async/sync context manager for wrapping operations in a traced span."""

    def __init__(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        self.name = name
        self.attributes = attributes or {}
        self.span: Optional[Span] = None

    def __enter__(self) -> Span:
        self.span = tracer.start_span(self.name, attributes=self.attributes)
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            if exc_type:
                tracer.finish_span(self.span, status="ERROR", error=str(exc_val))
            else:
                tracer.finish_span(self.span, status="OK")
        return False

    async def __aenter__(self) -> Span:
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)
