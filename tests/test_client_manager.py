"""Proves the two failure modes now report differently."""
import socket, threading, sys, pytest
sys.path.insert(0, '.')
import tests.conftest  # noqa
from hosting import client_manager


def test_refused_says_not_running():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    with pytest.raises(RuntimeError) as e:
        client_manager.send_command("status", "127.0.0.1", port, timeout=5)
    assert "not running" in str(e.value)
    assert "could not reach" not in str(e.value)


def test_bound_but_silent_says_no_reply():
    """Mirrors a blocked event loop: bound, backlog accepts the handshake,
    nothing ever answers."""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0)); srv.listen(16)
    port = srv.getsockname()[1]
    with pytest.raises(RuntimeError) as e:
        client_manager.send_command("upgrade", "127.0.0.1", port, timeout=1)
    srv.close()
    msg = str(e.value)
    assert "no reply" in msg and "is running" in msg


def test_ssh_tunnel_command_uses_config_alias_and_loopback_only():
    command = client_manager.build_ssh_tunnel_command(
        "ssh", "Dan1l0s-VPS", 54321, 10000)

    assert command[-1] == "Dan1l0s-VPS"
    assert "127.0.0.1:54321:127.0.0.1:10000" in command
    assert "ExitOnForwardFailure=yes" in command
    assert "-N" in command


def test_ssh_tunnel_starts_on_ephemeral_port_and_closes(monkeypatch):
    captured = {}

    class FakeReservation:
        def bind(self, address):
            assert address == ("127.0.0.1", 0)

        def getsockname(self):
            return "127.0.0.1", 54321

        def close(self):
            pass

    class FakeProbe:
        def close(self):
            pass

    class FakeProcess:
        def __init__(self):
            self.terminated = False

        def poll(self):
            return 0 if self.terminated else None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            return 0

    process = FakeProcess()
    monkeypatch.setattr(client_manager.shutil, "which", lambda name: "ssh.exe")
    monkeypatch.setattr(client_manager.socket, "socket", lambda *args: FakeReservation())
    monkeypatch.setattr(client_manager.socket, "create_connection", lambda *args, **kwargs: FakeProbe())

    def fake_popen(command):
        captured["command"] = command
        return process

    monkeypatch.setattr(client_manager.subprocess, "Popen", fake_popen)

    tunnel = client_manager.SshTunnel("Dan1l0s-VPS", 10000)
    assert tunnel.start() == 54321
    assert captured["command"][-1] == "Dan1l0s-VPS"

    tunnel.close()
    assert process.terminated is True
