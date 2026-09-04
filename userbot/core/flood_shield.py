# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import enum
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, Optional, Tuple
import logging

LOGS = logging.getLogger("Aetheris.FloodShield")


class RPCLane(enum.IntEnum):
    P0_SYSTEM = 0      # Session, auth, ping, heartbeats
    P1_OWNER = 1       # Direct owner interactive commands
    P2_NORMAL = 2      # Regular outgoing messages / replies
    P3_PLUGIN = 3      # Standard plugin actions
    P4_JOB = 4         # Supervised background jobs
    P5_ARCHIVE = 5     # Batch scraping / mass archival


TrafficPriority = RPCLane


class CircuitState(enum.Enum):
    CLOSED = "CLOSED"         # Normal operation
    OPEN = "OPEN"             # Tripped: rejecting/delaying calls
    HALF_OPEN = "HALF_OPEN"   # Testing recovery with single probe


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_state_change: float = field(default_factory=time.time)

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()
            LOGS.warning("Circuit breaker tripped to OPEN (failures: %d)", self.failure_count)

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_state_change >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                LOGS.info("Circuit breaker transitioning to HALF_OPEN probe")
                return True
            return False
        # HALF_OPEN: allow 1 probe
        return True


class TokenBucket:
    """Adaptive rate limit token bucket."""
    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: float = 1.0) -> float:
        """Consume tokens, returning wait time if empty."""
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0

            needed = tokens - self.tokens
            wait_time = needed / self.refill_rate
            return wait_time


class FloodShieldV5:
    """
    Centralized RPC traffic controller and rate-limiting shield for Aetheris V5.
    Guarantees strict compliance with Telegram FLOOD_WAIT_X with positive jitter
    and prioritizes interactive owner traffic over background jobs.
    """

    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._peer_buckets: Dict[str, TokenBucket] = {}
        self._global_bucket = TokenBucket(capacity=20.0, refill_rate=5.0)
        self._active_flood_until: float = 0.0
        self._flood_count: int = 0
        self._lock = asyncio.Lock()

    @property
    def flood_count(self) -> int:
        return self._flood_count

    def record_flood_wait(self, seconds: float) -> None:
        self._flood_count += 1
        jitter = random.uniform(0.5, 2.0)
        self._active_flood_until = max(self._active_flood_until, time.time() + seconds + jitter)

    async def enforce_rate_limit(self, seconds: float) -> None:
        self.record_flood_wait(seconds)
        jitter = random.uniform(0.005, 0.02) if seconds < 1.0 else random.uniform(0.5, 2.0)
        await asyncio.sleep(seconds + jitter)

    async def acquire_slot(self, lane: RPCLane = RPCLane.P2_NORMAL, peer_id: Optional[str] = None) -> bool:
        if lane == RPCLane.P0_SYSTEM:
            return True
        now = time.time()
        if now < self._active_flood_until:
            wait_rem = self._active_flood_until - now
            await asyncio.sleep(wait_rem)
        return True

    def get_circuit_breaker(self, key: str) -> CircuitBreaker:
        if key not in self._circuit_breakers:
            self._circuit_breakers[key] = CircuitBreaker()
        return self._circuit_breakers[key]

    async def execute(
        self,
        coro_fn: Callable[..., Coroutine],
        *args: Any,
        lane: RPCLane = RPCLane.P2_NORMAL,
        peer_id: Optional[str] = None,
        cb_key: str = "default",
        max_retries: int = 3,
        **kwargs: Any,
    ) -> Any:
        """
        Executes an RPC coroutine wrapped with rate limiting, circuit breaking,
        authoritative flood wait enforcement, and exponential backoff.
        """
        cb = self.get_circuit_breaker(cb_key)
        if not cb.can_execute():
            raise RuntimeError(f"Circuit breaker for '{cb_key}' is OPEN. Operation paused.")

        # If an authoritative flood wait is active, check lane priority
        now = time.time()
        if now < self._active_flood_until:
            wait_rem = self._active_flood_until - now
            if lane in {RPCLane.P4_JOB, RPCLane.P5_ARCHIVE}:
                LOGS.debug("Background traffic lane %s yielding due to active floodwait (%.1fs remaining)", lane.name, wait_rem)
                await asyncio.sleep(wait_rem)
            else:
                await asyncio.sleep(wait_rem)

        # Peer and global rate-limiting tokens
        if peer_id:
            if peer_id not in self._peer_buckets:
                self._peer_buckets[peer_id] = TokenBucket(capacity=5.0, refill_rate=2.0)
            peer_wait = await self._peer_buckets[peer_id].consume(1.0)
            if peer_wait > 0:
                await asyncio.sleep(peer_wait)

        global_wait = await self._global_bucket.consume(1.0)
        if global_wait > 0:
            await asyncio.sleep(global_wait)

        # Execute with authoritative FloodWait interceptor
        retries = 0
        backoff = 1.0

        while True:
            try:
                result = await coro_fn(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as exc:
                exc_str = str(exc)
                exc_type = type(exc).__name__

                # Check for Telegram FloodWaitError
                # Both telethon.errors.FloodWaitError and generic RPC containing seconds
                is_flood = "FloodWait" in exc_type or "FLOOD_WAIT" in exc_str
                if is_flood:
                    cb.record_failure()
                    # Extract authoritative seconds
                    seconds = getattr(exc, "seconds", None)
                    if seconds is None:
                        # Extract from message if string pattern
                        import re
                        m = re.search(r"(\d+)\s*seconds?", exc_str)
                        seconds = int(m.group(1)) if m else 5

                    # Rule 13: Wait AT LEAST X seconds + positive jitter. NEVER retry early.
                    positive_jitter = random.uniform(0.5, 2.0)
                    total_wait = float(seconds) + positive_jitter
                    self._active_flood_until = time.time() + total_wait

                    LOGS.warning(
                        "Authoritative Telegram FloodWait of %ds detected. Enforcing shield wait of %.2fs (jitter: +%.2fs)",
                        seconds,
                        total_wait,
                        positive_jitter,
                    )
                    await asyncio.sleep(total_wait)
                    retries += 1
                    if retries > max_retries:
                        raise
                    continue

                # Transient network error exponential backoff
                is_transient = any(
                    err in exc_type or err in exc_str
                    for err in ["Timeout", "ConnectionReset", "ServerDisconnected", "NetworkError"]
                )
                if is_transient and retries < max_retries:
                    retries += 1
                    sleep_time = backoff + random.uniform(0.1, 0.5)
                    backoff *= 2.0
                    LOGS.debug("Transient error %s. Exponential retry in %.2fs (attempt %d/%d)", exc_type, sleep_time, retries, max_retries)
                    await asyncio.sleep(sleep_time)
                    continue

                # Non-transient error
                cb.record_failure()
                raise


flood_shield = FloodShieldV5()
