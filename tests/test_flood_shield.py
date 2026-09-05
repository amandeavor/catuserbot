# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import time
from unittest.mock import AsyncMock, patch
import pytest

from userbot.core.flood_shield import (
    CircuitBreaker,
    CircuitState,
    FloodShieldV5,
    RPCLane,
    calculate_flood_wait,
)


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


def test_flood_wait_semantics_never_retries_before_x():
    """
    Section 9: When Telegram returns FLOOD_WAIT_X, the scheduler MUST NOT
    retry before X seconds. Positive jitter may be added, but calculated duration
    must never be less than X.
    """
    test_durations = [0.1, 1.0, 5.0, 30.0, 120.0, 3600.0]
    for x in test_durations:
        wait_val = calculate_flood_wait(x)
        assert wait_val >= x, f"Wait time {wait_val} was less than authoritative {x}s!"
        # Verify jitter is strictly positive
        assert (wait_val - x) > 0.0, "Jitter must be strictly positive"


@pytest.mark.asyncio
async def test_flood_shield_acquire_and_system_bypass():
    shield = FloodShieldV5()
    # P0_SYSTEM must acquire immediately even if shield is under flood wait
    shield.record_flood_wait(10.0)
    assert shield._active_flood_until > time.time()

    # System maintenance traffic bypasses active flood wait
    acquired = await shield.acquire_slot(RPCLane.P0_SYSTEM)
    assert acquired is True


@pytest.mark.asyncio
async def test_flood_shield_central_execution_and_retry():
    shield = FloodShieldV5()
    call_count = 0

    class FakeFloodError(Exception):
        seconds = 0.05

    async def mock_rpc_call():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise FakeFloodError("FLOOD_WAIT_0")
        return "RPC_SUCCESS"

    # Execution should catch FakeFloodError, wait authoritative time + positive jitter, and succeed on retry
    t0 = time.perf_counter()
    result = await shield.execute(mock_rpc_call, lane=RPCLane.P2_NORMAL, cb_key="test_rpc")
    elapsed = time.perf_counter() - t0

    assert result == "RPC_SUCCESS"
    assert call_count == 2
    assert elapsed >= 0.05, f"Elapsed {elapsed}s was less than authoritative wait of 0.05s"


@pytest.mark.asyncio
async def test_flood_shield_rpc_families_scheduling():
    shield = FloodShieldV5()

    async def dummy_rpc(name: str):
        return f"handled_{name}"

    # P0_SYSTEM (Pings, Heartbeats)
    res_sys = await shield.execute(dummy_rpc, "ping", lane=RPCLane.P0_SYSTEM)
    assert res_sys == "handled_ping"

    # P4_JOB (File Uploads / Downloads)
    res_job = await shield.execute(dummy_rpc, "upload_part", lane=RPCLane.P4_JOB)
    assert res_job == "handled_upload_part"

    # P2_NORMAL (Messages / Interactive)
    res_msg = await shield.execute(dummy_rpc, "send_msg", lane=RPCLane.P2_NORMAL)
    assert res_msg == "handled_send_msg"


def test_is_maintenance_request_classification():
    from userbot.core.flood_shield import is_maintenance_request

    maintenance_classes = [
        "GetStateRequest",
        "GetDifferenceRequest",
        "GetChannelDifferenceRequest",
        "GetConfigRequest",
    ]

    for cls_name in maintenance_classes:
        mock_rpc = type(cls_name, (), {})()
        assert is_maintenance_request(mock_rpc) is True, f"Failed to classify {cls_name} as maintenance"

    non_maintenance = [
        # In the pinned audit fork these service messages travel through sender.send,
        # below __call__. Explicit high-level uses must not receive blanket exemptions.
        "PingRequest",
        "PingDelayDisconnectRequest",
        "InitConnectionRequest",
        "InvokeWithLayerRequest",
        "DestroySessionRequest",
        "GetNearestDcRequest",
        "GetFutureSaltsRequest",
        "MsgsAck",
        "HttpWait",
        "GetStateOfUnrelatedPluginRequest",
        "SendMessageRequest",
        "EditMessageRequest",
        "DeleteMessagesRequest",
        "GetHistoryRequest",
        "GetFileRequest",
        "SaveFilePartRequest",
        "UploadMediaRequest",
    ]

    for cls_name in non_maintenance:
        mock_rpc = type(cls_name, (), {})()
        assert is_maintenance_request(mock_rpc) is False, f"Erroneously classified {cls_name} as maintenance"

    assert is_maintenance_request(None) is False
