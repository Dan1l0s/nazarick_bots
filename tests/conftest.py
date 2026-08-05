"""Shared test setup.

1. A fake `configs.private_config` so the suite never needs the real one (which
   holds live bot tokens and is gitignored). Values here are dummies.
2. A fresh event loop per test - see `_fresh_event_loop` below.
"""

import asyncio
import sys
import types
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if "configs.private_config" not in sys.modules:
    fake_private_config = types.ModuleType("configs.private_config")
    fake_private_config.bots = []
    fake_private_config.openai_api_key = "test-key"
    fake_private_config.bot_ids = {"music_main": 1, "moderate": 2, "logs": 3}
    fake_private_config.supreme_beings = [111111111111111111]
    fake_private_config.test_guilds = [222222222222222222]
    fake_private_config.hosting_ip = "127.0.0.1"
    fake_private_config.hosting_port = 0
    fake_private_config.server_manager_password = "test"
    fake_private_config.backup_url = "https://example.invalid/"
    fake_private_config.backup_login = "test"
    fake_private_config.backup_password = "test"
    sys.modules["configs.private_config"] = fake_private_config


@pytest.fixture(autouse=True)
def _fresh_event_loop():
    """Gives every test a fresh, installed event loop.

    Needed because `asyncio.run()` closes its loop and leaves the thread's
    current loop unset. disnake's `View.__init__` and `InteractionBot()` both
    reach for `asyncio.get_event_loop()`, so any test that constructs a bot or
    a UI panel *after* another test called `asyncio.run()` would otherwise fail
    with "There is no current event loop in thread 'MainThread'". Ordering
    dependence like that makes failures depend on which tests ran before, so it
    is fixed here rather than per-test.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        loop.close()
        asyncio.set_event_loop(None)
