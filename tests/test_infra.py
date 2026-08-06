"""Unit tests for helpers/view_panels.py, helpers/database_logger.py, and the
hosting scripts - the remaining pieces with logic worth pinning.
"""

import asyncio
import os
import socket
import threading
import types
from datetime import datetime

import aiosqlite
import pytest

import helpers.database_logger as database_logger
import helpers.helpers as helpers
import helpers.view_panels as view_panels
from hosting import client_manager, server_manager


# --------------------------------------------------------------------------- #
# view_panels: pagination button state
# --------------------------------------------------------------------------- #

class BareView:
    """Stands in for the disnake View: update_buttons only reads self.children,
    self.start_index and the collection being paged."""

    def __init__(self, children, start_index, collection, attr):
        self.children = children
        self.start_index = start_index
        setattr(self, attr, collection)


def run_update(cls, collection_attr, start_index, size):
    """update_buttons() checks `isinstance(child, disnake.ui.Button)`, so these
    have to be real Buttons rather than stand-ins."""
    import disnake
    buttons = [disnake.ui.Button(custom_id=cid) for cid in ("prev", "next", "refresh")]
    view = BareView(buttons, start_index, list(range(size)), collection_attr)
    cls.update_buttons(view)
    return {b.custom_id: b.disabled for b in buttons}


def test_queue_list_disables_prev_on_first_page():
    states = run_update(view_panels.QueueList, "queue", start_index=0, size=25)
    assert states["prev"] is True
    assert states["next"] is False


def test_queue_list_enables_prev_after_first_page():
    states = run_update(view_panels.QueueList, "queue", start_index=10, size=25)
    assert states["prev"] is False


def test_queue_list_disables_next_on_last_page():
    states = run_update(view_panels.QueueList, "queue", start_index=20, size=25)
    assert states["next"] is True


def test_queue_list_disables_both_when_single_page():
    states = run_update(view_panels.QueueList, "queue", start_index=0, size=5)
    assert states["prev"] is True and states["next"] is True


def test_top_xp_pagination_matches_queue_behavior():
    states = run_update(view_panels.TopXP, "top_users", start_index=0, size=25)
    assert states["prev"] is True and states["next"] is False


def test_message_form_defaults():
    form = view_panels.MessageForm()
    assert "Supreme Beings" in form.title
    assert "other Supreme Beings" in form.response


def test_message_form_custom_title_and_response():
    form = view_panels.MessageForm(title="Message to a user", response="Sent.")
    assert form.title == "Message to a user"
    assert form.response == "Sent."


def test_song_selection_builds_urls_and_strips_tracking_params():
    """disnake.ui.View.__init__ requires a running loop, hence the async wrapper."""
    async def scenario():
        songs = [
            {"title": "A", "url_suffix": "/watch?v=aaa&pp=tracking", "duration": "1:00"},
            {"title": "B", "url_suffix": "/watch?v=bbb&pp=tracking", "duration": "2:00"},
        ]
        inter = types.SimpleNamespace(author=types.SimpleNamespace(id=1))
        return view_panels.SongSelection(songs, None, inter, None, None)

    panel = asyncio.run(scenario())
    assert panel.url_list == [
        "https://www.youtube.com//watch?v=aaa",
        "https://www.youtube.com//watch?v=bbb",
    ]
    assert panel.value is False


# --------------------------------------------------------------------------- #
# database_logger
# --------------------------------------------------------------------------- #

@pytest.fixture
def logs_db(tmp_path, monkeypatch):
    path = str(tmp_path / "logs.db")
    monkeypatch.setattr(helpers, "LOGS_DB_PATH", path)
    monkeypatch.setattr(database_logger, "LOGS_DB_PATH", path)
    return path


def read_rows(path, table):
    async def scenario():
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(f"SELECT * FROM {table}")
            return [dict(r) for r in await cur.fetchall()]
    return asyncio.run(scenario())


def test_commit_to_database_writes_common_row(logs_db):
    asyncio.run(database_logger.commit_to_database(
        "common", guild_id=5, tag="PLAY", comment="hello"))
    rows = read_rows(logs_db, "common")
    assert len(rows) == 1
    assert rows[0]["guild_id"] == 5
    assert rows[0]["tag"] == "PLAY"
    assert rows[0]["comment"] == "hello"
    # date/time are stamped automatically
    datetime.strptime(rows[0]["date"], "%Y-%m-%d")
    datetime.strptime(rows[0]["time"], "%H:%M:%S")


def test_commit_to_database_writes_bots_row(logs_db):
    asyncio.run(database_logger.commit_to_database("bots", tag="STARTUP", comment="up"))
    rows = read_rows(logs_db, "bots")
    assert rows[0]["tag"] == "STARTUP"


def test_commit_to_database_writes_gpt_row(logs_db):
    asyncio.run(database_logger.commit_to_database(
        "gpt", user_id=9, query="q", response="r"))
    rows = read_rows(logs_db, "gpt")
    assert rows[0]["query"] == "q" and rows[0]["response"] == "r"


def test_commit_to_database_writes_status_row(logs_db):
    asyncio.run(database_logger.commit_to_database("status", user_id=9, comment="online"))
    rows = read_rows(logs_db, "status")
    assert rows[0]["comment"] == "online"


def test_commit_to_database_rejects_unknown_table(logs_db):
    """Regression test for the `raise "<string>"` bug - this used to raise
    TypeError ('exceptions must derive from BaseException') instead."""
    with pytest.raises(ValueError):
        asyncio.run(database_logger.commit_to_database("nope", comment="x"))


def test_enabled_logger_writes_startup_row(logs_db):
    bot = types.SimpleNamespace(user="TestBot#0001")
    asyncio.run(database_logger.enabled(bot))
    rows = read_rows(logs_db, "bots")
    assert "TestBot#0001" in rows[0]["comment"]


def test_error_logger_writes_error_row(logs_db):
    guild = types.SimpleNamespace(id=77)
    asyncio.run(database_logger.error(RuntimeError("boom"), guild))
    rows = read_rows(logs_db, "common")
    assert rows[0]["tag"] == "ERROR"
    assert "boom" in rows[0]["comment"]


def test_activity_upd_summarizes_added_and_removed(logs_db):
    from bots.log_bot import Activity, UserStatus
    member = types.SimpleNamespace(id=1, name="Someone")
    old = UserStatus("online")
    old.activities = [Activity("game", "Old Game")]
    new = UserStatus("online")
    new.activities = [Activity("game", "New Game")]

    asyncio.run(database_logger.activity_upd(member, old, new))
    comment = read_rows(logs_db, "status")[0]["comment"]
    assert "- Old Game" in comment
    assert "+ New Game" in comment


# --------------------------------------------------------------------------- #
# hosting/server_manager: FileWithDates
# --------------------------------------------------------------------------- #

def test_file_with_dates_timestamps_each_line(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / "logs", exist_ok=True)
    monkeypatch.setattr(server_manager, "__file__", str(tmp_path / "hosting" / "server_manager.py"))
    os.makedirs(tmp_path / "hosting", exist_ok=True)

    writer = server_manager.FileWithDates()
    writer.write("first line\nsecond line\n")

    log_name = datetime.now().strftime("%d-%m-%Y") + ".txt"
    content = (tmp_path / "logs" / log_name).read_text(encoding="utf-8")
    assert "first line" in content and "second line" in content
    assert content.count("]: ") == 2


def test_file_with_dates_buffers_partial_lines(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / "logs", exist_ok=True)
    os.makedirs(tmp_path / "hosting", exist_ok=True)
    monkeypatch.setattr(server_manager, "__file__", str(tmp_path / "hosting" / "server_manager.py"))

    writer = server_manager.FileWithDates()
    writer.write("partial")          # no trailing newline -> buffered
    assert writer.buffer == "partial"
    writer.write(" rest\n")          # completes the line
    assert writer.buffer == ""

    log_name = datetime.now().strftime("%d-%m-%Y") + ".txt"
    content = (tmp_path / "logs" / log_name).read_text(encoding="utf-8")
    assert "partial rest" in content


def test_file_with_dates_ignores_empty_write(tmp_path, monkeypatch):
    writer = server_manager.FileWithDates()
    writer.write("")          # must not touch the filesystem
    assert writer.buffer == ""
    assert writer.flush() is None


# --------------------------------------------------------------------------- #
# hosting/server_manager: command dispatch
# --------------------------------------------------------------------------- #

class StubHost:
    """Exercises Host.process_command's dispatch table without a real process."""

    def __init__(self):
        self.calls = []

    async def _record(self, name, *args):
        self.calls.append((name, *args))
        return f"{name} ok"

    async def run(self):
        return await self._record("run")

    async def stop(self):
        return await self._record("stop")

    async def status(self):
        return await self._record("status")

    async def reboot(self):
        return await self._record("reboot")

    async def backup(self):
        return await self._record("backup")

    async def clear_errors(self):
        return await self._record("clear")

    async def update(self, branch):
        return await self._record("update", branch)

    def get_current_branch(self):
        return "master"


@pytest.fixture
def password(monkeypatch):
    monkeypatch.setattr(server_manager, "server_manager_password", "secret", raising=False)
    return "secret"


def dispatch(command):
    host = StubHost()
    result = asyncio.run(server_manager.Host.process_command(host, command))
    return host, result


@pytest.mark.parametrize("command,expected", [
    ("secret run", "run"),
    ("secret start", "run"),
    ("secret stop", "stop"),
    ("secret status", "status"),
    ("secret reboot", "reboot"),
    ("secret reload", "reboot"),
    ("secret restart", "reboot"),
    ("secret backup", "backup"),
    ("secret clear", "clear"),
])
def test_process_command_dispatch(password, command, expected):
    host, result = dispatch(command)
    assert host.calls[0][0] == expected
    assert result == f"{expected} ok"


def test_process_command_is_case_insensitive(password):
    host, _ = dispatch("secret STATUS")
    assert host.calls[0][0] == "status"


def test_process_command_update_defaults_to_current_branch(password):
    host, _ = dispatch("secret update")
    assert host.calls[0] == ("update", "master")


def test_process_command_update_accepts_explicit_branch(password):
    host, _ = dispatch("secret update dev")
    assert host.calls[0] == ("update", "dev")


def test_process_command_rejects_wrong_password(password):
    host, result = dispatch("wrong status")
    assert result == "Unauthorized access"
    assert host.calls == []


def test_process_command_rejects_unknown_command(password):
    host, result = dispatch("secret frobnicate")
    assert result is None


def test_process_command_rejects_too_few_arguments(password):
    host, result = dispatch("secret")
    assert result is None


# --------------------------------------------------------------------------- #
# hosting/client_manager: receive_all
# --------------------------------------------------------------------------- #

def test_receive_all_reads_until_close():
    """Serves a known payload over a real loopback socket, split across writes,
    to prove receive_all() reassembles it and stops at close."""
    payload = b"x" * 3000 + b"END"
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve():
        conn, _ = server.accept()
        conn.sendall(payload)
        conn.close()

    thread = threading.Thread(target=serve)
    thread.start()

    client = socket.socket()
    client.connect(("127.0.0.1", port))
    result = client_manager.receive_all(client)
    client.close()
    thread.join()
    server.close()

    assert result == payload.decode("utf8")
    assert result.endswith("END")


def test_client_manager_help_text_lists_every_command():
    for command in ["status", "run", "stop", "reboot", "backup", "update", "clear"]:
        assert command in client_manager.HELP_TEXT


# --------------------------------------------------------------------------- #
# FileWithDates: the dated logs were never pruned
# --------------------------------------------------------------------------- #

def test_old_dated_logs_are_pruned(tmp_path, monkeypatch):
    """These accumulated one per day forever. A full disk is a nasty failure:
    sshd can accept a connection and then fail to create a session, which looks
    like "Connection timed out during banner exchange" and locks you out of the
    machine you need in order to fix it."""
    import time
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    old = log_dir / "01-01-2020.txt"
    old.write_text("ancient", encoding="utf-8")
    recent = log_dir / "yesterday.txt"
    recent.write_text("recent", encoding="utf-8")
    keep = log_dir / "notalog.db"
    keep.write_text("not a log", encoding="utf-8")

    stale = time.time() - (server_manager.RETAIN_DAYS + 5) * 86400
    os.utime(old, (stale, stale))
    os.utime(keep, (stale, stale))

    writer = server_manager.FileWithDates()
    writer.file = open(log_dir / "today.txt", "a", encoding="utf-8")
    writer.prune_old_logs(str(log_dir))
    writer.file.close()

    assert not old.exists(), "a log older than the retention window survived"
    assert recent.exists(), "a recent log was deleted"
    assert keep.exists(), "a non-.txt file was deleted"


def test_pruning_runs_once_per_file(tmp_path):
    """Guards against sweeping the directory on every write."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    writer = server_manager.FileWithDates()
    writer.file = open(log_dir / "today.txt", "a", encoding="utf-8")

    calls = []
    real_listdir = os.listdir
    try:
        os.listdir = lambda p: calls.append(p) or real_listdir(p)
        writer.prune_old_logs(str(log_dir))
        writer.prune_old_logs(str(log_dir))
        writer.prune_old_logs(str(log_dir))
    finally:
        os.listdir = real_listdir
        writer.file.close()

    assert len(calls) == 1, f"pruned {len(calls)} times; expected once"


def test_pruning_failure_never_breaks_logging(tmp_path):
    """Losing the ability to log is far worse than failing to prune."""
    writer = server_manager.FileWithDates()
    writer.file = open(tmp_path / "today.txt", "a", encoding="utf-8")
    try:
        writer.prune_old_logs(str(tmp_path / "does-not-exist"))
    finally:
        writer.file.close()
