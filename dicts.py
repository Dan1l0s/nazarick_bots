#----------------RANDOM DICTS
emojis = {
    "dead": "<:dead:1087767664342077450>",
    "banned": "<a:Banned:774353769550315540>",
    "rage": "<a:Reeeee:774363284731854889>",
    "albedo_talking": "<a:AlbedoTalking:1093989362112409610>",
    "true": ":white_check_mark:",
    "false": ":no_entry:",
}

embed_colors = {"songs": [0, 0, 0], #BLACK
                "member_action": [150, 255, 255], #TEAL
                "other_action": [150, 150, 255], #PURPLE
                "vc": [255, 255, 255], #WHITE
                "voice_update":  [255, 255, 255], #WHITE
                "welcome_message": [190, 255, 0], #LIME
                "message": [255, 153, 255], #PINK
                "ban_leave": [255, 0, 0], #RED
                }


#---------------- BASIC BOT SETTINGS

YTDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': False,
                'simulate': True, 'key': 'FFmpegExtractAudio', 'forceduration': True, 'quiet': True, 'no_warnings': True}
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

music_settings = {
    "SelectionPanelTimeout": 30,
    "PlayTimeout": 30,
    "SelectionPanelMaxNameLen": 40,
}

radio_url = "http://pool.anison.fm:9000/AniSonFM(320)"
radio_widget = "http://anison.fm/status.php?widget=true"

dm_error = "You are not allowed to DM me, trash. The only reason I serve you is the order of the Supreme Beings.\nProceed to your guild, where I MUST follow your commands."
dm_error_admin = "I am sorry, my master, but I can't follow your order. Please, proceed to any of your guilds, where I can serve you."

#----------------ENTRY EMBED DICTS
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

guild_scheduled_event = [
    'name',
    'description',
    'privacy_level',
    'status',
    'entity_type',
    #'channel',
    'location',
    #'image',
]

sticker_ent = [
    'name',
    'emoji',
    'type',
    'format_type',
    'description',
    'available',
]

threads = [
    'name',
    'archived',
    'locked',
    'auto_archive_duration',
    'type',
    'slowmode_delay',
    'invitable',
    #'flags',
    #'applied_tags',
]

channel_create = [
    'name',
    'type',
    #'overwrites',
    'topic',
    'bitrate',
    'rtc_region',
    'video_quality_mode',
    'default_auto_archive_duration',
    'user_limit',
    'slowmode_delay',
    'default_thread_slowmode_delay',
    'nsfw',
    #'available_tags',
    'default_reaction',
]

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
    #'available_tags',
    'default_reaction',
]

invites = [
    'max_age',
    'code',
    'temporary',
    #'channel',
    'uses',
    'max_uses',
]

role_delete = [
    'colour',
    'mentionable',
    'hoist',
    'name',
    #'permissions',
    #'icon',
    #'emoji',
]