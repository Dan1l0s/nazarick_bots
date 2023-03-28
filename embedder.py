import disnake
import datetime
import helpers


class embed:
    def songs(self, ctx, info, text): #BLACK
        embed = disnake.Embed(
            title=info['description'],
            url=info['webpage_url'],
            description=text,
            color=disnake.Colour.from_rgb(0, 0, 0),
            timestamp=datetime.datetime.now())

        embed.set_author(name=info['uploader'])
        embed.set_thumbnail(url=f"https://img.youtube.com/vi/{info['id']}/0.jpg")
        embed.add_field(name="*Duration*",
                        value=helpers.get_duration(info['duration']), inline=True)
        embed.add_field(name="*Requested by*",
                        value=helpers.get_nickname(ctx.author), inline=True)
        return embed
    
    def action(self, entry): #White or SkyBlue
        if "member" in f'{entry.action}':
            embed = disnake.Embed(
                description=f'**{entry.user.mention} did `{entry.action}` to `{entry.target}`**'.replace('AuditLogAction.', ''),
                color=disnake.Colour.from_rgb(255, 255, 255),
                timestamp=datetime.datetime.now())
        else:
            embed = disnake.Embed(
                description=f'**{entry.user.mention} did `{entry.action}` to `{entry.target}`**'.replace('AuditLogAction.', ''),
                color=disnake.Colour.from_rgb(160, 220, 255),
                timestamp=datetime.datetime.now())
        embed.set_author(name = entry.user.name, icon_url= entry.user.avatar.url)
        embed.set_footer(text = f'{entry.user.guild.name}')
        return embed
    
    def switched(self, member, before, after): #Pink
        embed = disnake.Embed(
            description=f'**{member.mention} switched from `{before.channel.name}` to `{after.channel.name}`**',
            color=disnake.Colour.from_rgb(255, 180, 255),
            timestamp=datetime.datetime.now())
        embed.set_author(name = member.name, icon_url= member.avatar.url)
        embed.set_footer(text = f'{member.guild.name}')
        return embed
    
    def connected(self, member, after): #Green
        embed = disnake.Embed(
            description=f"**{member.mention} connected to `{after.channel.name}`**",
            color=disnake.Colour.from_rgb(0, 255, 0),
            timestamp=datetime.datetime.now())
        embed.set_author(name = member.name, icon_url= member.avatar.url)
        embed.set_footer(text = f'{member.guild.name}')
        return embed
    
    def disconnected(self, member, before): #Red
        embed = disnake.Embed(
            description=f'**{member.mention} disconnected from `{before.channel.name}`**',
            color=disnake.Colour.from_rgb(255, 0, 0),
            timestamp=datetime.datetime.now())
        embed.set_author(name = member.name, icon_url= member.avatar.url)
        embed.set_footer(text = f'{member.guild.name}')
        return embed
    
    def voice_update(self, member): #Yellow
        embed = disnake.Embed(
            description=f'**{member.mention} updated voice state**',
            color=disnake.Colour.from_rgb(255, 255, 0),
            timestamp=datetime.datetime.now())
        embed.set_author(name = member.name, icon_url= member.avatar.url)
        embed.set_footer(text = f'{member.guild.name}')
        return embed