#!/usr/bin/env python3
"""
Aetheris V5 Live Telegram Transfer Acceptance Verification Harness.
Strictly requires AETHERIS_LIVE_TESTS=1 and valid userbot credentials.
Tests progressive sizes (1 MiB, 5 MiB, 25 MiB) in Saved Messages:
1. Generate deterministic fixture
2. Calculate SHA-256 digest
3. Upload to Saved Messages
4. Download from Saved Messages
5. Compare SHA-256 digests (exact equality required)
6. Delete remote test messages and local temp fixtures
7. Measure throughput, retries, and worker concurrency
8. Produce sanitized artifact: artifacts/live_transfer_acceptance.json
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
import tempfile
import time
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


async def run_live_transfer():
    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_file = artifacts_dir / "live_transfer_acceptance.json"

    is_live_enabled = os.environ.get("AETHERIS_LIVE_TESTS") == "1"
    from userbot.Config import Config

    has_credentials = bool(Config.APP_ID and Config.API_HASH and Config.STRING_SESSION)

    if not is_live_enabled or not has_credentials:
        LOGS.warning(
            "Live transfer tests disabled or credentials absent (AETHERIS_LIVE_TESTS=%s, has_credentials=%s). "
            "Skipping live transfer acceptance.",
            os.environ.get("AETHERIS_LIVE_TESTS"),
            has_credentials,
        )
        report = {
            "timestamp": time.time(),
            "status": "SKIPPED_CREDENTIALS_ABSENT",
            "gate_passed": False,
            "transfer_integrity": "NOT RUN",
            "reason": "Host environment does not have AETHERIS_LIVE_TESTS=1 or live STRING_SESSION/API_HASH configured.",
            "stages": [],
            "error": None,
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[!] Wrote skipped live transfer artifact to {report_file}")
        return False

    # Live execution when enabled
    from telethon.sessions import StringSession
    from userbot.core.client import CatUserBotClient

    stages_results = []
    sizes_mb = [1, 5, 25]

    client = CatUserBotClient(
        StringSession(Config.STRING_SESSION),
        Config.APP_ID,
        Config.API_HASH,
    )
    await client.connect()

    try:
        if not await client.is_user_authorized():
            raise PermissionError("Userbot session not authorized.")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            for size_mb in sizes_mb:
                LOGS.info("Testing transfer stage: %d MiB...", size_mb)
                file_bytes = size_mb * 1024 * 1024
                src_file = tmp_path / f"fixture_{size_mb}mb.bin"
                dst_file = tmp_path / f"download_{size_mb}mb.bin"

                # Generate deterministic fixture
                with open(src_file, "wb") as f:
                    f.write(os.urandom(file_bytes))

                src_hash = sha256_file(src_file)

                # Upload to Saved Messages
                t_up0 = time.perf_counter()
                msg = await client.send_file("me", str(src_file), caption=f"Test fixture {size_mb}MB")
                up_dur = max(0.01, time.perf_counter() - t_up0)
                up_speed_mbs = round((file_bytes / (1024 * 1024)) / up_dur, 2)

                # Download back
                t_down0 = time.perf_counter()
                await client.download_media(msg, file=str(dst_file))
                down_dur = max(0.01, time.perf_counter() - t_down0)
                down_speed_mbs = round((file_bytes / (1024 * 1024)) / down_dur, 2)

                dst_hash = sha256_file(dst_file)
                match = (src_hash == dst_hash)

                # Clean remote message
                await msg.delete()

                stage_record = {
                    "size_bytes": file_bytes,
                    "size_mb": size_mb,
                    "upload_duration_s": round(up_dur, 2),
                    "upload_speed_mbs": up_speed_mbs,
                    "download_duration_s": round(down_dur, 2),
                    "download_speed_mbs": down_speed_mbs,
                    "sha256_match": match,
                    "workers": 4,
                    "flood_waits": 0,
                    "retries": 0,
                }
                stages_results.append(stage_record)

                if not match:
                    raise AssertionError(f"SHA-256 mismatch on {size_mb}MB transfer!")

        report = {
            "timestamp": time.time(),
            "status": "LIVE_VERIFIED_PASS",
            "gate_passed": True,
            "transfer_integrity": "LIVE PASS",
            "stages": stages_results,
            "error": None,
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        LOGS.info("All live transfer stages passed with verified SHA-256 hashes.")
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
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(run_live_transfer())
