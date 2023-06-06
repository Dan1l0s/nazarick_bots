import disnake
import datetime
import helpers
import config
import dicts

class Embed:
    def songs(self, client, data, text):
        info = data
        if "entries" in info:
            info = info["entries"][0]
        embed = disnake.Embed(
            title=info['title'],
            url=info['webpage_url'],
            description=text,
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["songs"]),
            timestamp=datetime.datetime.now())
        duration = helpers.get_duration(info)

        embed.set_author(name=info['uploader'])
        embed.set_thumbnail(
            url=f"https://img.youtube.com/vi/{info['id']}/0.jpg")
        embed.add_field(name="*Duration*",
                        value=duration, inline=True)
        embed.add_field(name="*Requested by*",
                        value=client.display_name, inline=True)
        embed.add_field(name="*Channel*",
                        value=client.voice.channel.name, inline=True)
        return embed

    def radio(self, data):
        embed = disnake.Embed(
            title=data['name'],
            description="Playing from ANISON.FM",
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["songs"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=data['source'])
        embed.add_field(name="*Duration*",
                        value=helpers.get_duration(data),
                        inline=True)
        embed.add_field(name="*Channel*",
                        value=data['channel'].name, inline=True)
        return embed

# --------------------- Entry Actions --------------------------------

    def entry_channel_create(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} created channel {entry.user.guild.get_channel(entry.target.id).mention}**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["other_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        for attr in entry.after.__dict__.keys():
            if attr in dicts.channel_create:
                embed.add_field(name = f"**{helpers.parse_key(attr)}**", value = f"{getattr(entry.after, attr)}", inline = False)
        return embed
    
    def entry_channel_update(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} updated channel {entry.user.guild.get_channel(entry.target.id).mention}**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["other_action"]),
            timestamp=datetime.datetime.now())
        for attr in entry.after.__dict__.keys():
            if attr in dicts.channel_update:
                embed.add_field(name = "", value = "", inline = False)
                embed.add_field(name = f"**Old {helpers.parse_key(attr)}**", value = f"{getattr(entry.before, attr)}", inline = True)
                embed.add_field(name = f"**New {helpers.parse_key(attr)}**", value = f"{getattr(entry.after, attr)}", inline = True)
        if hasattr(entry.after, 'nsfw'):
            if entry.before.nsfw:
                embed.add_field(name = "", value = "", inline = False)
                embed.add_field(name = "**Old NSFW settings:**", value = "NSFW", inline = True)
                embed.add_field(name = "**New NSFW settings:**", value = ":sob: Not NSFW", inline = True)
            else:
                embed.add_field(name = "", value = "", inline = False)
                embed.add_field(name = "**Old NSFW settings:**", value = "Not NSFW", inline = True)
                embed.add_field(name = "**New NSFW settings:**", value = ":smiling_imp: NSFW", inline = True)
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_channel_delete(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} deleted channel `{entry.before.name}`**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["other_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_kick(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} kicked member `{entry.target.name}`**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.add_field(name="**REASON:**", value = f'{entry.reason}')
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_ban(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} banned member `{entry.target.name}`**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.add_field(name="**REASON:**", value = f'{entry.reason}')
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_unban(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} unbanned user `{entry.target.name}`**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_member_move(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} moved a user to {entry.user.guild.get_channel(entry.extra.channel.id).mention}**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_member_update(self, entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} updated user {entry.target.mention}**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["member_action"]),
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
                *dicts.embed_colors["member_action"]),
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
                *dicts.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_role_create(self,entry):
        embed = disnake.Embed(
            description=f'**A new role has been added to the Guild by {entry.user.mention}**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["other_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        if hasattr(entry.after, "name"):
            embed.add_field(name = "**Role name:**", value = entry.after.name)
        return embed

    def entry_role_update(self,entry):
        embed = disnake.Embed(
            description=f'**The role {entry.target.mention} has been updated by {entry.user.mention}**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["other_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        if hasattr(entry.after, "name"):
            embed.add_field(name = "**New Role name:**", value = entry.after.name)
        if hasattr(entry.after, "icon"):
            embed.set_thumbnail(url = entry.after.icon.url)
        if hasattr(entry.after, "colour"):
            embed.add_field(name = "**Role Color:**", value = f'Red : {entry.after.colour.r}\nGreen : {entry.after.colour.g}\nBlue : {entry.after.colour.b}')
        #PERMISSIONS 
        if hasattr(entry.after, "permissions"):
            perms = []
            for attr in entry.after.__dict__.keys():
                if attr in dicts.permissions_list:
                    if (getattr(entry.before.permissions, attr) != getattr(entry.after.permissions, attr)):
                        perms += [f"{dicts.emojis['true']} {helpers.parse_key(attr)}"] if getattr(entry.before.permissions, attr) == False else [f"{dicts.emojis['false']} {helpers.parse_key(attr)}"]           
            perms = '\n'.join(perms)
            embed.add_field(name = "**CHANGED PERMISSIONS:**", value = perms, inline = False)
        return embed
    
    def entry_role_delete(self,entry):
        embed = disnake.Embed(
            description=f'**A role has been deleted by {entry.user.mention} from the guild**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["other_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        for attr in entry.before.__dict__.keys():
            if attr in dicts.role_delete:              
                embed.add_field(name = f"**{helpers.parse_key(attr)}**", value = f"{getattr(entry.before, attr)}", inline = False)
        return embed
    
    def entry_guild_update(self,entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} has updated the Guild**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["other_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        for attr in entry.before.__dict__.keys():
            if attr in dicts.guild_update:
                embed.add_field(name = "", value = "", inline = False)
                embed.add_field(name = f"**Old {helpers.parse_key(attr)}**", value = f"{getattr(entry.before, attr)}", inline = True)
                embed.add_field(name = f"**New {helpers.parse_key(attr)}**", value = f"{getattr(entry.after, attr)}", inline = True)
        return embed
    
    def entry_member_prune(self,entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} has pruned members from the Guild**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        embed.add_field(name = "**Members Removed:**", value = entry.extra.members_removed, inline = False)
        embed.add_field(name = "**Prune size:**", value = entry.extra.delete_members_days, inline = False)
        return embed
        
    def entry_invite_create(self,entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} has created an invite to the Guild**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        if hasattr(entry.after, 'channel'):
            embed.add_field(name = "**Channel:**", value = entry.after.channel.mention, inline = False)
        for attr in entry.after.__dict__.keys():
            if attr in dicts.invites:
                embed.add_field(name = f"**{helpers.parse_key(attr)}**", value = f"{getattr(entry.after, attr)}", inline = False)
        return embed
    
    def entry_invite_update(self,entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} has updated an invite to the Guild**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        return embed
    
    def entry_invite_delete(self,entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} has deleted an invite to the Guild**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        if hasattr(entry.before, 'channel'):
            embed.add_field(name = "**Channel:**", value = entry.after.channel.mention, inline = False)
        for attr in entry.before.__dict__.keys():
            if attr in dicts.invites:
                embed.add_field(name = f"**{helpers.parse_key(attr)}**", value = f"{getattr(entry.before, attr)}", inline = False)
        return embed
    
    def entry_emoji_create(self,entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} has added an emoji to the Guild**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["other_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        embed.add_field(name = "**Emoji:**", value = entry.after.name, inline = False)
        return embed
    
    def entry_emoji_update(self,entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} has updated an emoji in the Guild**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["other_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        embed.add_field(name = "**Old Emoji Name:**", value = entry.before.name, inline = False)
        embed.add_field(name = "**New Emoji Name:**", value = entry.after.name, inline = False)

        return embed
    
    def entry_emoji_delete(self,entry):
        embed = disnake.Embed(
            description=f'**{entry.user.mention} has removed an emoji from the Guild**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        embed.add_field(name = "**Emoji:**", value = entry.before.name, inline = False)
        return embed

    def entry_message_delete(self,entry):
        embed = disnake.Embed(
            description=f"**{entry.target.mention}'s messages have been deleted by moderator {entry.user.mention}**",
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["member_action"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=entry.user.name, icon_url=entry.user.avatar.url)
        embed.set_footer(text=f'{entry.user.guild.name}')
        embed.add_field(name = "**Channel from which the messages were deleted**", value = entry.extra.channel.mention, inline = False)
        embed.add_field(name = "**Amount of deleted messages**", value = entry.extra.count, inline = False)
        return embed
    
# --------------------- CHANNEL SWITCHING --------------------------------

    def switched(self, member, before, after):
        embed = disnake.Embed(
            description=f'**{member.mention} switched from `{before.channel.name}` to `{after.channel.name}`**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["vc"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.display_avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed

    def connected(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention} joined voice channel `{after.channel.name}`**",
            color=disnake.Colour.from_rgb(*dicts.embed_colors["vc"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.display_avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed

    def disconnected(self, member, before):
        embed = disnake.Embed(
            description=f'**{member.mention} left voice channel `{before.channel.name}`**',
            color=disnake.Colour.from_rgb(*dicts.embed_colors["vc"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.display_avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed
    
    def afk(self, member, after):
        embed = disnake.Embed(
            description=f'**{member.mention} has gone AFK in `{after.channel.name}`**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["vc"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed

# --------------------- USER ACTIONS --------------------------------

    def welcome_message(self, member):
        embed = disnake.Embed(
            description=f'**{member.mention}, welcome to {helpers.get_guild_name(member.guild)}!**',
            color=disnake.Colour.from_rgb(
                *dicts.embed_colors["welcome_message"]),
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
                *dicts.embed_colors["member_action"]),
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
                *dicts.embed_colors["ban_leave"]),
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
                *dicts.embed_colors["welcome_message"]),
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
                *dicts.embed_colors["ban_leave"]),
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
                *dicts.embed_colors["welcome_message"]),
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
                *dicts.embed_colors["message"]),
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
                *dicts.embed_colors["message"]),
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
                *dicts.embed_colors["message"]),
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
                *dicts.embed_colors["message"]),
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
                *dicts.embed_colors["voice_update"]),
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
                *dicts.embed_colors["voice_update"]),
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
                *dicts.embed_colors["voice_update"]),
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
                *dicts.embed_colors["voice_update"]),
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
                *dicts.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.display_avatar.url)
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
                *dicts.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        if after.self_video:
            embed.add_field(name = f":video_camera:** Video Enabled**", value = "Enabled")
        else:
            embed.add_field(name = f":video_camera:** Video Enabled**", value = "Disabled")
        return embed