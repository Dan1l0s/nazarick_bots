import disnake
import datetime
import helpers
import config


class embed:
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
        if "live_status" in info and info['live_status'] == "is_live":
            duration = "Live"
        else:
            duration = helpers.get_duration(info['duration'])

        embed.set_author(name=info['uploader'])
        embed.set_thumbnail(
            url=f"https://img.youtube.com/vi/{info['id']}/0.jpg")
        embed.add_field(name="*Duration*",
                        value=duration, inline=True)
        embed.add_field(name="*Requested by*",
                        value=helpers.get_nickname(inter.author), inline=True)
        return embed

    def radio(self, title, source, duration):
        embed = disnake.Embed(
            title=title,
            description="Playing from ANISON.FM",
            color=disnake.Colour.from_rgb(
                *config.embed_colors["songs"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=source)
        embed.add_field(name="*Duration*",
                        value=helpers.get_duration(duration),
                        inline=True)
        return embed

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

    def switched(self, member, before, after):
        embed = disnake.Embed(
            description=f'**{member.mention} switched from `{before.channel.name}` to `{after.channel.name}`**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["switched_vc"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed

    def connected(self, member, after):
        embed = disnake.Embed(
            description=f"**{member.mention} connected to `{after.channel.name}`**",
            color=disnake.Colour.from_rgb(*config.embed_colors["joined_vc"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed

    def disconnected(self, member, before):
        embed = disnake.Embed(
            description=f'**{member.mention} disconnected from `{before.channel.name}`**',
            color=disnake.Colour.from_rgb(*config.embed_colors["left_vc"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed

    def voice_update(self, member):
        embed = disnake.Embed(
            description=f'**{member.mention} updated voice state**',
            color=disnake.Colour.from_rgb(
                *config.embed_colors["voice_update"]),
            timestamp=datetime.datetime.now())
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        embed.set_footer(text=f'{member.guild.name}')
        return embed
