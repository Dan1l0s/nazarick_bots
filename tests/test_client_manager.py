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
