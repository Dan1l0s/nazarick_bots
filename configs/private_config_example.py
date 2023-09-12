# bots' specifications, value type: [[string, string, string], [string, string, string], ...]
# bot_type can be one of a folowing values: MusicLeader, MusicInstance, Admin, Logger
bots = [
    ["bot_name1", "bot_type1", "bot_token1"],
    ["bot_name1", "bot_type1", "bot_token1"],
]

# openai api key, value type: string
openai_api_key = "api_key"

# bots' discord ids, values type: {string: int}
bot_ids = {
    "bot_name1": bot_id1, "bot_name2": bot_id2,
}

# The following data is for hosting the bot on the VDS and VPS servers

# (Optional) hosting address and port, value type: string, int
# hosting_ip = "0.0.0.0"
# hosting_port = 0

# (Optional) backup url, login and password for WebDAV, value type: string
# backup_url = "https://url/path/"
# backup_login = "your_login"
# backup_password = "your_password"
