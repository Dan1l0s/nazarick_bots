"""Decides which lines of captured output are worth waking the owner over.

Two components read the bot's output and report problems - the admin bot
(monitor_errors, which DMs) and the supervisor (pull_errors, which feeds
`status`). Both used to keep their own copy of the noise list, which is exactly
how the two drift apart, so the logic lives here once.

Why this exists at all: the original filter was permanently broken (a bare
`or "[hls @"` with no `in line`, making the condition always true), so error
reporting never fired. Fixing it revealed that the raw stream is mostly noise -
ffmpeg retry chatter and disnake INFO records - and a naive "report everything
not on the denylist" approach turns into DM spam.

Three defences, in order of how much they matter:

  1. Suppress at the source. main.py keeps third-party loggers at WARNING, so
     disnake's INFO records never reach the stream. This module also drops
     INFO/DEBUG records defensively, in case a library logs somewhere else.
  2. Reassemble lines before judging them. ffmpeg emits very long URLs and uses
     bare carriage returns for progress, so a fixed-size read can split one
     message across chunks. A half-line can lose the very substring that would
     have identified it as noise, which makes the denylist look leaky.
  3. Deduplicate. Even if something slips through, a burst of near-identical
     messages collapses into one report rather than a stream of DMs.
"""

from __future__ import annotations

import re
import time

# Routine chatter from ffmpeg, HLS streaming, and the network stack. Matched
# case-insensitively as a substring.
IGNORED_ERROR_FRAGMENTS = (
    # ffmpeg protocol-level noise
    "[tls @",
    "[https @",
    "[http @",
    "[hls @",
    "[mp4 @",
    "[matroska",
    "[AVIOContext",
    # transient stream retries - ffmpeg recovers from these on its own
    "retrying with new connection",
    "when opening url",
    "Failed to open segment",
    "Will reconnect at",
    "error while decoding",
    "Non-monotonous DTS",
    "Last message repeated",
    # HLS segment URLs, which appear when a fetch is retried mid-playlist
    "index.m3u8",
    "/seg.ts",
    "googlevideo.com",
    # yt-dlp progress/warnings that are not actionable
    "[youtube]",
    "[download]",
    "[info]",
    "WARNING: [youtube]",
    # disnake lifecycle - the gateway reconnects routinely, by design
    "disnake.gateway",
    "disnake.client",
    "disnake.http",
    "attempting a reconnect",
    "has sent the RESUME payload",
    "has successfully RESUMED session",
    "Got a request to RESUME",
    "Shard ID None has connected to Gateway",
    "logging in using static token",
)

# A log record emitted at INFO or DEBUG level, in the format main.py configures
# ("2026-08-05 21:41:54,333 INFO disnake.gateway: ..."). Nothing informational
# should ever page the owner.
_INFO_RECORD = re.compile(r"\b(INFO|DEBUG)\b\s+[\w.]+\s*:")

# How long an identical message stays suppressed after being reported once.
DEDUPE_WINDOW_SECONDS = 3600

# Upper bound on distinct messages remembered, so a pathological stream cannot
# grow this without limit.
DEDUPE_MAX_ENTRIES = 256


def is_ignorable_error_line(line: str) -> bool:
    """True if `line` is routine noise rather than something to report."""
    if not line or not line.strip():
        return True

    if _INFO_RECORD.search(line):
        return True

    lowered = line.lower()
    return any(fragment.lower() in lowered for fragment in IGNORED_ERROR_FRAGMENTS)


def split_lines(buffer: str, data: str) -> tuple[list[str], str]:
    """Splits `buffer + data` into complete lines plus a leftover remainder.

    Returns (complete_lines, new_buffer). The caller keeps new_buffer and passes
    it back next time, so a message cut in half by a fixed-size read is judged
    once, whole, rather than as two fragments that each look unfamiliar.

    Carriage returns are treated as line separators too: ffmpeg writes progress
    with a bare `\\r`, so splitting only on `\\n` yields one enormous pseudo-line
    containing many unrelated messages.
    """
    text = buffer + data
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = normalized.split("\n")
    # The final element has no terminator yet, so hold it back.
    return parts[:-1], parts[-1]


def normalize_for_dedupe(line: str) -> str:
    """Collapses the variable parts of a message so repeats compare equal.

    Digits, hex blobs and quoted strings are the parts that differ between
    otherwise identical errors (timestamps, segment numbers, memory addresses,
    URLs), and they are what would otherwise defeat deduplication.
    """
    collapsed = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", line)
    collapsed = re.sub(r"https?://\S+", "URL", collapsed)
    collapsed = re.sub(r"\d+", "N", collapsed)
    return " ".join(collapsed.split())


class ErrorReporter:
    """Accumulates report-worthy lines and suppresses repeats.

    `feed()` is called with each raw read; `drain()` returns the text to report
    (or None). Keeping the dedupe state here rather than in the callers means
    the admin bot and the supervisor behave identically.
    """

    def __init__(self, dedupe_window: int = DEDUPE_WINDOW_SECONDS,
                 max_entries: int = DEDUPE_MAX_ENTRIES):
        self._buffer = ""
        self._pending: list[str] = []
        self._seen: dict[str, float] = {}
        self._dedupe_window = dedupe_window
        self._max_entries = max_entries
        self.suppressed = 0

    def feed(self, data: str) -> None:
        lines, self._buffer = split_lines(self._buffer, data)
        for line in lines:
            self._consider(line)

    def flush_buffer(self) -> None:
        """Treats any half-line as complete. Call when the stream ends, so a
        final message without a trailing newline is not lost."""
        if self._buffer:
            self._consider(self._buffer)
            self._buffer = ""

    def _consider(self, line: str) -> None:
        if is_ignorable_error_line(line):
            return

        now = time.time()
        key = normalize_for_dedupe(line)

        last_seen = self._seen.get(key)
        if last_seen is not None and now - last_seen < self._dedupe_window:
            self.suppressed += 1
            return

        if len(self._seen) >= self._max_entries:
            # Drop the oldest entry rather than growing without bound.
            oldest = min(self._seen, key=self._seen.get)
            del self._seen[oldest]

        self._seen[key] = now
        self._pending.append(line)

    def drain(self) -> str | None:
        """Returns the accumulated report and clears it, or None if empty."""
        if not self._pending:
            return None
        report = "\n".join(self._pending)
        self._pending.clear()
        if self.suppressed:
            report += f"\n\n({self.suppressed} repeat(s) suppressed)"
            self.suppressed = 0
        return report
