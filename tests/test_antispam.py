"""Tests for helpers/antispam.py.

The obfuscation cases matter most: spam is deliberately written to defeat
substring matching, and the old filter fell to the simplest trick there is
(uppercase). Each normalisation case below is a real evasion technique.

Equally important is the other direction - the filter must not punish members
for linking the server they are already in, which is the fastest way to have it
switched off.
"""

import pytest

import configs.public_config as public_config
from helpers import antispam


@pytest.fixture
def config():
    return antispam.SpamConfig(allowed_invite_codes=("ourserver",))


# --------------------------------------------------------------------------- #
# Invite detection, including the evasions that beat the old check
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("text", [
    pytest.param("join discord.gg/abc123", id="plain"),
    pytest.param("join DISCORD.GG/abc123", id="uppercase"),
    pytest.param("join DiScOrD.gG/abc123", id="mixed-case"),
    pytest.param("join discordapp.com/invite/abc123", id="discordapp"),
    pytest.param("join DISCORDAPP.COM/INVITE/abc", id="discordapp-uppercase"),
    pytest.param("join discord.com/invite/abc123", id="discord-com"),
    pytest.param("join discord . gg / abc123", id="spaced"),
    pytest.param("join discord.gg /abc123", id="space-before-path"),
    pytest.param("join discord[dot]gg/abc123", id="bracket-dot"),
    pytest.param("join discord(dot)gg/abc123", id="paren-dot"),
    pytest.param("join discord dot gg/abc123", id="written-dot"),
    pytest.param("join dis​cord.gg/abc123", id="zero-width-space"),
    pytest.param("join discord.gg‌/abc123", id="zero-width-non-joiner"),
    pytest.param("join disсord.gg/abc", id="cyrillic-homoglyph"),
    pytest.param("join d i s c o r d . g g / abc", id="letter-spaced"),
    pytest.param("join ｄｉｓｃｏｒｄ.gg/abc", id="fullwidth"),
    pytest.param("join dsc.gg/abc123", id="dsc-gg"),
    pytest.param("join invite.gg/abc123", id="invite-gg"),
    pytest.param("join discord.me/abc123", id="discord-me"),
    pytest.param("join discord.io/abc123", id="discord-io"),
])
def test_invites_are_detected_through_obfuscation(text):
    assert antispam.find_invites(text), f"missed an invite in {text!r}"


@pytest.mark.parametrize("text", [
    "check out youtube.com/watch?v=abc",
    "my website is example.com",
    "the discord API is documented at discord.com/developers",
    "nothing here at all",
    "",
])
def test_ordinary_messages_contain_no_invites(text):
    assert antispam.find_invites(text) == []


def test_discord_com_developers_is_not_an_invite():
    """`discord.com/invite` is an invite; `discord.com/developers` is not. A
    looser pattern would flag every link to Discord's own documentation."""
    assert antispam.find_invites("see discord.com/developers/docs") == []


def test_multiple_invites_are_all_returned():
    codes = antispam.find_invites("discord.gg/aaa and discord.gg/bbb")
    assert len(codes) == 2
    assert set(codes) == {"aaa", "bbb"}


# --------------------------------------------------------------------------- #
# Allow-listing your own server
# --------------------------------------------------------------------------- #

def test_an_allowed_invite_scores_nothing(config):
    verdict = antispam.analyse("come to discord.gg/ourserver", config=config)
    assert verdict.score == 0
    assert verdict.action(config) == "none"


def test_an_allowed_invite_is_matched_case_insensitively(config):
    verdict = antispam.analyse("discord.gg/OURSERVER", config=config)
    assert verdict.score == 0


def test_a_foreign_invite_is_penalised(config):
    verdict = antispam.analyse("come to discord.gg/somewhereelse", config=config)
    assert verdict.score == config.invite_weight
    assert verdict.action(config) == "timeout"


def test_mixing_allowed_and_foreign_invites_still_penalises(config):
    verdict = antispam.analyse(
        "discord.gg/ourserver and discord.gg/elsewhere", config=config)
    assert verdict.score == config.invite_weight


# --------------------------------------------------------------------------- #
# The action ladder
# --------------------------------------------------------------------------- #

def test_clean_message_does_nothing(config):
    verdict = antispam.analyse("hello everyone, nice server", config=config)
    assert verdict.score == 0
    assert verdict.action(config) == "none"
    assert verdict.summary() == "clean"


def test_invite_alone_is_a_timeout(config):
    """Matches the previous single-signal behaviour."""
    verdict = antispam.analyse("discord.gg/spam", config=config)
    assert verdict.action(config) == "timeout"


def test_invite_plus_banned_term_is_a_ban(config):
    """Matches the previous two-signal behaviour."""
    verdict = antispam.analyse("free leaks at discord.gg/spam", config=config)
    assert verdict.score >= config.ban_score
    assert verdict.action(config) == "ban"


def test_banned_term_alone_is_a_timeout(config):
    verdict = antispam.analyse("selling leaks here", config=config)
    assert verdict.action(config) == "timeout"


def test_weak_signals_accumulate_into_a_delete(config):
    """No single one of these should act, but together they should."""
    verdict = antispam.analyse(
        "FREE NITRO CLICK HERE TO CLAIM NOW bit.ly/xyz", config=config)
    assert verdict.action(config) in ("delete", "timeout", "ban")
    assert len(verdict.reasons) >= 2


def test_shouting_alone_does_nothing(config):
    verdict = antispam.analyse("I AM VERY EXCITED ABOUT THIS GAME", config=config)
    assert verdict.score == config.all_caps_weight
    assert verdict.action(config) == "none"


def test_short_uppercase_message_is_not_shouting(config):
    """"OK!" and "LOL" must not score - the length floor exists for this."""
    verdict = antispam.analyse("LOL OK", config=config)
    assert verdict.score == 0


def test_mass_mentions_are_penalised(config):
    verdict = antispam.analyse("hey", config=config, mention_count=8)
    assert verdict.score == config.mass_mention_weight
    assert "8 mentions" in verdict.summary()


def test_a_couple_of_mentions_is_fine(config):
    verdict = antispam.analyse("hey @a @b", config=config, mention_count=2)
    assert verdict.score == 0


@pytest.mark.parametrize("phrase", [
    "free nitro", "steam gift", "claim your gift", "free robux",
    "crypto giveaway", "you have been selected",
])
def test_scam_phrases_are_recognised(config, phrase):
    verdict = antispam.analyse(f"hey {phrase} for you", config=config)
    assert verdict.score >= config.scam_phrase_weight


def test_link_shorteners_are_a_weak_signal(config):
    verdict = antispam.analyse("look at bit.ly/abc", config=config)
    assert verdict.score == config.shortener_weight
    assert verdict.action(config) == "none"


def test_verdict_summary_lists_reasons(config):
    verdict = antispam.analyse("free leaks discord.gg/x", config=config)
    summary = verdict.summary()
    assert "score" in summary
    assert "invite" in summary
    assert "banned term" in summary


# --------------------------------------------------------------------------- #
# Flood and duplicate detection
# --------------------------------------------------------------------------- #

def test_flood_is_detected(config):
    history = antispam.MessageHistory()
    now = 1000.0
    for i in range(config.flood_messages):
        history.record(1, f"message {i}", now=now + i * 0.1)

    verdict = antispam.analyse("one more", config=config, user_id=1,
                               history=history, now=now + 1)
    assert verdict.score >= config.flood_weight
    assert "messages in" in verdict.summary()


def test_slow_talking_is_not_a_flood(config):
    history = antispam.MessageHistory()
    now = 1000.0
    # Same number of messages, spread beyond the window.
    for i in range(config.flood_messages):
        history.record(1, f"message {i}", now=now + i * 60)

    verdict = antispam.analyse("one more", config=config, user_id=1,
                               history=history, now=now + config.flood_messages * 60)
    assert verdict.score == 0


def test_duplicate_spam_is_detected(config):
    history = antispam.MessageHistory()
    now = 1000.0
    for i in range(config.duplicate_messages):
        history.record(1, "buy my thing", now=now + i)

    verdict = antispam.analyse("buy my thing", config=config, user_id=1,
                               history=history, now=now + 3)
    assert verdict.score >= config.duplicate_weight
    assert "same message" in verdict.summary()


def test_duplicates_are_matched_after_normalisation(config):
    """Retyping with different casing and spacing is still the same message."""
    history = antispam.MessageHistory()
    now = 1000.0
    for variant in ("buy my thing", "BUY MY THING", "buy   my   thing"):
        history.record(1, variant, now=now)

    verdict = antispam.analyse("Buy My Thing", config=config, user_id=1,
                               history=history, now=now + 1)
    assert verdict.score >= config.duplicate_weight


def test_different_messages_are_not_duplicates(config):
    history = antispam.MessageHistory()
    now = 1000.0
    for text in ("hello", "how are you", "nice weather"):
        history.record(1, text, now=now)

    verdict = antispam.analyse("goodbye", config=config, user_id=1,
                               history=history, now=now + 1)
    assert verdict.score == 0


def test_history_is_per_user(config):
    history = antispam.MessageHistory()
    now = 1000.0
    for i in range(config.flood_messages + 2):
        history.record(1, f"m{i}", now=now + i * 0.1)

    quiet_user = antispam.analyse("hi", config=config, user_id=2,
                                 history=history, now=now + 1)
    assert quiet_user.score == 0


def test_rate_signals_are_skipped_without_history(config):
    """analyse() must work on a message in isolation."""
    verdict = antispam.analyse("hello", config=config, user_id=1, history=None)
    assert verdict.score == 0


# --------------------------------------------------------------------------- #
# MessageHistory bookkeeping
# --------------------------------------------------------------------------- #

def test_history_prunes_old_events():
    history = antispam.MessageHistory()
    history.record(1, "old", now=0)
    history.record(1, "new", now=1000)
    history.prune(1, horizon=100, now=1000)
    assert history.count_since(1, window=10_000, now=1000) == 1


def test_history_evicts_the_quietest_user_when_full():
    """A raid must not grow this without bound."""
    history = antispam.MessageHistory(max_users=3)
    for user in range(10):
        history.record(user, "hi", now=1000 + user)
    assert history.tracked_users() <= 3


def test_history_forget():
    history = antispam.MessageHistory()
    history.record(1, "hi")
    history.forget(1)
    assert history.count_since(1, window=100) == 0


def test_prune_of_unknown_user_is_harmless():
    antispam.MessageHistory().prune(999, horizon=10)


# --------------------------------------------------------------------------- #
# Normalisation, directly
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("raw,expected_substring", [
    ("DISCORD.GG", "discord.gg"),
    ("discord . gg", "discord.gg"),
    ("discord[dot]gg", "discord.gg"),
    ("discord dot gg", "discord.gg"),
    ("dis​cord.gg", "discord.gg"),
    ("ｄｉｓｃｏｒｄ.gg", "discord.gg"),
])
def test_normalisation_folds_evasions(raw, expected_substring):
    assert expected_substring in antispam.normalize(raw)


def test_normalisation_does_not_glue_unrelated_words():
    """Collapsing all whitespace would make "cat dog" match "catdog" and cause
    false positives, so only whitespace around punctuation is closed up."""
    assert antispam.normalize("hello world") == "hello world"


def test_normalisation_handles_empty_input():
    assert antispam.normalize("") == ""
    assert antispam.normalize(None) == ""


# --------------------------------------------------------------------------- #
# Config plumbing
# --------------------------------------------------------------------------- #

def test_config_is_built_from_public_config():
    config = antispam.config_from_public(public_config)
    assert config.ban_score == public_config.antispam["ban_score"]
    assert config.allowed_invite_codes == public_config.antispam["allowed_invite_codes"]


def test_unknown_config_keys_are_ignored():
    """A stale key in someone's config must not crash startup."""
    class Fake:
        antispam = {"ban_score": 77, "not_a_real_setting": True}

    config = antispam.config_from_public(Fake)
    assert config.ban_score == 77


def test_missing_config_section_uses_defaults():
    class Fake:
        pass

    config = antispam.config_from_public(Fake)
    assert config.ban_score == antispam.SpamConfig().ban_score


def test_defaults_reproduce_the_previous_behaviour():
    """One signal -> timeout, two -> ban. This was the original contract and
    should not change silently."""
    config = antispam.SpamConfig()
    one = antispam.analyse("discord.gg/x", config=config)
    two = antispam.analyse("leaks at discord.gg/x", config=config)
    assert one.action(config) == "timeout"
    assert two.action(config) == "ban"


# --------------------------------------------------------------------------- #
# Regression: embed-only / attachment-only messages are not "duplicates"
# --------------------------------------------------------------------------- #

def test_empty_content_is_not_a_duplicate():
    """Our log bot posts embeds, whose .content is "". Counting those as
    repeats of each other scored duplicate(35) + flood(40) = timeout, which
    deleted every log embed and timed the log bot out."""
    config = antispam.SpamConfig()
    history = antispam.MessageHistory()
    for _ in range(10):
        history.record(1, "")
    verdict = antispam.analyse("", config=config, user_id=1, history=history)
    assert "same message" not in verdict.summary()


def test_empty_content_still_scores_flood():
    """Flood is about rate, so it must still fire - the bot exemption in
    admin_bot is what protects our own bots, not a hole in the scoring."""
    config = antispam.SpamConfig()
    history = antispam.MessageHistory()
    for _ in range(config.flood_messages):
        history.record(2, "")
    verdict = antispam.analyse("", config=config, user_id=2, history=history)
    assert "messages in" in verdict.summary()


def test_repeated_real_text_is_still_a_duplicate():
    config = antispam.SpamConfig()
    history = antispam.MessageHistory()
    for _ in range(config.duplicate_messages):
        history.record(3, "buy my thing")
    verdict = antispam.analyse("buy my thing", config=config,
                               user_id=3, history=history)
    assert "same message" in verdict.summary()
