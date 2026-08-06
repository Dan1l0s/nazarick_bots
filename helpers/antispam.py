"""Anti-spam scoring for incoming messages.

Replaces the two-signal check that lived in admin_bot: one signal timed the
author out, two banned them. That was easy to evade (an uppercased
`DISCORDAPP.COM/INVITE` slipped straight past) and easy to trip innocently
(linking your own server was punished the same as advertising someone else's).

Design notes worth knowing before changing anything here:

**Normalise, then match.** Spam is deliberately obfuscated - `discord . gg`,
`discord[dot]gg`, zero-width characters between letters, Cyrillic homoglyphs
that render identically to Latin. Matching raw text means maintaining a pattern
per trick. Normalising first means one pattern covers all of them.

**Score, don't branch.** Each signal contributes; the total picks an action.
A single weak signal should not ban anyone, and several weak signals together
usually should do something.

**Your own server is not spam.** Invites to guilds in `allowed_guild_ids`, and
any code in `allowed_invite_codes`, score nothing. Without this the filter
punishes members for sharing the server they are in, which is the fastest way to
have it turned off.

**Admins are exempt**, checked by the caller before this module is consulted.
"""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #

#: Characters inserted purely to break substring matching. Zero-width space,
#: zero-width non-joiner/joiner, word joiner, soft hyphen, BOM, and the
#: right-to-left/left-to-right marks.
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠­﻿‎‏"))

#: Cyrillic and Greek letters that render like Latin ones. `disсord.gg` with a
#: Cyrillic 'с' looks identical and matches nothing without this.
_HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "і": "i", "ѕ": "s", "ԁ": "d", "ｇ": "g", "ɡ": "g", "ѵ": "v", "һ": "h",
    "ν": "v", "ο": "o", "ρ": "p", "τ": "t", "ι": "i", "κ": "k", "α": "a",
})

#: Written-out or bracketed separators standing in for a literal dot.
_DOT_SPELLINGS = (
    r"\s*\[\s*\.?\s*dot\s*\.?\s*\]\s*",
    r"\s*\(\s*\.?\s*dot\s*\.?\s*\)\s*",
    r"\s+dot\s+",
    r"\s*\[\s*\.\s*\]\s*",
    r"\s*\(\s*\.\s*\)\s*",
    r"\s*\{\s*\.\s*\}\s*",
)


def normalize(text: str) -> str:
    """Folds away the tricks used to hide a URL from a substring match.

    Lowercases, strips invisible characters, maps homoglyphs to ASCII, turns
    written-out dots into real ones, and closes gaps around punctuation so
    `discord . gg` and `discord.gg` compare equal.
    """
    if not text:
        return ""

    # NFKC first: collapses fullwidth and other compatibility forms.
    folded = unicodedata.normalize("NFKC", text).lower()
    folded = folded.translate(_INVISIBLE)
    folded = folded.translate(_HOMOGLYPHS)

    for pattern in _DOT_SPELLINGS:
        folded = re.sub(pattern, ".", folded)

    # Close whitespace around dots and slashes, so "discord . gg / abc" reads as
    # "discord.gg/abc" - without collapsing all whitespace, which would glue
    # unrelated words together and cause false matches.
    folded = re.sub(r"\s*([./:])\s*", r"\1", folded)
    return folded


def normalize_for_compare(text: str) -> str:
    """Normalisation for deciding whether two messages are *the same* message.

    Adds whitespace-run collapsing on top of `normalize`, so retyping the same
    line with different spacing still counts as a duplicate. Kept separate
    because collapsing whitespace is wrong for invite matching - it would make
    "my discord gg" look like a link.
    """
    return " ".join(normalize(text).split())


def _despace(text: str) -> str:
    """Every space removed. Used only as a second pass for invite matching.

    Catches the "d i s c o r d . g g" evasion, which survives `normalize`
    because that deliberately preserves word boundaries. Applied as an extra
    check rather than as the primary form, so ordinary prose is still matched
    with its spacing intact.
    """
    return re.sub(r"\s+", "", text)


# --------------------------------------------------------------------------- #
# Signals
# --------------------------------------------------------------------------- #

#: Invite hosts, matched against normalised text. Covers Discord's own domains
#: plus the common third-party vanity redirectors.
_INVITE_PATTERN = re.compile(
    r"(?:"
    r"discord(?:app)?\.com/invite|"
    r"discord\.gg|"
    r"discord\.me|"
    r"discord\.io|"
    r"discord\.li|"
    r"discord\.link|"
    r"dsc\.gg|"
    r"invite\.gg|"
    r"disboard\.org/server/join"
    r")/?([a-z0-9\-_]+)?"
)

#: Link shorteners, which hide the destination. Not spam alone, but a signal.
_SHORTENER_PATTERN = re.compile(
    r"\b(?:bit\.ly|tinyurl\.com|goo\.gl|t\.co|is\.gd|cutt\.ly|rb\.gy|shorturl\.at)\b")

#: Phrases from the standard Discord scam repertoire. Each is weak on its own -
#: they earn their weight by co-occurring with a link.
_SCAM_PHRASES = (
    "free nitro",
    "nitro giveaway",
    "free discord nitro",
    "steam gift",
    "free steam",
    "claim your gift",
    "airdrop",
    "free robux",
    "free vbucks",
    "crypto giveaway",
    "double your",
    "@everyone free",
    "click here to claim",
    "you have been selected",
    "dm me to claim",
)

#: Terms the server treats as disallowed regardless of context. Kept separate
#: from the scam list because these are a policy choice, not fraud detection -
#: they carry the weight the original code gave them.
_BANNED_TERMS = (
    "leaks",
    ":underage:",
)


@dataclass
class SpamConfig:
    """Thresholds and weights. Overridden from configs.public_config."""

    # Score at which each action kicks in. Ordered, and checked highest first.
    ban_score: int = 100
    timeout_score: int = 50
    delete_score: int = 25

    timeout_seconds: int = 2_332_800          # 27 days, as before

    # Signal weights.
    invite_weight: int = 50
    banned_term_weight: int = 50
    scam_phrase_weight: int = 30
    shortener_weight: int = 15
    mass_mention_weight: int = 30
    flood_weight: int = 40
    duplicate_weight: int = 35
    all_caps_weight: int = 10

    # Signal thresholds.
    mass_mention_limit: int = 5               # mentions in one message
    flood_messages: int = 5                   # messages...
    flood_window_seconds: int = 8             # ...within this window
    duplicate_messages: int = 3               # identical messages...
    duplicate_window_seconds: int = 60        # ...within this window
    min_caps_length: int = 20                 # ignore short shouty messages
    caps_ratio: float = 0.8

    # Invites that are fine: your own guilds, and any explicitly allowed code.
    allowed_guild_ids: tuple[int, ...] = ()
    allowed_invite_codes: tuple[str, ...] = ()


@dataclass
class Verdict:
    """The outcome for one message."""

    score: int = 0
    reasons: list[str] = field(default_factory=list)

    def add(self, points: int, reason: str) -> None:
        self.score += points
        self.reasons.append(reason)

    def action(self, config: SpamConfig) -> str:
        """One of "ban", "timeout", "delete", "none"."""
        if self.score >= config.ban_score:
            return "ban"
        if self.score >= config.timeout_score:
            return "timeout"
        if self.score >= config.delete_score:
            return "delete"
        return "none"

    def summary(self) -> str:
        return f"score {self.score}: " + "; ".join(self.reasons) if self.reasons else "clean"


def find_invites(text: str) -> list[str]:
    """Returns the invite codes present in `text`, normalising obfuscation first.

    Scans two forms: the normalised text, and the same with every space removed.
    The second pass catches "d i s c o r d . g g", which survives `normalize`
    precisely because that preserves word boundaries on purpose.

    A code may be absent (bare domain with no path); those come back as "" so the
    caller still learns that an invite host was mentioned.
    """
    normalized = normalize(text)
    codes = [(m.group(1) or "") for m in _INVITE_PATTERN.finditer(normalized)]

    # Second pass with spaces removed, to catch "d i s c o r d . g g".
    #
    # Removing spaces also welds neighbouring words onto a code - "discord.gg/aaa
    # and discord.gg/bbb" becomes ".../aaaanddiscord.gg/bbb", yielding a bogus
    # "aaaanddiscord". Codes that merely extend one already found are therefore
    # discarded; a genuinely new spaced-out invite does not start with an
    # existing code and survives.
    for match in _INVITE_PATTERN.finditer(_despace(normalized)):
        code = match.group(1) or ""
        if code in codes:
            continue
        if any(existing and code.startswith(existing) for existing in codes):
            continue
        codes.append(code)
    return codes


class MessageHistory:
    """Per-user recent message timestamps and hashes, for flood and duplicate
    detection.

    Bounded: entries older than the longest window are discarded on access, and
    the number of tracked users is capped, so a raid cannot grow this without
    limit.
    """

    def __init__(self, max_users: int = 10_000):
        self._events: dict[int, list[tuple[float, str]]] = {}
        self._max_users = max_users

    def record(self, user_id: int, content: str, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        if user_id not in self._events and len(self._events) >= self._max_users:
            # Evict whoever has been quiet longest.
            oldest = min(self._events, key=lambda uid: self._events[uid][-1][0])
            del self._events[oldest]
        self._events.setdefault(user_id, []).append((now, normalize_for_compare(content)))

    def prune(self, user_id: int, horizon: float, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        events = self._events.get(user_id)
        if not events:
            return
        cutoff = now - horizon
        self._events[user_id] = [e for e in events if e[0] >= cutoff]
        if not self._events[user_id]:
            del self._events[user_id]

    def count_since(self, user_id: int, window: float, now: float | None = None) -> int:
        now = now if now is not None else time.time()
        cutoff = now - window
        return sum(1 for stamp, _ in self._events.get(user_id, []) if stamp >= cutoff)

    def count_duplicates(self, user_id: int, content: str, window: float,
                         now: float | None = None) -> int:
        now = now if now is not None else time.time()
        cutoff = now - window
        target = normalize_for_compare(content)
        return sum(1 for stamp, text in self._events.get(user_id, [])
                   if stamp >= cutoff and text == target)

    def forget(self, user_id: int) -> None:
        self._events.pop(user_id, None)

    def tracked_users(self) -> int:
        return len(self._events)


def analyse(content: str, *, config: SpamConfig, mention_count: int = 0,
            user_id: int | None = None, history: MessageHistory | None = None,
            now: float | None = None) -> Verdict:
    """Scores one message.

    `content` is the raw text. `mention_count` is the number of user+role
    mentions - passed in rather than parsed, since the caller already has the
    resolved objects. `history` enables flood and duplicate detection; without
    it those signals are skipped, which is what makes this function usable on a
    single message in isolation (and easy to test).
    """
    verdict = Verdict()
    normalized = normalize(content)

    # --- invites -----------------------------------------------------------
    codes = find_invites(content)
    if codes:
        allowed = {c.lower() for c in config.allowed_invite_codes}
        disallowed = [c for c in codes if c.lower() not in allowed]
        if disallowed:
            verdict.add(config.invite_weight,
                        f"invite link ({len(disallowed)} disallowed)")

    # --- explicitly banned terms ------------------------------------------
    hit_terms = [term for term in _BANNED_TERMS if term in normalized]
    if hit_terms:
        verdict.add(config.banned_term_weight,
                    f"banned term(s): {', '.join(hit_terms)}")

    # --- scam phrasing -----------------------------------------------------
    hit_phrases = [phrase for phrase in _SCAM_PHRASES if phrase in normalized]
    if hit_phrases:
        verdict.add(config.scam_phrase_weight,
                    f"scam phrase(s): {', '.join(hit_phrases[:3])}")

    # --- link shorteners ---------------------------------------------------
    if _SHORTENER_PATTERN.search(normalized):
        verdict.add(config.shortener_weight, "link shortener")

    # --- mass mentions -----------------------------------------------------
    if mention_count >= config.mass_mention_limit:
        verdict.add(config.mass_mention_weight, f"{mention_count} mentions")

    # --- shouting ----------------------------------------------------------
    letters = [c for c in content if c.isalpha()]
    if len(letters) >= config.min_caps_length:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio >= config.caps_ratio:
            verdict.add(config.all_caps_weight, f"{upper_ratio:.0%} caps")

    # --- rate-based signals ------------------------------------------------
    if history is not None and user_id is not None:
        recent = history.count_since(user_id, config.flood_window_seconds, now)
        if recent >= config.flood_messages:
            verdict.add(config.flood_weight,
                        f"{recent} messages in {config.flood_window_seconds}s")

        # Empty text is not a repeated message. Embed-only, attachment-only and
        # sticker-only messages all normalize to "", so without this guard
        # posting three images in a minute scores as spamming the same message
        # three times.
        if normalized:
            duplicates = history.count_duplicates(
                user_id, content, config.duplicate_window_seconds, now)
            if duplicates >= config.duplicate_messages:
                verdict.add(config.duplicate_weight,
                            f"same message {duplicates} times")

    return verdict


def config_from_public(public_config, guild_ids: tuple[int, ...] = ()) -> SpamConfig:
    """Builds a SpamConfig from configs.public_config.antispam, if present.

    Any key absent from the config keeps its default, so adding a knob here does
    not require editing every deployment's config file.
    """
    overrides = getattr(public_config, "antispam", None) or {}
    valid = {f for f in SpamConfig.__dataclass_fields__}
    filtered = {k: v for k, v in overrides.items() if k in valid}
    config = SpamConfig(**filtered)
    if guild_ids and not config.allowed_guild_ids:
        config.allowed_guild_ids = tuple(guild_ids)
    return config
