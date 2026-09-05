"""Offline regressions. Load real units without executing userbot's login-time imports.

These tests do not qualify production startup or Telegram networking.
"""
import ast
import asyncio
import importlib.util
import io
import logging
import sys
import tarfile
import types
import typing
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[2]


def unit(relative):
    name = "audit_" + relative.replace("/", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_job_failure_never_reexecutes_side_effect():
    m = unit("userbot/core/jobs/supervisor.py")
    supervisor = m.JobSupervisor(max_concurrent=1)
    calls = []
    async def job(token):
        calls.append("side effect committed")
        raise ValueError("failure after side effect")
    record = await supervisor.submit("probe", job)
    await supervisor._execute_job(record)
    assert calls == ["side effect committed"]
    assert record.state == m.JobState.FAILED


@pytest.mark.asyncio
async def test_stop_drains_workers_and_job_finalizers():
    m = unit("userbot/core/jobs/supervisor.py")
    supervisor = m.JobSupervisor(max_concurrent=1)
    started, cleaned = asyncio.Event(), asyncio.Event()
    async def job(token):
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            cleaned.set()
    await supervisor.start()
    record = await supervisor.submit("probe", job)
    await started.wait()
    workers = list(supervisor._workers)
    await supervisor.stop()
    assert cleaned.is_set()
    assert record.task.done()
    assert all(w.done() for w in workers)


def test_client_really_overrides_rpc_boundary():
    tree = ast.parse((ROOT / "userbot/core/client.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CatUserBotClient")
    assert any(isinstance(n, ast.AsyncFunctionDef) and n.name == "__call__" for n in cls.body)


@pytest.mark.asyncio
async def test_ambiguous_rpc_failure_is_not_automatically_replayed():
    m = unit("userbot/core/flood_shield.py")
    calls = []
    async def request():
        calls.append("server may have applied operation")
        raise ConnectionResetError("connection lost after write")
    with pytest.raises(ConnectionResetError):
        await m.FloodShieldV5().execute(request)
    assert len(calls) == 1


def test_release_artifact_rejects_unknown_commit_and_conflicting_status():
    m = unit("scripts/artifact_utils.py")
    assert not m.validate_artifact({"git_commit": "UNKNOWN_COMMIT", "result": "PASS"}, "UNKNOWN_COMMIT")[0]
    assert not m.validate_artifact({"git_commit": "a" * 40, "result": "PENDING", "gate_passed": True}, "a" * 40)[0]


def test_no_automatic_external_error_pastes():
    tree = ast.parse((ROOT / "userbot/core/client.py").read_text(encoding="utf-8"))
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "paste_message" for n in ast.walk(tree))


def test_lexer_consumes_newline_without_infinite_loop():
    # A progress invariant catches the infinite loop without allowing it to exhaust RAM.
    m = unit("userbot/core/parser.py")
    lexer = m.CommandLexer("hello\nworld")
    original = m.Token
    count = 0
    def bounded_token(*args, **kwargs):
        nonlocal count
        count += 1
        assert count < 12, "lexer made no progress on newline"
        return original(*args, **kwargs)
    m.Token = bounded_token
    tokens = lexer.tokenize()
    assert [t.value for t in tokens if t.type == m.TokenType.WORD] == ["hello", "world"]


def test_configured_session_failure_does_not_fall_back(monkeypatch, capsys):
    source = (ROOT / "userbot/core/session.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    calls = []
    def invalid(value):
        raise ValueError("secret should not appear")
    ns = {"Config": types.SimpleNamespace(STRING_SESSION="private-short-secret", APP_ID=1, API_HASH="test", TG_BOT_TOKEN=None),
          "StringSession": invalid, "CatUserBotClient": lambda **kw: calls.append(kw),
          "ConnectionTcpAbridged": object}
    with pytest.raises((ValueError, RuntimeError)):
        exec(compile(tree, "session.py", "exec"), ns)
    assert calls == []
    assert "private-short-secret" not in capsys.readouterr().out


def test_archive_refuses_path_traversal_before_writing(tmp_path):
    m = unit("userbot/core/safe_archive.py")
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        entry = tarfile.TarInfo("../escaped.txt")
        entry.size = 5
        archive.addfile(entry, io.BytesIO(b"hello"))
    data.seek(0)
    with tarfile.open(fileobj=data) as archive, pytest.raises(ValueError):
        m.extract_tar_safely(archive, tmp_path / "extract")
    assert not (tmp_path / "escaped.txt").exists()


@pytest.mark.parametrize("expression", ["__import__('os').getcwd()", "(1).__class__", "'x' * 1000000000"])
def test_remote_link_expression_cannot_execute_python(expression):
    m = unit("userbot/core/safe_expression.py")
    with pytest.raises(ValueError):
        m.evaluate_link_expression(expression)


def test_safe_link_expression_preserves_arithmetic_and_concatenation():
    m = unit("userbot/core/safe_expression.py")
    assert m.evaluate_link_expression("(12 % 5 + 3)") == 5
    assert m.evaluate_link_expression("'/d/' + '5' + '/file.zip'") == "/d/5/file.zip"


def storage_module(monkeypatch, uri):
    prefix = "audit_storage"
    for name, path in [(prefix, ROOT / "userbot"), (prefix + ".core", ROOT / "userbot/core")]:
        pkg = types.ModuleType(name)
        pkg.__path__ = [str(path)]
        monkeypatch.setitem(sys.modules, name, pkg)
    config = types.ModuleType(prefix + ".Config")
    config.Config = types.SimpleNamespace(DB_URI=uri)
    monkeypatch.setitem(sys.modules, config.__name__, config)
    logger = types.ModuleType(prefix + ".core.logger")
    logger.logging = logging
    monkeypatch.setitem(sys.modules, logger.__name__, logger)
    name = prefix + ".sql_helper"
    spec = importlib.util.spec_from_file_location(name, ROOT / "userbot/sql_helper/__init__.py")
    m = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, m)
    spec.loader.exec_module(m)
    return m


def test_sqlite_open_failure_cannot_create_empty_memory_database(monkeypatch, tmp_path):
    with pytest.raises(RuntimeError):
        storage_module(monkeypatch, "sqlite:///" + (tmp_path / "absent" / "state.db").as_posix())


def test_unknown_configured_database_cannot_fall_back(monkeypatch):
    with pytest.raises(ValueError):
        storage_module(monkeypatch, "postgreql://private-credentials@host/db")


def test_failed_global_update_keeps_previous_persistent_value(monkeypatch, tmp_path):
    db = storage_module(monkeypatch, "sqlite:///" + (tmp_path / "state.db").as_posix())
    spec = importlib.util.spec_from_file_location("audit_storage.sql_helper.globals", ROOT / "userbot/sql_helper/globals.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    try:
        m.addgvar("key", "old")
        db.ENGINE.execute("CREATE TRIGGER reject_new BEFORE INSERT ON globals WHEN NEW.value = 'new' BEGIN SELECT RAISE(ABORT, 'write failed'); END")
        with pytest.raises(Exception):
            m.addgvar("key", "new")
        m.invalidate_cache()
        assert m.gvarstatus("key") == "old"
    finally:
        db.SESSION.remove()
        db.ENGINE.dispose()


@pytest.mark.asyncio
async def test_actual_client_override_routes_through_shield():
    shield_module = unit("userbot/core/flood_shield.py")
    shield = shield_module.FloodShieldV5()
    # Real production class body; only the network parent boundary is replaced.
    class NetworkBoundary:
        async def __call__(self, request, **kwargs):
            return request
    tree = ast.parse((ROOT / "userbot/core/client.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CatUserBotClient")
    namespace = {**vars(typing), "TelegramClient": NetworkBoundary,
                 "is_maintenance_request": shield_module.is_maintenance_request,
                 "flood_shield": shield}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), "client.py", "exec"), namespace)
    # Import inside production method is a dependency reference, not network behavior.
    prior = sys.modules.get("userbot.core.flood_shield")
    sys.modules["userbot.core.flood_shield"] = shield_module
    try:
        called = []
        original = shield.execute
        async def record(*args, **kwargs):
            called.append(kwargs)
            return await original(*args, **kwargs)
        shield.execute = record
        client = namespace["CatUserBotClient"]()
        request = object()
        assert await client(request) is request
        assert len(called) == 1
        maintenance = type("GetStateRequest", (), {})()
        assert await client(maintenance) is maintenance
        assert len(called) == 1
    finally:
        if prior is None:
            sys.modules.pop("userbot.core.flood_shield", None)
        else:
            sys.modules["userbot.core.flood_shield"] = prior


def test_link_helpers_pass_url_as_single_process_argument():
    tree = ast.parse((ROOT / "userbot/plugins/direct_links.py").read_text(encoding="utf-8"))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {"mega_dl", "cm_ru"}]
    import re
    from unittest.mock import Mock
    process = Mock()
    process.run.return_value.stdout = '{"url":"safe","download":"safe","file_name":"safe","file_size":1}'
    ns = {"re": re, "subprocess": process, "json": __import__("json"), "LOGS": logging.getLogger("audit"), "naturalsize": str}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "direct_links.py", "exec"), ns)
    for helper, url in [("mega_dl", "https://mega.nz/test;echo${IFS}probe"), ("cm_ru", "https://cloud.mail.ru/test;echo${IFS}probe")]:
        ns[helper](url)
        args, kwargs = process.run.call_args
        assert args[0][-1] == url
        assert isinstance(args[0], list)
        assert not kwargs.get("shell", False)


@pytest.mark.asyncio
async def test_upload_sender_disconnects_after_failed_part():
    m = unit("userbot/core/fasttelethon.py")
    transport = types.SimpleNamespace(disconnect=AsyncMock())
    sender = m.UploadSender(None, transport, 1, 1, False, 0, 1, asyncio.get_running_loop())
    future = asyncio.get_running_loop().create_future()
    future.set_exception(IOError("upload failed"))
    sender.previous = future
    with pytest.raises(IOError):
        await sender.disconnect()
    transport.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_real_parallel_download_orders_bytes_and_closes_senders():
    m = unit("userbot/core/fasttelethon.py")
    import hashlib
    payload = bytes(range(256)) * 8193
    network = types.SimpleNamespace(loop=asyncio.get_running_loop(), session=types.SimpleNamespace(dc_id=1, auth_key=True))
    async def call(sender, request):
        await asyncio.sleep(0)
        return types.SimpleNamespace(bytes=payload[request.offset:request.offset + request.limit])
    network._call = call
    engine = m.ParallelTransferrer(network)
    senders = []
    async def create():
        sender = types.SimpleNamespace(disconnect=AsyncMock())
        senders.append(sender)
        return sender
    engine._create_sender = create
    result = b"".join([chunk async for chunk in engine.download(None, len(payload), part_size_kb=64, connection_count=3)])
    assert hashlib.sha256(result).digest() == hashlib.sha256(payload).digest()
    assert engine.senders is None
    assert all(sender.disconnect.await_count == 1 for sender in senders)


@pytest.mark.asyncio
async def test_download_generator_close_releases_all_senders():
    m = unit("userbot/core/fasttelethon.py")
    network = types.SimpleNamespace(loop=asyncio.get_running_loop(), session=types.SimpleNamespace(dc_id=1, auth_key=True))
    network._call = AsyncMock(return_value=types.SimpleNamespace(bytes=b"x" * 65536))
    engine = m.ParallelTransferrer(network)
    senders = []
    async def create():
        sender = types.SimpleNamespace(disconnect=AsyncMock())
        senders.append(sender)
        return sender
    engine._create_sender = create
    stream = engine.download(None, 1024 * 1024, part_size_kb=64, connection_count=3)
    await stream.__anext__()
    await stream.aclose()
    assert all(sender.disconnect.await_count == 1 for sender in senders)
    assert engine.senders is None


@pytest.mark.asyncio
async def test_partial_sender_initialization_cleans_acquired_connections():
    m = unit("userbot/core/fasttelethon.py")
    network = types.SimpleNamespace(loop=asyncio.get_running_loop(), session=types.SimpleNamespace(dc_id=1, auth_key=True))
    engine = m.ParallelTransferrer(network)
    senders = []
    calls = 0
    async def create():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise IOError("connection failed")
        sender = types.SimpleNamespace(disconnect=AsyncMock())
        senders.append(sender)
        return sender
    engine._create_sender = create
    with pytest.raises(IOError):
        await engine._init_download(3, None, 20, 65536)
    assert all(sender.disconnect.await_count == 1 for sender in senders)
    assert engine.senders is None


@pytest.mark.parametrize("extra", [{"status": "FAILED"}, {"result": "SKIPPED", "gate_passed": True}, {"git_tree_clean": False}, {"git_commit": "b" * 40}])
def test_release_evidence_rejects_stale_dirty_or_conflicting_results(extra):
    m = unit("scripts/artifact_utils.py")
    data = {"git_commit": "a" * 40, "git_tree_clean": True, "result": "PASS", **extra}
    assert not m.validate_artifact(data, "a" * 40)[0]


def test_release_evidence_accepts_unambiguous_matching_pass():
    m = unit("scripts/artifact_utils.py")
    assert m.validate_artifact({"git_commit": "a" * 40, "git_tree_clean": True, "result": "PASS"}, "a" * 40)[0]


def test_release_gate_rejects_stale_plugin_evidence(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    m = unit("scripts/release_gate.py")
    with pytest.raises(SystemExit) as error:
        m.require_evidence({"git_commit": "0" * 40, "git_tree_clean": True, "result": "PASS"})
    assert error.value.code == 1


def test_release_manifest_cannot_qualify_without_secret_scan(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT))
    m = unit("scripts/release_gate.py")
    monkeypatch.setattr(m, "ROOT_DIR", tmp_path)
    (tmp_path / "artifacts").mkdir()
    m.generate_manifest("a" * 40, True, dict.fromkeys(["session_preservation", "basic_mtproto", "live_transfer", "live_hotreload"], "PASS"))
    import json
    data = json.loads((tmp_path / "artifacts/final_acceptance_manifest.json").read_text())
    assert data["qualification_level"] == "INCOMPLETE"
    assert data["secret_scan"] == "NOT_VERIFIED"
    assert data["stable_promotion_eligible"] is False
