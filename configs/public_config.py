# ---------------- RANDOM DICTS

# emojis used by bots
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

# colors used in embeds
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

# yt-dlp configuration
YTDL_OPTIONS = {
    'extract_flat': 'in_playlist',
    'format': 'bestaudio/best', 'noplaylist': False,
    'simulate': True, 'key': 'FFmpegExtractAudio', 'quiet': True, 'no_warnings': True
}

# ffmpeg configuration
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'
}

# settings for music bots
music_settings = {
    "SelectionPanelTimeout": 30,
    "PlayTimeout": 30,
    "SelectionPanelMaxNameLen": 40,
}

# settings for temporary channels
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

# list of voice state properties to be logged
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

# list of bitrate values to be set
bitrate_values = {0: 96000, 1: 128000, 2: 256000, 3: 384000}

# list of files to backup
auto_backup_files = ['db/bot_database.db',]
manual_backup_files = ['db/bot_database.db', 'db/logs.db']

# limit of kicks+bans per bot startup
kick_ban_limit = 5
