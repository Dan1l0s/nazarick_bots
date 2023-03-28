import disnake
import datetime
import helpers


class embed:
    def songs(self, ctx, info, text): #BLACK
        embed = disnake.Embed(
            title=info['title'],
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
                title=f'`{entry.user}` did `{entry.action}` to `{entry.target}`'.replace('AuditLogAction.', ''),
                color=disnake.Colour.from_rgb(255, 255, 255),
                timestamp=datetime.datetime.now())
        else:
            embed = disnake.Embed(
                title=f'`{entry.user}` did `{entry.action}` to `{entry.target}`'.replace('AuditLogAction.', ''),
                color=disnake.Colour.from_rgb(160, 220, 255),
                timestamp=datetime.datetime.now())
        return embed
    
    def switched(self, member, before, after): #Pink
        embed = disnake.Embed(
            title=f'`{helpers.get_nickname(member)}` switched from `{before.channel.name}` to `{after.channel.name}`',
            color=disnake.Colour.from_rgb(255, 180, 255),
            timestamp=datetime.datetime.now())
        return embed
    
    def connected(self, member, after): #Green
        embed = disnake.Embed(
            title=f"`{helpers.get_nickname(member)}` connected to `{after.channel.name}`",
            color=disnake.Colour.from_rgb(0, 255, 0),
            timestamp=datetime.datetime.now())
        return embed
    
    def disconnected(self, member, before): #Red
        embed = disnake.Embed(
            title=f'`{helpers.get_nickname(member)}` disconnected from `{before.channel.name}`',
            color=disnake.Colour.from_rgb(255, 0, 0),
            timestamp=datetime.datetime.now())
        return embed
    
    def voice_update(self, member): #Yellow
        embed = disnake.Embed(
            title=f'`{helpers.get_nickname(member)}` updated voice state',
            color=disnake.Colour.from_rgb(255, 255, 0),
            timestamp=datetime.datetime.now())
        return embed