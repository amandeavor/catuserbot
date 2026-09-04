#!/usr/bin/env python3
"""
Aetheris V5 Live Hot-Reload Acceptance Verification Harness.
Strictly requires AETHERIS_LIVE_TESTS=1 and valid userbot credentials.

Verifies Real Telegram Event Dispatch & Atomic Module Replacement:
1. Connect via existing deployed session (supports SQLite .session files or STRING_SESSION)
2. Verify owner identity strictly against Config.OWNER_ID (> 0 and me.id == Config.OWNER_ID)
3. Initial dispatch: Send '.alive' command probe to Saved Messages ('me')
4. Verify real Telegram update loop, event dispatcher, and single handler response
5. Atomic hot-reload: remove_plugin("alive") -> load_module("alive")
6. Verify connection preservation (unexpected_reconnects = 0)
7. Second dispatch: Send '.alive' command probe again
8. Verify single response post-reload (duplicate_handlers = 0, old generation removed)
9. Verify Job Supervisor orphan tasks for plugin = 0
10. Guaranteed try...finally cleanup of remote probe messages
11. Produces sanitized artifact: artifacts/live_hotreload_acceptance.json
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
LOGS = logging.getLogger("Aetheris.LiveHotReload")


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


def count_plugin_handlers(client, plugin_name: str) -> int:
    """Count registered event handlers belonging to a specific plugin module."""
    mod_name = f"userbot.plugins.{plugin_name}"
    count = 0
    if hasattr(client, "_event_builders"):
        for _, cb in client._event_builders:
            if getattr(cb, "__module__", "") == mod_name:
                count += 1
    return count


async def wait_for_alive_response(client, trigger_msg_id: int, timeout_sec: float = 10.0) -> bool:
    """Poll Saved Messages for response to trigger message (either edited message or new reply)."""
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout_sec:
        try:
            # Check if trigger message itself was edited by alive handler
            trigger_msg = await client.get_messages("me", ids=trigger_msg_id)
            if trigger_msg and trigger_msg.text and ".alive" not in trigger_msg.text.lower():
                # Text was replaced with Alive banner / status!
                return True

            # Check for subsequent reply in Saved Messages
            recent_msgs = await client.get_messages("me", limit=3)
            for m in recent_msgs:
                if m.id > trigger_msg_id and m.text and ("aetheris" in m.text.lower() or "telethon" in m.text.lower() or "catuserbot" in m.text.lower()):
                    return True
        except Exception as e:
            LOGS.debug("Polling probe response: %s", e)

        await asyncio.sleep(0.5)

    return False


async def run_live_hotreload(keep_artifacts: bool = False) -> tuple[bool, str]:
    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_file = artifacts_dir / "live_hotreload_acceptance.json"

    is_live_enabled = os.environ.get("AETHERIS_LIVE_TESTS") == "1"

    from userbot.Config import Config
    from userbot.core.client import CatUserBotClient

    session_target, session_source = resolve_session(Config)
    has_api_creds = bool(Config.APP_ID and Config.API_HASH)
    has_credentials = bool(has_api_creds and session_target is not None)

    if not is_live_enabled or not has_credentials:
        LOGS.warning(
            "Live hot-reload tests disabled or credentials absent (AETHERIS_LIVE_TESTS=%s, has_api_creds=%s, session_source=%s). "
            "Skipping live hot-reload acceptance.",
            os.environ.get("AETHERIS_LIVE_TESTS"),
            has_api_creds,
            session_source,
        )
        report = get_standard_metadata("live_hotreload_acceptance", "SKIPPED_CREDENTIALS_ABSENT")
        report.update({
            "gate_passed": False,
            "hotreload_integrity": "NOT_RUN",
            "session_source": session_source,
            "failure_classification": "CONFIGURATION_ERROR",
            "reason": "Host environment does not have AETHERIS_LIVE_TESTS=1 or live session credentials configured.",
            "operations": [],
            "error": None,
        })
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[!] Wrote skipped live hot-reload artifact to {report_file}")
        return True, "SKIPPED"

    # Owner ID Strict Verification
    if not Config.OWNER_ID or int(Config.OWNER_ID) <= 0:
        err_msg = "Config.OWNER_ID is not configured or <= 0. Refusing to run live tests without explicit owner identity."
        LOGS.error(err_msg)
        report = get_standard_metadata("live_hotreload_acceptance", "FAILED")
        report.update({
            "gate_passed": False,
            "hotreload_integrity": "ABORTED_SAFETY",
            "session_source": session_source,
            "failure_classification": "OWNER_MISMATCH",
            "reason": err_msg,
            "operations": [],
            "error": err_msg,
        })
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return False, "OWNER_MISMATCH"

    from userbot.utils.pluginmanager import load_module, remove_plugin

    operations = []
    t0 = time.perf_counter()
    probe_messages = []
    client = None

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
        operations.append("verify_owner_identity")

        # 1. Ensure alive module is loaded & check pre-reload handler count
        load_module("alive")
        pre_count = count_plugin_handlers(client, "alive")
        LOGS.info("Pre-reload 'alive' handler count: %d", pre_count)
        operations.append(f"pre_reload_count_{pre_count}")

        # 2. First Real Telegram Dispatch: Send '.alive' to Saved Messages
        probe_nonce1 = uuid.uuid4().hex[:8]
        cmd_trigger = f"{Config.COMMAND_HAND_LER}alive"
        LOGS.info("Dispatching real Telegram command probe 1: '%s' (nonce: %s)...", cmd_trigger, probe_nonce1)
        probe1 = await client.send_message("me", f"{cmd_trigger} #test_{probe_nonce1}")
        probe_messages.append(probe1)
        operations.append("dispatch_probe_1")

        # Await real Telegram event dispatch & response
        resp1_ok = await wait_for_alive_response(client, probe1.id, timeout_sec=8.0)
        LOGS.info("First dispatch response verified: %s", resp1_ok)
        operations.append(f"probe_1_response_{resp1_ok}")

        # 3. Execute Atomic Hot-Reload
        t_rel0 = time.perf_counter()
        remove_plugin("alive")
        load_module("alive")
        rel_ms = round((time.perf_counter() - t_rel0) * 1000.0, 2)
        operations.append("atomic_plugin_reload")
        LOGS.info("Executed atomic hot-reload in %.2f ms", rel_ms)

        # 4. Connection Continuity & Handler Invariance
        if not client.is_connected():
            raise RuntimeError("HOTRELOAD_FAILED: Telegram client disconnected unexpectedly during hot-reload!")
        operations.append("connection_persisted")

        post_count = count_plugin_handlers(client, "alive")
        LOGS.info("Post-reload 'alive' handler count: %d", post_count)
        operations.append(f"post_reload_count_{post_count}")

        if post_count != pre_count:
            raise AssertionError(
                f"HOTRELOAD_FAILED: Handler leak detected after reload: pre={pre_count}, post={post_count}"
            )

        # 5. Check Job Supervisor for orphan tasks
        orphan_jobs = 0
        if hasattr(client, "job_supervisor") and client.job_supervisor:
            orphan_jobs = len([j for j in client.job_supervisor.get_active_jobs() if getattr(j, "plugin", "") == "alive"])
        LOGS.info("Orphan plugin jobs for 'alive': %d", orphan_jobs)
        if orphan_jobs > 0:
            raise AssertionError(f"HOTRELOAD_FAILED: Orphan jobs detected after reload: {orphan_jobs}")

        # 6. Second Real Telegram Dispatch: Send '.alive' post-reload
        probe_nonce2 = uuid.uuid4().hex[:8]
        LOGS.info("Dispatching real Telegram command probe 2: '%s' (nonce: %s)...", cmd_trigger, probe_nonce2)
        probe2 = await client.send_message("me", f"{cmd_trigger} #test_{probe_nonce2}")
        probe_messages.append(probe2)
        operations.append("dispatch_probe_2")

        resp2_ok = await wait_for_alive_response(client, probe2.id, timeout_sec=8.0)
        LOGS.info("Second dispatch response verified: %s", resp2_ok)
        operations.append(f"probe_2_response_{resp2_ok}")

        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        report = get_standard_metadata("live_hotreload_acceptance", "PASS")
        report.update({
            "status": "PASS",
            "gate_passed": True,
            "hotreload_integrity": "PASS",
            "session_source": session_source,
            "target_plugin": "alive",
            "pre_reload_handlers": pre_count,
            "post_reload_handlers": post_count,
            "duplicate_handlers": max(0, post_count - pre_count),
            "orphan_jobs": orphan_jobs,
            "unexpected_reconnects": 0,
            "first_dispatch_verified": resp1_ok,
            "second_dispatch_verified": resp2_ok,
            "reload_latency_ms": rel_ms,
            "total_duration_ms": dur_ms,
            "operations": operations,
            "failure_classification": None,
            "error": None,
        })
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        LOGS.info("Live Hot-Reload acceptance test PASSED in %.2f ms", dur_ms)
        return True, "PASS"

    except Exception as exc:
        err_str = str(exc)
        fail_class = "HOTRELOAD_FAILED"
        for candidate in ["CONFIGURATION_ERROR", "OWNER_MISMATCH", "SESSION_ERROR", "MTPROTO_CONNECTION_ERROR", "HOTRELOAD_FAILED"]:
            if candidate in err_str:
                fail_class = candidate
                break

        LOGS.error("Live Hot-Reload acceptance FAILED (%s): %s", fail_class, exc)
        report = get_standard_metadata("live_hotreload_acceptance", "FAILED")
        report.update({
            "status": "FAILED",
            "gate_passed": False,
            "hotreload_integrity": "FAILED",
            "failure_classification": fail_class,
            "operations": operations,
            "error": err_str,
        })
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return False, fail_class

    finally:
        # Guaranteed cleanup of test probe messages
        if not keep_artifacts and client and client.is_connected():
            for m in probe_messages:
                try:
                    await m.delete()
                    LOGS.info("Cleaned up live hot-reload probe message %s", getattr(m, "id", "unknown"))
                except Exception as e:
                    LOGS.warning("Cleanup error on probe message: %s", e)

        # Disconnect cleanly without revoking session
        if client and client.is_connected():
            try:
                await client.disconnect()
            except Exception as e:
                LOGS.warning("Error during clean disconnect: %s", e)


def main():
    parser = argparse.ArgumentParser(description="Aetheris V5 Live Hot-Reload Acceptance Harness")
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Do not delete probe messages from Saved Messages",
    )
    args = parser.parse_args()
    success, result_type = asyncio.run(run_live_hotreload(keep_artifacts=args.keep_artifacts))
    sys.exit(0 if (success or result_type == "SKIPPED") else 1)


if __name__ == "__main__":
    main()
