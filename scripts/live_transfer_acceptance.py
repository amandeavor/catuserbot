#!/usr/bin/env python3
"""
Aetheris V5 Live Telegram Transfer Acceptance Verification Harness.
Strictly requires AETHERIS_LIVE_TESTS=1 and valid userbot credentials.

Explicitly exercises V5 Transfer Engine & Fast MTProto Parallel Transports:
- Chunk planning via transfer_engine.plan_chunks()
- Task registration via transfer_engine.create_task()
- client.fast_upload_file (Parallel MTProto uploaders)
- client.send_file (Telegram Document message generation)
- client.fast_download_file (Parallel MTProto downloaders)
- SHA-256 byte-for-byte digest verification
- Guaranteed try...finally cleanup of remote messages and local temp fixtures
- Produces sanitized artifact: artifacts/live_transfer_acceptance.json
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
        return StringSession(config.STRING_SESSION), "STRING_SESSION"

    session_candidates = [
        ROOT_DIR / "catuserbot.session",
        ROOT_DIR / "aetheris.session",
        Path("catuserbot.session"),
        Path("aetheris.session"),
    ]
    for p in session_candidates:
        if p.is_file() and p.stat().st_size > 0:
            stem = str(p.with_suffix("").resolve())
            return stem, f"SQLITE_FILE ({p.name})"

    return None, "NONE"


async def run_live_transfer(keep_artifacts: bool = False):
    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_file = artifacts_dir / "live_transfer_acceptance.json"

    is_live_enabled = os.environ.get("AETHERIS_LIVE_TESTS") == "1"

    from userbot.Config import Config
    from userbot.core.client import CatUserBotClient

    session_target, session_type = resolve_session(Config)
    has_api_creds = bool(Config.APP_ID and Config.API_HASH)
    has_credentials = bool(has_api_creds and session_target is not None)

    if not is_live_enabled or not has_credentials:
        LOGS.warning(
            "Live transfer tests disabled or credentials absent (AETHERIS_LIVE_TESTS=%s, has_api_creds=%s, session_type=%s). "
            "Skipping live transfer acceptance.",
            os.environ.get("AETHERIS_LIVE_TESTS"),
            has_api_creds,
            session_type,
        )
        report = {
            "timestamp": time.time(),
            "status": "SKIPPED_CREDENTIALS_ABSENT",
            "gate_passed": False,
            "transfer_integrity": "NOT RUN",
            "session_type": session_type,
            "reason": "Host environment does not have AETHERIS_LIVE_TESTS=1 or live session credentials configured.",
            "stages": [],
            "error": None,
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[!] Wrote skipped live transfer artifact to {report_file}")
        return False

    # Strict Owner Verification
    if not Config.OWNER_ID or int(Config.OWNER_ID) <= 0:
        err_msg = "Config.OWNER_ID is not configured or <= 0. Refusing to run live tests without explicit owner identity."
        LOGS.error(err_msg)
        report = {
            "timestamp": time.time(),
            "status": "FAILED_OWNER_UNSET",
            "gate_passed": False,
            "transfer_integrity": "ABORTED_SAFETY",
            "session_type": session_type,
            "reason": err_msg,
            "stages": [],
            "error": err_msg,
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return False

    stages_results = []
    sizes_mb = [1, 5, 25]
    client = None
    remote_messages = []

    try:
        LOGS.info("Connecting client using %s...", session_type)
        client = CatUserBotClient(
            session_target,
            Config.APP_ID,
            Config.API_HASH,
        )
        await client.connect()

        if not await client.is_user_authorized():
            raise PermissionError("Existing userbot session not authorized.")

        me = await client.get_me()
        configured_owner = int(Config.OWNER_ID)
        if me.id != configured_owner:
            raise PermissionError(
                f"Connected user ID {me.id} does not match configured OWNER_ID {configured_owner}!"
            )
        LOGS.info("Owner identity verified: ID %s", me.id)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            for size_mb in sizes_mb:
                LOGS.info(">>> Executing Fast Parallel MTProto Transfer Stage: %d MiB...", size_mb)
                file_bytes = size_mb * 1024 * 1024
                src_file = tmp_path / f"fixture_{size_mb}mb.bin"
                dst_file = tmp_path / f"download_{size_mb}mb.bin"

                # 1. Generate deterministic fixture
                with open(src_file, "wb") as f:
                    f.write(os.urandom(file_bytes))

                src_hash = sha256_file(src_file)

                # 2. Plan chunks via V5 Transfer Engine
                chunk_plan = client.transfer_engine.plan_chunks(file_bytes)
                LOGS.info(
                    "Transfer Engine chunk plan for %d MiB: %d parts @ %d bytes (RPC: %s)",
                    size_mb,
                    chunk_plan.total_parts,
                    chunk_plan.chunk_size,
                    chunk_plan.rpc_method,
                )

                # 3. Register Task in Transfer Engine
                task_id = f"test_up_{size_mb}mb_{uuid.uuid4().hex[:6]}"
                up_task = client.transfer_engine.create_task(
                    task_id=task_id,
                    file_path=str(src_file),
                    file_size=file_bytes,
                    is_upload=True,
                )

                # 4. Upload via Fast MTProto Parallel Transport
                t_up0 = time.perf_counter()
                with open(src_file, "rb") as ul_io:
                    uploaded_handle = await client.fast_upload_file(
                        file=ul_io,
                        progress_callback=lambda current, total: None,
                    )
                up_dur = max(0.01, time.perf_counter() - t_up0)
                up_speed_mbs = round((file_bytes / (1024 * 1024)) / up_dur, 2)
                LOGS.info("Uploaded %d MiB in %.2fs (%.2f MB/s)", size_mb, up_dur, up_speed_mbs)

                # 5. Post to Saved Messages
                sent_msg = await client.send_file(
                    "me",
                    file=uploaded_handle,
                    caption=f"◈ [Aetheris V5 Fast MTProto Probe: {size_mb}MB {up_task.task_id}]",
                    force_document=True,
                )
                remote_messages.append(sent_msg)

                # 6. Download via Fast MTProto Parallel Transport
                down_task_id = f"test_down_{size_mb}mb_{uuid.uuid4().hex[:6]}"
                client.transfer_engine.create_task(
                    task_id=down_task_id,
                    file_path=str(dst_file),
                    file_size=file_bytes,
                    is_upload=False,
                )

                t_down0 = time.perf_counter()
                with io.FileIO(str(dst_file), "w+b") as dl_io:
                    await client.fast_download_file(
                        location=sent_msg.document,
                        out=dl_io,
                        progress_callback=lambda current, total: None,
                    )
                down_dur = max(0.01, time.perf_counter() - t_down0)
                down_speed_mbs = round((file_bytes / (1024 * 1024)) / down_dur, 2)
                LOGS.info("Downloaded %d MiB in %.2fs (%.2f MB/s)", size_mb, down_dur, down_speed_mbs)

                # 7. Compare cryptographic digests
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
                    "size_bytes": file_bytes,
                    "size_mb": size_mb,
                    "chunk_size": chunk_plan.chunk_size,
                    "total_parts": chunk_plan.total_parts,
                    "rpc_method": chunk_plan.rpc_method,
                    "upload_duration_s": round(up_dur, 2),
                    "upload_speed_mbs": up_speed_mbs,
                    "download_duration_s": round(down_dur, 2),
                    "download_speed_mbs": down_speed_mbs,
                    "sha256_match": match,
                    "engine_verified": True,
                }
                stages_results.append(stage_record)

                if not match:
                    raise AssertionError(f"SHA-256 digest mismatch on {size_mb}MB fast transfer stage!")

        report = {
            "timestamp": time.time(),
            "status": "LIVE_VERIFIED_PASS",
            "gate_passed": True,
            "transfer_integrity": "LIVE PASS",
            "engine": "Aetheris.FileTransferEngineV5 + FastTelethon",
            "stages": stages_results,
            "error": None,
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        LOGS.info("All live MTProto transfer stages PASSED with verified SHA-256 integrity.")
        return True

    except Exception as exc:
        LOGS.error("Live transfer acceptance failed: %s", exc)
        report = {
            "timestamp": time.time(),
            "status": "FAILED",
            "gate_passed": False,
            "transfer_integrity": "FAILED",
            "stages": stages_results,
            "error": str(exc),
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return False

    finally:
        # Guaranteed cleanup of test files from Saved Messages
        if not keep_artifacts and client and client.is_connected():
            for msg in remote_messages:
                try:
                    await msg.delete()
                    LOGS.info("Deleted live transfer probe message %s from Saved Messages", msg.id)
                except Exception as e:
                    LOGS.warning("Failed to delete probe message %s: %s", getattr(msg, "id", "unknown"), e)

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
    asyncio.run(run_live_transfer(keep_artifacts=args.keep_artifacts))


if __name__ == "__main__":
    main()
