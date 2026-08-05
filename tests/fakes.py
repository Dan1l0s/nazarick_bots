"""Permissive stand-ins for disnake objects, for testing helpers/embedder.py.

`Anything` answers any attribute access with another `Anything`, which lets a
single object stand in for the wildly different audit-log entry shapes the
embedder handles (`entry.extra.channel.mention`, `entry.before.colour.r`,
`entry.after.permissions.administrator`, ...) without hand-building 60 fixtures.

A few attribute names get real typed values because the embedder does actual
arithmetic or dict lookups on them - see TYPED_ATTRS. Without those the sweep
would fail on `hex()`, `emojis[...]`, and similar rather than on genuine bugs.

`__dir__` reports every attribute name listed in public_config's logging
allowlists, so the `for attr in dir(obj): if attr in public_config.<list>`
loops inside the embedder actually execute instead of finding nothing.
"""

from __future__ import annotations

from datetime import datetime, timezone

import configs.public_config as public_config

# Attribute names the embedder treats as numbers, booleans, or dict keys.
TYPED_ATTRS = {
    # rgb_to_hex() calls hex() on these
    "r": 128, "g": 64, "b": 255,
    # arithmetic / f-string counts
    "count": 3,
    "members_removed": 7,
    "delete_members_days": 30,
    "uses": 2,
    "max_uses": 10,
    "max_age": 3600,
    "duration": 125,
    "id": 123456789012345678,
    "position": 5,
    "bitrate": 64000,
    "user_limit": 10,
    "slowmode_delay": 0,
    # joined with str.join() in the tag-listing loops, so must be a real str
    "name": "SomeName",
    # booleans
    "nsfw": False,
    "pinned": False,
    "afk": False,
    "archived": False,
    "locked": False,
    "invitable": True,
    "available": True,
    "temporary": False,
    "mentionable": True,
    "hoist": False,
    "managed": False,
    "bot": False,
    "pending": False,
    "self_mute": True,
    "self_deaf": False,
    "self_stream": True,
    "self_video": False,
    "mute": True,
    "deaf": False,
}

# Every attribute name any embedder loop looks for, so dir() surfaces them.
_ALLOWLIST_NAMES = sorted(set(
    public_config.permissions_list
    + public_config.guild_update
    + public_config.guild_scheduled_event
    + public_config.sticker_ent
    + public_config.threads
    + public_config.channel_create
    + public_config.channel_update
    + public_config.invites
    + public_config.role_delete
    + public_config.on_v_s_update
    + public_config.member_update
))


class Anything:
    """Answers any attribute with another Anything; renders as a stable string."""

    def __init__(self, name: str = "obj"):
        object.__setattr__(self, "_name", name)

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        # Permissions objects are read as booleans and their str() is used as
        # an emoji dict key ("true"/"false"), so these must be real bools.
        if item in public_config.permissions_list:
            return True
        if item in TYPED_ATTRS:
            return TYPED_ATTRS[item]
        if item == "created_at":
            return datetime(2020, 1, 1, tzinfo=timezone.utc)
        return Anything(f"{self._name}.{item}")

    def __dir__(self):
        return _ALLOWLIST_NAMES

    def __str__(self):
        return self._name

    def __repr__(self):
        return self._name

    def __format__(self, spec):
        return self._name

    def __len__(self):
        return 1

    def __iter__(self):
        return iter([Anything(f"{self._name}[0]")])

    def __getitem__(self, key):
        return Anything(f"{self._name}[{key}]")

    def __contains__(self, key):
        return False

    def __call__(self, *args, **kwargs):
        return Anything(f"{self._name}()")

    def __int__(self):
        return 1

    def __float__(self):
        return 1.0

    # before != after in every diffing loop, so every field branch is taken
    def __eq__(self, other):
        return False

    def __ne__(self, other):
        return True

    def __lt__(self, other):
        return False

    def __gt__(self, other):
        return True

    def __hash__(self):
        return hash(self._name)


class FakeAuthor:
    """Song requester: embedder.songs() reads display_name and voice.channel."""

    def __init__(self, display_name="Requester", channel_name="General"):
        self.display_name = display_name
        self.name = display_name
        self.id = 1
        self.avatar = type("A", (), {"url": "https://example.invalid/a.png"})()
        self.display_avatar = self.avatar
        # voice.channel.name must be a real string for the embed field
        self.voice = type("V", (), {"channel": type("C", (), {"name": channel_name})()})()


class FakeGuild:
    def __init__(self, name="Nazarick", guild_id=778558780111060992):
        self.name = name
        self.id = guild_id
        self.icon = type("Icon", (), {"url": "https://example.invalid/icon.png"})()


class FakeRole:
    def __init__(self, role_id=1, name="Rank I"):
        self.id = role_id
        self.name = name
        self.mention = f"<@&{role_id}>"


class FakeMember:
    def __init__(self, member_id=42, name="Someone"):
        self.id = member_id
        self.name = name
        self.display_name = name
        self.mention = f"<@{member_id}>"
        self.guild = FakeGuild()
        self.display_avatar = type("A", (), {"url": "https://example.invalid/m.png"})()
        self.created_at = datetime(2021, 6, 1, tzinfo=timezone.utc)


def track(title="Some Song", duration=125, live=False, uploader="Uploader"):
    """A yt-dlp info dict shaped the way the embedder expects."""
    info = {
        "title": title,
        "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "id": "dQw4w9WgXcQ",
        "uploader": uploader,
        "duration": 0 if live else duration,
    }
    if live:
        info["live_status"] = "is_live"
    return info
