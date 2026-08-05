"""Tests for helpers/log_filter.py.

The fixtures below are the *actual* messages that were DM'd to the owner in
production after error reporting was un-broken. They are the specification: none
of them should ever page anyone again.
"""

import time

import pytest

import bots.admin_bot as admin_bot
from helpers import log_filter, logging_setup
from hosting import server_manager


def marked(text: str) -> str:
    """Wraps `text` the way logging_setup's alert handler would.

    ErrorReporter only accepts marked lines now, so tests that exercise
    buffering and dedupe have to mark their input - which is itself the point:
    unmarked output cannot reach a human by any path.
    """
    return "\n".join(f"{logging_setup.ALERT_MARKER} {line}"
                      for line in text.splitlines()) + "\n"


# Verbatim from the owner's DMs.
FFMPEG_HLS_NOISE = (
    "7f4yu35Gg8K8CIDXoRIxgjnSTVKLTAe3AEXGrfUA2kkcLf2tcsxf1mRSO/playlist/"
    "index.m3u8/sq/2009901/goap/clen%3D81894%3Blmt%3D1709632990593990/dur/"
    "5.005/file/seg.ts' with error: 'Invalid argument' when opening url, "
    "retrying with new connection"
)

DISNAKE_RECONNECT = (
    "2026-08-05 21:41:54,333 INFO disnake.gateway: Websocket closed with 1006, "
    "attempting a reconnect."
)

DISNAKE_RESUME_REQUEST = (
    "2026-08-05 21:41:54,333 INFO disnake.client: Got a request to RESUME the websocket."
)

DISNAKE_RESUME_PAYLOAD = (
    "2026-08-05 21:41:54,551 INFO disnake.gateway: Shard ID None has sent the RESUME payload."
)

DISNAKE_RESUMED = (
    '2026-08-05 21:41:54,690 INFO disnake.gateway: Shard ID None has successfully '
    'RESUMED session 3da46608c353c55be6b714ebea6ea948 under trace '
    '["gateway-prd-arm-us-east1-c-vffk",{"micros":3211}].'
)

REPORTED_IN_PRODUCTION = [
    pytest.param(FFMPEG_HLS_NOISE, id="ffmpeg-hls-retry"),
    pytest.param(DISNAKE_RECONNECT, id="disnake-reconnect"),
    pytest.param(DISNAKE_RESUME_REQUEST, id="disnake-resume-request"),
    pytest.param(DISNAKE_RESUME_PAYLOAD, id="disnake-resume-payload"),
    pytest.param(DISNAKE_RESUMED, id="disnake-resumed"),
]


# --------------------------------------------------------------------------- #
# The messages that actually reached Discord must all be suppressed
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("line", REPORTED_IN_PRODUCTION)
def test_production_noise_is_now_suppressed(line):
    """Under the allowlist these are unmarked, so they cannot be reported at
    all - regardless of what the legacy noise list says about them."""
    assert log_filter.is_reportable(line) is False
    assert log_filter.is_ignorable_error_line(line) is True


@pytest.mark.parametrize("line", REPORTED_IN_PRODUCTION)
def test_suppressed_by_both_readers(line):
    """The admin bot (which DMs) and the supervisor (which fills `status`) must
    agree, or you get a DM about something `status` calls healthy."""
    assert admin_bot.is_reportable(line) is False
    assert server_manager.is_reportable(line) is False


def test_both_readers_share_one_fragment_list():
    assert admin_bot.IGNORED_ERROR_FRAGMENTS is log_filter.IGNORED_ERROR_FRAGMENTS
    assert server_manager.IGNORED_ERROR_FRAGMENTS is log_filter.IGNORED_ERROR_FRAGMENTS


# --------------------------------------------------------------------------- #
# ...without suppressing anything that matters
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("line", [
    "Traceback (most recent call last):",
    '  File "main.py", line 42, in <module>',
    "RuntimeError: something actually broke",
    "disnake.errors.Forbidden: 403 Forbidden (error code: 50013): Missing Permissions",
    "sqlite3.OperationalError: database is locked",
    "2026-08-05 21:41:54,333 ERROR nazarick.music: play_loop crashed",
    "2026-08-05 21:41:54,333 WARNING nazarick.admin: could not reach guild",
    "MemoryError",
])
def test_real_problems_are_not_classified_as_noise(line):
    """These are not noise. Whether they get *reported* now depends on whether
    logging marked them - see test_marked_lines_are_reported. Unmarked output is
    logged and not escalated, which is the point of the inversion."""
    assert log_filter.is_ignorable_error_line(line) is False


def test_blank_lines_are_ignored():
    for blank in ("", "   ", "\t"):
        assert log_filter.is_ignorable_error_line(blank) is True


def test_info_records_are_dropped_whatever_the_logger():
    """Defence in depth: main.py holds third-party loggers at WARNING, but if
    anything logs INFO to this stream anyway it must not page anyone."""
    assert log_filter.is_ignorable_error_line(
        "2026-08-05 21:41:54,333 INFO some.new.library: started up") is True
    assert log_filter.is_ignorable_error_line(
        "2026-08-05 21:41:54,333 DEBUG some.new.library: gory detail") is True


def test_error_level_from_an_unknown_logger_is_kept():
    assert log_filter.is_ignorable_error_line(
        "2026-08-05 21:41:54,333 ERROR some.new.library: it broke") is False


# --------------------------------------------------------------------------- #
# Line assembly - the reason the denylist looked leaky
# --------------------------------------------------------------------------- #

def test_split_lines_holds_back_the_incomplete_tail():
    lines, buffer = log_filter.split_lines("", "complete\nincomple")
    assert lines == ["complete"]
    assert buffer == "incomple"


def test_split_lines_rejoins_across_reads():
    lines, buffer = log_filter.split_lines("", "first half ")
    assert lines == []
    lines, buffer = log_filter.split_lines(buffer, "second half\n")
    assert lines == ["first half second half"]
    assert buffer == ""


def test_carriage_returns_are_treated_as_line_breaks():
    """ffmpeg writes progress with a bare \\r. Splitting on \\n alone yields one
    enormous pseudo-line containing many unrelated messages."""
    lines, _ = log_filter.split_lines("", "one\rtwo\rthree\n")
    assert lines == ["one", "two", "three"]


def test_crlf_is_not_turned_into_blank_lines():
    lines, _ = log_filter.split_lines("", "one\r\ntwo\r\n")
    assert lines == ["one", "two"]


@pytest.mark.parametrize("chunk_size", [10, 33, 60, 100, 231])
def test_a_noise_line_split_across_reads_is_still_suppressed(chunk_size):
    """The core regression. A long ffmpeg URL routinely spans a fixed-size read,
    and a fragment of it can be missing the very substring that identifies it as
    noise. Buffering means the line is judged once, whole - at every split point."""
    reporter = log_filter.ErrorReporter()
    text = FFMPEG_HLS_NOISE + "\n"      # unmarked: cannot be reported
    for i in range(0, len(text), chunk_size):
        reporter.feed(text[i:i + chunk_size])
    assert reporter.drain() is None


def test_middle_chunks_alone_would_have_leaked():
    """Why buffering is required, concretely: the interior of that URL contains
    none of the identifying fragments, so an unbuffered reader reports it.
    Verified by scanning every 60-char window - 5 of them would leak."""
    windows = [FFMPEG_HLS_NOISE[a:a + 60] for a in range(0, len(FFMPEG_HLS_NOISE) - 60, 10)]
    leaky = [w for w in windows if not log_filter.is_ignorable_error_line(w)]
    assert leaky, "expected some interior windows to look unfamiliar in isolation"
    # e.g. 'ex.m3u8/sq/2009901/goap/clen%3D81894%3Blmt%3D170963299059399'
    assert log_filter.is_ignorable_error_line(FFMPEG_HLS_NOISE) is True


def test_flush_buffer_reports_a_trailing_partial_error():
    reporter = log_filter.ErrorReporter()
    reporter.feed(f"{logging_setup.ALERT_MARKER} Traceback (most recent call last):")
    assert reporter.drain() is None
    reporter.flush_buffer()
    assert "Traceback" in reporter.drain()


# --------------------------------------------------------------------------- #
# Deduplication - so nothing can spam, even if it slips the denylist
# --------------------------------------------------------------------------- #

def test_repeats_are_collapsed():
    reporter = log_filter.ErrorReporter()
    for _ in range(50):
        reporter.feed(marked("RuntimeError: the same thing keeps happening"))
    report = reporter.drain()
    assert report.count("RuntimeError") == 1
    assert "49 repeat(s) suppressed" in report


def test_repeats_differing_only_in_numbers_are_collapsed():
    """Segment numbers, timestamps and addresses are exactly what would defeat
    naive deduplication."""
    reporter = log_filter.ErrorReporter()
    for n in range(2009901, 2009911):
        reporter.feed(marked(f"Custom failure at segment {n} address 0x7f4a{n:x}"))
    report = reporter.drain()
    assert report.count("Custom failure") == 1


def test_distinct_errors_are_all_reported():
    reporter = log_filter.ErrorReporter()
    reporter.feed(marked("RuntimeError: first problem"))
    reporter.feed(marked("ValueError: second problem"))
    report = reporter.drain()
    assert "first problem" in report
    assert "second problem" in report


def test_a_repeat_reports_again_after_the_window_expires():
    reporter = log_filter.ErrorReporter(dedupe_window=0)
    reporter.feed(marked("RuntimeError: boom"))
    assert reporter.drain() is not None
    time.sleep(0.01)
    reporter.feed(marked("RuntimeError: boom"))
    assert reporter.drain() is not None


def test_dedupe_memory_is_bounded():
    reporter = log_filter.ErrorReporter(max_entries=8)
    for n in range(50):
        reporter.feed(marked(f"UniqueError kind{chr(65 + n % 26)}{n // 26}: boom"))
    reporter.drain()
    assert len(reporter._seen) <= 8


def test_drain_is_empty_when_nothing_was_reportable():
    reporter = log_filter.ErrorReporter()
    reporter.feed(DISNAKE_RECONNECT + "\n")
    reporter.feed(FFMPEG_HLS_NOISE + "\n")
    assert reporter.drain() is None


def test_drain_clears_state():
    reporter = log_filter.ErrorReporter()
    reporter.feed(marked("RuntimeError: boom"))
    assert reporter.drain() is not None
    assert reporter.drain() is None


# --------------------------------------------------------------------------- #
# normalize_for_dedupe
# --------------------------------------------------------------------------- #

def test_normalization_collapses_the_variable_parts():
    a = log_filter.normalize_for_dedupe("failed at 0xdeadbeef segment 1234 url https://a.b/c")
    b = log_filter.normalize_for_dedupe("failed at 0xcafef00d segment 9999 url https://x.y/z")
    assert a == b


def test_normalization_keeps_genuinely_different_messages_apart():
    a = log_filter.normalize_for_dedupe("PermissionError: cannot write")
    b = log_filter.normalize_for_dedupe("MemoryError: out of memory")
    assert a != b


def test_normalization_collapses_whitespace():
    assert (log_filter.normalize_for_dedupe("a    b\tc")
            == log_filter.normalize_for_dedupe("a b c"))


# --------------------------------------------------------------------------- #
# main.py logging configuration - the root cause of the disnake DMs
# --------------------------------------------------------------------------- #

def test_noisy_third_party_loggers_are_listed():
    assert "disnake" in logging_setup.NOISY_LOGGERS


def test_configure_silences_disnake_info(monkeypatch, tmp_path):
    """The original root cause: configure_logging called basicConfig on the ROOT
    logger at INFO, so disnake's gateway chatter reached stderr - which the
    supervisor pipes back as the admin bot's error feed."""
    import logging

    monkeypatch.delenv("NAZARICK_LOG_LEVEL", raising=False)
    logging_setup.configure(log_dir=str(tmp_path), force=True)

    assert logging.getLogger("disnake").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("disnake.gateway").isEnabledFor(logging.INFO) is False
    assert logging.getLogger("nazarick.music").isEnabledFor(logging.INFO) is True


def test_configure_does_not_hijack_the_root_logger(monkeypatch, tmp_path):
    import logging

    before = list(logging.getLogger().handlers)
    monkeypatch.delenv("NAZARICK_LOG_LEVEL", raising=False)
    logging_setup.configure(log_dir=str(tmp_path), force=True)
    assert logging.getLogger().handlers == before


def test_configure_is_idempotent(monkeypatch, tmp_path):
    """The supervisor restarts the bot repeatedly; handlers must not stack up and
    emit each record several times."""
    import logging

    monkeypatch.delenv("NAZARICK_LOG_LEVEL", raising=False)
    for _ in range(3):
        logging_setup.configure(log_dir=str(tmp_path), force=True)
    assert len(logging.getLogger("nazarick").handlers) == 2   # file + alert


def test_debug_level_is_opt_in_via_environment(monkeypatch, tmp_path):
    import logging

    monkeypatch.setenv("NAZARICK_LOG_LEVEL", "DEBUG")
    logging_setup.configure(log_dir=str(tmp_path), force=True)
    assert logging.getLogger("nazarick").isEnabledFor(logging.DEBUG) is True
    # ...but raising our verbosity must not unleash disnake's
    assert logging.getLogger("disnake").isEnabledFor(logging.DEBUG) is False


# --------------------------------------------------------------------------- #
# End to end: what actually reaches a human
# --------------------------------------------------------------------------- #

def _capture_stderr(tmp_path, monkeypatch, emit):
    """Runs `emit(logger)` with logging configured, returning what hit stderr."""
    import io
    import logging

    stream = io.StringIO()
    monkeypatch.setattr("sys.stderr", stream)
    log = logging_setup.configure(log_dir=str(tmp_path), force=True)
    emit(log)
    for handler in log.handlers:
        handler.flush()
    return stream.getvalue()


def test_our_error_is_marked_and_reported(tmp_path, monkeypatch):
    output = _capture_stderr(tmp_path, monkeypatch,
                             lambda log: log.error("the queue exploded"))
    assert logging_setup.ALERT_MARKER in output
    reporter = log_filter.ErrorReporter()
    reporter.feed(output)
    report = reporter.drain()
    assert report is not None and "the queue exploded" in report


def test_our_info_reaches_the_file_but_not_stderr(tmp_path, monkeypatch):
    output = _capture_stderr(tmp_path, monkeypatch,
                            lambda log: log.info("started up"))
    assert output == ""
    assert "started up" in (tmp_path / "nazarick.log").read_text(encoding="utf-8")


def test_our_warning_is_logged_but_never_reported(tmp_path, monkeypatch):
    """Explicitly what was asked for: no notification for warnings."""
    output = _capture_stderr(tmp_path, monkeypatch,
                            lambda log: log.warning("something looks odd"))
    assert output == ""
    assert "something looks odd" in (tmp_path / "nazarick.log").read_text(encoding="utf-8")


def test_a_third_party_error_is_logged_but_not_reported(tmp_path, monkeypatch):
    """A disnake error belongs in the log; it is not ours to be woken for."""
    import logging

    def emit(_log):
        logging.getLogger("disnake").error("gateway exploded")

    output = _capture_stderr(tmp_path, monkeypatch, emit)
    assert logging_setup.ALERT_MARKER not in output
    assert "gateway exploded" in (tmp_path / "nazarick.log").read_text(encoding="utf-8")


def test_a_traceback_is_marked_on_every_line(tmp_path, monkeypatch):
    """A stack spans many lines and the reader judges lines independently.
    Marking only the first would report the exception without the stack."""
    def emit(log):
        try:
            raise ValueError("inner failure")
        except ValueError:
            log.exception("while doing the thing")

    output = _capture_stderr(tmp_path, monkeypatch, emit)
    lines = [l for l in output.splitlines() if l.strip()]
    assert len(lines) > 3
    assert all(logging_setup.ALERT_MARKER in line for line in lines)

    reporter = log_filter.ErrorReporter()
    reporter.feed(output)
    report = reporter.drain()
    assert "inner failure" in report
    assert "Traceback" in report


def test_warnings_module_output_is_captured_into_logging(tmp_path, monkeypatch):
    """warnings.warn() used to print raw to stderr, which is how a
    DeprecationWarning became an incident."""
    import warnings

    def emit(_log):
        warnings.warn("an old api", DeprecationWarning, stacklevel=1)

    output = _capture_stderr(tmp_path, monkeypatch, emit)
    assert logging_setup.ALERT_MARKER not in output
    assert log_filter.is_reportable(output) is False


def test_strip_marker_leaves_readable_text():
    line = f"{logging_setup.ALERT_MARKER} 2026-01-01 ERROR nazarick.x: boom"
    assert log_filter.strip_marker(line).startswith("2026-01-01")
    assert logging_setup.ALERT_MARKER not in log_filter.strip_marker(line)
