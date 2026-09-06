# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import time
from unittest.mock import AsyncMock, patch
import pytest

from userbot.Config import Config
from userbot.core import CMD_INFO, GRP_INFO, PLG_INFO
from userbot.core.callbacks import SecureCallbackManager, secure_callbacks
from userbot.core.inline_menu import (
    acquire_message_revision,
    build_categories_menu,
    build_category_plugins_menu,
    build_command_details_menu,
    build_home_menu,
    build_plugin_commands_menu,
    build_settings_menu,
    build_sysinfo_menu,
    build_task_cancel_confirmation_menu,
    build_tasks_menu,
    get_command_permission,
    handle_menu_categories,
    handle_menu_category,
    handle_menu_close,
    handle_menu_command,
    handle_menu_home,
    handle_menu_plugin,
    handle_menu_settings,
    handle_menu_sysinfo,
    handle_menu_tasks,
    handle_setting_cycle_rows,
    handle_setting_toggle,
    handle_task_confirm_cancel,
    handle_task_prompt_cancel,
    is_latest_message_revision,
    register_inline_menu_handlers,
    safe_edit,
)
from userbot.core.inlinebot import inline_search, youtube_data_article
from userbot.core.tasks import task_manager
from userbot.sql_helper.globals import addgvar, delgvar, gvarstatus
from telethon.errors import MessageIdInvalidError, MessageNotModifiedError


@pytest.fixture(autouse=True)
def setup_test_metadata():
    """Seed test command metadata for deterministic menu testing."""
    Config.COMMAND_HAND_LER = "."
    Config.OWNER_ID = 111222333
    Config.SUDO_USERS = {444555666}

    GRP_INFO["tools"] = ["alive", "ping", "testmod"]
    PLG_INFO["testmod"] = ["testcmd", "democmd"]
    CMD_INFO["testcmd"] = [
        "**Test Command Header**\n\n✘ **Description :**\n__A test command for verification.__\n\n✘ **Usage :**\n`{tr}testcmd [arg]`",
        "A test command for verification.",
    ]
    CMD_INFO["democmd"] = [
        "**Demo Command Header**\n\n✘ **Description :**\n__Demo utility command.__\n\n✘ **Usage :**\n`{tr}democmd`",
        "Demo utility command.",
    ]


# ---------------------------------------------------------------------------
# Test 1: Home Menu Structure & Tokens
# ---------------------------------------------------------------------------

def test_home_menu_structure_and_tokens():
    text, buttons = build_home_menu(sender_id=111222333)

    assert "AETHERIS CONTROL" in text
    assert "Operational" in text
    assert "Prefix:" in text
    assert "111222333" in text

    # Verify buttons layout
    assert len(buttons) >= 3
    all_buttons = [b for row in buttons for b in row]
    btn_texts = [b.text for b in all_buttons]

    assert any("Commands" in t for t in btn_texts)
    assert any("Settings" in t for t in btn_texts)
    assert any("Tasks" in t for t in btn_texts)
    assert any("Quick Search" in t for t in btn_texts)
    assert any("System Info" in t for t in btn_texts)
    assert any("Close" in t for t in btn_texts)

    # Check that inline callback_data adheres to Telegram <= 64 byte limit
    for b in all_buttons:
        if getattr(b, "data", None):
            data_bytes = b.data if isinstance(b.data, bytes) else b.data.encode("utf-8")
            assert len(data_bytes) <= 64
            assert data_bytes.startswith(b"cb:")


# ---------------------------------------------------------------------------
# Test 2: Categories Menu Overview
# ---------------------------------------------------------------------------

def test_categories_menu():
    text, buttons = build_categories_menu(sender_id=111222333)

    assert "COMMAND CATEGORIES" in text
    all_buttons = [b for row in buttons for b in row]
    btn_texts = [b.text for b in all_buttons]

    # Standard categories should be represented
    assert any("Tools" in t for t in btn_texts)
    assert any("Home" in t for t in btn_texts)


# ---------------------------------------------------------------------------
# Test 3: Category Plugins Pagination & Boundaries
# ---------------------------------------------------------------------------

def test_category_plugins_pagination_and_boundaries():
    # Normal page
    text_p0, buttons_p0 = build_category_plugins_menu("tools", page=0, sender_id=111222333)
    assert "CATEGORY:" in text_p0
    assert "Page 1 of 1" in text_p0
    all_b0 = [b for row in buttons_p0 for b in row]
    b0_texts = [b.text for b in all_b0]
    assert any("testmod" in t for t in b0_texts)

    # Boundary test: negative page clamped to 0
    text_neg, _ = build_category_plugins_menu("tools", page=-99, sender_id=111222333)
    assert "Page 1" in text_neg

    # Boundary test: overflow page clamped to max
    text_overflow, _ = build_category_plugins_menu("tools", page=9999, sender_id=111222333)
    assert "Page 1 of 1" in text_overflow


# ---------------------------------------------------------------------------
# Test 4: Plugin Commands Browser & Command Details
# ---------------------------------------------------------------------------

def test_plugin_commands_and_command_details():
    # 1. Plugin commands list
    text_cmds, buttons_cmds = build_plugin_commands_menu("testmod", "tools", cat_page=0, page=0, sender_id=111222333)
    assert "PLUGIN: `TESTMOD`" in text_cmds
    assert "Commands: `2`" in text_cmds
    all_cmds_b = [b for row in buttons_cmds for b in row]
    cmd_texts = [b.text for b in all_cmds_b]
    assert ".testcmd" in cmd_texts
    assert ".democmd" in cmd_texts

    # 2. Command details view
    text_det, buttons_det = build_command_details_menu("testcmd", "testmod", "tools", cat_page=0, plg_page=0, sender_id=111222333)
    assert "COMMAND: `.testcmd`" in text_det
    assert "**Plugin:** `testmod`" in text_det
    assert "A test command for verification." in text_det
    assert "`.testcmd [arg]`" in text_det

    det_buttons = [b for row in buttons_det for b in row]
    det_btn_texts = [b.text for b in det_buttons]
    assert any("Back to testmod" in t for t in det_btn_texts)
    assert any("Categories" in t for t in det_btn_texts)
    assert any("Home" in t for t in det_btn_texts)


# ---------------------------------------------------------------------------
# Test 5: Settings Dashboard & Toggles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_settings_menu_and_toggles():
    # Ensure clean starting state
    delgvar("ALLOW_NSFW")
    delgvar("SPOILER_MEDIA")
    delgvar("pmpermit")
    delgvar("bot_antif")
    delgvar("NO_OF_ROWS_IN_HELP")

    text, buttons = build_settings_menu(sender_id=111222333)
    assert "SYSTEM SETTINGS" in text
    assert "ALLOW_NSFW" in text
    assert "PM_GUARD" in text

    # Toggle ALLOW_NSFW on
    mock_event = AsyncMock()
    mock_token = AsyncMock()
    mock_token.payload = {"key": "ALLOW_NSFW", "current": False, "sender_id": 111222333}

    await handle_setting_toggle(mock_event, mock_token)
    assert gvarstatus("ALLOW_NSFW") == "True"
    mock_event.answer.assert_called_with("✅ Set ALLOW_NSFW to True", alert=False)

    # Toggle ALLOW_NSFW off
    mock_token.payload = {"key": "ALLOW_NSFW", "current": True, "sender_id": 111222333}
    await handle_setting_toggle(mock_event, mock_token)
    assert gvarstatus("ALLOW_NSFW") is None
    mock_event.answer.assert_called_with("✅ Set ALLOW_NSFW to False", alert=False)

    # Toggle pmpermit on
    mock_token.payload = {"key": "pmpermit", "current": False, "sender_id": 111222333}
    await handle_setting_toggle(mock_event, mock_token)
    assert gvarstatus("pmpermit") == "true"
    mock_event.answer.assert_called_with("✅ Enabled PM Guard (PMPERMIT)", alert=False)

    # Toggle pmpermit off
    mock_token.payload = {"key": "pmpermit", "current": True, "sender_id": 111222333}
    await handle_setting_toggle(mock_event, mock_token)
    assert gvarstatus("pmpermit") is None
    mock_event.answer.assert_called_with("✅ Disabled PM Guard (PMPERMIT)", alert=False)

    # Test cycling help rows (5 -> 7 -> 10 -> 5)
    mock_token.payload = {"current": 5, "sender_id": 111222333}
    await handle_setting_cycle_rows(mock_event, mock_token)
    assert gvarstatus("NO_OF_ROWS_IN_HELP") == "7"

    mock_token.payload = {"current": 7, "sender_id": 111222333}
    await handle_setting_cycle_rows(mock_event, mock_token)
    assert gvarstatus("NO_OF_ROWS_IN_HELP") == "10"


# ---------------------------------------------------------------------------
# Test 6: Task Controls & Safe Two-Step Confirmation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_task_controls_and_cancellation():
    # 1. Empty state
    text_empty, buttons_empty = build_tasks_menu(sender_id=111222333)
    assert "No background async tasks" in text_empty

    # 2. Add an active async task
    async def infinite_mock_task():
        while True:
            await asyncio.sleep(1)

    t = task_manager.add_task("test_mock_task", infinite_mock_task(), description="Mock runner")
    try:
        text_active, buttons_active = build_tasks_menu(sender_id=111222333)
        assert f"Task `#{t.id}`" in text_active
        assert "Runtime:" in text_active

        all_b = [b for row in buttons_active for b in row]
        assert any(f"Cancel Task #{t.id}" in b.text for b in all_b)

        # 3. Step 1: Prompt cancel (shows confirmation prompt)
        mock_event = AsyncMock()
        mock_token = AsyncMock()
        mock_token.payload = {
            "source": "tm",
            "task_id": t.id,
            "name": t.name,
            "duration": 5.0,
            "sender_id": 111222333,
        }
        await handle_task_prompt_cancel(mock_event, mock_token)
        # Verify safe_edit was called with confirmation text
        edit_args = mock_event.edit.call_args[0]
        assert "CONFIRM TASK TERMINATION" in edit_args[0]

        # 4. Step 2: Confirm cancel
        confirm_token = AsyncMock()
        confirm_token.payload = {
            "source": "tm",
            "target_id": t.id,
            "name": t.name,
            "sender_id": 111222333,
        }
        await handle_task_confirm_cancel(mock_event, confirm_token)
        await asyncio.sleep(0.05)
        assert t.is_cancelled or t.is_done
        mock_event.answer.assert_called_with(f"🛑 Cancellation requested for AsyncTask #{t.id} ({t.name}).", alert=True)

    finally:
        task_manager.cancel_task(t.id)


# ---------------------------------------------------------------------------
# Test 7: Unauthorized Callback Rejection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthorized_callback_rejection():
    mgr = SecureCallbackManager()
    called = False

    async def protected_handler(event, token):
        nonlocal called
        called = True

    mgr.register_handler("test_action", protected_handler)
    tok = mgr.create_token("test_action", payload={}, allowed_user_ids={111222333})

    mock_event = AsyncMock()
    mock_event.data = tok.encode("utf-8")
    mock_event.sender_id = 999999999  # Unauthorized

    handled = await mgr.handle_callback_query(mock_event)
    assert handled is True
    assert called is False
    mock_event.answer.assert_called_with("⛔ Access Denied: You cannot trigger this action.", alert=True)


# ---------------------------------------------------------------------------
# Test 8: Expired or Stale Button Handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expired_callback_rejection():
    mgr = SecureCallbackManager()
    tok = mgr.create_token("test_action", payload={}, allowed_user_ids={111222333}, ttl=0.001)

    await asyncio.sleep(0.02)  # Force expiration

    mock_event = AsyncMock()
    mock_event.data = tok.encode("utf-8")
    mock_event.sender_id = 111222333

    handled = await mgr.handle_callback_query(mock_event)
    assert handled is True
    assert mock_event.answer.call_args[0][0] in {
        "⚠️ Session expired. Please re-run the command.",
        "⚠️ This button session has expired or is invalid.",
    }
    assert mock_event.answer.call_args[1].get("alert") is True


# ---------------------------------------------------------------------------
# Test 9: Repeated Taps Debouncing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_repeated_taps_debouncing():
    mgr = SecureCallbackManager()
    execution_count = 0
    barrier = asyncio.Event()

    async def slow_handler(event, token):
        nonlocal execution_count
        execution_count += 1
        await barrier.wait()

    mgr.register_handler("slow_action", slow_handler)
    tok = mgr.create_token("slow_action", payload={}, allowed_user_ids={111222333})

    mock_event1 = AsyncMock()
    mock_event1.data = tok.encode("utf-8")
    mock_event1.sender_id = 111222333

    mock_event2 = AsyncMock()
    mock_event2.data = tok.encode("utf-8")
    mock_event2.sender_id = 111222333

    # Start first invocation
    t1 = asyncio.create_task(mgr.handle_callback_query(mock_event1))
    await asyncio.sleep(0.01)

    # Attempt second simultaneous tap while t1 is in flight
    t2 = asyncio.create_task(mgr.handle_callback_query(mock_event2))
    await asyncio.sleep(0.01)

    # Release barrier
    barrier.set()
    await t1
    await t2

    # Handler should execute only once, second tap gets debounced toast
    assert execution_count == 1
    mock_event2.answer.assert_called_with("⏳ Processing... please wait.", alert=False)


# ---------------------------------------------------------------------------
# Test 10: Safe Message Edit Resilience
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_safe_edit_resilience():
    mock_event = AsyncMock()

    # MessageNotModifiedError should be caught cleanly
    mock_event.edit.side_effect = MessageNotModifiedError("Message not modified")
    await safe_edit(mock_event, "Test text")

    # MessageIdInvalidError should be caught cleanly
    mock_event.edit.side_effect = MessageIdInvalidError("Message id invalid")
    await safe_edit(mock_event, "Test text")


# ---------------------------------------------------------------------------
# Test 11: End-to-End Vertical Slice: Home -> Browse -> Details -> Return
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_vertical_slice_navigation():
    """
    Exercise real production router and handlers:
    Home -> Categories -> Plugin -> Command Details -> Return back to Home.
    """
    sender_id = 111222333
    mock_event = AsyncMock()
    mock_event.sender_id = sender_id

    # 1. Step 1: Open Home Menu
    text_home, buttons_home = build_home_menu(sender_id=sender_id)
    assert "AETHERIS CONTROL" in text_home

    # Find "Commands" token
    cmd_token = None
    for row in buttons_home:
        for b in row:
            if "Commands" in b.text:
                cmd_token = b.data.decode("utf-8") if isinstance(b.data, bytes) else str(b.data)
    assert cmd_token is not None

    # 2. Step 2: Tap "Commands" -> Route to Categories Menu
    mock_event.data = cmd_token.encode("utf-8")
    handled = await secure_callbacks.handle_callback_query(mock_event)
    assert handled is True
    # Verify categories menu was rendered
    edit_call_categories = mock_event.edit.call_args
    assert "COMMAND CATEGORIES" in edit_call_categories[0][0]
    categories_buttons = edit_call_categories[1].get("buttons")

    # Find "Tools" token
    tools_token = None
    for row in categories_buttons:
        for b in row:
            if "Tools" in b.text:
                tools_token = b.data.decode("utf-8") if isinstance(b.data, bytes) else str(b.data)
    assert tools_token is not None

    # 3. Step 3: Tap "Tools" -> Route to Category Plugins Menu
    mock_event.data = tools_token.encode("utf-8")
    handled = await secure_callbacks.handle_callback_query(mock_event)
    assert handled is True
    edit_call_plugins = mock_event.edit.call_args
    assert "CATEGORY: 🧰 TOOLS" in edit_call_plugins[0][0]
    plugins_buttons = edit_call_plugins[1].get("buttons")

    # Find "testmod" token
    testmod_token = None
    for row in plugins_buttons:
        for b in row:
            if "testmod" in b.text:
                testmod_token = b.data.decode("utf-8") if isinstance(b.data, bytes) else str(b.data)
    assert testmod_token is not None

    # 4. Step 4: Tap "testmod" -> Route to Plugin Commands Menu
    mock_event.data = testmod_token.encode("utf-8")
    handled = await secure_callbacks.handle_callback_query(mock_event)
    assert handled is True
    edit_call_cmds = mock_event.edit.call_args
    assert "PLUGIN: `TESTMOD`" in edit_call_cmds[0][0]
    cmds_buttons = edit_call_cmds[1].get("buttons")

    # Find ".testcmd" token
    testcmd_token = None
    for row in cmds_buttons:
        for b in row:
            if ".testcmd" in b.text:
                testcmd_token = b.data.decode("utf-8") if isinstance(b.data, bytes) else str(b.data)
    assert testcmd_token is not None

    # 5. Step 5: Tap ".testcmd" -> Route to Command Details View
    mock_event.data = testcmd_token.encode("utf-8")
    handled = await secure_callbacks.handle_callback_query(mock_event)
    assert handled is True
    edit_call_details = mock_event.edit.call_args
    assert "COMMAND: `.testcmd`" in edit_call_details[0][0]
    assert "A test command for verification." in edit_call_details[0][0]
    details_buttons = edit_call_details[1].get("buttons")

    # 6. Step 6: Tap "Back to testmod" -> Returns to plugin commands
    back_plg_token = None
    home_token = None
    for row in details_buttons:
        for b in row:
            if "Back to testmod" in b.text:
                back_plg_token = b.data.decode("utf-8") if isinstance(b.data, bytes) else str(b.data)
            if "Home" in b.text:
                home_token = b.data.decode("utf-8") if isinstance(b.data, bytes) else str(b.data)
    assert back_plg_token is not None
    assert home_token is not None

    mock_event.data = back_plg_token.encode("utf-8")
    handled = await secure_callbacks.handle_callback_query(mock_event)
    assert handled is True
    assert "PLUGIN: `TESTMOD`" in mock_event.edit.call_args[0][0]

    # 7. Step 7: Tap "Home" -> Returns straight to Home dashboard
    mock_event.data = home_token.encode("utf-8")
    handled = await secure_callbacks.handle_callback_query(mock_event)
    assert handled is True
    assert "AETHERIS CONTROL" in mock_event.edit.call_args[0][0]


# ---------------------------------------------------------------------------
# Test 12: Stale Task Cancellation Detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stale_task_cancellation():
    """Verify that cancelling a completed/stale task yields a friendly alert."""
    async def quick_task():
        return "done"

    t = task_manager.add_task("quick_task", quick_task(), description="Finishes fast")
    # Wait for completion
    await asyncio.sleep(0.05)
    assert t.is_done

    mock_event = AsyncMock()
    confirm_token = AsyncMock()
    confirm_token.payload = {
        "source": "tm",
        "target_id": t.id,
        "name": t.name,
        "sender_id": 111222333,
    }

    await handle_task_confirm_cancel(mock_event, confirm_token)
    mock_event.answer.assert_called_with(
        f"ℹ️ AsyncTask #{t.id} already finished or is no longer running.",
        alert=True,
    )


# ---------------------------------------------------------------------------
# Test 13: Message Revision Tracking & Out-of-Order Edit Drop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_message_revision_tracking():
    """Verify message revisions ensure older navigation results do not overwrite newer ones."""
    mock_event = AsyncMock()
    mock_event.chat_id = 999888
    mock_event.message_id = 777

    # Turn 1: Acquired revision 1
    rev1 = await acquire_message_revision(mock_event)
    assert rev1 >= 1
    assert await is_latest_message_revision(mock_event, rev1) is True

    # Turn 2: User rapidly clicked another button, acquiring revision 2
    rev2 = await acquire_message_revision(mock_event)
    assert rev2 == rev1 + 1
    assert await is_latest_message_revision(mock_event, rev1) is False
    assert await is_latest_message_revision(mock_event, rev2) is True

    # Older handler (rev1) attempts to edit -> must be dropped
    success_stale = await safe_edit(mock_event, "Old Text", rev=rev1)
    assert success_stale is False
    mock_event.edit.assert_not_called()

    # Newer handler (rev2) attempts to edit -> accepted
    success_current = await safe_edit(mock_event, "New Text", rev=rev2)
    assert success_current is True
    mock_event.edit.assert_called_once()


# ---------------------------------------------------------------------------
# Test 14: Command Permissions Derivation
# ---------------------------------------------------------------------------

def test_command_permissions_resolution():
    """Verify get_command_permission accurately resolves sudo status and registry flags."""
    # When sudo is disabled
    delgvar("sudoenable")
    perm = get_command_permission("testcmd")
    assert perm == "Master Only"

    # When sudo is enabled with authorized sudo users
    addgvar("sudoenable", "true")
    perm_sudo = get_command_permission("testcmd")
    assert perm_sudo == "Master & Authorized Sudo"

    # Cleanup
    delgvar("sudoenable")


# ---------------------------------------------------------------------------
# Test 15: Inline Search Flows & Query Normalization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inline_search_flows():
    """Verify quick search handles empty query guide, matching query docs, and unknown query safety."""
    builder = AsyncMock()
    builder.article = lambda **kwargs: kwargs
    mock_event = AsyncMock()
    mock_event.builder = builder

    # 1. Empty query -> returns search guide with clear instruction
    res_empty = await inline_search(mock_event, "")
    assert len(res_empty) == 1
    assert "Search Commands & Plugins" in res_empty[0]["title"]
    assert "directly to search" in res_empty[0]["text"]

    # 2. Matching command query -> returns doc article without executing command
    res_match = await inline_search(mock_event, "testcmd")
    assert len(res_match) >= 1
    matched_cmd = res_match[0]
    assert "Command: .testcmd" in matched_cmd["title"]
    assert "A test command for verification." in matched_cmd["text"]

    # 3. Normalized query: handles accidental redundant "s " prefix gracefully
    res_norm = await inline_search(mock_event, "s testcmd")
    assert len(res_norm) >= 1
    assert "Command: .testcmd" in res_norm[0]["title"]

    # 4. Matching plugin query
    res_plg = await inline_search(mock_event, "testmod")
    assert len(res_plg) >= 1
    plg_titles = [r["title"] for r in res_plg]
    assert any("Plugin: testmod" in t for t in plg_titles)

    # 5. No matches -> clean informative result
    res_none = await inline_search(mock_event, "xyznonexistent999")
    assert len(res_none) == 1
    assert "No results for 'xyznonexistent999'" in res_none[0]["title"]


# ---------------------------------------------------------------------------
# Test 16: Menu Revision Race with Reversed Completion Order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_menu_revision_reversed_completion_order():
    """
    Test two different buttons tapped on the same menu where Handler 1 starts first
    but finishes second. The newer navigation must win and the stale edit is dropped.
    """
    mock_event = AsyncMock()
    mock_event.chat_id = 12345
    mock_event.message_id = 67890

    # Button 1 pressed: acquires rev 1
    rev1 = await acquire_message_revision(mock_event)
    assert rev1 >= 1

    # Button 2 pressed shortly after: acquires rev 2
    rev2 = await acquire_message_revision(mock_event)
    assert rev2 == rev1 + 1

    # Handler 2 completes quickly
    success2 = await safe_edit(mock_event, "Menu 2 Content", rev=rev2)
    assert success2 is True
    assert mock_event.edit.call_count == 1
    assert mock_event.edit.call_args[0][0] == "Menu 2 Content"

    # Handler 1 completes LATE (reversed completion order)
    success1 = await safe_edit(mock_event, "Menu 1 Stale Content", rev=rev1)
    assert success1 is False  # Must be dropped!
    # Ensure edit was NOT called again with stale content
    assert mock_event.edit.call_count == 1
    assert mock_event.edit.call_args[0][0] == "Menu 2 Content"


# ---------------------------------------------------------------------------
# Test 17: Separate Menus Remain Independent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_separate_menus_independence():
    """Verify that revisions on Menu A do not interfere with or suppress Menu B."""
    event_a = AsyncMock()
    event_a.chat_id = 111
    event_a.message_id = 222

    event_b = AsyncMock()
    event_b.chat_id = 333
    event_b.message_id = 444

    rev_a1 = await acquire_message_revision(event_a)
    rev_b1 = await acquire_message_revision(event_b)

    # Both are at revision 1 in their own isolated namespaces
    assert await is_latest_message_revision(event_a, rev_a1) is True
    assert await is_latest_message_revision(event_b, rev_b1) is True

    # Advance Menu A to revision 2
    rev_a2 = await acquire_message_revision(event_a)
    assert await is_latest_message_revision(event_a, rev_a1) is False
    assert await is_latest_message_revision(event_a, rev_a2) is True

    # Menu B is completely untouched and still accepts rev_b1
    assert await is_latest_message_revision(event_b, rev_b1) is True
    success_b = await safe_edit(event_b, "Menu B Content", rev=rev_b1)
    assert success_b is True


# ---------------------------------------------------------------------------
# Test 18: Replay Prevention & Freshness Protection on Settings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setting_toggle_replay_prevention_and_freshness():
    """Verify single-use tokens prevent replay, and freshness check halts redundant mutation."""
    delgvar("ALLOW_NSFW")
    sender_id = 111222333
    mock_event = AsyncMock()
    mock_event.sender_id = sender_id

    # 1. Build menu -> generates single-use token
    _, buttons = build_settings_menu(sender_id=sender_id)
    nsfw_btn = buttons[0][0]
    token_str = nsfw_btn.data.decode("utf-8") if isinstance(nsfw_btn.data, bytes) else str(nsfw_btn.data)

    # 2. First tap: executes mutation successfully
    mock_event.data = token_str.encode("utf-8")
    handled1 = await secure_callbacks.handle_callback_query(mock_event)
    assert handled1 is True
    assert gvarstatus("ALLOW_NSFW") == "True"

    # 3. Replay tap: token was single-use, so it's already popped from _tokens!
    mock_event.data = token_str.encode("utf-8")
    mock_event.answer.reset_mock()
    handled2 = await secure_callbacks.handle_callback_query(mock_event)
    assert handled2 is True
    mock_event.answer.assert_called_with("⚠️ This button session has expired or is invalid.", alert=True)
    # Ensure ALLOW_NSFW did not get toggled or modified again
    assert gvarstatus("ALLOW_NSFW") == "True"

    # 4. Freshness check: if a token has stale expected state matching current DB, it does not mutate
    stale_token = AsyncMock()
    stale_token.payload = {"key": "ALLOW_NSFW", "current": False, "sender_id": sender_id}
    await handle_setting_toggle(mock_event, stale_token)
    # ALLOW_NSFW remains True, alert warns of synchronization
    assert gvarstatus("ALLOW_NSFW") == "True"
    mock_event.answer.assert_called_with("⚠️ Setting was already updated. Menu synchronized.", alert=True)

    # Cleanup
    delgvar("ALLOW_NSFW")


# ---------------------------------------------------------------------------
# Test 19: Graceful Fallback when youtubesearchpython is Missing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_youtube_missing_dependency_graceful_response():
    """Verify youtube_data_article provides a clear notice when optional dependency is absent."""
    builder = AsyncMock()
    builder.article = lambda **kwargs: kwargs
    mock_event = AsyncMock()
    mock_event.builder = builder

    with patch("userbot.core.inlinebot.VideosSearch", None):
        res = await youtube_data_article(mock_event, ["ytdl", "uninstalled_video_title"])
        assert res is not None
        assert "YouTube Search Unavailable" in res["title"]
        assert "youtube-search-python" in res["text"]
