import disnake
import datetime
import helpers
import config


class Embed:
    def songs(self, inter, data, text):
        info = data
        if "entries" in info:
            info = info["entries"][0]
        embed = disnake.Embed(
            title=info['title'],
            url=info['webpage_url'],
            description=text,
            color=disnake.Colour.from_rgb(
                *config.embed_colors["songs"]),
            timestamp=datetime.datetime.now())
        duration = helpers.get_duration(info)

        embed.set_author(name=info['uploader'])
        embed.set_thumbnail(
            url=f"https://img.youtube.com/vi/{info['id']}/0.jpg")
        embed.add_field(name="*Duration*",
                        value=duration, inline=True)
        embed.add_field(name="*Requested by*",
                        value=helpers.get_nickname(inter.author), inline=True)
        return embed

    def radio(self, data):
        embed = disnake.Embed(
            title=data['name'],
            description="Playing from ANISON.FM",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["songs"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=data['source'])
        embed.add_field(name="*Duration*",
                        value=helpers.get_duration(data),
                        inline=True)
        return embed

    def entry_channel_create(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} created channel {entry.user.guild.get_channel(entry.target.id).mention}**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["other_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        if hasattr(entry.after, 'name'):
            embed.add_field(name = "Channel Name", value = entry.after.name, inline = False)
        if hasattr(entry.after, 'type'):
            embed.add_field(name = "Channel Type", value = entry.after.type, inline = False)
        if hasattr(entry.after, 'bitrate'):
            embed.add_field(name = "Channel Bitrate", value = entry.after.bitrate, inline = False)
        if hasattr(entry.after, 'user_limit'):
            if entry.after.user_limit != 0:
                embed.add_field(name = "Channel User Limit", value = entry.after.user_limit, inline = False)
            else:
                embed.add_field(name = "Channel User Limit", value = "None", inline = False)                
        if hasattr(entry.after, 'nsfw'):
            embed.add_field(name = "Channel NSFW settings", value = entry.after.nsfw, inline = False)
        return embed
    
    def entry_channel_update(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} updated channel {entry.user.guild.get_channel(entry.target.id).mention}**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["other_action"]),
            timestamp=datetime.datetime.now())
        if hasattr(entry.before, 'name'):
            embed.add_field(name = "", value = "", inline = False)
            embed.add_field(name = "**Old Name:**", value = entry.before.name, inline = True)
            embed.add_field(name = "**New Name:**", value = entry.after.name, inline = True)
        if hasattr(entry.after, 'type'):
            embed.add_field(name = "", value = "", inline = False)
            embed.add_field(name = "**Old Type:**", value = entry.before.type, inline = True)
            embed.add_field(name = "**New Type:**", value = entry.after.type, inline = True)
        if hasattr(entry.after, 'bitrate'):
            embed.add_field(name = "", value = "", inline = False)
            embed.add_field(name = "**Old Bitrate:**", value = entry.before.bitrate, inline = True)
            embed.add_field(name = "**New Bitrate:**", value = entry.after.bitrate, inline = True)
        if hasattr(entry.after, 'rtc_region'):
            embed.add_field(name = "", value = "", inline = False)
            embed.add_field(name = "**Old RTC Region:**", value = entry.before.rtc_region, inline = True)
            embed.add_field(name = "**New RTC Region:**", value = entry.after.rtc_region, inline = True)
        if hasattr(entry.after, 'user_limit'):
            embed.add_field(name = "", value = "", inline = False)
            if entry.before.user_limit != 0:
                embed.add_field(name = "**Old User Limit:**", value = entry.before.user_limit, inline = True)
            else:
                embed.add_field(name = "**Old User Limit:**", value = "None", inline = True)
            if entry.after.user_limit != 0:
                embed.add_field(name = "**New User Limit:**", value = entry.after.user_limit, inline = True)
            else:
                embed.add_field(name = "**New User Limit:**", value = "None", inline = True)
        if hasattr(entry.after, 'nsfw'):
            if entry.before.nsfw:
                embed.add_field(name = "", value = "", inline = False)
                embed.add_field(name = "**Old NSFW settings:**", value = "NSFW", inline = True)
                embed.add_field(name = "**New NSFW settings:**", value = ":sob: Not NSFW", inline = True)
            else:
                embed.add_field(name = "", value = "", inline = False)
                embed.add_field(name = "**Old NSFW settings:**", value = "Not NSFW", inline = True)
                embed.add_field(name = "**New NSFW settings:**", value = ":smiling_imp: NSFW", inline = True)
        if hasattr(entry.after, 'position'):
            embed.add_field(name = "", value = "", inline = False)
            embed.add_field(name = "**Old Position:**", value = entry.before.position, inline = True)
            embed.add_field(name = "**New Position:**", value = entry.after.position, inline = True)
        if hasattr(entry.after, 'topic'):
            embed.add_field(name = "", value = "", inline = False)
            embed.add_field(name = "**Old Topic:**", value = entry.before.topic, inline = True)
            embed.add_field(name = "**New Topic:**", value = entry.after.topic, inline = True)
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_channel_delete(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} deleted channel `{entry.before.name}`**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["other_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_kick(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} kicked member `{entry.target.name}`**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.add_field(name="**REASON:**", value = f'{entry.reason}')
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_ban(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} banned member `{entry.target.name}`**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.add_field(name="**REASON:**", value = f'{entry.reason}')
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_unban(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} unbanned user `{entry.target.name}`**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_member_move(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} moved a user to {entry.user.guild.get_channel(entry.extra.channel.id).mention}**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_member_update(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} updated user {entry.target.mention}**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        if hasattr(entry.before, "nick"):
            if entry.before.nick != None:
                embed.add_field(name="**Old Nickname:**", value = f'`{entry.before.nick}`')
            if entry.after.nick != None:
                embed.add_field(name="**New Nickname:**", value = f'`{entry.after.nick}`')
        if hasattr(entry.after, "timeout"):
            if entry.after.timeout != None:
                embed.add_field(name="**Timeout expiration date:**", value = entry.after.timeout.strftime("%d/%m %H:%M:%S"))
            else:
                embed.add_field(name="**Timeout:**", value = "Timeout has been removed")
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_member_role_update(self, entry):
        x = entry.after.roles
        z = entry.before.roles
        embed = disnake.Embed(
            description=f"**{entry.user.mention} updated user {entry.target.mention}'s roles**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        for y in range(len(x)):
            embed.add_field(name = f"Role added:", value = x[y].name)
        for y in range(len(z)):
            embed.add_field(name = f"Role removed:", value = z[y].name)
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed

    def entry_member_disconnect(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} disconnected {entry.extra.count} user(s) from a voice channel**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
# --------------------- CHANNEL SWITCHING --------------------------------

    def switched(self, member, before, after):
        embed = disnake.Embed(
            description=f'**{member.mention} switched from `{before.channel.name}` to `{after.channel.name}`**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["vc"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed

    def connected(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention} joined voice channel `{after.channel.name}`**",
            color=disnake.Colour.from_rgb(*config.embed_colors["vc"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed

    def disconnected(self, member, before):
        embed = disnake.Embed(
            description=f'**{member.mention} left voice channel `{before.channel.name}`**',
            color=disnake.Colour.from_rgb(*config.embed_colors["vc"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed
    
    def afk(self, member, after):
        embed = disnake.Embed(
            description=f'**{member.mention} has gone AFK in `{after.channel.name}`**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["vc"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed

# --------------------- USER ACTIONS --------------------------------

    def welcome_message(self, member):
        embed = disnake.Embed(
            description=f'**{member.mention}, welcome to {helpers.get_guild_name(member.guild)}!**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["welcome_message"]),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=member.name, icon_url=member.display_avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        embed.add_field(name="**⏲ Age of account:**", value=f'`{member.created_at.strftime("%d/%m/%Y %H:%M")}`\n**{helpers.get_welcome_time(member.created_at)}**',
                        inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        return embed
    
    def profile_upd(self,member):
        embed = disnake.Embed(
            description=f'**{member.mention} has updated their profile**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["member_action"]),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=member.name, icon_url=member.display_avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        embed.set_thumbnail(url=member.display_avatar.url)
        return embed
    
    def member_remove(self, payload):
        embed = disnake.Embed(
            description=f'**:no_entry_sign: {payload.user.mention} has left the server**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["Ban_leave"]),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=payload.user.name, icon_url=payload.user.display_avatar.url)
        embed.set_footer(text=f'{payload.user.guild.name}')
        embed.set_thumbnail(url=payload.user.display_avatar.url)
        return embed
    
    def member_join(self, member):
        embed = disnake.Embed(
            description=f'**:white_check_mark: {member.mention} has joined the server**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["welcome_message"]),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=member.name, icon_url=member.display_avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        embed.add_field(name="**⏲ Age of account:**", value=f'`{member.created_at.strftime("%d/%m/%Y %H:%M")}`\n**{helpers.get_welcome_time(member.created_at)}**',
                        inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        return embed
    
    def ban(self, guild, user):
        embed = disnake.Embed(
            description=f'**:CatBan: {user.mention} has been banned from {guild.name}**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["Ban_leave"]),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=user.name, icon_url=user.display_avatar.url)
        embed.set_footer(text=f'{guild.name}')
        embed.set_thumbnail(url=user.display_avatar.url)
        return embed
    
    def unban(self, guild, user):
        embed = disnake.Embed(
            description=f'**:ballot_box_with_check: {user.mention} has been unbanned from {guild.name}**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["welcome_message"]),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name=user.name, icon_url=user.display_avatar.url)
        embed.set_footer(text=f'{guild.name}')
        embed.set_thumbnail(url=user.display_avatar.url)
        return embed

# --------------------- MESSAGES --------------------------------

    def message_edit(self, before, after):
        embed = disnake.Embed(
            description=f'**:pencil2:{before.author.mention} has edited a message in {before.channel.mention}. [Jump to message]({before.jump_url})**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["Message"]),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name = before.author, icon_url = before.author.display_avatar.url)
        embed.set_footer(text=f'{before.guild.name}')
        embed.add_field(name="** Before: **", value = f'`{before.content}`')
        embed.add_field(name="** After: **", value = f'`{after.content}`')
        return embed
    
    def message_pin(self, before, after):
        embed = disnake.Embed(
            description=f'**:pushpin:A Message has been pinned in {before.channel.mention}. [Jump to message]({before.jump_url})**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["Message"]),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name = before.guild.name, icon_url = before.guild.icon.url)
        embed.set_footer(text=f'{before.guild.name}')
        embed.add_field(name="** Message Author: **", value = f'{before.author.mention}')
        embed.add_field(name="** Message Content: **", value = f'`{after.content}`\n')
        return embed
    
    def message_unpin(self, before, after):
        embed = disnake.Embed(
            description=f'**:pushpin:A Message has been unpinned in {before.channel.mention}. [Jump to message]({before.jump_url})**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["Message"]),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name = before.guild.name, icon_url = before.guild.icon.url)
        embed.set_footer(text=f'{before.guild.name}')
        embed.add_field(name="** Message Author: **", value = f'{before.author.mention}\n')
        embed.add_field(name="** Message Content: **", value = f'`{after.content}`\n')
        return embed
    
    def message_delete(self, message):
        embed = disnake.Embed(
            description=f'**:wastebasket:A Message sent by {message.author} has been deleted in `{message.channel}`.**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["Message"]),
            timestamp=datetime.datetime.now()
        )
        embed.set_author(name = message.author, icon_url = message.author.display_avatar.url)
        embed.set_footer(text=f'{message.channel.guild.name}')
        embed.add_field(name="** Message Content: **", value = f'`{message.content}`\n')
        return embed
    
# --------------------- VOICE STATES --------------------------------
    
    def sv_mute(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention}'s voice state has been updated**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        if after.mute:
            embed.add_field(name = f":microphone2:** Server Mute**", value = "Yes")
        else:
            embed.add_field(name = f":microphone2:** Server Mute**", value = "No")
        return embed
    
    def sv_deaf(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention}'s voice state has been updated**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        if after.deaf:
            embed.add_field(name = f":mute:** Server Deafen**", value = "Yes")
        else:
            embed.add_field(name = f":mute:** Server Deafen**", value = "No")
        return embed
    
    def self_mute(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention} updated their own voice state**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        if after.self_mute:
            embed.add_field(name = f":microphone2:** Muted**", value = "Yes")
        else:
            embed.add_field(name = f":microphone2:** Muted**", value = "No")
        return embed
    
    def self_deaf(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention} updated their own voice state**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        if after.self_deaf:
            embed.add_field(name = f":mute:** Deafened**", value = "Yes")
        else:
            embed.add_field(name = f":mute:** Deafened**", value = "No")
        return embed
    
    def stream(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention} updated their stream status**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        if after.self_stream:
            embed.add_field(name = f":tv:** Stream Enabled**", value = "Enabled")
        else:
            embed.add_field(name = f":tv:** Stream Enabled**", value = "Disabled")
        return embed
    
    def video(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention} updated their video status**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        if after.self_video:
            embed.add_field(name = f":video_camera:** Video Enabled**", value = "Enabled")
        else:
            embed.add_field(name = f":video_camera:** Video Enabled**", value = "Disabled")
        return embed