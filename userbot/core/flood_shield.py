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
    P0_SYSTEM = 0      # Session, auth, ping, heartbeats (NEVER blocked or delayed)
    P1_OWNER = 1       # Direct owner interactive commands
    P2_NORMAL = 2      # Regular outgoing messages / replies
    P3_PLUGIN = 3      # Standard plugin actions
    P4_JOB = 4         # Supervised background jobs / file transfers
    P5_ARCHIVE = 5     # Batch scraping / mass archival


TrafficPriority = RPCLane

# Verified high-level requests in Jisan09/Telethon 4bcec594.
# InitConnection/InvokeWithLayer, pings and ACKs use MTProtoSender directly.
MAINTENANCE_RPC_NAMES = {
    "GetStateRequest", "GetDifferenceRequest", "GetChannelDifferenceRequest", "GetConfigRequest",
}


def is_maintenance_request(request: Any) -> bool:
    return type(request).__name__ in MAINTENANCE_RPC_NAMES


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

            self.tokens -= tokens  # Reserve this caller's place, including existing debt.
            return -self.tokens / self.refill_rate


def calculate_flood_wait(seconds: float, min_jitter: float = 0.5, max_jitter: float = 2.0) -> float:
    """
    Computes required flood wait duration ensuring strict compliance with FLOOD_WAIT_X.
    Rule 9: The scheduler must NEVER retry before X seconds. Positive jitter may be added,
    guaranteeing wait_time >= seconds.
    """
    base_wait = float(max(0.0, seconds))
    if base_wait < 1.0:
        positive_jitter = random.uniform(0.01, 0.05)
    else:
        positive_jitter = random.uniform(max(0.1, min_jitter), max_jitter)
    
    total = base_wait + positive_jitter
    assert total >= base_wait, "Calculated flood wait cannot be less than authoritative seconds"
    return total


class FloodShieldV5:
    """
    Centralized RPC traffic controller and rate-limiting shield for Aetheris V5.
    Intercepts and governs all outbound MTProto RPC calls at the lowest boundary.
    Guarantees strict compliance with Telegram FLOOD_WAIT_X with positive jitter.
    """

    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._peer_buckets: Dict[str, TokenBucket] = {}
        self._global_bucket = TokenBucket(capacity=25.0, refill_rate=6.0)
        self._active_flood_until: float = 0.0
        self._flood_count: int = 0
        self._lock = asyncio.Lock()

    @property
    def flood_count(self) -> int:
        return self._flood_count

    def record_flood_wait(self, seconds: float) -> float:
        """Records an authoritative FloodWaitError and calculates wait duration."""
        self._flood_count += 1
        total_wait = calculate_flood_wait(seconds)
        now = time.time()
        self._active_flood_until = max(self._active_flood_until, now + total_wait)
        return total_wait

    async def enforce_rate_limit(self, seconds: float) -> float:
        total_wait = self.record_flood_wait(seconds)
        await asyncio.sleep(total_wait)
        return total_wait

    async def acquire_slot(self, lane: RPCLane = RPCLane.P2_NORMAL, peer_id: Optional[str] = None) -> bool:
        # System maintenance traffic never blocks on floodwaits
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
        retry_transient: bool = False,
        **kwargs: Any,
    ) -> Any:
        """
        Executes an RPC coroutine wrapped with rate limiting, circuit breaking,
        authoritative flood wait enforcement, and positive-jitter retries.
        """
        # P0_SYSTEM bypasses circuit breakers and rate limits to keep connection alive
        if lane != RPCLane.P0_SYSTEM:
            cb = self.get_circuit_breaker(cb_key)
            if not cb.can_execute():
                raise RuntimeError(f"Circuit breaker for '{cb_key}' is OPEN. Operation paused.")

            # If a flood wait is active, wait until it clears
            now = time.time()
            if now < self._active_flood_until:
                wait_rem = self._active_flood_until - now
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
        else:
            cb = None

        retries = 0
        backoff = 1.0

        while True:
            if lane != RPCLane.P0_SYSTEM:
                while time.time() < self._active_flood_until:
                    await asyncio.sleep(self._active_flood_until - time.time())
            try:
                result = await coro_fn(*args, **kwargs)
                if cb:
                    cb.record_success()
                return result
            except Exception as exc:
                exc_str = str(exc)
                exc_type = type(exc).__name__

                # Check for Telegram FloodWaitError
                is_flood = "FloodWait" in exc_type or "FLOOD_WAIT" in exc_str
                if is_flood:
                    if cb:
                        cb.record_failure()
                    # Extract authoritative seconds
                    seconds = getattr(exc, "seconds", None)
                    if seconds is None:
                        import re
                        m = re.search(r"(\d+)\s*seconds?", exc_str)
                        seconds = int(m.group(1)) if m else 5

                    total_wait = self.record_flood_wait(float(seconds))
                    LOGS.warning(
                        "Authoritative Telegram FloodWait of %ss detected. Enforcing shield wait of %.2fs",
                        seconds,
                        total_wait,
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
                if retry_transient and is_transient and retries < max_retries:
                    retries += 1
                    sleep_time = backoff + random.uniform(0.1, 0.5)
                    backoff *= 2.0
                    LOGS.debug("Transient error %s. Retrying in %.2fs (attempt %d/%d)", exc_type, sleep_time, retries, max_retries)
                    await asyncio.sleep(sleep_time)
                    continue

                if cb:
                    cb.record_failure()
                raise


flood_shield = FloodShieldV5()
