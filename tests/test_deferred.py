"""Tests for the deferred-restart machinery: hosting/status.py plus the
queueing, cancellation and idle-gating added to hosting/server_manager.py.

The safety property being pinned here is: **a deploy must never wait forever**.
A wedged or crashed bot process must not be able to block updates, so both a
missing/stale status file and a force deadline release the queued action.
"""

import asyncio
import json
import os
import sys
import time
import signal
import socket
import subprocess
import types

import pytest

from hosting import server_manager, status


# --------------------------------------------------------------------------- #
# count_active_plays
# --------------------------------------------------------------------------- #

def make_state(voice=None, current_song=None):
    return types.SimpleNamespace(voice=voice, current_song=current_song)


def make_instance(name, states):
    return types.SimpleNamespace(name=name, states=states)


def test_counts_nothing_when_no_bots():
    assert status.count_active_plays([]) == (0, 0, {})


def test_counts_idle_bot_as_zero():
    inst = make_instance("music_main", {1: make_state()})
    active, connected, breakdown = status.count_active_plays([inst])
    assert (active, connected) == (0, 0)
    assert breakdown == {}


def test_counts_connected_but_not_playing():
    """A bot sitting in a voice channel with an empty queue is connected but
    not active - it does not block a restart, since it disconnects itself
    after PlayTimeout."""
    inst = make_instance("music_main", {1: make_state(voice=object())})
    active, connected, breakdown = status.count_active_plays([inst])
    assert active == 0
    assert connected == 1
    assert breakdown["music_main"] == {"playing": 0, "connected": 1}


def test_counts_active_play():
    inst = make_instance("music_main", {1: make_state(voice=object(), current_song=object())})
    active, connected, _ = status.count_active_plays([inst])
    assert (active, connected) == (1, 1)


def test_counts_across_bots_and_guilds():
    a = make_instance("a", {
        1: make_state(voice=object(), current_song=object()),
        2: make_state(voice=object(), current_song=object()),
    })
    b = make_instance("b", {3: make_state(voice=object())})
    active, connected, breakdown = status.count_active_plays([a, b])
    assert active == 2
    assert connected == 3
    assert breakdown["a"]["playing"] == 2
    assert breakdown["b"]["playing"] == 0


def test_tolerates_objects_without_states():
    """Admin and logger bots have no `states` attribute; they must be skipped
    rather than raise."""
    active, connected, _ = status.count_active_plays([types.SimpleNamespace(name="admin")])
    assert (active, connected) == (0, 0)


# --------------------------------------------------------------------------- #
# write_status / read_status
# --------------------------------------------------------------------------- #

@pytest.fixture
def status_path(tmp_path):
    return str(tmp_path / "run" / "status.json")


def test_write_then_read_round_trip(status_path):
    inst = make_instance("music_main", {1: make_state(voice=object(), current_song=object())})
    written = status.write_status([inst], status_path)
    read_back = status.read_status(status_path)

    assert read_back["active_plays"] == 1
    assert read_back["pid"] == os.getpid()
    assert read_back["updated_at"] == pytest.approx(written["updated_at"])


def test_write_creates_missing_directory(tmp_path):
    path = str(tmp_path / "deeply" / "nested" / "status.json")
    status.write_status([], path)
    assert os.path.exists(path)


def test_write_is_atomic_and_leaves_no_temp_file(status_path):
    status.write_status([], status_path)
    assert not os.path.exists(status_path + ".tmp")


def test_read_missing_file_returns_none(status_path):
    assert status.read_status(status_path) is None


def test_read_corrupt_file_returns_none(tmp_path):
    path = tmp_path / "status.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert status.read_status(str(path)) is None


def test_clear_status_removes_file_and_tolerates_absence(status_path):
    status.write_status([], status_path)
    status.clear_status(status_path)
    assert not os.path.exists(status_path)
    status.clear_status(status_path)   # second call must not raise


# --------------------------------------------------------------------------- #
# is_idle - the gate that decides whether a deploy may proceed
# --------------------------------------------------------------------------- #

def test_idle_when_no_status_file(status_path):
    idle, reason = status.is_idle(status_path)
    assert idle is True
    assert "no status file" in reason


def test_idle_when_nothing_playing(status_path):
    status.write_status([make_instance("a", {1: make_state(voice=object())})], status_path)
    idle, reason = status.is_idle(status_path)
    assert idle is True
    assert "no active plays" in reason


def test_not_idle_while_playing(status_path):
    status.write_status(
        [make_instance("a", {1: make_state(voice=object(), current_song=object())})],
        status_path)
    idle, reason = status.is_idle(status_path)
    assert idle is False
    assert "1 active play" in reason


def test_stale_status_counts_as_idle(status_path):
    """The critical anti-deadlock property: if the bot process stopped updating
    the file, a queued deploy must go ahead rather than wait forever."""
    status.write_status(
        [make_instance("a", {1: make_state(voice=object(), current_song=object())})],
        status_path)
    # rewrite with an old timestamp
    data = status.read_status(status_path)
    data["updated_at"] = time.time() - 10_000
    with open(status_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)

    idle, reason = status.is_idle(status_path)
    assert idle is True
    assert "stale" in reason


def test_fresh_status_is_not_treated_as_stale(status_path):
    status.write_status(
        [make_instance("a", {1: make_state(voice=object(), current_song=object())})],
        status_path)
    idle, _ = status.is_idle(status_path, stale_after=3600)
    assert idle is False


# --------------------------------------------------------------------------- #
# status_writer task
# --------------------------------------------------------------------------- #

def test_status_writer_refreshes_the_file(status_path):
    async def scenario():
        inst = make_instance("a", {1: make_state()})
        task = asyncio.create_task(status.status_writer([inst], status_path, interval=0.01))
        await asyncio.sleep(0.05)
        task.cancel()
        return status.read_status(status_path)

    assert asyncio.run(scenario())["active_plays"] == 0


def test_status_writer_survives_a_write_failure(monkeypatch, status_path):
    """A broken status write must never take the bots down."""
    calls = {"n": 0}

    def exploding_write(instances, path):
        calls["n"] += 1
        raise OSError("disk full")

    monkeypatch.setattr(status, "write_status", exploding_write)

    async def scenario():
        task = asyncio.create_task(status.status_writer([], status_path, interval=0.01))
        await asyncio.sleep(0.05)
        task.cancel()

    asyncio.run(scenario())
    assert calls["n"] > 1        # kept retrying instead of dying


# --------------------------------------------------------------------------- #
# PendingAction
# --------------------------------------------------------------------------- #

def test_pending_action_describes_itself():
    action = server_manager.PendingAction("update", "master")
    text = action.describe()
    assert "update master" in text
    assert "queued" in text


def test_pending_action_deadline_not_passed_immediately():
    assert server_manager.PendingAction("reboot").deadline_passed() is False


def test_pending_action_deadline_passes(monkeypatch):
    monkeypatch.setattr(server_manager, "DEFERRED_FORCE_AFTER", 0)
    assert server_manager.PendingAction("reboot").deadline_passed() is True


# --------------------------------------------------------------------------- #
# queue / cancel
# --------------------------------------------------------------------------- #

class BareHost:
    """Stands in for Host - the queue/cancel methods only touch `pending`."""

    def __init__(self):
        self.pending = None


@pytest.fixture
def manager_status_path(tmp_path, monkeypatch):
    path = str(tmp_path / "status.json")
    monkeypatch.setattr(server_manager, "STATUS_PATH", path)
    return path


def test_queue_action_records_the_request(manager_status_path):
    host = BareHost()
    message = server_manager.Host.queue_action(host, "update", "master")
    assert host.pending.kind == "update"
    assert host.pending.branch == "master"
    assert "Queued" in message


def test_queue_action_reports_immediate_run_when_idle(manager_status_path):
    host = BareHost()
    message = server_manager.Host.queue_action(host, "reboot")
    assert "idle now" in message


def test_queue_action_reports_waiting_when_playing(manager_status_path):
    status.write_status(
        [make_instance("a", {1: make_state(voice=object(), current_song=object())})],
        manager_status_path)
    host = BareHost()
    message = server_manager.Host.queue_action(host, "reboot")
    assert "force-run after" in message


def test_queueing_twice_replaces_the_previous_action(manager_status_path):
    host = BareHost()
    server_manager.Host.queue_action(host, "update", "master")
    message = server_manager.Host.queue_action(host, "reboot")
    assert "Replaced pending update" in message
    assert host.pending.kind == "reboot"


def test_cancel_with_nothing_queued():
    host = BareHost()
    assert server_manager.Host.cancel_pending(host) == "Nothing is queued"


def test_cancel_clears_the_queued_action(manager_status_path):
    host = BareHost()
    server_manager.Host.queue_action(host, "update", "master")
    message = server_manager.Host.cancel_pending(host)
    assert "Cancelled" in message
    assert host.pending is None


# --------------------------------------------------------------------------- #
# Command parsing: `when-idle` suffix
# --------------------------------------------------------------------------- #

class DispatchHost:
    """Records which path a command took without performing any action."""

    def __init__(self):
        self.pending = None
        self.calls = []

    async def run(self):
        self.calls.append("run"); return "run"

    async def stop(self):
        self.calls.append("stop"); return "stop"

    async def status(self):
        self.calls.append("status"); return "status"

    async def reboot(self):
        self.calls.append("reboot-now"); return "reboot-now"

    async def backup(self):
        self.calls.append("backup"); return "backup"

    async def update(self, branch):
        self.calls.append(("update-now", branch)); return "update-now"

    async def upgrade_ytdlp(self, deferred=False):
        self.calls.append(("upgrade", deferred)); return "upgrade"

    async def clear_errors(self):
        self.calls.append("clear"); return "clear"

    def get_current_branch(self):
        return "master"

    def queue_action(self, kind, branch=None):
        self.calls.append(("queued", kind, branch))
        self.pending = server_manager.PendingAction(kind, branch)
        return "queued"

    def cancel_pending(self):
        self.calls.append("cancel"); return "cancel"


@pytest.fixture
def password(monkeypatch):
    monkeypatch.setattr(server_manager, "server_manager_password", "pw", raising=False)
    return "pw"


def dispatch(command):
    host = DispatchHost()
    result = asyncio.run(server_manager.Host.process_command(host, command))
    return host, result


def test_immediate_reboot_is_unchanged(password):
    host, _ = dispatch("pw reboot")
    assert host.calls == ["reboot-now"]


def test_reboot_when_idle_is_queued(password):
    host, _ = dispatch("pw reboot when-idle")
    assert host.calls == [("queued", "reboot", None)]


def test_update_when_idle_keeps_the_branch(password):
    host, _ = dispatch("pw update develop/dan1l0s when-idle")
    assert host.calls == [("queued", "update", "develop/dan1l0s")]


def test_update_when_idle_without_branch_uses_current(password):
    host, _ = dispatch("pw update when-idle")
    assert host.calls == [("queued", "update", "master")]


def test_immediate_update_is_unchanged(password):
    host, _ = dispatch("pw update master")
    assert host.calls == [("update-now", "master")]


@pytest.mark.parametrize("suffix", ["when-idle", "when_idle", "whenidle", "WHEN-IDLE"])
def test_when_idle_spelling_variants(password, suffix):
    host, _ = dispatch(f"pw reboot {suffix}")
    assert host.calls == [("queued", "reboot", None)]


def test_upgrade_passes_deferred_flag(password):
    host, _ = dispatch("pw upgrade when-idle")
    assert host.calls == [("upgrade", True)]

    host2, _ = dispatch("pw upgrade")
    assert host2.calls == [("upgrade", False)]


def test_cancel_is_dispatched(password):
    host, _ = dispatch("pw cancel")
    assert host.calls == ["cancel"]


def test_wrong_password_is_rejected_before_anything_runs(password):
    host, result = dispatch("nope reboot when-idle")
    assert result == "Unauthorized access"
    assert host.calls == []


def test_unknown_command_returns_none(password):
    host, result = dispatch("pw frobnicate when-idle")
    assert result is None
    assert host.calls == []


# --------------------------------------------------------------------------- #
# deferred_watcher
# --------------------------------------------------------------------------- #

class WatcherHost:
    def __init__(self, pending=None):
        self.state = server_manager.BotState.RUNNING
        self.pending = pending
        self.ran = []

    async def update(self, branch):
        self.ran.append(("update", branch)); return "updated"

    async def reboot(self):
        self.ran.append(("reboot",)); return "rebooted"

    async def run_ytdlp_upgrade(self):
        self.ran.append(("upgrade",)); return "upgraded"


def run_watcher_once(host, monkeypatch, path):
    """Runs a single watcher tick by shrinking the poll interval and stopping
    the loop immediately afterwards."""
    monkeypatch.setattr(server_manager, "DEFERRED_POLL_INTERVAL", 0.01)
    monkeypatch.setattr(server_manager, "STATUS_PATH", path)

    async def scenario():
        task = asyncio.create_task(server_manager.Host.deferred_watcher(host))
        await asyncio.sleep(0.05)
        task.cancel()

    asyncio.run(scenario())


def test_watcher_runs_queued_update_when_idle(monkeypatch, manager_status_path):
    host = WatcherHost(server_manager.PendingAction("update", "master"))
    run_watcher_once(host, monkeypatch, manager_status_path)
    assert host.ran == [("update", "master")]
    assert host.pending is None


def test_watcher_waits_while_music_is_playing(monkeypatch, manager_status_path):
    status.write_status(
        [make_instance("a", {1: make_state(voice=object(), current_song=object())})],
        manager_status_path)
    host = WatcherHost(server_manager.PendingAction("reboot"))
    run_watcher_once(host, monkeypatch, manager_status_path)
    assert host.ran == []
    assert host.pending is not None      # still queued


def test_watcher_forces_the_action_after_the_deadline(monkeypatch, manager_status_path):
    """The anti-deadlock guarantee: still 'playing', but the deadline has passed,
    so the action runs regardless."""
    status.write_status(
        [make_instance("a", {1: make_state(voice=object(), current_song=object())})],
        manager_status_path)
    monkeypatch.setattr(server_manager, "DEFERRED_FORCE_AFTER", 0)
    host = WatcherHost(server_manager.PendingAction("reboot"))
    run_watcher_once(host, monkeypatch, manager_status_path)
    assert host.ran == [("reboot",)]


def test_watcher_does_nothing_without_a_queued_action(monkeypatch, manager_status_path):
    host = WatcherHost(None)
    run_watcher_once(host, monkeypatch, manager_status_path)
    assert host.ran == []


def test_watcher_survives_a_failing_action(monkeypatch, manager_status_path):
    class Failing(WatcherHost):
        async def reboot(self):
            raise RuntimeError("boom")

    host = Failing(server_manager.PendingAction("reboot"))
    run_watcher_once(host, monkeypatch, manager_status_path)
    # cleared rather than retried forever, and the watcher itself stayed alive
    assert host.pending is None


# --------------------------------------------------------------------------- #
# yt-dlp upgrade
# --------------------------------------------------------------------------- #

class UpgradeHost:
    def __init__(self, versions, returncode=0):
        self.state = server_manager.BotState.RUNNING
        self._versions = list(versions)
        self._returncode = returncode
        self.pending = None
        self.rebooted = False

    def get_ytdlp_version(self):
        return self._versions.pop(0) if self._versions else None

    async def reboot(self):
        self.rebooted = True
        return "rebooted"

    def queue_action(self, kind, branch=None):
        self.pending = server_manager.PendingAction(kind, branch)
        return f"queued {kind}"


@pytest.fixture
def fake_pip(monkeypatch):
    def runner(returncode=0, stderr=""):
        def fake_run(cmd, **kwargs):
            return types.SimpleNamespace(returncode=returncode, stdout="", stderr=stderr)
        monkeypatch.setattr(server_manager.subprocess, "run", fake_run)
    return runner


def test_upgrade_restarts_when_version_changed(fake_pip):
    fake_pip()
    host = UpgradeHost(["2024.1.1", "2026.7.4"])
    message = asyncio.run(server_manager.Host.run_ytdlp_upgrade(host))
    assert "2024.1.1 -> 2026.7.4" in message
    assert host.rebooted is True


def test_upgrade_skips_restart_when_already_current(fake_pip):
    """Most daily runs hit this path - yt-dlp publishes often, but not daily."""
    fake_pip()
    host = UpgradeHost(["2026.7.4", "2026.7.4"])
    message = asyncio.run(server_manager.Host.run_ytdlp_upgrade(host))
    assert "already current" in message
    assert host.rebooted is False


def test_upgrade_reports_pip_failure(fake_pip):
    fake_pip(returncode=1, stderr="ERROR: could not reach pypi")
    host = UpgradeHost(["2026.7.4"])
    message = asyncio.run(server_manager.Host.run_ytdlp_upgrade(host))
    assert "failed" in message
    assert "could not reach pypi" in message
    assert host.rebooted is False


def test_upgrade_does_not_restart_a_stopped_bot(fake_pip):
    fake_pip()
    host = UpgradeHost(["2024.1.1", "2026.7.4"])
    host.state = server_manager.BotState.STOPPED
    message = asyncio.run(server_manager.Host.run_ytdlp_upgrade(host))
    assert "not running" in message
    assert host.rebooted is False


def test_deferred_upgrade_queues_instead_of_restarting(fake_pip):
    """Deferred mode still installs immediately - only the restart waits - so
    the fix is on disk the moment playback ends."""
    fake_pip()
    host = UpgradeHost(["2024.1.1", "2026.7.4"])
    message = asyncio.run(server_manager.Host.upgrade_ytdlp(host, deferred=True))
    assert "2024.1.1 -> 2026.7.4" in message
    assert host.pending is not None
    assert host.pending.kind == "reboot"
    assert host.rebooted is False


def test_deferred_upgrade_queues_nothing_when_current(fake_pip):
    fake_pip()
    host = UpgradeHost(["2026.7.4", "2026.7.4"])
    message = asyncio.run(server_manager.Host.upgrade_ytdlp(host, deferred=True))
    assert "nothing queued" in message
    assert host.pending is None


# --------------------------------------------------------------------------- #
# update() - four bugs that broke the first real deploy
# --------------------------------------------------------------------------- #

class UpdateHost:
    """Captures the shell commands update() issues, without running any."""

    def __init__(self, state=None, port=10000):
        self.state = state or server_manager.BotState.STOPPED
        self.pending = None
        self.commands = []
        self.listener_socket = types.SimpleNamespace(close=lambda: None)
        self.port = port

    async def stop(self):
        self.state = server_manager.BotState.STOPPED
        return "stopped"


@pytest.fixture
def captured_shell(monkeypatch):
    """Intercepts os.system so update() can be exercised safely."""
    calls = []

    def fake_system(cmd):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(server_manager.os, "system", fake_system)
    monkeypatch.setattr(server_manager.os.path, "exists", lambda p: True)
    return calls


def test_update_looks_for_setup_sh_at_the_repo_root(captured_shell, monkeypatch):
    """Regression: it ran `bash setup.sh` from hosting/, so every update printed
    'bash: setup.sh: No such file or directory' and skipped the dependency
    install entirely."""
    monkeypatch.delenv("INVOCATION_ID", raising=False)
    host = UpdateHost()
    asyncio.run(server_manager.Host.update(host, "master"))

    setup_calls = [c for c in captured_shell if "setup.sh" in c]
    assert setup_calls, "setup.sh was never invoked"
    assert all(os.path.join("..", "setup.sh") in c for c in setup_calls), setup_calls


def test_update_skips_setup_sh_when_absent(monkeypatch):
    calls = []
    monkeypatch.setattr(server_manager.os, "system", lambda c: calls.append(c) or 0)
    monkeypatch.setattr(server_manager.os.path, "exists", lambda p: False)
    monkeypatch.delenv("INVOCATION_ID", raising=False)

    asyncio.run(server_manager.Host.update(UpdateHost(), "master"))
    assert not [c for c in calls if "setup.sh" in c]


def test_update_does_not_use_the_dash_incompatible_disown(captured_shell, monkeypatch):
    """Regression: the relaunch ended in `& disown`, but os.system runs through
    /bin/sh (dash on Debian) where disown is not a builtin - 'sh: 1: disown: not
    found'. setsid achieves the same detachment in any POSIX shell."""
    monkeypatch.delenv("INVOCATION_ID", raising=False)
    asyncio.run(server_manager.Host.update(UpdateHost(), "master"))

    relaunch = [c for c in captured_shell if "server_manager.py" in c]
    assert relaunch, "supervisor was never relaunched"
    assert not any("disown" in c for c in relaunch), relaunch
    assert all("setsid" in c for c in relaunch), relaunch


def test_update_relaunches_with_the_current_interpreter(captured_shell, monkeypatch):
    """Debian has no bare `python`, only `python3`; sys.executable also keeps a
    venv interpreter in play."""
    monkeypatch.delenv("INVOCATION_ID", raising=False)
    asyncio.run(server_manager.Host.update(UpdateHost(), "master"))

    relaunch = [c for c in captured_shell if "server_manager.py" in c]
    assert all(sys.executable in c for c in relaunch), relaunch


def test_update_passes_dash_r_only_if_the_bots_were_running(captured_shell, monkeypatch):
    monkeypatch.delenv("INVOCATION_ID", raising=False)

    running = UpdateHost(state=server_manager.BotState.RUNNING)
    asyncio.run(server_manager.Host.update(running, "master"))
    assert any(" -r" in c for c in captured_shell if "server_manager.py" in c)

    captured_shell.clear()
    stopped = UpdateHost(state=server_manager.BotState.STOPPED)
    asyncio.run(server_manager.Host.update(stopped, "master"))
    relaunch = [c for c in captured_shell if "server_manager.py" in c]
    assert relaunch and not any(" -r" in c for c in relaunch)


def test_update_under_systemd_exits_instead_of_respawning(captured_shell, monkeypatch):
    """With Restart=always, exiting is enough - and spawning our own replacement
    alongside systemd's would give two supervisors competing for the port."""
    monkeypatch.setenv("INVOCATION_ID", "deadbeef")   # systemd sets this
    host = UpdateHost()
    result = asyncio.run(server_manager.Host.update(host, "master"))

    assert not [c for c in captured_shell if "server_manager.py" in c]
    assert "systemd" in result
    assert host.state == server_manager.BotState.SHUTDOWN


def test_update_aborts_and_restores_on_fetch_failure(monkeypatch):
    calls = []

    def fake_system(cmd):
        calls.append(cmd)
        return 1 if "fetch" in cmd else 0

    monkeypatch.setattr(server_manager.os, "system", fake_system)
    monkeypatch.delenv("INVOCATION_ID", raising=False)

    result = asyncio.run(server_manager.Host.update(UpdateHost(), "master"))
    assert "Failed to fetch" in result
    assert any("stash pop" in c for c in calls), "local changes were not restored"
    assert not any("checkout" in c for c in calls), "checked out despite fetch failing"


def test_update_never_runs_git_clean(captured_shell, monkeypatch):
    """git clean -fdx would delete private_config.py and db/, both gitignored."""
    monkeypatch.delenv("INVOCATION_ID", raising=False)
    asyncio.run(server_manager.Host.update(UpdateHost(), "master"))
    assert not any("clean" in c for c in captured_shell), captured_shell


# --------------------------------------------------------------------------- #
# Executable bits must survive a Windows-authored commit
# --------------------------------------------------------------------------- #

def test_shell_scripts_are_executable_in_git():
    """The first real deploy failed with exit 126 because deploy.sh was stored
    as mode 100644: committed from Windows, which has no exec bit. SSH surfaces
    that only as 'Permission denied', which is a confusing way to learn it."""
    import subprocess as sp

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = sp.run(["git", "ls-files", "-s", "hosting/deploy.sh",
                  "hosting/setup_cicd.sh", "setup.sh"],
                 cwd=repo, capture_output=True, text=True)
    if out.returncode != 0:
        pytest.skip("not a git checkout")

    for line in out.stdout.strip().splitlines():
        mode, _, _, path = line.replace("\t", " ").split(maxsplit=3)
        assert mode == "100755", f"{path} is mode {mode}, needs 100755 to run on the VPS"


# --------------------------------------------------------------------------- #
# Regression: a slow upgrade must not freeze the control port
# --------------------------------------------------------------------------- #

def test_upgrade_does_not_block_the_event_loop(monkeypatch):
    """The CI symptom was `could not reach the manager at 127.0.0.1:PORT:
    timed out`. subprocess.run() called straight from the coroutine froze the
    loop, so sock_accept never ran; the kernel still completed the handshake
    from the listen() backlog, so the client connected and then hung until its
    30 s timeout. Proven here by checking the loop keeps ticking."""
    def slow_run(cmd, **kwargs):
        time.sleep(0.30)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(server_manager.subprocess, "run", slow_run)

    ticks = 0

    async def scenario():
        nonlocal ticks

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.02)
                ticks += 1

        beat = asyncio.create_task(ticker())
        host = UpgradeHost(["2024.1.1", "2026.7.4"])
        message = await server_manager.Host.run_ytdlp_upgrade(host)
        beat.cancel()
        return message

    message = asyncio.run(scenario())
    assert "2024.1.1 -> 2026.7.4" in message
    # Blocking the loop would leave this at 0.
    assert ticks >= 5, f"event loop was blocked during the upgrade (ticks={ticks})"


def test_upgrade_uses_the_running_interpreter(monkeypatch):
    """A literal "python" does not exist on Debian, so pip never ran and
    get_ytdlp_version always returned None - making before == after, which
    reported "already current (None)" and skipped the restart forever."""
    seen = []

    def record(cmd, **kwargs):
        seen.append(cmd)
        return types.SimpleNamespace(returncode=0, stdout="2026.7.4\n", stderr="")
    monkeypatch.setattr(server_manager.subprocess, "run", record)

    host = UpgradeHost(["2024.1.1", "2026.7.4"])
    asyncio.run(server_manager.Host.run_ytdlp_upgrade(host))
    assert seen, "pip was never invoked"
    for cmd in seen:
        assert cmd[0] == sys.executable, f"expected sys.executable, got {cmd[0]!r}"


def test_get_ytdlp_version_uses_the_running_interpreter(monkeypatch):
    seen = []

    def record(cmd, **kwargs):
        seen.append(cmd)
        return types.SimpleNamespace(returncode=0, stdout="2026.7.4\n", stderr="")
    monkeypatch.setattr(server_manager.subprocess, "run", record)

    host = object.__new__(server_manager.Host)
    assert server_manager.Host.get_ytdlp_version(host) == "2026.7.4"
    assert seen[0][0] == sys.executable


# --------------------------------------------------------------------------- #
# Regression: a deferred update must terminate the supervisor
# --------------------------------------------------------------------------- #

class ShutdownHost:
    """Drives deferred_watcher far enough to run one queued action."""

    def __init__(self, kind="update"):
        self.state = server_manager.BotState.RUNNING
        self.pending = server_manager.PendingAction(kind, "master")
        self.updated = False

    async def update(self, branch):
        # What the real update() leaves behind: bots stopped, listener closed.
        self.updated = True
        self.state = server_manager.BotState.SHUTDOWN
        return f"Updated to branch {branch}"

    async def reboot(self):
        return "rebooted"

    async def run_ytdlp_upgrade(self):
        return "upgraded"


def test_deferred_update_exits_the_process(monkeypatch):
    """CI's `deploy` queues `update ... when-idle` and returns instantly, so the
    workflow goes green long before this runs. When it did run, update() stopped
    the bots and closed the control port but nothing exited - leaving bots
    offline, the manager unreachable, and systemd seeing the unit as active so
    Restart=always never fired."""
    monkeypatch.setattr(server_manager, "DEFERRED_POLL_INTERVAL", 0)
    monkeypatch.setattr(server_manager.status_module, "is_idle",
                        lambda *a, **k: (True, "idle"))

    exited = []
    monkeypatch.setattr(server_manager, "force_exit",
                        lambda: exited.append(True))

    host = ShutdownHost()
    asyncio.run(asyncio.wait_for(
        server_manager.Host.deferred_watcher(host), timeout=5))

    assert host.updated is True
    assert exited == [True], "the supervisor stayed alive with everything down"


def test_deferred_reboot_does_not_exit(monkeypatch):
    """Only a shutdown-marking action should terminate the process; a plain
    deferred reboot must leave the supervisor serving its port."""
    monkeypatch.setattr(server_manager, "DEFERRED_POLL_INTERVAL", 0)
    monkeypatch.setattr(server_manager.status_module, "is_idle",
                        lambda *a, **k: (True, "idle"))

    exited = []
    monkeypatch.setattr(server_manager, "force_exit",
                        lambda: exited.append(True))

    host = ShutdownHost("reboot")

    async def scenario():
        task = asyncio.create_task(
            server_manager.Host.deferred_watcher(host))
        await asyncio.sleep(0.05)
        task.cancel()

    asyncio.run(scenario())
    assert exited == []


def test_closing_the_listener_does_not_wake_the_accept_loop():
    """Documents WHY the explicit force_exit() above is mandatory.

    update() closes the listener socket, which looks like it should end the
    accept loop. It does not: asyncio has the fd registered in its selector, and
    closing it underneath a pending sock_accept() leaves the future pending
    forever rather than raising. So the loop never notices, start() never
    returns, and the process lives on with the bots stopped and the port shut -
    which is precisely the state a deferred deploy used to leave behind.

    If a future Python or asyncio version starts raising here, this test fails
    and the `except OSError` guard in start() becomes the live path. Either way
    the process must not survive; nothing should depend on which one happens.
    """
    host = object.__new__(server_manager.Host)
    host.state = server_manager.BotState.RUNNING
    host.listener_socket = socket.socket()
    host.listener_socket.bind(("127.0.0.1", 0))
    host.listener_socket.listen(1)
    host.listener_socket.setblocking(False)

    async def scenario():
        task = asyncio.create_task(server_manager.Host.start(host, False))
        await asyncio.sleep(0.05)
        host.listener_socket.close()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=0.5)
            return "loop exited"
        except asyncio.TimeoutError:
            return "still hanging"
        finally:
            task.cancel()

    outcome = asyncio.run(scenario())

    # Platform-dependent, and that is exactly the point: nothing may rely on it.
    # Linux (the deployment platform) leaves the future pending; Windows wakes
    # the accept. Asserted per-platform so the Linux guarantee stays pinned.
    assert outcome in ("loop exited", "still hanging")
    if os.name != "nt":
        assert outcome == "still hanging", (
            "Linux used to leave sock_accept pending forever after the listener "
            "closed. If that changed, re-read the shutdown path - but the "
            "explicit force_exit() must remain either way.")


# --------------------------------------------------------------------------- #
# Regression: stopped bots must be reaped, and pkill must not be used
# --------------------------------------------------------------------------- #

class FakeProc:
    def __init__(self, pid=4242, stubborn=False):
        self.pid = pid
        self.stubborn = stubborn
        self.waited = 0
        self.signals = []
        self.terminated = False
        self.killed = False

    def wait(self, timeout=None):
        self.waited += 1
        if self.stubborn and self.waited == 1:
            raise subprocess.TimeoutExpired("main.py", timeout)
        return 0

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def _stop_host(proc):
    host = object.__new__(server_manager.Host)
    host.state = server_manager.BotState.RUNNING
    host.process = proc
    host.errors = "some errors"
    return host


# os.killpg/os.getpgid/SIGKILL are POSIX-only; on Windows _stop_process_tree
# falls back to Popen.terminate()/kill(). These tests assert the same contract on
# both, so they run everywhere rather than only on the deployment platform.
HAS_PROCESS_GROUPS = hasattr(os, "killpg") and hasattr(os, "getpgid")


def _patch_group_signals(monkeypatch, sink):
    """Intercepts whichever mechanism this platform actually uses."""
    if HAS_PROCESS_GROUPS:
        monkeypatch.setattr(server_manager.os, "getpgid", lambda pid: pid,
                            raising=False)
        monkeypatch.setattr(server_manager.os, "killpg",
                            lambda pgid, sig: sink.append(sig), raising=False)


def _stop_signals(sink, proc):
    """Normalises 'what did we send' across platforms: on POSIX read the
    intercepted signals, on Windows read which Popen methods were called."""
    if HAS_PROCESS_GROUPS:
        return list(sink)
    calls = []
    if proc.terminated:
        calls.append("terminate")
    if proc.killed:
        calls.append("kill")
    return calls


def test_stop_reaps_the_child(monkeypatch):
    """Without a wait() the child lingers as <defunct> for the supervisor's whole
    life. `ps -ax` on the VPS showed one zombie per stop."""
    sent = []
    _patch_group_signals(monkeypatch, sent)
    monkeypatch.setattr(server_manager.status_module, "clear_status",
                        lambda *a, **k: None)

    proc = FakeProc()
    host = _stop_host(proc)
    asyncio.run(server_manager.Host.stop(host))

    assert proc.waited >= 1, "child was never reaped - it becomes a zombie"
    expected = [signal.SIGTERM] if HAS_PROCESS_GROUPS else ["terminate"]
    assert _stop_signals(sent, proc) == expected
    assert host.state is server_manager.BotState.STOPPED


def test_stop_escalates_when_the_child_ignores_the_first_request(monkeypatch):
    sent = []
    _patch_group_signals(monkeypatch, sent)
    monkeypatch.setattr(server_manager.status_module, "clear_status",
                        lambda *a, **k: None)

    proc = FakeProc(stubborn=True)
    asyncio.run(server_manager.Host.stop(_stop_host(proc)))

    if HAS_PROCESS_GROUPS:
        assert _stop_signals(sent, proc) == [signal.SIGTERM, signal.SIGKILL]
    else:
        assert _stop_signals(sent, proc) == ["terminate", "kill"]
    assert proc.waited == 2, "the forced kill must also be reaped"


def test_stop_never_shells_out_to_pkill(monkeypatch):
    """`pkill -f <pid>` matched that number anywhere in any command line, so it
    could kill unrelated processes."""
    _patch_group_signals(monkeypatch, [])
    monkeypatch.setattr(server_manager.status_module, "clear_status",
                        lambda *a, **k: None)
    calls = []
    monkeypatch.setattr(server_manager.os, "system",
                        lambda cmd: calls.append(cmd) or 0)

    asyncio.run(server_manager.Host.stop(_stop_host(FakeProc())))
    assert not any("pkill" in c for c in calls), calls


def test_stop_works_without_process_groups(monkeypatch):
    """Explicitly exercises the Windows branch even on Linux: os.killpg missing
    used to raise AttributeError, so the bots could not be stopped at all."""
    monkeypatch.delattr(server_manager.os, "killpg", raising=False)
    monkeypatch.delattr(server_manager.os, "getpgid", raising=False)
    monkeypatch.setattr(server_manager.status_module, "clear_status",
                        lambda *a, **k: None)

    proc = FakeProc()
    asyncio.run(server_manager.Host.stop(_stop_host(proc)))
    assert proc.terminated is True
    assert proc.waited >= 1


@pytest.mark.skipif(
    os.name == "nt",
    reason="On Windows SO_REUSEADDR permits a second bind to the same port, so "
           "the guard cannot fire. Linux is the deployment platform.")
def test_second_supervisor_refuses_to_start():
    """Two supervisors would start and stop main.py behind each other's backs."""
    first = socket.socket()
    first.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    first.bind(("127.0.0.1", 0))
    first.listen(1)
    port = first.getsockname()[1]
    try:
        with pytest.raises(SystemExit) as excinfo:
            server_manager.Host(port)
        assert "already running" in str(excinfo.value)
        assert "grep server_manager" in str(excinfo.value)
    finally:
        first.close()


# --------------------------------------------------------------------------- #
# `<verb>-idle` aliases
# --------------------------------------------------------------------------- #

class CommandHost:
    """Records which branch process_command() dispatched to."""

    def __init__(self):
        self.state = server_manager.BotState.RUNNING
        self.pending = None
        self.calls = []

    async def reboot(self):
        self.calls.append("reboot-now")
        return "rebooted"

    async def update(self, branch):
        self.calls.append(f"update-now:{branch}")
        return "updated"

    async def upgrade_ytdlp(self, deferred=False):
        self.calls.append(f"upgrade:deferred={deferred}")
        return "upgraded"

    def queue_action(self, kind, branch=None):
        self.calls.append(f"queued:{kind}:{branch}")
        return f"queued {kind}"

    def get_current_branch(self):
        return "master"


def _run(host, command):
    monkey = server_manager.server_manager_password
    return asyncio.run(server_manager.Host.process_command(
        host, f"{monkey} {command}"))


@pytest.mark.parametrize("command", [
    "reboot-idle", "reboot_idle", "reboot when-idle",
    "REBOOT-IDLE", "restart-idle", "reload-idle",
])
def test_deferred_reboot_aliases_queue(command):
    host = CommandHost()
    _run(host, command)
    assert host.calls == ["queued:reboot:None"], command


@pytest.mark.parametrize("command", ["reboot", "restart", "reload"])
def test_immediate_reboot_still_immediate(command):
    host = CommandHost()
    _run(host, command)
    assert host.calls == ["reboot-now"], command


def test_update_idle_keeps_its_branch_argument():
    host = CommandHost()
    _run(host, "update-idle develop")
    assert host.calls == ["queued:update:develop"]


def test_update_idle_defaults_to_the_current_branch():
    host = CommandHost()
    _run(host, "update-idle")
    assert host.calls == ["queued:update:master"]


def test_upgrade_idle_defers():
    host = CommandHost()
    _run(host, "upgrade-idle")
    assert host.calls == ["upgrade:deferred=True"]

    host = CommandHost()
    _run(host, "upgrade")
    assert host.calls == ["upgrade:deferred=False"]


def test_a_bare_idle_verb_is_not_stripped_into_nothing():
    """Guards the len() check: "-idle" alone must not become an empty verb."""
    host = CommandHost()
    assert _run(host, "-idle") is None
    assert host.calls == []


def test_help_lists_both_forms_side_by_side():
    from hosting import client_manager
    for verb in ("reboot-idle", "update-idle", "upgrade-idle"):
        assert verb in client_manager.HELP_TEXT, verb
