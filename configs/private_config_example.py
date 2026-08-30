# Copy this file to private_config.py. The destination is gitignored; never
# commit real Discord tokens, manager passwords, or backup credentials.

# Bot specifications: [name, type, Discord token].
# type: MusicLeader, MusicInstance, Admin, or Logger.
bots = [
    ["bot_name1", "bot_type1", "bot_token1"],
    ["bot_name2", "bot_type2", "bot_token2"],
]

# Discord application IDs, keyed by the same names used above.
bot_ids = {
    "bot_name1": bot_id1, "bot_name2": bot_id2,
}

# Owners who receive error reports and bypass bot-side moderation.
supreme_beings = [your_discord_user_id]

# Guilds where the emergency anti-abuse protections are enabled.
test_guilds = [your_discord_guild_id]

# Optional ChatGPT integration (currently disabled in music_leader.py).
# openai_api_key = "replace-me"

# VPS supervisor. The server itself always binds to loopback; hosting_ip is the
# client target and normally stays loopback too. Use an SSH tunnel for remote
# interactive access instead of opening this port in UFW.
hosting_ip = "127.0.0.1"
hosting_port = 10000

# Optional SSH config alias used by the interactive client on your PC. When
# set, `python hosting/client_manager.py` creates and owns a temporary local
# tunnel automatically. Omit it on machines that connect to a local supervisor.
manager_ssh_host = "Dan1l0s-VPS"

# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
server_manager_password = "replace-with-a-long-random-value"

# Optional WebDAV backup. Leave all three commented when unused.
# backup_url = "https://url/path/"
# backup_login = "your_login"
# backup_password = "your_password"
