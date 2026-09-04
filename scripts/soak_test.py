#!/usr/bin/env python3
"""
Aetheris V5 Long-Running Stability and Soak Test Harness.
Exercises sustained concurrent workloads across JobSupervisor, FileTransferEngineV5,
FloodShieldV5, and AtomicHandlerRegistry while profiling RSS, heap objects,
active tasks, and event loop lag.
Outputs telemetry to artifacts/soak_metrics.jsonl.
"""

import asyncio
import gc
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import psutil

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))
os.environ["AETHERIS_OFFLINE_VALIDATION"] = "1"
os.environ["DB_PATH"] = ":memory:"
os.environ["SQL_ENGINE"] = "sqlite"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGS = logging.getLogger("Aetheris.SoakTest")


async def measure_loop_lag() -> float:
    """Measures event loop delay in milliseconds."""
    t0 = time.perf_counter()
    await asyncio.sleep(0.001)
    delay = (time.perf_counter() - t0 - 0.001) * 1000.0
    return max(0.0, delay)


async def run_soak_test(duration_seconds: int = 30, sample_interval: float = 1.0):
    from userbot.core.jobs.supervisor import JobPriority, job_supervisor
    from userbot.core.transfer.engine import transfer_engine
    from userbot.core.flood_shield import flood_shield, RPCLane
    from userbot.core.plugins.registry import atomic_registry

    LOGS.info("Starting Aetheris V5 Soak Test (Duration: %ds, Sample Rate: %.1fs)...", duration_seconds, sample_interval)

    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = artifacts_dir / "soak_metrics.jsonl"
    if metrics_file.exists():
        metrics_file.unlink()

    proc = psutil.Process()
    await job_supervisor.start()

    stop_event = asyncio.Event()
    metrics_history: List[Dict] = []
    total_workload_cycles = 0

    # 1. Continuous Workload Generator
    async def workload_generator():
        nonlocal total_workload_cycles
        counter = 0
        while not stop_event.is_set():
            counter += 1
            total_workload_cycles += 1

            # A. Job Supervisor Workload
            async def dummy_job_work(token=None):
                await asyncio.sleep(0.01)
                return "done"

            priority = JobPriority.HIGH if (counter % 5 == 0) else JobPriority.NORMAL
            await job_supervisor.submit(
                name=f"soak_job_{counter}",
                coro_fn=dummy_job_work,
                priority=priority,
                plugin_id="soak_harness",
            )

            # B. Transfer Engine Task
            transfer_task = transfer_engine.create_task(
                task_id=f"soak_tx_{counter}",
                file_size=512 * 1024,
                is_upload=(counter % 2 == 0),
            )
            # Advance transfer
            transfer_task.update_progress(0, 128 * 1024)

            # C. FloodShield RPC Execution
            async def fake_rpc(val):
                return val * 2

            lane = RPCLane.P0_SYSTEM if (counter % 7 == 0) else RPCLane.P2_NORMAL
            await flood_shield.execute(fake_rpc, 21, lane=lane, cb_key="soak_rpc")

            # Yield briefly to maintain steady pace
            await asyncio.sleep(0.02)

    # 2. Metrics Sampler
    async def metrics_sampler():
        start_time = time.time()
        sample_idx = 0

        with open(metrics_file, "a", encoding="utf-8") as f:
            while not stop_event.is_set():
                sample_idx += 1
                now = time.time()
                elapsed = round(now - start_time, 2)

                gc.collect()
                mem_info = proc.memory_info()
                rss_mb = round(mem_info.rss / (1024 * 1024), 2)
                heap_objects = len(gc.get_objects())
                active_async_tasks = len(asyncio.all_tasks())
                loop_lag = round(await measure_loop_lag(), 3)
                active_jobs = len(job_supervisor.list_jobs(active_only=True))

                record = {
                    "sample": sample_idx,
                    "elapsed_s": elapsed,
                    "rss_mb": rss_mb,
                    "heap_objects": heap_objects,
                    "active_tasks": active_async_tasks,
                    "active_jobs": active_jobs,
                    "loop_lag_ms": loop_lag,
                    "timestamp": now,
                }
                metrics_history.append(record)
                f.write(json.dumps(record) + "\n")
                f.flush()

                LOGS.info(
                    "[%02ds/%02ds] RSS: %.2f MB | Objects: %d | Tasks: %d | Jobs: %d | Lag: %.2fms",
                    int(elapsed),
                    duration_seconds,
                    rss_mb,
                    heap_objects,
                    active_async_tasks,
                    active_jobs,
                    loop_lag,
                )

                await asyncio.sleep(sample_interval)

    # Run tasks concurrently
    workload_task = asyncio.create_task(workload_generator())
    sampler_task = asyncio.create_task(metrics_sampler())

    await asyncio.sleep(duration_seconds)
    stop_event.set()

    await asyncio.gather(workload_task, sampler_task, return_exceptions=True)
    await job_supervisor.stop()

    # Final evaluation
    if not metrics_history:
        raise RuntimeError("No metrics recorded during soak test!")

    initial_rss = metrics_history[0]["rss_mb"]
    final_rss = metrics_history[-1]["rss_mb"]
    peak_rss = max(m["rss_mb"] for m in metrics_history)
    rss_delta = final_rss - initial_rss

    avg_lag = sum(m["loop_lag_ms"] for m in metrics_history) / len(metrics_history)
    max_lag = max(m["loop_lag_ms"] for m in metrics_history)

    print("=" * 80)
    print("AETHERIS V5 SOAK TEST RESULTS:")
    print(f"  Duration:                  {duration_seconds}s")
    print(f"  Total Workload Cycles:     {total_workload_cycles}")
    print(f"  Samples Recorded:          {len(metrics_history)}")
    print(f"  Initial RSS:               {initial_rss:.2f} MB")
    print(f"  Final RSS:                 {final_rss:.2f} MB")
    print(f"  Peak RSS:                  {peak_rss:.2f} MB")
    print(f"  Net Memory Delta:          {rss_delta:+.2f} MB")
    print(f"  Average Loop Lag:          {avg_lag:.2f} ms")
    print(f"  Peak Loop Lag:             {max_lag:.2f} ms")
    print(f"  Metrics Telemetry:         {metrics_file}")
    print("=" * 80)

    # Stability criteria: memory delta must not exceed 25 MB in this timeframe
    assert rss_delta < 25.0, f"Unbounded memory growth detected: +{rss_delta:.2f} MB"
    assert avg_lag < 15.0, f"Event loop degraded: avg lag {avg_lag:.2f}ms"
    LOGS.info("SOAK TEST PASSED: Stability criteria satisfied.")
    return True


if __name__ == "__main__":
    dur = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    asyncio.run(run_soak_test(duration_seconds=dur))
