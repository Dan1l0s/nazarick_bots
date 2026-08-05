"""Tests for helpers/log_filter.py.

The fixtures below are the *actual* messages that were DM'd to the owner in
production after error reporting was un-broken. They are the specification: none
of them should ever page anyone again.
"""

import time

import pytest

import bots.admin_bot as admin_bot
from helpers import log_filter
from hosting import server_manager


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
    assert log_filter.is_ignorable_error_line(line) is True


@pytest.mark.parametrize("line", REPORTED_IN_PRODUCTION)
def test_suppressed_by_both_readers(line):
    """The admin bot (which DMs) and the supervisor (which fills `status`) must
    agree, or you get a DM about something `status` calls healthy."""
    assert admin_bot.is_ignorable_error_line(line) is True
    assert server_manager.is_ignorable_error_line(line) is True


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
def test_real_problems_still_reported(line):
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
    text = FFMPEG_HLS_NOISE + "\n"
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
    reporter.feed("Traceback (most recent call last):")   # no newline yet
    assert reporter.drain() is None
    reporter.flush_buffer()
    assert "Traceback" in reporter.drain()


# --------------------------------------------------------------------------- #
# Deduplication - so nothing can spam, even if it slips the denylist
# --------------------------------------------------------------------------- #

def test_repeats_are_collapsed():
    reporter = log_filter.ErrorReporter()
    for _ in range(50):
        reporter.feed("RuntimeError: the same thing keeps happening\n")
    report = reporter.drain()
    assert report.count("RuntimeError") == 1
    assert "49 repeat(s) suppressed" in report


def test_repeats_differing_only_in_numbers_are_collapsed():
    """Segment numbers, timestamps and addresses are exactly what would defeat
    naive deduplication."""
    reporter = log_filter.ErrorReporter()
    for n in range(2009901, 2009911):
        reporter.feed(f"Custom failure at segment {n} address 0x7f4a{n:x}\n")
    report = reporter.drain()
    assert report.count("Custom failure") == 1


def test_distinct_errors_are_all_reported():
    reporter = log_filter.ErrorReporter()
    reporter.feed("RuntimeError: first problem\n")
    reporter.feed("ValueError: second problem\n")
    report = reporter.drain()
    assert "first problem" in report
    assert "second problem" in report


def test_a_repeat_reports_again_after_the_window_expires():
    reporter = log_filter.ErrorReporter(dedupe_window=0)
    reporter.feed("RuntimeError: boom\n")
    assert reporter.drain() is not None
    time.sleep(0.01)
    reporter.feed("RuntimeError: boom\n")
    assert reporter.drain() is not None


def test_dedupe_memory_is_bounded():
    reporter = log_filter.ErrorReporter(max_entries=8)
    for n in range(50):
        reporter.feed(f"UniqueError kind{chr(65 + n % 26)}{n // 26}: boom\n")
    reporter.drain()
    assert len(reporter._seen) <= 8


def test_drain_is_empty_when_nothing_was_reportable():
    reporter = log_filter.ErrorReporter()
    reporter.feed(DISNAKE_RECONNECT + "\n")
    reporter.feed(FFMPEG_HLS_NOISE + "\n")
    assert reporter.drain() is None


def test_drain_clears_state():
    reporter = log_filter.ErrorReporter()
    reporter.feed("RuntimeError: boom\n")
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
    import main
    assert "disnake" in main.NOISY_LOGGERS


def test_configure_logging_silences_disnake_info(monkeypatch):
    """The actual root cause: configure_logging used to call basicConfig on the
    ROOT logger at INFO, so disnake's gateway chatter reached stderr - which the
    supervisor pipes back as the admin bot's error feed."""
    import logging
    import main

    monkeypatch.delenv("NAZARICK_LOG_LEVEL", raising=False)
    main.configure_logging()

    assert logging.getLogger("disnake").getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("disnake.gateway").isEnabledFor(logging.INFO) is False
    # ...while our own logging still works
    assert logging.getLogger("nazarick.music").isEnabledFor(logging.INFO) is True


def test_configure_logging_does_not_hijack_the_root_logger(monkeypatch):
    import logging
    import main

    root_handlers_before = list(logging.getLogger().handlers)
    monkeypatch.delenv("NAZARICK_LOG_LEVEL", raising=False)
    main.configure_logging()
    assert logging.getLogger().handlers == root_handlers_before


def test_configure_logging_is_idempotent(monkeypatch):
    """The supervisor can restart the bot repeatedly; handlers must not stack up
    and emit each record several times."""
    import logging
    import main

    monkeypatch.delenv("NAZARICK_LOG_LEVEL", raising=False)
    main.configure_logging()
    main.configure_logging()
    main.configure_logging()
    assert len(logging.getLogger("nazarick").handlers) == 1


def test_debug_level_is_opt_in_via_environment(monkeypatch):
    import logging
    import main

    monkeypatch.setenv("NAZARICK_LOG_LEVEL", "DEBUG")
    main.configure_logging()
    assert logging.getLogger("nazarick").isEnabledFor(logging.DEBUG) is True
