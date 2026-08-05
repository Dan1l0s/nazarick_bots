"""Decides which captured output is worth reporting to a human.

Two components read the bot process's output: the admin bot (monitor_errors,
which DMs the owners) and the supervisor (pull_errors, which fills `status`).

**This is an allowlist, not a denylist.** Only lines carrying
`logging_setup.ALERT_MARKER` are reported. Severity is decided at the point of
logging, where it is actually known, so this module does not have to guess.

The previous design was the other way round: report everything on stderr unless
a substring matched a growing list of known-harmless phrases. That could not be
made to work. ffmpeg retry chatter, disnake gateway reconnects and
DeprecationWarnings were all reported as incidents, and every new library brings
phrases nobody has denylisted yet. Under an allowlist, unknown output is
silently logged rather than escalated - which is the right default.

The denylist survives only as a diagnostic aid for `status`, which shows recent
unmarked output too; nothing in it can cause a notification.

Line assembly and deduplication still matter and are unchanged in spirit:

  * ffmpeg emits very long HLS URLs and uses bare carriage returns for progress,
    so a fixed-size read regularly cuts a message in half. Lines are reassembled
    before being judged, so a marked multi-line traceback stays intact.
  * repeats collapse, so a failure in a loop produces one report, not a flood.
"""

from __future__ import annotations

import re
import time

from helpers.logging_setup import ALERT_MARKER

#: Routine chatter. Nothing here can trigger a notification any more - marked
#: lines are reported and unmarked lines are not - but `status` uses this to
#: decide which recent output is worth echoing back when you ask for it.
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
    # HLS segment URLs, seen when a fetch is retried mid-playlist
    "index.m3u8",
    "/seg.ts",
    "googlevideo.com",
    # yt-dlp progress
    "[youtube]",
    "[download]",
    "[info]",
    # disnake lifecycle - the gateway reconnects routinely, by design
    "disnake.gateway",
    "disnake.client",
    "disnake.http",
    "attempting a reconnect",
    "has sent the RESUME payload",
    "has successfully RESUMED session",
    "Got a request to RESUME",
    "logging in using static token",
)

# A log record at INFO or DEBUG level.
_INFO_RECORD = re.compile(r"\b(INFO|DEBUG)\b\s+[\w.]+\s*:")

# A Python warning as the warnings module prints it:
#     /app/bots/log_bot.py:321: DeprecationWarning: dm_permission is deprecated
# Matched on the `<file>:<line>: <Something>Warning:` shape rather than the
# category name, because a bare "DeprecationWarning" substring also matches real
# failures that merely mention one, e.g.
#     RuntimeError: failed to configure the DeprecationWarning filter
_WARNING_RECORD = re.compile(r":\d+:\s+\w*Warning:\s")

DEDUPE_WINDOW_SECONDS = 3600
DEDUPE_MAX_ENTRIES = 256


def is_reportable(line: str) -> bool:
    """True if `line` was explicitly marked as needing human attention.

    The whole reporting decision, in one predicate. Only logging_setup's alert
    handler produces this marker, and only for ERROR/CRITICAL records from the
    `nazarick.*` namespace - including unhandled exceptions, which the hooks in
    logging_setup route through logging precisely so they are marked.
    """
    return ALERT_MARKER in line


def strip_marker(line: str) -> str:
    """Removes the marker so reports read naturally."""
    return line.replace(ALERT_MARKER + " ", "").replace(ALERT_MARKER, "")


def is_ignorable_error_line(line: str) -> bool:
    """True if `line` is routine noise.

    No longer gates notifications - `is_reportable` does that. Retained because
    `status` uses it to decide which recent unmarked output is worth echoing, and
    because the existing tests document precisely which real-world lines are
    considered noise.
    """
    if not line or not line.strip():
        return True

    if _INFO_RECORD.search(line) or _WARNING_RECORD.search(line):
        return True

    lowered = line.lower()
    return any(fragment.lower() in lowered for fragment in IGNORED_ERROR_FRAGMENTS)


def split_lines(buffer: str, data: str) -> tuple[list[str], str]:
    """Splits `buffer + data` into complete lines plus a leftover remainder.

    Returns (complete_lines, new_buffer). The caller keeps new_buffer and passes
    it back, so a message cut in half by a fixed-size read is judged once, whole.

    Carriage returns count as separators: ffmpeg writes progress with a bare
    `\\r`, so splitting only on `\\n` yields one enormous pseudo-line containing
    many unrelated messages.
    """
    text = buffer + data
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = normalized.split("\n")
    return parts[:-1], parts[-1]


def normalize_for_dedupe(line: str) -> str:
    """Collapses the variable parts of a message so repeats compare equal.

    Timestamps, segment numbers and memory addresses are exactly what would
    otherwise defeat deduplication.
    """
    collapsed = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", line)
    collapsed = re.sub(r"https?://\S+", "URL", collapsed)
    collapsed = re.sub(r"\d+", "N", collapsed)
    return " ".join(collapsed.split())


class ErrorReporter:
    """Accumulates marked lines and suppresses repeats.

    `feed()` takes each raw read; `drain()` returns the text to report, or None.
    Holding the dedupe state here means the admin bot and the supervisor behave
    identically.
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
        """Treats a half-line as complete. Call when the stream ends so a final
        message without a trailing newline is not lost."""
        if self._buffer:
            self._consider(self._buffer)
            self._buffer = ""

    def _consider(self, line: str) -> None:
        if not is_reportable(line):
            return

        text = strip_marker(line)
        now = time.time()
        key = normalize_for_dedupe(text)

        last_seen = self._seen.get(key)
        if last_seen is not None and now - last_seen < self._dedupe_window:
            self.suppressed += 1
            return

        if len(self._seen) >= self._max_entries:
            oldest = min(self._seen, key=self._seen.get)
            del self._seen[oldest]

        self._seen[key] = now
        self._pending.append(text)

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
