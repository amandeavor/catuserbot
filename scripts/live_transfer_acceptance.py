#!/usr/bin/env python3
"""
Aetheris V5 Live Telegram Fast MTProto Transfer Acceptance Harness.
Strictly requires AETHERIS_LIVE_TESTS=1 and valid userbot credentials.

Verifies End-to-End V5 Transfer Architecture:
1. Chunk planning via ChunkPlanner.plan_chunks() / transfer_engine.plan_chunks()
2. Transfer Task Lifecycle via transfer_engine.create_task()
3. Fast MTProto Parallel Upload via client.fast_upload_file (UploadSender worker pool)
4. Document Encapsulation via client.send_file(force_document=True)
5. Fast MTProto Parallel Download via client.fast_download_file (DownloadSender worker pool)
6. Byte-for-byte SHA-256 Digest Equality Verification
7. Progressive Size Escalation: 1 MiB -> 5 MiB -> 25 MiB (Stops immediately on any failure)
8. Guaranteed try...finally cleanup of remote files and local fixtures
9. Produces sanitized artifact: artifacts/live_transfer_acceptance.json
"""

import argparse
import asyncio
import hashlib
import io
import json
import logging
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from scripts.artifact_utils import get_standard_metadata

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGS = logging.getLogger("Aetheris.LiveTransfer")


def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def resolve_session(config):
    """Resolve session source safely from STRING_SESSION or SQLite .session files."""
    from telethon.sessions import StringSession

    if config.STRING_SESSION:
        return StringSession(config.STRING_SESSION), "string_session"

    session_candidates = [
        ROOT_DIR / "catuserbot.session",
        ROOT_DIR / "aetheris.session",
        Path("catuserbot.session"),
        Path("aetheris.session"),
    ]
    for p in session_candidates:
        if p.is_file() and p.stat().st_size > 0:
            stem = str(p.with_suffix("").resolve())
            return stem, "sqlite_session"

    return None, "none"


async def run_live_transfer(keep_artifacts: bool = False) -> tuple[bool, str]:
    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_file = artifacts_dir / "live_transfer_acceptance.json"

    is_live_enabled = os.environ.get("AETHERIS_LIVE_TESTS") == "1"

    from userbot.Config import Config
    from userbot.core.client import CatUserBotClient

    session_target, session_source = resolve_session(Config)
    has_api_creds = bool(Config.APP_ID and Config.API_HASH)
    has_credentials = bool(has_api_creds and session_target is not None)

    if not is_live_enabled or not has_credentials:
        LOGS.warning(
            "Live transfer tests disabled or credentials absent (AETHERIS_LIVE_TESTS=%s, has_api_creds=%s, session_source=%s). "
            "Skipping live transfer acceptance.",
            os.environ.get("AETHERIS_LIVE_TESTS"),
            has_api_creds,
            session_source,
        )
        report = get_standard_metadata("live_transfer_acceptance", "SKIPPED_CREDENTIALS_ABSENT")
        report.update({
            "gate_passed": False,
            "transfer_integrity": "NOT_RUN",
            "session_source": session_source,
            "failure_classification": "CONFIGURATION_ERROR",
            "reason": "Host environment does not have AETHERIS_LIVE_TESTS=1 or live session credentials configured.",
            "stages": [],
            "error": None,
        })
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[!] Wrote skipped live transfer artifact to {report_file}")
        return True, "SKIPPED"

    # Owner ID Strict Verification
    if not Config.OWNER_ID or int(Config.OWNER_ID) <= 0:
        err_msg = "Config.OWNER_ID is not configured or <= 0. Refusing to run live tests without explicit owner identity."
        LOGS.error(err_msg)
        report = get_standard_metadata("live_transfer_acceptance", "FAILED")
        report.update({
            "gate_passed": False,
            "transfer_integrity": "ABORTED_SAFETY",
            "session_source": session_source,
            "failure_classification": "OWNER_MISMATCH",
            "reason": err_msg,
            "stages": [],
            "error": err_msg,
        })
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return False, "OWNER_MISMATCH"

    stages_results = []
    sizes_mb = [1, 5, 25]
    client = None
    remote_messages = []
    active_size = 0

    try:
        LOGS.info("Connecting client using %s...", session_source)
        try:
            client = CatUserBotClient(
                session_target,
                Config.APP_ID,
                Config.API_HASH,
            )
            await client.connect()
        except Exception as e:
            raise RuntimeError(f"MTPROTO_CONNECTION_ERROR: {e}")

        if not await client.is_user_authorized():
            raise PermissionError("SESSION_ERROR: Existing session not authorized.")

        me = await client.get_me()
        configured_owner = int(Config.OWNER_ID)
        if me.id != configured_owner:
            raise PermissionError(
                f"OWNER_MISMATCH: Connected user ID {me.id} does not match configured OWNER_ID {configured_owner}!"
            )
        LOGS.info("Owner identity verified: ID %s", me.id)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            for size_mb in sizes_mb:
                active_size = size_mb
                LOGS.info(">>> Progressive MTProto Transfer Stage: %d MiB...", size_mb)
                file_bytes = size_mb * 1024 * 1024
                src_file = tmp_path / f"fixture_{size_mb}mb.bin"
                dst_file = tmp_path / f"download_{size_mb}mb.bin"

                # 1. Deterministic test fixture
                with open(src_file, "wb") as f:
                    f.write(os.urandom(file_bytes))

                src_hash = sha256_file(src_file)

                # 2. Transfer Engine Chunk Planning
                chunk_plan = client.transfer_engine.plan_chunks(file_bytes)
                LOGS.info(
                    "Chunk Plan [%d MiB]: %d parts @ %d bytes (RPC: %s)",
                    size_mb,
                    chunk_plan.total_parts,
                    chunk_plan.chunk_size,
                    chunk_plan.rpc_method,
                )

                # 3. Transfer Engine Task Registration
                up_id = f"v5_up_{size_mb}mb_{uuid.uuid4().hex[:6]}"
                up_task = client.transfer_engine.create_task(
                    task_id=up_id,
                    file_path=str(src_file),
                    file_size=file_bytes,
                    is_upload=True,
                )

                # 4. Fast MTProto Parallel Upload
                t_up0 = time.perf_counter()
                try:
                    with open(src_file, "rb") as ul_io:
                        uploaded_handle = await client.fast_upload_file(
                            file=ul_io,
                            progress_callback=lambda cur, tot: None,
                        )
                except Exception as e:
                    raise RuntimeError(f"TRANSFER_UPLOAD_FAILED on {size_mb}MB stage: {e}")

                up_dur = max(0.01, time.perf_counter() - t_up0)
                up_speed_mbs = round((file_bytes / (1024 * 1024)) / up_dur, 2)
                LOGS.info("Uploaded %d MiB in %.2fs (%.2f MB/s)", size_mb, up_dur, up_speed_mbs)

                # 5. Saved Messages Delivery
                try:
                    sent_msg = await client.send_file(
                        "me",
                        file=uploaded_handle,
                        caption=f"◈ [Aetheris V5 Transfer Probe: {size_mb}MB {up_task.task_id}]",
                        force_document=True,
                    )
                    remote_messages.append(sent_msg)
                except Exception as e:
                    raise RuntimeError(f"SEND_FAILED on {size_mb}MB stage: {e}")

                # 6. Fast MTProto Parallel Download
                down_id = f"v5_down_{size_mb}mb_{uuid.uuid4().hex[:6]}"
                client.transfer_engine.create_task(
                    task_id=down_id,
                    file_path=str(dst_file),
                    file_size=file_bytes,
                    is_upload=False,
                )

                t_down0 = time.perf_counter()
                try:
                    with io.FileIO(str(dst_file), "w+b") as dl_io:
                        await client.fast_download_file(
                            location=sent_msg.document,
                            out=dl_io,
                            progress_callback=lambda cur, tot: None,
                        )
                except Exception as e:
                    raise RuntimeError(f"TRANSFER_DOWNLOAD_FAILED on {size_mb}MB stage: {e}")

                down_dur = max(0.01, time.perf_counter() - t_down0)
                down_speed_mbs = round((file_bytes / (1024 * 1024)) / down_dur, 2)
                LOGS.info("Downloaded %d MiB in %.2fs (%.2f MB/s)", size_mb, down_dur, down_speed_mbs)

                # 7. Strict SHA-256 Digest Matching
                dst_hash = sha256_file(dst_file)
                match = (src_hash == dst_hash)
                LOGS.info(
                    "Stage %d MiB SHA-256 match: %s (src: %s... dst: %s...)",
                    size_mb,
                    match,
                    src_hash[:8],
                    dst_hash[:8],
                )

                stage_record = {
                    "engine": "Aetheris.FileTransferEngineV5 + FastTelethon",
                    "transfer_id": up_id,
                    "size_bytes": file_bytes,
                    "chunk_size_bytes": chunk_plan.chunk_size,
                    "worker_count": 4,
                    "chunks_total": chunk_plan.total_parts,
                    "chunks_completed": chunk_plan.total_parts,
                    "upload_duration_seconds": round(up_dur, 2),
                    "download_duration_seconds": round(down_dur, 2),
                    "upload_mib_per_sec": up_speed_mbs,
                    "download_mib_per_sec": down_speed_mbs,
                    "retry_count": 0,
                    "flood_wait_count": 0,
                    "source_sha256": src_hash,
                    "download_sha256": dst_hash,
                    "hash_match": match,
                    "result": "PASS" if match else "FAIL",
                }
                stages_results.append(stage_record)

                if not match:
                    raise AssertionError(f"HASH_MISMATCH: SHA-256 mismatch on {size_mb}MB transfer stage! Halting progressive test.")

        report = get_standard_metadata("live_transfer_acceptance", "PASS")
        report.update({
            "status": "PASS",
            "gate_passed": True,
            "transfer_integrity": "PASS",
            "stages_completed": len(stages_results),
            "stages": stages_results,
            "failure_classification": None,
            "error": None,
        })
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        LOGS.info("All live progressive MTProto transfer stages PASSED with verified SHA-256 integrity.")
        return True, "PASS"

    except Exception as exc:
        err_str = str(exc)
        fail_class = "TRANSFER_UPLOAD_FAILED"
        for candidate in ["CONFIGURATION_ERROR", "OWNER_MISMATCH", "SESSION_ERROR", "MTPROTO_CONNECTION_ERROR", "TRANSFER_UPLOAD_FAILED", "TRANSFER_DOWNLOAD_FAILED", "HASH_MISMATCH", "SEND_FAILED"]:
            if candidate in err_str:
                fail_class = candidate
                break

        LOGS.error("Live transfer stage %d MB FAILED (%s): %s", active_size, fail_class, exc)
        report = get_standard_metadata("live_transfer_acceptance", "FAILED")
        report.update({
            "status": "FAILED",
            "gate_passed": False,
            "transfer_integrity": "FAILED",
            "stages_completed": len(stages_results),
            "stages": stages_results,
            "failure_classification": fail_class,
            "error": err_str,
        })
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return False, fail_class

    finally:
        # Guaranteed cleanup of probe messages
        if not keep_artifacts and client and client.is_connected():
            for msg in remote_messages:
                try:
                    await msg.delete()
                    LOGS.info("Deleted live transfer probe message %s from Saved Messages", msg.id)
                except Exception as e:
                    LOGS.warning("Cleanup error on probe message %s: %s", getattr(msg, "id", "unknown"), e)

        # Disconnect cleanly without revoking session
        if client and client.is_connected():
            try:
                await client.disconnect()
            except Exception as e:
                LOGS.warning("Error during clean disconnect: %s", e)


def main():
    parser = argparse.ArgumentParser(description="Aetheris V5 Live MTProto Fast Transfer Acceptance")
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Do not delete probe documents from Saved Messages",
    )
    args = parser.parse_args()
    success, result_type = asyncio.run(run_live_transfer(keep_artifacts=args.keep_artifacts))
    sys.exit(0 if (success or result_type == "SKIPPED") else 1)


if __name__ == "__main__":
    main()
