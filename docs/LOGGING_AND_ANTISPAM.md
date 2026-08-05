# Logging and anti-spam

Two subsystems added together because they solve the same class of problem:
deciding, in one place, what a human should be bothered with.

## 1. Logging

### The problem this replaces

The admin bot's error feed is the supervisor's captured stderr. Previously
`configure_logging()` called `basicConfig` on the **root** logger at INFO, so
every third-party INFO record — disnake reconnects, ffmpeg HLS retries, yt-dlp
chatter — landed on stderr and was DM'd as an "error".

The first fix attempt was a denylist (`IGNORED_ERROR_FRAGMENTS`): match noisy
phrases and drop them. That is unwinnable. Every new library version invents new
phrasing, and a denylist that grows by guessing eventually suppresses something
real. It already nearly did: matching the bare substring `DeprecationWarning`
also swallowed `RuntimeError: failed to configure the DeprecationWarning filter`.

### The design

Severity is decided **where it is known** — at the call site — and the transport
carries that decision explicitly.

```
                          ┌─ RotatingFileHandler (DEBUG)  → logs/nazarick.log
logging records ──────────┤     everything, unmarked
                          └─ StreamHandler(stderr) (ERROR)
                                + AlertFilter      → only nazarick.* at ERROR+
                                + AlertFormatter   → prefixes [[NZ-ALERT]]
```

`helpers/logging_setup.py`:

| Piece | Role |
| --- | --- |
| `ALERT_MARKER = "[[NZ-ALERT]]"` | The only thing that makes a line reportable. |
| `AlertFilter` | Passes a record only if `levelno >= ERROR` **and** the logger is `nazarick` or a child. Third-party ERRORs are logged, never DM'd. |
| `AlertFormatter` | Marks **every line** of the formatted record, so a multi-line traceback survives the line-oriented reader intact. |
| `RotatingFileHandler` | 10 MB × 10 files. Bounded, unlike the old per-day files that accumulated forever. |
| `captureWarnings(True)` | `warnings.warn` becomes a WARNING record on `py.warnings` → file only. This is why `dm_permission` deprecation spam stopped. |
| `NOISY_LOGGERS` | disnake, websockets, asyncio, urllib3, yt_dlp, aiosqlite → WARNING, `propagate=False`, file handler only. |
| `sys.excepthook`, `threading.excepthook`, `install_asyncio_handler` | Unhandled failures reach a `nazarick` logger, so an allowlist can't silently drop a real crash. |

`helpers/log_filter.py` became a pure allowlist:

```python
def is_reportable(line: str) -> bool:
    return ALERT_MARKER in line
```

`IGNORED_ERROR_FRAGMENTS` and `is_ignorable_error_line` are kept, but demoted to
`status` diagnostics — nothing routes on them any more.

**Consequence worth knowing:** anything that writes to stderr *without* going
through `logging` is now invisible to the reporter. That's intentional (it is
exactly what was generating false alarms), but it means new code must log via
`logging_setup.get_logger(__name__)` rather than `print`.

`hosting/server_manager.py` still writes its own per-day files via
`FileWithDates` — that's the supervisor's own stream, separate and low-volume.

### Verified behaviour

| Event | `logs/nazarick.log` | DM |
| --- | --- | --- |
| `log.info("bot connected")` | yes | no |
| `log.warning("retrying")` | yes | no |
| disnake INFO `Websocket closed with 1006` | yes | no |
| `DeprecationWarning` | yes | no |
| `log.error("play_loop crashed")` | yes | **yes** |
| `log.exception(...)` + traceback | yes | **yes**, all lines |
| third-party ERROR | yes | no |

`NAZARICK_LOG_LEVEL` controls our own verbosity only.

## 2. Anti-spam

`helpers/antispam.py`. Weighted scoring rather than a chain of `if`s, so
thresholds are tunable from `configs/public_config.py` without touching logic.

### Normalization first

Matching raw text is trivially evaded. `normalize()` applies, in order:

1. NFKC (defeats fullwidth `ｄｉｓｃｏｒｄ.ｇｇ` and other compatibility forms)
2. lowercase
3. strip invisible characters — ZWSP, ZWNJ, ZWJ, word-joiner, soft hyphen, BOM, LRM/RLM
4. Cyrillic→Latin homoglyph mapping (`аеорс` → `aeopc`)
5. dot spellings — `[dot]`, ` dot `, `(.)` → `.`
6. close spaces around `.` `/` `:`

`_despace()` runs a second pass with all whitespace removed, catching
`d i s c o r d . g g`. Newly-found codes that merely extend an already-found one
are discarded, because despacing welds `.../aaa and discord.gg/bbb` into a bogus
`aaaanddiscord`.

`normalize_for_compare()` is separate — it collapses whitespace runs instead of
deleting them, which is what duplicate detection needs.

### Signals and weights

| Signal | Weight | Notes |
| --- | --- | --- |
| Discord invite | 50 | 9 host forms incl. `dsc.gg`, `disboard.org/server/join` |
| Banned term | 50 | `leaks`, `:underage:` |
| Flood | 40 | 5 messages / 8 s |
| Duplicates | 35 | 3 identical / 60 s |
| Scam phrase | 30 | `free nitro`, `steam gift`, `free robux`, … |
| Mass mention | 30 | > 5 user+role mentions |
| Link shortener | 15 | `bit.ly`, `t.co`, … |
| ALL CAPS | 10 | ≥ 20 chars, ≥ 80 % caps |

Thresholds: **≥ 100** ban, **≥ 50** timeout (27 days), **≥ 25** delete.

The additive design preserves the old two-signal behaviour — invite + banned
term is 50 + 50 = ban — while letting one strong signal act alone and weak
signals accumulate.

### Allowlist

`allowed_invite_codes` in `public_config.py` defaults to `("nazarick",)`.
Without it the filter punishes members for linking the server they're already
in, which is the fastest route to having moderation switched off. Admins are
exempt (`helpers.is_admin`).

`MessageHistory` tracks up to 10 000 users, evicting the quietest, so flood
state can't grow without bound.

### Tuning

Everything is in the `antispam` dict in `configs/public_config.py`;
`config_from_public()` filters to valid `SpamConfig` fields, so an unknown key is
ignored rather than crashing at startup. To make the filter advisory, raise
`ban_score` and `timeout_score` above any reachable total and leave
`delete_score` — messages get removed and logged, nobody is punished.

## Tests

`tests/test_antispam.py` (71) and `tests/test_log_filter.py` (55), the latter
including end-to-end assertions that our ERROR is marked and reportable, our
INFO/WARNING reach the file but not stderr, a third-party ERROR is logged but
not marked, and a traceback is marked on every line.
