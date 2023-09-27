import disnake
from datetime import datetime, timezone

import configs.private_config as private_config
import configs.public_config as public_config

import helpers.helpers as helpers


class EmbedField():
    name = None
    value = None
    inline = None

    def __init__(self, name="", value="", inline=False):
        self.name = name
        self.value = value
        self.inline = inline


def create_embed(title=None, url=None, description=None, color_tag: str = None, author_name=None, author_icon_url=None, footer_text=None, footer_icon_url=None, thumbnail_url=None, fields=None):
    embed = disnake.Embed(title=title, url=url, description=description, color=disnake.Colour.from_rgb(*public_config.embed_colors[color_tag]), timestamp=datetime.now())
    embed.set_author(name=author_name, icon_url=author_icon_url)
    if footer_text:
        embed.set_footer(text=footer_text, icon_url=footer_icon_url)
    elif footer_icon_url:
        embed.set_footer(icon_url=footer_icon_url)
    embed.set_thumbnail(url=thumbnail_url)
    if fields:
        for field in fields:
            embed.add_field(name=field.name, value=field.value, inline=field.inline)
    return embed


def songs(author, info, text):
    if "entries" in info:
        info = info["entries"][0]
    fields = [
        EmbedField(name="*Duration*", value=helpers.get_duration(info), inline=True),
        EmbedField(name="*Requested by*", value=author.display_name, inline=True),
        EmbedField(name="*Channel*", value=author.voice.channel.name, inline=True)
    ]
    return create_embed(title=info['title'], url=info['webpage_url'], description=text, color_tag="songs",
                        author_name=info['uploader'], thumbnail_url=f"https://img.youtube.com/vi/{info['id']}/0.jpg", fields=fields)


def radio(data):
    fields = [
        EmbedField(name="*Duration*", value=helpers.get_duration(data), inline=True),
        EmbedField(name="*Channel*", value=data['channel'].name, inline=True)
    ]
    return create_embed(title=data['name'], description="Playing from ANISON.FM", color_tag="songs", author_name=data['source'], fields=fields)


# --------------------- Entry Actions --------------------------------


def entry_channel_create(entry):
    fields = []
    for attr in dir(entry.after):
        if attr in public_config.channel_create:
            fields.append(EmbedField(name=f"**{helpers.parse_key(attr)}**", value=f"{getattr(entry.after, attr)}"))
    if hasattr(entry.after, 'overwrites'):
        overwrites = []
        for role in entry.after.overwrites:
            if f"{role[1].pair()[0]}" == "<Permissions value=1024>":
                overwrites.append(f"{('Role', 'User')[type(role[0]) == disnake.member.Member]} : {role[0].mention}")
        overwrites = '\n'.join(overwrites)
        fields.append(EmbedField(name=f"**Viewing Permissions:**", value=overwrites))
    if hasattr(entry.after, 'available_tags'):
        tags = []
        for tag in entry.after.available_tags:
            tags.append(tag.name)
        tags = '\n'.join(tags)
        fields.append(EmbedField(name=f"**Available tags:**", value=tags))
    return create_embed(description=f'**{entry.user.mention} created channel {entry.user.guild.get_channel(entry.target.id).mention}**', color_tag="other_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_channel_update(entry):
    fields = []
    for attr in dir(entry.after):
        if attr in public_config.channel_update:
            fields.append(EmbedField())
            fields.append(EmbedField(name=f"**Old {helpers.parse_key(attr)}**", value=f"{getattr(entry.before, attr)}", inline=True))
            fields.append(EmbedField(name=f"**New {helpers.parse_key(attr)}**", value=f"{getattr(entry.after, attr)}", inline=True))
    if hasattr(entry.after, 'nsfw'):
        if entry.before.nsfw:
            fields.append(EmbedField())
            fields.append(EmbedField(name="**Old NSFW settings:**", value="NSFW", inline=True))
            fields.append(EmbedField(name="**New NSFW settings:**", value=":sob: Not NSFW", inline=True))
        else:
            fields.append(EmbedField())
            fields.append(EmbedField(name="**Old NSFW settings:**", value="Not NSFW", inline=True))
            fields.append(EmbedField(name="**New NSFW settings:**", value=":smiling_imp: NSFW", inline=True))
    if hasattr(entry.after, 'available_tags'):
        tags = []
        for tag in entry.before.available_tags:
            if tag not in entry.after.available_tags:
                tags.append(f"{public_config.emojis['false']} {tag.name}")
        for tag in entry.after.available_tags:
            if tag not in entry.before.available_tags:
                tags.append(f"{public_config.emojis['true']} {tag.name}")
        tags = '\n'.join(tags)
        fields.append(EmbedField(name="**Tag Updates**", value=tags))
    return create_embed(description=f'**{entry.user.mention} updated channel {entry.user.guild.get_channel(entry.target.id).mention}**', color_tag="other_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_channel_delete(entry):
    return create_embed(description=f'**{entry.user.mention} deleted channel `{entry.before.name}`**', color_tag="other_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name)


def entry_thread_create(entry):
    fields = []
    for attr in dir(entry.after):
        if attr in public_config.threads:
            fields.append(EmbedField(name=f"**{helpers.parse_key(attr)}**", value=f"{getattr(entry.after, attr)}"))
    if hasattr(entry.after, 'applied_tags'):
        tags = []
        for tag in entry.after.applied_tags:
            tags.append(tag.name)
        tags = '\n'.join(tags)
        fields.append(EmbedField(name=f"**Applied tags:**", value=tags))
    return create_embed(description=f'**{entry.user.mention} has created thread {entry.target.mention}**', color_tag="other_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_thread_update(entry):
    fields = []
    for attr in dir(entry.after):
        if attr in public_config.threads:
            fields.append(EmbedField())
            fields.append(EmbedField(name=f"**Old {helpers.parse_key(attr)}**", value=f"{getattr(entry.before, attr)}", inline=True))
            fields.append(EmbedField(name=f"**New {helpers.parse_key(attr)}**", value=f"{getattr(entry.after, attr)}", inline=True))
    if hasattr(entry.after, 'applied_tags'):
        tags = []
        for tag in entry.before.applied_tags:
            if tag not in entry.after.applied_tags:
                tags.append(f"{public_config.emojis['false']} {tag.name}")
        for tag in entry.after.applied_tags:
            if tag not in entry.before.applied_tags:
                tags.append(f"{public_config.emojis['true']} {tag.name}")
        tags = '\n'.join(tags)
        fields.append(EmbedField(name="**Tag Updates**", value=tags))
    return create_embed(description=f'**{entry.user.mention} has updated thread {entry.target.mention}**', color_tag="other_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_thread_delete(entry):
    return create_embed(description=f'**{entry.user.mention} deleted thread `{entry.before.name}`**', color_tag="other_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name)


def entry_kick(entry):
    return create_embed(description=f'**{entry.user.mention} kicked member {entry.target.mention}**', color_tag="member_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=[EmbedField(name="**REASON:**", value=f'{entry.reason}')])


def entry_ban(entry):
    return create_embed(description=f'**{entry.user.mention} banned member {entry.target.mention}**', color_tag="member_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=[EmbedField(name="**REASON:**", value=f'{entry.reason}')])


def entry_unban(entry):
    return create_embed(description=f'**{entry.user.mention} unbanned member {entry.target.mention}**', color_tag="member_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name)


def entry_member_move(entry):
    return create_embed(description=f'**{entry.user.mention} moved a user to {entry.user.guild.get_channel(entry.extra.channel.id).mention}**', color_tag="member_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name)


def entry_member_update(entry):
    fields = []
    if hasattr(entry.before, "nick"):
        if entry.before.nick is not None:
            fields.append(EmbedField(name="**Old Nickname:**", value=f'`{entry.before.nick}`'))
        if entry.after.nick is not None:
            fields.append(EmbedField(name="**New Nickname:**", value=f'`{entry.after.nick}`'))
    if hasattr(entry.after, "timeout"):
        if entry.after.timeout is not None:
            fields.append(EmbedField(name="**Timeout expiration date:**", value=entry.after.timeout.strftime("%d/%m %H:%M:%S")))
        else:
            fields.append(EmbedField(name="**Timeout:**", value="Timeout has been removed"))
    return create_embed(description=f'**{entry.user.mention} updated user {entry.target.mention}**', color_tag="member_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_member_role_update(entry):
    fields = []
    for role in entry.after.roles:
        fields.append(EmbedField(name=f"Role added:", value=role.name))
    for role in entry.before.roles:
        fields.append(EmbedField(name=f"Role removed:", value=role.name))
    return create_embed(description=f"**{entry.user.mention} updated user {entry.target.mention}'s roles**", color_tag="member_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_member_disconnect(entry):
    return create_embed(description=f'**{entry.user.mention} disconnected {("1 user", f"{entry.extra.count} users")[entry.extra.count > 1]} from a voice channel**', color_tag="member_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name)


def entry_role_create(entry):
    if hasattr(entry.after, "name"):
        fields = [EmbedField(name="**Role name:**", value=entry.after.name)]
    else:
        fields = None
    return create_embed(description=f'**A new role has been added to the Guild by {entry.user.mention}**', color_tag="other_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_role_update(entry):
    fields = []
    if hasattr(entry.after, "name"):
        fields.append(EmbedField())
        fields.append(EmbedField(name="**Old name:**", value=entry.before.name, inline=True))
        fields.append(EmbedField(name="**New name:**", value=entry.after.name, inline=True))
    if hasattr(entry.after, "icon"):
        thumbnail = entry.after.icon.url
    else:
        thumbnail = None
    if hasattr(entry.after, "colour"):
        fields.append(EmbedField())
        fields.append(EmbedField(name="**Old Color:**", value=helpers.rgb_to_hex(entry.before.colour.r, entry.before.colour.g, entry.before.colour.b), inline=True))
        fields.append(EmbedField(name="**New Color:**", value=helpers.rgb_to_hex(entry.after.colour.r, entry.after.colour.g, entry.after.colour.b), inline=True))
    if hasattr(entry.after, "permissions"):
        perms = []
        for attr in dir(entry.after.permissions):
            if attr in public_config.permissions_list:
                if (getattr(entry.before.permissions, attr) != getattr(entry.after.permissions, attr)):
                    perms.append(f"{public_config.emojis[f'{str(getattr(entry.before.permissions, attr)).lower}']} {helpers.parse_key(attr)}")
        perms = '\n'.join(perms)
        fields.append(EmbedField(name="**CHANGED PERMISSIONS:**", value=perms))
    return create_embed(description=f'**The role {entry.target.mention} has been updated by {entry.user.mention}**', color_tag="other_action", thumbnail_url=thumbnail,
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_role_delete(entry):
    fields = []
    for attr in dir(entry.before):
        if attr in public_config.role_delete:
            fields.append(EmbedField(name=f"**{helpers.parse_key(attr)}**", value=f"{getattr(entry.before, attr)}"))
    return create_embed(description=f'**A role has been deleted by {entry.user.mention} from the guild**', color_tag="other_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_guild_update(entry):
    fields = []
    for attr in dir(entry.before):
        if attr in public_config.guild_update:
            fields.append(EmbedField())
            fields.append(EmbedField(name=f"**Old {helpers.parse_key(attr)}**", value=f"{getattr(entry.before, attr)}", inline=True))
            fields.append(EmbedField(name=f"**New {helpers.parse_key(attr)}**", value=f"{getattr(entry.after, attr)}", inline=True))
    return create_embed(description=f'**{entry.user.mention} has updated the Guild**', color_tag="other_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_member_prune(entry):
    fields = [EmbedField(name="**Members Removed:**", value=entry.extra.members_removed), EmbedField(name="**Prune size:**", value=entry.extra.delete_members_days)]
    return create_embed(description=f'**{entry.user.mention} has pruned members from the Guild**', color_tag="member_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_invite_create(entry):
    fields = []
    if hasattr(entry.after, 'channel'):
        fields.append(EmbedField(name="**Channel:**", value=entry.after.channel.mention))
    for attr in dir(entry.after):
        if attr in public_config.invites:
            fields.append(EmbedField(name=f"**{helpers.parse_key(attr)}**", value=f"{getattr(entry.after, attr)}"))
    return create_embed(description=f'**{entry.user.mention} has created an invite to the Guild**', color_tag="member_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_invite_update(entry):
    return create_embed(description=f'**{entry.user.mention} has updated an invite to the Guild**', color_tag="member_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name)


def entry_invite_delete(entry):
    fields = []
    if hasattr(entry.before, 'channel'):
        fields.append(EmbedField(name="**Channel:**", value=entry.after.channel.mention))
    for attr in dir(entry.before):
        if attr in public_config.invites:
            fields.append(EmbedField(name=f"**{helpers.parse_key(attr)}**", value=f"{getattr(entry.before, attr)}"))
    return create_embed(description=f'**{entry.user.mention} has deleted an invite to the Guild**', color_tag="member_action",
                        author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_emoji_create(entry):
    return create_embed(description=f'**{entry.user.mention} has added an emoji to the Guild**', color_tag="other_action", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=[EmbedField(name="**Emoji:**", value=entry.after.name)])


def entry_emoji_update(entry):
    return create_embed(description=f'**{entry.user.mention} has updated an emoji in the Guild**', color_tag="other_action", author_name=entry.user.name, author_icon_url=entry.user.display_avatar.url,
                        footer_text=entry.user.guild.name, fields=[EmbedField(name="**Old Emoji Name:**", value=entry.before.name), EmbedField(name="**New Emoji Name:**", value=entry.after.name)])


def entry_emoji_delete(entry):
    return create_embed(description=f'**{entry.user.mention} has removed an emoji from the Guild**', color_tag="member_action", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=[EmbedField(name="**Emoji:**", value=entry.before.name)])


def entry_sticker_create(entry):
    fields = []
    for attr in dir(entry.before):
        if attr in public_config.sticker_ent:
            fields.append(EmbedField(name=f"**{helpers.parse_key(attr)}**", value=f"{getattr(entry.before, attr)}"))
    return create_embed(description=f'**{entry.user.mention} has added a sticker to the Guild**', color_tag="other_action", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_sticker_update(entry):
    fields = []
    for attr in dir(entry.before):
        if attr in public_config.sticker_ent:
            fields.append(EmbedField(name=f"**{helpers.parse_key(attr)}**", value=f"{getattr(entry.before, attr)}"))
    return create_embed(description=f'**{entry.user.mention} has updated a sticker in the Guild**', color_tag="other_action", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_sticker_create(entry):
    fields = []
    for attr in dir(entry.before):
        if attr in public_config.sticker_ent:
            fields.append(EmbedField(name=f"**{helpers.parse_key(attr)}**", value=f"{getattr(entry.before, attr)}"))
    return create_embed(description=f'**{entry.user.mention} has deleted a sticker from the Guild**', color_tag="other_action", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=fields)


def entry_message_delete(entry):
    return create_embed(description=f"**{(f'<@{entry.target.id}>',entry.target.mention)[hasattr(entry.target, 'mention')]}'s messages have been deleted by moderator {entry.user.mention}**", color_tag="member_action", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, fields=[EmbedField(
                            name="**Channel from which the messages were deleted**", value=entry.extra.channel.mention), EmbedField(name="**Amount of deleted messages**", value=entry.extra.count)])


def entry_message_bulk_delete(entry):
    return create_embed(description=f"**{entry.user.mention} has deleted {entry.extra['count']} message(s) from {entry.target.mention}**", color_tag="message", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name)


def entry_message_pin(entry):
    return create_embed(description=f"**{entry.user.mention} has pinned {entry.target.mention}'s message in {entry.extra.channel.mention}**", color_tag="message", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name)


def entry_message_unpin(entry):
    return create_embed(description=f"**{entry.user.mention} has unpinned {entry.target.mention}'s message in {entry.extra.channel.mention}**", color_tag="message", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name)


def entry_guild_scheduled_event_create(entry):
    fields = []
    if hasattr(entry.after, 'channel'):
        fields.append(EmbedField(name="**Channel**", value=f"{entry.after.channel.mention}"))
    for attr in dir(entry.after):
        if attr in public_config.guild_scheduled_event:
            fields.append(EmbedField(name=f"**{helpers.parse_key(attr)}**", value=f"{getattr(entry.after, attr)}"))
    if hasattr(entry.after, 'image'):
        thumbnail_url = entry.after.image.url
    else:
        thumbnail_url = None
    return create_embed(description=f"**{entry.user.mention} has created a scheduled guild event**", color_tag="other_action", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, thumbnail_url=thumbnail_url, fields=fields)


def entry_guild_scheduled_event_update(entry):
    fields = []
    if hasattr(entry.after, 'channel'):
        fields.append(EmbedField())
        fields.append(EmbedField(name="**Old Channel**", value=f"{entry.before.channel.mention}", inline=True))
        fields.append(EmbedField(name="**New Channel**", value=f"{entry.after.channel.mention}", inline=True))
    for attr in dir(entry.before):
        if attr in public_config.guild_scheduled_event:
            fields.append(EmbedField())
            fields.append(EmbedField(name=f"**Old {helpers.parse_key(attr)}**", value=f"{getattr(entry.before, attr)}", inline=True))
            fields.append(EmbedField(name=f"**New {helpers.parse_key(attr)}**", value=f"{getattr(entry.after, attr)}", inline=True))
    if hasattr(entry.after, 'image'):
        thumbnail_url = entry.after.image.url
    else:
        thumbnail_url = None
    return create_embed(description=f"**{entry.user.mention} has updated a scheduled guild event**", color_tag="other_action", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, thumbnail_url=thumbnail_url, fields=fields)


def entry_guild_scheduled_event_delete(entry):
    fields = []
    if hasattr(entry.before, 'channel'):
        fields.append(EmbedField(name="**Channel**", value=f"{entry.before.channel.mention}"))
    for attr in dir(entry.before):
        if attr in public_config.guild_scheduled_event:
            fields.append(EmbedField(name=f"**{helpers.parse_key(attr)}**", value=f"{getattr(entry.before, attr)}"))
    if hasattr(entry.before, 'image'):
        thumbnail_url = entry.after.before.url
    else:
        thumbnail_url = None
    return create_embed(description=f"**{entry.user.mention} has deleted a scheduled guild event**", color_tag="other_action", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name, thumbnail_url=thumbnail_url, fields=fields)


def entry_bot_add(entry):
    return create_embed(description=f"**{entry.user.mention} has added a BOT - {entry.target.mention} - to the GUILD**", color_tag="member_action", author_name=entry.user.name,
                        author_icon_url=entry.user.display_avatar.url, footer_text=entry.user.guild.name)


# --------------------- CHANNEL SWITCHING --------------------------------


def switched(member, before, after):
    return create_embed(description=f'**{member.mention} switched from {before.channel.mention} to {after.channel.mention}**', color_tag="voice_update", author_name=member.name,
                        author_icon_url=member.display_avatar.url, footer_text=member.guild.name)


def connected(member, after):
    return create_embed(description=f"**{member.mention} joined voice channel {after.channel.mention}**", color_tag="voice_update", author_name=member.name,
                        author_icon_url=member.display_avatar.url, footer_text=member.guild.name)


def disconnected(member, before):
    return create_embed(description=f'**{member.mention} left voice channel {before.channel.mention}**', color_tag="voice_update", author_name=member.name,
                        author_icon_url=member.display_avatar.url, footer_text=member.guild.name)


def afk(member, after):
    return create_embed(description=f'**{member.mention} has gone AFK in {after.channel.mention}**', color_tag="voice_update", author_name=member.name,
                        author_icon_url=member.display_avatar.url, footer_text=member.guild.name)


# --------------------- USER ACTIONS --------------------------------


def welcome_message(member, user):
    return create_embed(description=f'**{user.mention}, welcome to {helpers.get_guild_name(member.guild)}!**', color_tag="welcome_message",
                        author_name=member.name, author_icon_url=member.display_avatar.url, thumbnail_url=member.display_avatar.url, footer_text=member.guild.name,
                        fields=[EmbedField(name="**⏲ Age of account:**", value=f'**{f"<t:{int(member.created_at.timestamp())}:R>"}**', inline=True)])


def profile_upd(before, after):
    fields = []
    for attr in dir(before):
        if attr in public_config.member_update and getattr(before, attr) != getattr(after, attr):
            fields.append(EmbedField())
            fields.append(EmbedField(name=f"**Old {helpers.parse_key(attr)}**", value=f"{getattr(before, attr)}", inline=True))
            fields.append(EmbedField(name=f"**New {helpers.parse_key(attr)}**", value=f"{getattr(after, attr)}", inline=True))
    return create_embed(description=f'**{after.mention} has updated their profile**', color_tag="member_action", author_name=after.name,
                        author_icon_url=after.display_avatar.url, footer_text=after.guild.name, thumbnail_url=after.display_avatar.url, fields=fields)


def member_remove(payload):
    return create_embed(description=f'**{public_config.emojis["false"]} {payload.user.mention} has left the server**', color_tag="ban_leave", author_name=payload.user.name,
                        author_icon_url=payload.user.display_avatar.url, footer_text=payload.user.guild.name, thumbnail_url=payload.user.display_avatar.url)


def member_join(member):
    return create_embed(description=f'**{public_config.emojis["true"]} {member.mention} has joined the server**', color_tag="welcome_message", author_name=member.name, author_icon_url=member.display_avatar.url,
                        footer_text=member.guild.name, thumbnail_url=member.display_avatar.url, fields=[EmbedField(name="**⏲ Age of account:**", value=f'**{f"<t:{int(member.created_at.timestamp())}:R>"}**', inline=True)])


def ban(guild, user):
    return create_embed(description=f'**{public_config.emojis["cat_ban"]} {user.mention} has been banned from {guild.name}**', color_tag="ban_leave", author_name=user.name, author_icon_url=user.display_avatar.url,
                        footer_text=guild.name, thumbnail_url=user.display_avatar.url)


def unban(guild, user):
    return create_embed(description=f'**:ballot_box_with_check: {user.mention} has been unbanned from {guild.name}**', color_tag="member_action", author_name=user.name, author_icon_url=user.display_avatar.url,
                        footer_text=guild.name, thumbnail_url=user.display_avatar.url)


def activity_update(member, old_user_status, new_user_status):
    fields = []
    if old_user_status.status != new_user_status.status:
        fields.append(EmbedField())
        fields.append(EmbedField(name="**Old Status**", value=f'```{helpers.parse_key(old_user_status.status)}```', inline=True))
        fields.append(EmbedField(name="**Current Status**", value=f'```{helpers.parse_key(new_user_status.status)}```', inline=True))
    if old_user_status.activities != new_user_status.activities and old_user_status.activities:
        act_list = []
        for act in old_user_status.activities:
            if act not in new_user_status.activities:
                act_list.append(f'{act.actname}')
        act_list = '\n'.join(act_list)
        if len(act_list) > 0:
            fields.append(EmbedField(name="**Finished Activities :**", value=f"```{act_list}```"))
    thumbnail_url = None
    if member.activity is not None:
        fields.append(EmbedField(name="**Current Activities:**"))
        for act in member.activities:
            if type(act) == disnake.activity.Spotify:
                fields.append(EmbedField(name="**Listening to spotify:**", value=f'```{act.artists[0]} - "{act.title}"```Track url : {act.track_url}'))
                thumbnail_url = f"{act.album_cover_url}"
            elif act is not None:
                fields.append(EmbedField(name=f"**{f'{act.type}'[13:]}**", value=f"```{act.name}```"))
    return create_embed(description=f"**{member.mention}'s has updated their status/activities**", color_tag="member_action", author_name=member.name, author_icon_url=member.display_avatar.url,
                        footer_text=member.guild.name, thumbnail_url=thumbnail_url, fields=fields)

# --------------------- MESSAGES --------------------------------


def message_edit(before, after):
    return create_embed(description=f'**:pencil2:{before.author.mention} has edited a message in {before.channel.mention}. [Jump to message]({before.jump_url})**', color_tag="message", author_name=before.author.name, author_icon_url=before.author.display_avatar.url,
                        footer_text=before.guild.name, fields=[EmbedField(name="** Before: **", value=f'```{before.content}```'), EmbedField(name="** After: **", value=f'```{after.content}```')])


def message_pin(before, after):
    return create_embed(description=f'**:pushpin:A Message has been pinned in {before.channel.mention}. [Jump to message]({before.jump_url})**', color_tag="message", author_name=before.guild.name, author_icon_url=before.guild.icon.url,
                        footer_text=before.guild.name, fields=[EmbedField(name="** Message Author: **", value=f'{before.author.mention}'), EmbedField(name="** Message Content: **", value=f'```{after.content}```\n')])


def message_unpin(before, after):
    return create_embed(description=f'**:pushpin:A Message has been unpinned in {before.channel.mention}. [Jump to message]({before.jump_url})**', color_tag="message", author_name=before.guild.name, author_icon_url=before.guild.icon.url,
                        footer_text=before.guild.name, fields=[EmbedField(name="** Message Author: **", value=f'{before.author.mention}'), EmbedField(name="** Message Content: **", value=f'```{after.content}```\n')])


def message_delete(message):
    return create_embed(description=f'**:wastebasket: A Message sent by {message.author.mention} has been deleted in {message.channel.mention}.**', color_tag="message", author_name=message.author, author_icon_url=message.author.display_avatar.url,
                        footer_text=message.channel.guild.name, fields=[EmbedField(name="** Message Content: **", value=f'```{(f"{message.content[:1010]}...",message.content)[len(message.content) < 1000]}```\n')])

# --------------------- VOICE STATES --------------------------------


def mute(member, after):
    return create_embed(description=f"**{member.mention}'s voice state has been updated**", color_tag="voice_update", author_name=member.name, author_icon_url=member.display_avatar.url,
                        footer_text=member.guild.name, fields=[EmbedField(name=f"{public_config.emojis['microphone']}** Server Mute**", value=('No', 'Yes')[after.mute])])


def deaf(member, after):
    return create_embed(description=f"**{member.mention}'s voice state has been updated**", color_tag="voice_update", author_name=member.name, author_icon_url=member.display_avatar.url,
                        footer_text=member.guild.name, fields=[EmbedField(name=f"{public_config.emojis['deafen']}** Server Deafen**", value=('No', 'Yes')[after.deaf])])


def self_mute(member, before, after):
    fields = []
    fields.append(EmbedField(name=f"{public_config.emojis['microphone']}** Muted**", value=('No', 'Yes')[after.self_mute], inline=True))
    if after.self_deaf:
        fields.append(EmbedField(name=f"{public_config.emojis['deafen']}** Deafened**", value="Yes", inline=True))
    elif before.self_deaf and not after.self_deaf:
        fields.append(EmbedField(name=f"{public_config.emojis['deafen']}** Deafened**", value="No", inline=True))
    return create_embed(description=f"**{member.mention} updated their voice state**", color_tag="voice_update", author_name=member.name, author_icon_url=member.display_avatar.url,
                        footer_text=member.guild.name, fields=fields)


def self_stream(member, after):
    return create_embed(description=f"**{member.mention} updated their stream status**", color_tag="voice_update", author_name=member.name, author_icon_url=member.display_avatar.url,
                        footer_text=member.guild.name, fields=[EmbedField(name=f"{public_config.emojis['stream']}** Stream enabled**", value=('No', 'Yes')[after.self_stream])])


def self_video(member, after):
    return create_embed(description=f"**{member.mention} updated their video status**", color_tag="voice_update", author_name=member.name, author_icon_url=member.display_avatar.url,
                        footer_text=member.guild.name, fields=[EmbedField(name=f"{public_config.emojis['stream']}** Video enabled**", value=('No', 'Yes')[after.self_video])])


def role_notification(guild, roles_list):
    roles = []
    for role in roles_list:
        roles.append(role.name)
    roles = '\n* '.join(roles)
    return create_embed(description=f'**You got {("a new role", "new roles")[len(roles_list) > 1]}!** {public_config.emojis["yay"]}', color_tag="welcome_message", author_name=guild.name, author_icon_url=guild.icon.url,
                        fields=[EmbedField(name="", value=f"* {roles}")])


def song_selections(author, songs):
    selection_field = []
    cnt = 0
    for song in songs:
        cnt += 1
        suffix = song['url_suffix'][:song['url_suffix'].find("&")]
        if song['duration'] == 0:
            song['duration'] = "Live"
        selection_field.append(f'**{cnt}.** {public_config.emojis["blue_diamond"]} **[{song["title"]}](https://www.youtube.com/{suffix})** ({song["duration"]})')
    return create_embed(color_tag="songs", author_name="Song selection. Select the song number to continue.", author_icon_url=author.avatar.url,
                        footer_text=f"This timeouts in {public_config.music_settings['SelectionPanelTimeout']} seconds", footer_icon_url=author.avatar.url, fields=[EmbedField(value='\n'.join(selection_field))])


def queue(guild, queue, start_index, curr_song):
    fields = []
    if "entries" in curr_song:
        curr_song = curr_song["entries"][0]
    if (isinstance(curr_song, str)):
        curr_title = "Radio"
        curr_url = curr_song
        curr_duration = "Live"
    else:
        curr_title = curr_song['title']
        curr_url = curr_song['webpage_url']
        curr_duration = helpers.get_duration(curr_song)
    ff = False
    if len(queue) > 0 and not 'artificial' in curr_song:
        ff = True
        for num in (range(10), range(len(queue) - start_index))[start_index + 10 > len(queue)]:
            try:
                if not queue[num + start_index].track_info.done():
                    num -= 1
                    continue
            except:
                break
            song = queue[num + start_index].track_info.result()
            if (isinstance(song, str)):
                title = "Radio"
                url = song
                duration = "Live"
            else:
                title = song['title']
                url = song['webpage_url']
                duration = helpers.get_duration(song)
            song_info = f'**{num + start_index + 1}.** **[{title}]({url})** {duration}'
            fields.append(EmbedField(value=song_info))
            ff = False
    else:
        fields.append(EmbedField(value="Queue is currently empty!"))
    if ff:
        fields.append(EmbedField(value="Queue is currently empty!"))
    else:
        duration = helpers.get_queue_duration(queue)
        if duration:
            fields.append(EmbedField(value=duration))
    return create_embed(description=f"**Currently playing : [{curr_title}]({curr_url})** {curr_duration}", color_tag="songs",
                        author_name=guild.name, author_icon_url=guild.icon.url, footer_text=guild.name, fields=fields)


def xp_top(guild, top_users, start_index, author_info, func, xp_type_voice):
    fields = []
    ff = False
    for num in (range(10), range(len(top_users) - start_index))[start_index + 10 > len(top_users)]:
        user_info = top_users[num + start_index]
        if user_info == author_info:
            ff = True
        user = func(user_info[0])
        if not user:
            user_mention = f'<@{user_info[0]}>'
        else:
            user_mention = f'{user.mention}'
        value = f'**{helpers.get_user_num_badge(num+start_index)}** **{user_mention} - {user_info[(2, 1)[xp_type_voice]]}xp**'
        fields.append(EmbedField(value=value))
    if ff:
        description = ""
    else:
        description = f"*{helpers.get_user_num_badge(top_users.index(author_info))}* {func(author_info[0]).mention} - {author_info[(2, 1)[xp_type_voice]]}xp*"
    return create_embed(title=("Type: Text", "Type: Voice")[xp_type_voice], description=description, color_tag="xp",
                        author_name=guild.name, author_icon_url=guild.icon.url, footer_text=guild.name, fields=fields)


def xp_show(member: disnake.Member, user_info: list, curr_rank: disnake.Role, next_rank: disnake.Role, required_xp: int):
    fields = [
        EmbedField(name="**Voice XP**", value=f"**{user_info[1]}**", inline=True),
        EmbedField(name="**Text XP**", value=f"**{user_info[2]}**", inline=True),
    ]
    if next_rank:
        fields.append(EmbedField(name="**Next rank**", value=f"**{next_rank.mention} in {required_xp} voice xp**"))
    if curr_rank:
        desc = f"**{member.mention} currently has the {curr_rank.mention} rank**"
    else:
        desc = f"**{member.mention} currently has no ranks :c**"
    return create_embed(description=desc, color_tag="xp",
                        author_name=member.name, author_icon_url=member.display_avatar.url, thumbnail_url=member.display_avatar.url,
                        footer_text=member.guild.name, fields=fields)


def admin_list(admin_list, func, guild):
    ans = ""
    num = 0
    for admin in admin_list:
        user = func(admin)
        if user:
            num += 1
            ans += f"**{num}: **{user.mention}\n"
    return create_embed(color_tag="xp", fields=[EmbedField(name="**Admin list:**", value=ans)],
                        author_name=guild.name, author_icon_url=guild.icon.url, footer_text=guild.name)


def rank_list(ranks, guild):
    fields = []
    num = 0
    for rank in ranks:
        num += 1
        role = guild.get_role(rank.role_id)
        fields.append(EmbedField(value=f"**{num}. {role.mention} - {rank.voice_xp} XP**"))

    return create_embed(description="**Rank list:**", color_tag="xp", fields=fields, footer_text=guild.name, author_name=guild.name, author_icon_url=guild.icon.url)
