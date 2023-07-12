# bots' specifications, value type: [[string, string, string],[string, string, string],...]
# bot_type can be one of a folowing values: MusicLeader, MusicInstance, Admin, Logger
bots = {
    ["bot_name1", "bot_type1", "bot_token1"],
    ["bot_name1", "bot_type1", "bot_token1"],
}

# openai api key, value type: string
openai_api_key = "api_key"

# bots' discord ids, values type: {string: int}
bot_ids = {
    "bot_name1": bot_id1, "bot_name2": bot_id2,
}

# category where tmp channels are created, values type: {int: int}
categories_ids = {
    # guild1_id: category_id,
}

# guild admins' discord ids, values type: {int: [int, int, int]}
admin_ids = {
    # guild1_id: [
    #     admin1_id, admin2_id, admin3_id,
    # ],
    # guild2_id: [
    #     admin1_id, admin2_id, admin3_idn
    # ],
}

# guild users' discord ids who are unmuted by bot automatically, values type: {int: [int, int]}
supreme_beings_ids = {
    # guild1_id: [
    #     user1_id, user2_id, user3_id,
    # ],
    # guild2_id: [
    #     user1_id, user2_id, user3_id,
    # ],
}

# logs channels' ids, values type: {int: int}
log_ids = {
    # guild1_id: channel_id,
    # guild2_id: channel_id,
}

# status logs channels' ids, values type: {int: int}
status_log_ids = {
    # guild1_id: channel_id,
    # guild2_id: channel_id,
}

# welcome messages channels' ids, values type: {int: int}
welcome_ids = {
    # guild1_id: channel_id,
    # guild2_id: channel_id,
}

# string values for some variables
dm_error = "You are not allowed to DM me, trash. The only reason I serve you is the order of the Supreme Beings.\nProceed to your guild, where I MUST follow your commands."
dm_error_admin = "I am sorry, my master, but I can't follow your order. Please, proceed to any of your guilds, where I can serve you."
