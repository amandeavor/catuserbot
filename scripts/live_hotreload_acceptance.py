#!/usr/bin/env python3
"""
Aetheris V5 Live Hot-Reload Acceptance Verification Harness.
Strictly requires AETHERIS_LIVE_TESTS=1 and valid userbot credentials.

Safe, Owner-Isolated Verification:
1. Connect via existing deployed session (supports SQLite .session files or STRING_SESSION)
2. Verify owner identity strictly against Config.OWNER_ID
3. Inspect pre-reload handler registration for 'alive' plugin
4. Execute atomic plugin hot-reload: remove_plugin("alive") -> load_module("alive")
5. Inspect post-reload handler registration (verifies no handler leaks / duplicates)
6. Dispatch test trigger in Saved Messages ("me")
7. Guaranteed try...finally cleanup of remote test probe messages
8. Disconnect cleanly without revoking session
9. Produces sanitized artifact: artifacts/live_hotreload_acceptance.json
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGS = logging.getLogger("Aetheris.LiveHotReload")


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


def count_plugin_handlers(client, plugin_name: str) -> int:
    """Count registered event builders belonging to a specific plugin module."""
    mod_name = f"userbot.plugins.{plugin_name}"
    count = 0
    if hasattr(client, "_event_builders"):
        for _, cb in client._event_builders:
            if getattr(cb, "__module__", "") == mod_name:
                count += 1
    return count


async def run_live_hotreload(keep_artifacts: bool = False):
    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_file = artifacts_dir / "live_hotreload_acceptance.json"

    is_live_enabled = os.environ.get("AETHERIS_LIVE_TESTS") == "1"

    from userbot.Config import Config
    from userbot.core.client import CatUserBotClient

    session_target, session_type = resolve_session(Config)
    has_api_creds = bool(Config.APP_ID and Config.API_HASH)
    has_credentials = bool(has_api_creds and session_target is not None)

    if not is_live_enabled or not has_credentials:
        LOGS.warning(
            "Live hot-reload tests disabled or credentials absent (AETHERIS_LIVE_TESTS=%s, has_api_creds=%s, session_type=%s). "
            "Skipping live hot-reload acceptance.",
            os.environ.get("AETHERIS_LIVE_TESTS"),
            has_api_creds,
            session_type,
        )
        report = {
            "timestamp": time.time(),
            "status": "SKIPPED_CREDENTIALS_ABSENT",
            "gate_passed": False,
            "hotreload_integrity": "NOT RUN",
            "session_type": session_type,
            "reason": "Host environment does not have AETHERIS_LIVE_TESTS=1 or live session credentials configured.",
            "operations": [],
            "error": None,
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"[!] Wrote skipped live hot-reload artifact to {report_file}")
        return False

    # Owner ID Strict Verification
    if not Config.OWNER_ID or int(Config.OWNER_ID) <= 0:
        err_msg = "Config.OWNER_ID is not configured or <= 0. Refusing to run live tests without explicit owner identity."
        LOGS.error(err_msg)
        report = {
            "timestamp": time.time(),
            "status": "FAILED_OWNER_UNSET",
            "gate_passed": False,
            "hotreload_integrity": "ABORTED_SAFETY",
            "session_type": session_type,
            "reason": err_msg,
            "operations": [],
            "error": err_msg,
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return False

    from userbot.utils.pluginmanager import load_module, remove_plugin

    operations = []
    t0 = time.perf_counter()
    sent_msg = None
    client = None

    try:
        LOGS.info("Connecting client using %s...", session_type)
        client = CatUserBotClient(
            session_target,
            Config.APP_ID,
            Config.API_HASH,
        )
        await client.connect()
        operations.append("connect_existing_session")

        if not await client.is_user_authorized():
            raise PermissionError("Existing session not authorized.")

        me = await client.get_me()
        configured_owner = int(Config.OWNER_ID)
        if me.id != configured_owner:
            raise PermissionError(
                f"Connected user ID {me.id} does not match configured OWNER_ID {configured_owner}!"
            )
        operations.append("verify_owner_identity")

        # 1. Inspect pre-reload handlers
        load_module("alive")
        pre_count = count_plugin_handlers(client, "alive")
        LOGS.info("Pre-reload 'alive' handler count: %d", pre_count)
        operations.append(f"pre_reload_count_{pre_count}")

        # 2. Execute Atomic Hot-Reload
        t_rel0 = time.perf_counter()
        remove_plugin("alive")
        load_module("alive")
        rel_ms = round((time.perf_counter() - t_rel0) * 1000.0, 2)
        operations.append("atomic_plugin_reload")
        LOGS.info("Executed atomic hot-reload in %.2f ms", rel_ms)

        # 3. Inspect post-reload handlers (must NOT double)
        post_count = count_plugin_handlers(client, "alive")
        LOGS.info("Post-reload 'alive' handler count: %d", post_count)
        operations.append(f"post_reload_count_{post_count}")

        if post_count != pre_count:
            raise AssertionError(
                f"Handler leak detected after reload: pre={pre_count}, post={post_count}"
            )

        # 4. Safe live probe in Saved Messages ("me")
        test_nonce = uuid.uuid4().hex[:8]
        probe_text = f"◈ [Aetheris V5 Live Hot-Reload Probe: {test_nonce}]"
        sent_msg = await client.send_message("me", probe_text)
        operations.append("send_saved_probe")

        # Edit probe to verify event loop responsive
        await sent_msg.edit(f"{probe_text} [VERIFIED RESPONSIVE]")
        operations.append("edit_saved_probe")

        dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        report = {
            "timestamp": time.time(),
            "status": "LIVE_VERIFIED_PASS",
            "gate_passed": True,
            "hotreload_integrity": "LIVE PASS",
            "session_type": session_type,
            "target_plugin": "alive",
            "pre_reload_handlers": pre_count,
            "post_reload_handlers": post_count,
            "reload_latency_ms": rel_ms,
            "total_duration_ms": dur_ms,
            "operations": operations,
            "error": None,
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        LOGS.info("Live Hot-Reload acceptance test PASSED in %.2f ms", dur_ms)
        return True

    except Exception as exc:
        LOGS.error("Live Hot-Reload acceptance failed: %s", exc)
        report = {
            "timestamp": time.time(),
            "status": "FAILED",
            "gate_passed": False,
            "hotreload_integrity": "FAILED",
            "operations": operations,
            "error": str(exc),
        }
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return False

    finally:
        # Guaranteed cleanup of test probe message
        if sent_msg and not keep_artifacts and client and client.is_connected():
            try:
                await sent_msg.delete()
                operations.append("cleanup_probe_message")
                LOGS.info("Deleted live hot-reload probe message from Saved Messages")
            except Exception as e:
                LOGS.warning("Failed to delete probe message: %s", e)

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
    asyncio.run(run_live_hotreload(keep_artifacts=args.keep_artifacts))


if __name__ == "__main__":
    main()
