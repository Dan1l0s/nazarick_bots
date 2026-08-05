"""Non-secret configuration shared by every bot.

Secrets (tokens, API keys, hosting credentials) live in private_config.py,
which is gitignored - see private_config_example.py for its shape.

The long lists near the bottom are allowlists for the logger bot: it iterates
`dir(obj)` on Discord audit-log entries and only reports attributes named here,
which is how you control log verbosity without touching code. Entries commented
out are deliberately excluded (usually because they're objects that don't
render usefully as a string, e.g. `icon`, `overwrites`, `applied_tags`).
"""

# ---------------- RANDOM DICTS

# emojis used by bots
# NOTE: these are custom-emoji IDs from specific guilds. A bot that isn't in
# the guild owning an emoji will render it as raw text, so if you deploy
# elsewhere you'll want to swap these for unicode equivalents.
emojis = {
    "dead": "<:dead:1087767664342077450>",
    "banned": "<a:Banned:774353769550315540>",
    "cat_ban": "<:CatBan:774376067699179540>",
    "rage": "<a:Reeeee:774363284731854889>",
    "roflan": "<:RoflanEbalo:913349767826919455>",
    "albedo_talking": "<a:AlbedoTalking:1093989362112409610>",
    "true": ":white_check_mark:",
    "false": ":no_entry:",
    "yay": "<a:RimuruYay:774377506659893268>",
    "blue_diamond": ":small_blue_diamond:",
    "first_place": ":first_place:",
    "second_place": ":second_place:",
    "third_place": ":third_place:",
    "deafen": ":mute:",
    "microphone": ":microphone2:",
    "stream": ":tv:",
}

# colors used in embeds, as [r, g, b]. Keyed by the `color_tag` argument that
# embedder.create_embed() takes - adding a new tag here is required before it
# can be used in an embed.
embed_colors = {
    "songs": [0, 0, 0],
    "xp": [0, 0, 0],
    "member_action": [150, 255, 255],
    "other_action": [150, 150, 255],
    "voice_update": [255, 255, 255],
    "welcome_message": [0, 0, 0],
    "message": [144, 19, 254],
    "ban_leave": [255, 0, 0],
}


# ---------------- BASIC BOT SETTINGS

# yt-dlp configuration, passed straight to YoutubeDL(...).
#
#   extract_flat: 'in_playlist'  - don't resolve every entry of a playlist up
#                                  front; entries are resolved lazily as they
#                                  reach the front of the queue
#   format: 'bestaudio/best'     - prefer an audio-only stream, fall back to
#                                  the best combined stream
#   noplaylist: False            - a URL carrying a playlist id expands it
#   simulate: True               - redundant given every call passes
#                                  download=False, but harmless; left in place
#   quiet / no_warnings          - keep yt-dlp off stdout (worker threads
#                                  already redirect it, this is belt-and-braces)
#
# REMOVED in the refactor: `'key': 'FFmpegExtractAudio'`. `key` is only
# meaningful *inside* an entry of the `postprocessors` list, never as a
# top-level option - yt-dlp stores unknown top-level keys but no extractor or
# postprocessor ever reads them, so this line had no effect whatsoever.
# (Verified against yt-dlp 2026.07.04.) Post-processing wouldn't apply here
# anyway, since nothing is ever downloaded. See CHANGES.md "Stage 6".
YTDL_OPTIONS = {
    'extract_flat': 'in_playlist',
    'format': 'bestaudio/best', 'noplaylist': False,
    'simulate': True, 'quiet': True, 'no_warnings': True
}

# ffmpeg configuration for disnake.FFmpegPCMAudio.
#
#   -reconnect 1 / -reconnect_streamed 1 / -reconnect_delay_max 5
#       makes ffmpeg retry a dropped HTTP stream instead of ending the track.
#       This is what stops long songs cutting out mid-playback.
#   -vn - discard any video stream; audio only.
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'
}

# settings for music bots
#   SelectionPanelTimeout    - seconds before an unanswered /play search panel
#                              cancels itself and drops the queued placeholder
#   PlayTimeout              - seconds a bot waits alone in a voice channel
#                              before disconnecting
#   SelectionPanelMaxNameLen - (not referenced by current code; retained)
music_settings = {
    "SelectionPanelTimeout": 30,
    "PlayTimeout": 30,
    "SelectionPanelMaxNameLen": 40,
}

# settings for temporary channels
# NOTE: 384000 is the tier-3 boost ceiling. Guilds below that tier reject it,
# which is why helpers.create_private() uses bitrate_values[premium_tier]
# rather than this value. Retained for reference/compatibility.
temporary_channels_settings = {
    "bitrate": 384000,
}

# default radio url and radio widget to parse for music bots
radio_url = "http://pool.anison.fm:9000/AniSonFM(320)"
radio_widget = "http://anison.fm/status.php?widget=true"

# string values for direct messages errors
on_message_supreme_being = "Your attention is an honor for me, my master."

# ----------------LOG BOT & EMBEDDER DICTS

# list of permissions to be logged
permissions_list = [
    'add_reactions',
    'administrator',
    'attach_files',
    'ban_members',
    'change_nickname',
    'connect',
    'create_forum_threads',
    'create_instant_invite',
    'create_private_threads',
    'create_public_threads',
    'deafen_members',
    'embed_links',
    'external_emojis',
    'external_stickers',
    'kick_members',
    'manage_channels',
    'manage_emojis',
    'manage_emojis_and_stickers',
    'manage_events',
    'manage_guild',
    'manage_messages',
    'manage_nicknames',
    'manage_permissions',
    'manage_roles',
    'manage_threads',
    'manage_webhooks',
    'mention_everyone',
    'moderate_members',
    'move_members',
    'mute_members',
    'priority_speaker',
    'read_message_history',
    'read_messages',
    'request_to_speak',
    'send_messages',
    'send_messages_in_threads',
    'send_tts_messages',
    'speak',
    'start_embedded_activities',
    'stream',
    'use_application_commands',
    'use_embedded_activities',
    'use_external_emojis',
    'use_external_stickers',
    'use_slash_commands',
    'use_voice_activation',
    'view_audit_log',
    'view_channel',
    'view_guild_insights',
]

# list of guild settings to be logged
guild_update = [
    'afk_channel',
    'system_channel',
    'afk_timeout',
    'default_message_notifications',
    'explicit_content_filter',
    'mfa_level',
    'name',
    'owner',
    'splash',
    'discovery_splash',
    'icon',
    'banner',
    'vanity_url_code',
    'preferred_locale',
    'description',
    'rules_channel',
    'public_updates_channel',
    'widget_enabled',
    'widget_channel',
    'verification_level',
    'premium_progress_bar_enabled',
    'system_channel_flags',
]

# list of guild events to be logged
guild_scheduled_event = [
    'name',
    'description',
    'privacy_level',
    'status',
    'entity_type',
    # 'channel',
    'location',
    # 'image',
]

# list of stickers properties to be logged
sticker_ent = [
    'name',
    'emoji',
    'type',
    'format_type',
    'description',
    'available',
]

# list of threads properties to be logged
threads = [
    'name',
    'archived',
    'locked',
    'auto_archive_duration',
    'type',
    'slowmode_delay',
    'invitable',
    # 'flags',
    # 'applied_tags',
]

# list of channel properties logged when channel is created
channel_create = [
    'name',
    'type',
    # 'overwrites',
    'topic',
    'bitrate',
    'rtc_region',
    'video_quality_mode',
    'default_auto_archive_duration',
    'user_limit',
    'slowmode_delay',
    'default_thread_slowmode_delay',
    'nsfw',
    # 'available_tags',
    'default_reaction',
]

# list of channel properties logged when channel is updated
channel_update = [
    'name',
    'type',
    'bitrate',
    'user_limit',
    'rtc_region',
    'position',
    'topic',
    'video_quality_mode',
    'default_auto_archive_duration',
    'slowmode_delay',
    'default_thread_slowmode_delay',
    # 'available_tags',
    'default_reaction',
]

# list of invite properties to be logged
invites = [
    'max_age',
    'code',
    'temporary',
    # 'channel',
    'uses',
    'max_uses',
]

# list of role properties to be logged when role is deleted
role_delete = [
    'colour',
    'mentionable',
    'hoist',
    'name',
    # 'permissions',
    # 'icon',
    # 'emoji',
]

# Voice-state properties diffed by log_bot.on_voice_state_update.
#
# IMPORTANT: every name here needs a matching function in BOTH
# helpers/embedder.py and helpers/database_logger.py (the handler looks them up
# by name). tests/test_log_bot.py::test_voice_state_attrs_have_matching_handlers
# enforces this, so adding a name here without both functions fails the suite
# rather than blowing up at runtime.
on_v_s_update = [
    'deaf',
    'mute',
    'self_deaf',
    'self_mute',
    'self_stream',
    'self_video',
    'suppress',
    'requested_to_speak_at',
    # 'afk',
    # 'channel',
]

# list of member properties to be logged
member_update = [
    'display_name',
    'pending',
    'name',
    'raw_status',
    'premium_since',
    'current_timeout',
]

# Max voice bitrate per guild boost tier, in bits/sec. Indexed directly by
# `guild.premium_tier`, so the keys must stay 0-3 and contiguous.
bitrate_values = {0: 96000, 1: 128000, 2: 256000, 3: 384000}

# Files uploaded by hosting/server_manager.py's backup routine. The automatic
# (twice daily) backup covers only the settings/XP database; the manual
# `backup` command also includes the much larger event log.
auto_backup_files = ['db/bot_database.db',]
manual_backup_files = ['db/bot_database.db', 'db/logs.db']

# Kick/ban budget per moderator, per bot uptime, on guilds listed in
# private_config.test_guilds. Exceeding it times the moderator out and notifies
# the owner - an anti-nuke tripwire. Counter resets when the bot restarts.
kick_ban_limit = 5
