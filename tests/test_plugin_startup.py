import importlib
from unittest.mock import Mock

import pytest


@pytest.mark.asyncio
async def test_environment_only_startup_loads_commands_without_env_flag(monkeypatch, tmp_path):
    from userbot.utils import startup
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)
    # Reload resets globals only through assignments: remove the previous value
    # to reproduce a fresh process, rather than inheriting the suite's ENV=1.
    monkeypatch.delattr(startup, "VPS_NOLOAD", raising=False)
    importlib.reload(startup)
    folder = tmp_path / "userbot/plugins"
    folder.mkdir(parents=True)
    source = folder / "alive.py"
    source.write_text("# harmless fixture\n")
    load = Mock()
    monkeypatch.setattr(startup, "load_module", load)
    monkeypatch.setattr(startup.Config, "NO_LOAD", [])
    await startup.load_plugins("plugins")
    load.assert_called_once_with("alive", plugin_path="userbot/plugins")
    assert source.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("disabled", [False, True])
async def test_skipped_or_failed_plugin_is_never_deleted(monkeypatch, tmp_path, disabled):
    from userbot.utils import startup
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "userbot/plugins"
    folder.mkdir(parents=True)
    source = folder / "alive.py"
    source.write_text("# harmless fixture\n")
    monkeypatch.setattr(startup, "VPS_NOLOAD", [], raising=False)
    monkeypatch.setattr(startup.Config, "NO_LOAD", ["alive"] if disabled else [])
    monkeypatch.setattr(startup, "load_module", Mock(side_effect=RuntimeError("temporary import failure")))
    await startup.load_plugins("plugins")
    assert source.read_text() == "# harmless fixture\n"
