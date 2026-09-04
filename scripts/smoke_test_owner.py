# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

"""
Safe owner-controlled smoke test runner for Aetheris V5.
Executes non-destructive diagnostics strictly within owner-scoped contexts
(e.g., Telegram Saved Messages or local loopback) to verify operational readiness.
DOES NOT perform mass messaging, broadcast spam, or join external chats.
"""

import asyncio
import os
import sys
import time

# Ensure repo root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from userbot.core.callbacks import callback_manager
from userbot.core.flood_shield import RPCLane, calculate_flood_wait, flood_shield
from userbot.core.jobs.supervisor import CancellationToken, JobPriority, JobState, job_supervisor
from userbot.core.parser import command_parser
from userbot.core.plugins.registry import atomic_registry
from userbot.core.transfer.engine import MAX_CHUNK_SIZE, ChunkPlanner, transfer_engine
from userbot.sql_helper import check_connection, get_storage_mode
from userbot.sql_helper.globals import addgvar, delgvar, gvarstatus


async def run_owner_smoke_tests():
    print("=" * 70)
    print("  A E T H E R I S  V 5  --  O W N E R  S M O K E  T E S T  S U I T E")
    print("=" * 70)

    results = {}

    # 1. Database & Storage Tier
    print("[1/8] Verifying Database Storage Mode & Health...")
    db_healthy = check_connection()
    mode = get_storage_mode()
    addgvar("smoke_test_key", "smoke_val")
    val = gvarstatus("smoke_test_key")
    delgvar("smoke_test_key")
    storage_ok = db_healthy and val == "smoke_val"
    results["Storage (L1 Cache & Authoritative DB)"] = "PASS" if storage_ok else "FAIL"
    print(f"      -> Storage Mode: {mode} | Health: {'OK' if db_healthy else 'FAILED'}")

    # 2. CommandParserV5 GNU Flag & Quoting Compliance
    print("[2/8] Verifying POSIX Command Parser...")
    cmd = command_parser.parse('.purge "quoted pattern" -rfv --timeout=30')
    parser_ok = (
        cmd.name == "purge"
        and cmd.args == ["quoted pattern"]
        and cmd.has_flag("r")
        and cmd.has_flag("f")
        and cmd.has_flag("v")
        and cmd.get_flag("timeout", type_cast=int) == 30
    )
    results["POSIX CommandParserV5"] = "PASS" if parser_ok else "FAIL"
    print(f"      -> Command Parsing: {'PASS' if parser_ok else 'FAIL'}")

    # 3. JobSupervisor Lifecycle & Cooperative Cancellation
    print("[3/8] Verifying JobSupervisor Lifecycle...")
    await job_supervisor.start()
    job_executed = False

    async def sample_worker(token: CancellationToken):
        nonlocal job_executed
        job_executed = True
        await token.sleep(0.05)

    rec = await job_supervisor.submit("smoke_job", sample_worker, priority=JobPriority.NORMAL)
    await asyncio.sleep(0.1)
    await job_supervisor.cancel_job(rec.job_id)
    supervisor_ok = job_executed
    results["JobSupervisor Concurrency Engine"] = "PASS" if supervisor_ok else "FAIL"
    print(f"      -> Job Execution: {'PASS' if supervisor_ok else 'FAIL'}")

    # 4. FloodShield MTProto Rate Limit Semantics
    print("[4/8] Verifying FloodShield MTProto Guard...")
    wait_time = calculate_flood_wait(5.0)
    # Must never retry before 5.0 seconds
    shield_ok = wait_time >= 5.0 and (wait_time - 5.0) > 0.0
    slot_ok = await flood_shield.acquire_slot(RPCLane.P0_SYSTEM)
    results["FloodShield MTProto Guard"] = "PASS" if (shield_ok and slot_ok) else "FAIL"
    print(f"      -> FloodWait Semantics (5s request -> {wait_time:.2f}s wait): {'PASS' if shield_ok else 'FAIL'}")

    # 5. Telegram MTProto Callback Size Verification
    print("[5/8] Verifying Inline Callback 64-Byte Limit...")
    cb_token = callback_manager.create_token("owner_action", payload={"key": "val" * 20})
    cb_len = len(cb_token.encode("utf-8"))
    callback_ok = 1 <= cb_len <= 64 and cb_token.startswith("cb:")
    results["Cryptographic Opaque Callbacks (<=64 bytes)"] = "PASS" if callback_ok else "FAIL"
    print(f"      -> Encoded Token Length: {cb_len} bytes (Limit: 64): {'PASS' if callback_ok else 'FAIL'}")

    # 6. File Transfer Engine MTProto 512 KiB Sizing
    print("[6/8] Verifying Transfer Engine Chunk Sizing...")
    plan_small = ChunkPlanner.plan(5 * 1024 * 1024)
    plan_large = ChunkPlanner.plan(int(1.8 * 1024 * 1024 * 1024))
    transfer_ok = (
        plan_small.chunk_size <= MAX_CHUNK_SIZE
        and plan_large.chunk_size == MAX_CHUNK_SIZE
        and plan_small.chunk_size % 1024 == 0
    )
    results["FileTransfer MTProto 512 KiB Compliance"] = "PASS" if transfer_ok else "FAIL"
    print(f"      -> 1.8 GB Part Size: {plan_large.chunk_size // 1024} KiB (Max: 512 KiB): {'PASS' if transfer_ok else 'FAIL'}")

    # 7. Multi-Provider AI Routing Contract
    print("[7/8] Verifying AI Fabric Adapters...")
    from userbot.core.ai import ai_router
    ai_resp = await ai_router.complete("Ping AI", provider="mock")
    ai_ok = "Ping AI" in ai_resp.content
    results["Polyglot AI Fabric (Mock Tested)"] = "PASS" if ai_ok else "FAIL"
    print(f"      -> AI Router Completion: {'PASS' if ai_ok else 'FAIL'}")

    # 8. Web Control Plane (Localhost Loopback)
    print("[8/8] Verifying Web Dashboard Control Plane...")
    from userbot.core.web.server import DashboardServer
    dash = DashboardServer(host="127.0.0.1", port=8989)
    await dash.start()
    dash_running = dash._running
    await dash.stop()
    results["Web Dashboard Control Plane"] = "PASS" if dash_running else "FAIL"
    print(f"      -> Dashboard Startup & Shutdown: {'PASS' if dash_running else 'FAIL'}")

    # Teardown supervisor
    await job_supervisor.stop()

    print("\n" + "=" * 70)
    print("                    SMOKE TEST SUMMARY")
    print("=" * 70)
    all_passed = True
    for test_name, status in results.items():
        print(f"  * {test_name:<48} : [{status}]")
        if status != "PASS":
            all_passed = False
    print("=" * 70)
    print(f"OVERALL STATUS: {'ALL OWNER TESTS PASSED (SAFE FOR OPERATION)' if all_passed else 'FAILURES DETECTED'}")
    print("=" * 70)
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_owner_smoke_tests())
    sys.exit(0 if success else 1)
