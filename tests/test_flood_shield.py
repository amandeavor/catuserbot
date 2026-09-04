# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import time
import pytest
from userbot.core.flood_shield import CircuitBreaker, CircuitState, FloodShieldV5, TrafficPriority


def test_circuit_breaker_transitions():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
    assert cb.state == CircuitState.CLOSED

    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    # Wait for recovery timeout
    time.sleep(0.12)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_flood_shield_acquire():
    shield = FloodShieldV5()
    # High-priority lane should acquire immediately
    acquired = await shield.acquire_slot(TrafficPriority.P0_SYSTEM)
    assert acquired is True


@pytest.mark.asyncio
async def test_flood_shield_rate_limit_backoff():
    shield = FloodShieldV5()
    t0 = time.perf_counter()
    # Enforce a tiny wait (0.05s)
    await shield.enforce_rate_limit(seconds=0.05)
    elapsed = time.perf_counter() - t0
    # Should take at least 0.05s
    assert elapsed >= 0.05
    assert shield.flood_count == 1
