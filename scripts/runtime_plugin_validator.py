#!/usr/bin/env python3
"""
Aetheris V5 Runtime Plugin Import and Unbind Validator.
Exercises dynamic loading, atomic registration, and clean teardown of all 138 plugins.
Runs in an isolated offline sandbox with zero network dependency.
"""

import asyncio
import importlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure root directory in sys.path
ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))
os.environ["AETHERIS_OFFLINE_VALIDATION"] = "1"
os.environ["DB_PATH"] = ":memory:"
os.environ["SQL_ENGINE"] = "sqlite"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGS = logging.getLogger("Aetheris.RuntimeValidator")

WHITELIST = {
    "wget", "telegraph", "selenium", "pymediainfo", "google", "google_auth_oauthlib",
    "googleapiclient", "psutil", "somnium", "humanize", "justwatch", "pytz",
    "prettytable", "pylast", "glitch_this", "github", "search_engine_parser",
    "geopy", "barcode", "git", "speedtest", "cloudscraper", "pafy", "bs4",
    "wikipedia", "gtts", "speech_recognition", "hachoir", "fitz", "docx",
    "pySmartDL", "urlextract", "cv2", "youtube_dl", "PIL", "spamwatch", "heroku3",
    "qrcode", "mutagen", "spotipy", "lyricsgenius", "yt_dlp", "deezloader",
    "aiohttp", "mechanize", "apscheduler", "ShazamAPI", "jikanpy", "googletrans",
    "validators", "torrentutils", "emoji", "PIL.Image", "PIL.ImageDraw",
    "PIL.ImageFont", "PIL.ImageFilter", "PIL.ImageOps", "PIL.features",
    "telethon.tl.functions.photos", "telethon.tl.functions.account"
}

class MockModule:
    def __init__(self, *args, **kwargs):
        pass
    def __getattr__(self, name):
        if name in ('__file__', '__spec__', '__loader__', '__path__'):
            return None
        if name == '__all__':
            return []
        if name == '__version__':
            return '1.0.0'
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()
    def __getitem__(self, item):
        return MockModule()
    def __setitem__(self, key, value):
        pass
    def __delitem__(self, key):
        pass
    def __iter__(self):
        return iter([])
    def __next__(self):
        raise StopIteration
    def __len__(self):
        return 0
    def __contains__(self, item):
        return False
    def __bool__(self):
        return True
    def __int__(self):
        return 0
    def __float__(self):
        return 0.0
    def __str__(self):
        return ""
    def __repr__(self):
        return '<MockModule>'
    def __add__(self, other):
        return str(self) + str(other)
    def __radd__(self, other):
        return str(other) + str(self)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass

class AutoMockFinder:
    def find_spec(self, fullname, path, target=None):
        top = fullname.split('.')[0]
        if top in WHITELIST or fullname in WHITELIST:
            import importlib.machinery
            spec = importlib.machinery.ModuleSpec(fullname, self)
            return spec
        return None

    def create_module(self, spec):
        mod = MockModule()
        mod.__name__ = spec.name
        mod.__file__ = f"<mock {spec.name}>"
        mod.__path__ = []
        return mod

    def exec_module(self, module):
        pass

sys.meta_path.insert(0, AutoMockFinder())


async def run_validator():
    from userbot.core.jobs.supervisor import job_supervisor
    from userbot.core.plugins.registry import atomic_registry
    from userbot.core.session import catub
    from userbot.utils.pluginmanager import load_module, remove_plugin

    await job_supervisor.start()

    plugins_dir = ROOT_DIR / "userbot" / "plugins"
    plugin_files = sorted([
        f.stem for f in plugins_dir.glob("*.py")
        if not f.name.startswith("__") and not f.name.startswith(".")
    ])

    total_plugins = len(plugin_files)
    LOGS.info(f"Discovered {total_plugins} plugins to validate in {plugins_dir}")

    results = []
    passed = 0
    failed = 0
    total_commands = 0

    print("=" * 80)
    print(f"AETHERIS V5 RUNTIME PLUGIN IMPORT & UNBIND VALIDATOR ({total_plugins} PLUGINS)")
    print("=" * 80)

    for idx, plugin_name in enumerate(plugin_files, 1):
        t0 = time.perf_counter()
        initial_cmd_count = atomic_registry.total_commands()
        initial_jobs = len(job_supervisor.list_jobs(active_only=True))

        error = None
        loaded = False
        registered_cmds = []
        unbound_clean = False

        try:
            # 1. Load module
            load_module(plugin_name)
            loaded = True

            # 2. Check registration
            handlers = atomic_registry.list_handlers_for_plugin(plugin_name)
            registered_cmds = [h.command_name for h in handlers if getattr(h, "command_name", None)]
            cmds_added = len(registered_cmds)
            total_commands += cmds_added

            # 3. Unbind plugin
            remove_plugin(plugin_name)
            await atomic_registry.unregister_plugin(plugin_name)
            await job_supervisor.cancel_plugin_jobs(plugin_name)

            remaining_handlers = atomic_registry.list_handlers_for_plugin(plugin_name)
            remaining_jobs = len([j for j in job_supervisor.list_jobs(active_only=True) if j.plugin_id == plugin_name])

            if len(remaining_handlers) == 0 and remaining_jobs == 0:
                unbound_clean = True
            else:
                error = f"Dangling resources: {len(remaining_handlers)} handlers, {remaining_jobs} jobs"

        except Exception as exc:
            error = str(exc)
            LOGS.warning("Plugin %s failed validation: %s", plugin_name, exc)

        dur_ms = (time.perf_counter() - t0) * 1000.0

        if loaded and unbound_clean and not error:
            status = "PASS"
            passed += 1
            print(f"[{idx:03d}/{total_plugins:03d}] [PASS] {plugin_name:<25} -> {len(registered_cmds):2d} cmds ({dur_ms:6.1f}ms)")
        else:
            status = "FAIL"
            failed += 1
            print(f"[{idx:03d}/{total_plugins:03d}] [FAIL] {plugin_name:<25} -> Error: {error} ({dur_ms:6.1f}ms)")

        results.append({
            "plugin": plugin_name,
            "status": status,
            "commands": registered_cmds,
            "commands_count": len(registered_cmds),
            "duration_ms": round(dur_ms, 2),
            "unbound_clean": unbound_clean,
            "error": error,
        })

    await job_supervisor.stop()

    # Save artifact
    artifacts_dir = ROOT_DIR / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_file = artifacts_dir / "plugin_runtime_validation.json"

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.time(),
            "total_plugins": total_plugins,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total_plugins * 100.0, 2) if total_plugins else 0.0,
            "total_commands_registered": total_commands,
            "details": results,
        }, f, indent=2)

    print("=" * 80)
    print(f"VALIDATION SUMMARY:")
    print(f"  Total Plugins:               {total_plugins}")
    print(f"  Passed (Import & Unbind):    {passed}")
    print(f"  Failed:                      {failed}")
    print(f"  Pass Rate:                   {passed / total_plugins * 100.0:.1f}%")
    print(f"  Total Unique Commands Tested:{total_commands}")
    print(f"  Detailed Report Saved:       {report_file}")
    print("=" * 80)

    if failed > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_validator())
