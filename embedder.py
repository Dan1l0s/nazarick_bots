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

# --------------------- ACTIONS --------------------------------

    def action(self, entry):
        if "member" in f'{entry.action}':
            embed = disnake.Embed(
                description=f'**{entry.user.mention} did `{entry.action}` to `{entry.target}`**'.replace(
                    'AuditLogAction.', ''),
                color=disnake.Colour.from_rgb(
                    *config.embed_colors["member_action"]),
                timestamp=datetime.datetime.now())
        else:
            embed = disnake.Embed(
                description=f'**{entry.user.mention} did `{entry.action}` to `{entry.target}`**'.replace(
                    'AuditLogAction.', ''),
                color=disnake.Colour.from_rgb(
                    *config.embed_colors["other_action"]),
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
            description=f"**{member.mention} connected to `{after.channel.name}`**",
            color=disnake.Colour.from_rgb(*config.embed_colors["vc"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed

    def disconnected(self, member, before):
        embed = disnake.Embed(
            description=f'**{member.mention} disconnected from `{before.channel.name}`**',
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
        embed.add_field(name="**⏲ Age of account:**", value=f'`{payload.user.created_at.strftime("%d/%m/%Y %H:%M")}`\n**{helpers.get_welcome_time(payload.user.created_at)}**',
                        inline=True)
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

    def voice_update(self, member):
        embed = disnake.Embed(
            description=f'**{member.mention} updated voice state**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed
    
    def sv_mute(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention}'s voice state has been updated**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        embed.add_field(name = f":speaker:** Server Mute**", value = after.mute)
        return embed
    
    def sv_deaf(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention}'s voice state has been updated**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        embed.add_field(name = f":headphones:** Server Deafen**", value = after.deaf)
        return embed
    
    def self_mute(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention} updated their own voice state**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        embed.add_field(name = f":speaker:** Muted**", value = after.self_mute)
        return embed
    
    def self_deaf(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention} updated their own voice state**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        embed.add_field(name = f":headphones:** Deafened**", value = after.self_deaf)
        return embed
    
    def stream(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention} updated their stream status**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        embed.add_field(name = f":tv:** Stream Enabled**", value = after.self_stream)
        return embed
    
    def video(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention} updated their video status**",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        embed.add_field(name = f":video_camera:** Video Enabled**", value = after.self_video)
        return embed