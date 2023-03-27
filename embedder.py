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
    
    def action(self, entry): #WHITE
        embed = disnake.Embed(
            title=f'`{entry.user}` did `{entry.action}` to `{entry.target}`',
            color=disnake.Colour.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.now())
        return embed
    
    def switched(self, member, before, after): #PINK
        embed = disnake.Embed(
            title=f'`{helpers.get_nickname(member)}` switched from `{before.channel.name}` to `{after.channel.name}`',
            color=disnake.Colour.from_rgb(255, 180, 255),
            timestamp=datetime.datetime.now())
        return embed
    
    def connected(self, member, after): #GREEN:
        embed = disnake.Embed(
            title=f"`{helpers.get_nickname(member)}` connected to `{after.channel.name}`",
            color=disnake.Colour.from_rgb(0, 255, 0),
            timestamp=datetime.datetime.now())
        return embed
    
    def disconnected(self, member, before): #RED
        embed = disnake.Embed(
            title=f'`{helpers.get_nickname(member)}` disconnected from `{before.channel.name}`',
            color=disnake.Colour.from_rgb(255, 0, 0),
            timestamp=datetime.datetime.now())
        return embed
    
    