#!/usr/bin/env python3
"""
Aetheris V5 Live MTProto Acceptance Verification Harness.
Strictly requires AETHERIS_LIVE_TESTS=1 and valid userbot credentials.
Executes safe, owner-isolated operations in Saved Messages:
1. Connect via existing deployed session
2. Verify owner identity
3. Send test message in Saved Messages
4. Edit test message
5. Fetch message
6. Delete test message
7. Perform read-only API request (GetConfigRequest)
8. Disconnect cleanly
9. Produce sanitized artifact: artifacts/live_mtproto_acceptance.json
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGS = logging.getLogger("Aetheris.LiveAcceptance")


async def run_live_acceptance():
    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_file = artifacts_dir / "live_mtproto_acceptance.json"

    is_live_enabled = os.environ.get("AETHERIS_LIVE_TESTS") == "1"

    # Preflight Check for Credentials
    from userbot.Config import Config

    has_credentials = bool(Config.APP_ID and Config.API_HASH and Config.STRING_SESSION)

    if not is_live_enabled or not has_credentials:
        LOGS.warning(
            "Live MTProto tests disabled or credentials absent (AETHERIS_LIVE_TESTS=%s, has_credentials=%s). "
            "Skipping live MTProto acceptance.",
            os.environ.get("AETHERIS_LIVE_TESTS"),
            has_credentials,
        )
        report = {
            "timestamp": time.time(),
            "status": "SKIPPED_CREDENTIALS_ABSENT",
            "gate_passed": False,
            "session_preservation": "NOT LIVE VERIFIED",
            "basic_mtproto": "NOT RUN",
            "reason": "Host environment does not have AETHERIS_LIVE_TESTS=1 or live STRING_SESSION/API_HASH configured.",
            "operations_executed": [],
            "error": None,
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[!] Wrote skipped live acceptance artifact to {report_file}")
        return False

    # Live execution when explicitly enabled with credentials
    from telethon import TelegramClient, functions
    from telethon.sessions import StringSession
    from userbot.core.client import CatUserBotClient

    operations = []
    t0 = time.perf_counter()

    try:
        client = CatUserBotClient(
            StringSession(Config.STRING_SESSION),
            Config.APP_ID,
            Config.API_HASH,
        )
        await client.connect()
        operations.append("connect_existing_session")

        if not await client.is_user_authorized():
            raise PermissionError("Existing session is not authorized or expired! Session preservation failed.")

        me = await client.get_me()
        owner_id = Config.OWNER_ID or me.id
        if me.id != owner_id:
            raise PermissionError(f"Connected user ID {me.id} does not match configured OWNER_ID {owner_id}!")
        operations.append("verify_owner_identity")

        # 1. Send test message in Saved Messages
        test_nonce = uuid.uuid4().hex[:8]
        msg_text = f"◈ [Aetheris V5 Live Acceptance Test Probe: {test_nonce}]"
        sent_msg = await client.send_message("me", msg_text)
        operations.append("send_saved_message")

        # 2. Edit test message
        edited_text = f"◈ [Aetheris V5 Live Acceptance Test Probe: {test_nonce} (EDITED)]"
        await sent_msg.edit(edited_text)
        operations.append("edit_saved_message")

        # 3. Fetch test message
        fetched = await client.get_messages("me", ids=sent_msg.id)
        assert fetched.text == edited_text
        operations.append("fetch_saved_message")

        # 4. Delete test message
        await fetched.delete()
        operations.append("delete_saved_message")

        # 5. Read-only API RPC call
        cfg = await client(functions.help.GetConfigRequest())
        assert cfg is not None
        operations.append("execute_get_config_rpc")

        await client.disconnect()
        operations.append("clean_disconnect")

        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        report = {
            "timestamp": time.time(),
            "status": "LIVE_VERIFIED_PASS",
            "gate_passed": True,
            "session_preservation": "LIVE PASS",
            "basic_mtproto": "PASS",
            "duration_ms": dur_ms,
            "operations_executed": operations,
            "error": None,
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        LOGS.info("Live MTProto acceptance test PASSED in %.2f ms", dur_ms)
        return True

    except Exception as exc:
        LOGS.error("Live MTProto acceptance failed: %s", exc)
        report = {
            "timestamp": time.time(),
            "status": "FAILED",
            "gate_passed": False,
            "session_preservation": "FAILED",
            "basic_mtproto": "FAILED",
            "operations_executed": operations,
            "error": str(exc),
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return False


if __name__ == "__main__":
    asyncio.run(run_live_acceptance())
