#!/usr/bin/env python3
"""
Aetheris V5 Live MTProto Acceptance Verification Harness.
Strictly requires AETHERIS_LIVE_TESTS=1 and valid userbot credentials.

Safe, Owner-Isolated Verification in Saved Messages ("me"):
1. Connect via existing deployed session (supports SQLite .session files or STRING_SESSION)
2. Verify owner identity strictly against Config.OWNER_ID (> 0 and me.id == Config.OWNER_ID)
3. Detect existing authorization without creating new sessions (produces artifacts/session_preservation.json)
4. Send isolated test probe in Saved Messages with unique nonce marker
5. Edit probe message and verify Telegram update delivery
6. Read-only API RPC call (GetConfigRequest)
7. Guaranteed try...finally cleanup of remote probe messages
8. Disconnect cleanly without revoking session
9. Produces sanitized artifacts:
   - artifacts/session_preservation.json
   - artifacts/live_mtproto_acceptance.json
"""

import argparse
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

from scripts.artifact_utils import get_standard_metadata

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGS = logging.getLogger("Aetheris.LiveAcceptance")


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


async def run_live_acceptance(keep_artifacts: bool = False):
    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_file = artifacts_dir / "live_mtproto_acceptance.json"
    session_file = artifacts_dir / "session_preservation.json"

    is_live_enabled = os.environ.get("AETHERIS_LIVE_TESTS") == "1"

    from userbot.Config import Config
    from userbot.core.client import CatUserBotClient

    session_target, session_source = resolve_session(Config)
    has_api_creds = bool(Config.APP_ID and Config.API_HASH)
    has_credentials = bool(has_api_creds and session_target is not None)

    if not is_live_enabled or not has_credentials:
        LOGS.warning(
            "Live MTProto tests disabled or credentials absent (AETHERIS_LIVE_TESTS=%s, has_api_creds=%s, session_source=%s). "
            "Skipping live MTProto acceptance.",
            os.environ.get("AETHERIS_LIVE_TESTS"),
            has_api_creds,
            session_source,
        )
        report = get_standard_metadata("live_mtproto_acceptance", "SKIPPED_CREDENTIALS_ABSENT")
        report.update({
            "gate_passed": False,
            "session_preservation": "NOT_RUN",
            "session_source": session_source,
            "basic_mtproto": "NOT_RUN",
            "failure_classification": "CONFIGURATION_ERROR",
            "reason": "Host environment does not have AETHERIS_LIVE_TESTS=1 or live session credentials configured.",
            "operations_executed": [],
            "error": None,
        })
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        sess_report = get_standard_metadata("session_preservation", "SKIPPED_CREDENTIALS_ABSENT")
        sess_report.update({
            "existing_session_detected": (session_source != "none"),
            "session_source": session_source,
            "otp_required": False,
            "qr_login_required": False,
            "fresh_authorization_created": False,
            "owner_identity_verified": False,
            "gate_passed": False,
            "failure_classification": "CONFIGURATION_ERROR",
            "reason": "Credentials absent in environment",
        })
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(sess_report, f, indent=2)

        print(f"[!] Wrote skipped artifacts to {report_file} and {session_file}")
        return True, "SKIPPED"

    # Owner ID Strict Verification
    if not Config.OWNER_ID or int(Config.OWNER_ID) <= 0:
        err_msg = "Config.OWNER_ID is not configured or <= 0. Refusing to run live tests without explicit owner identity."
        LOGS.error(err_msg)
        report = get_standard_metadata("live_mtproto_acceptance", "FAILED")
        report.update({
            "gate_passed": False,
            "session_preservation": "ABORTED_SAFETY",
            "basic_mtproto": "NOT_RUN",
            "failure_classification": "OWNER_MISMATCH",
            "reason": err_msg,
            "operations_executed": [],
            "error": err_msg,
        })
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return False

    from telethon import functions

    operations = []
    t0 = time.perf_counter()
    sent_msg = None
    client = None
    cleanup_success = True

    try:
        LOGS.info("Connecting client using %s...", session_source)
        try:
            client = CatUserBotClient(
                session_target,
                Config.APP_ID,
                Config.API_HASH,
            )
            await client.connect()
            operations.append("connect_existing_session")
        except Exception as e:
            raise RuntimeError(f"MTPROTO_CONNECTION_ERROR: {e}")

        # Check authorization without creating fresh login
        is_auth = await client.is_user_authorized()
        if not is_auth:
            sess_report = get_standard_metadata("session_preservation", "FAILED")
            sess_report.update({
                "existing_session_detected": True,
                "session_source": session_source,
                "otp_required": True,
                "qr_login_required": True,
                "fresh_authorization_created": False,
                "owner_identity_verified": False,
                "gate_passed": False,
                "failure_classification": "SESSION_ERROR",
                "reason": "Existing session is expired or unauthorized; refusing to create fresh login.",
            })
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(sess_report, f, indent=2)
            raise PermissionError("SESSION_ERROR: Existing session is not authorized or expired! Session preservation failed.")

        # Verify Owner Identity
        me = await client.get_me()
        configured_owner = int(Config.OWNER_ID)
        if me.id != configured_owner:
            raise PermissionError(
                f"OWNER_MISMATCH: Connected user ID {me.id} does not match configured OWNER_ID {configured_owner}!"
            )
        operations.append("verify_owner_identity")
        LOGS.info("Owner identity verified: ID %s", me.id)

        # Record verified session preservation
        sess_report = get_standard_metadata("session_preservation", "PASS")
        sess_report.update({
            "existing_session_detected": True,
            "session_source": session_source,
            "otp_required": False,
            "qr_login_required": False,
            "fresh_authorization_created": False,
            "owner_identity_verified": True,
            "gate_passed": True,
            "failure_classification": None,
        })
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(sess_report, f, indent=2)

        # 1. Send test message in Saved Messages
        test_nonce = uuid.uuid4().hex[:12]
        msg_text = f"◈ [Aetheris V5 Live MTProto Probe: {test_nonce}]"
        try:
            sent_msg = await client.send_message("me", msg_text)
            operations.append("send_saved_message")
        except Exception as e:
            raise RuntimeError(f"SEND_FAILED: {e}")

        # 2. Edit test message
        edited_text = f"◈ [Aetheris V5 Live MTProto Probe: {test_nonce} (EDITED)]"
        try:
            await sent_msg.edit(edited_text)
            operations.append("edit_saved_message")
        except Exception as e:
            raise RuntimeError(f"EDIT_FAILED: {e}")

        # 3. Fetch test message
        try:
            fetched = await client.get_messages("me", ids=sent_msg.id)
            assert fetched is not None, "Failed to retrieve test message"
            assert fetched.text == edited_text, "Edited message text mismatch"
            operations.append("fetch_saved_message")
        except Exception as e:
            raise RuntimeError(f"EDIT_FAILED: Message fetch/verification failed: {e}")

        # 4. Read-only API RPC call
        try:
            cfg = await client(functions.help.GetConfigRequest())
            assert cfg is not None, "GetConfigRequest returned None"
            operations.append("execute_get_config_rpc")
        except Exception as e:
            raise RuntimeError(f"RPC_FAILED: {e}")

        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        report = get_standard_metadata("live_mtproto_acceptance", "PASS")
        report.update({
            "status": "PASS",
            "gate_passed": True,
            "session_preservation": "PASS",
            "session_source": session_source,
            "owner_identity_verified": True,
            "basic_mtproto": "PASS",
            "duration_ms": dur_ms,
            "operations_executed": operations,
            "failure_classification": None,
            "error": None,
        })
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        LOGS.info("Live MTProto acceptance test PASSED in %.2f ms", dur_ms)
        return True, "PASS"

    except Exception as exc:
        err_str = str(exc)
        fail_class = "MTPROTO_CONNECTION_ERROR"
        for candidate in ["CONFIGURATION_ERROR", "OWNER_MISMATCH", "SESSION_ERROR", "SEND_FAILED", "EDIT_FAILED", "DELETE_FAILED", "RPC_FAILED"]:
            if candidate in err_str:
                fail_class = candidate
                break

        LOGS.error("Live MTProto acceptance failed (%s): %s", fail_class, exc)
        report = get_standard_metadata("live_mtproto_acceptance", "FAILED")
        report.update({
            "status": "FAILED",
            "gate_passed": False,
            "session_preservation": "FAILED",
            "session_source": session_source,
            "basic_mtproto": "FAILED",
            "failure_classification": fail_class,
            "operations_executed": operations,
            "error": err_str,
        })
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return False, fail_class

    finally:
        # Guaranteed cleanup of test probe message
        if sent_msg and not keep_artifacts and client and client.is_connected():
            try:
                await sent_msg.delete()
                operations.append("cleanup_saved_message")
                LOGS.info("Cleaned up live test probe message from Saved Messages")
            except Exception as e:
                cleanup_success = False
                LOGS.warning("Failed to delete test probe message: %s", e)

        # Disconnect cleanly without revoking session
        if client and client.is_connected():
            try:
                await client.disconnect()
                operations.append("clean_disconnect")
            except Exception as e:
                LOGS.warning("Error during clean disconnect: %s", e)


def main():
    parser = argparse.ArgumentParser(description="Aetheris V5 Live MTProto Acceptance Harness")
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Do not delete probe messages from Saved Messages",
    )
    args = parser.parse_args()
    success, res_type = asyncio.run(run_live_acceptance(keep_artifacts=args.keep_artifacts))
    sys.exit(0 if (success or res_type == "SKIPPED") else 1)


if __name__ == "__main__":
    main()
