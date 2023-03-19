import config
import disnake
import datetime


def is_admin(ctx):
    if ctx.guild.id not in config.admin_ids or ctx.author.id not in config.admin_ids[ctx.guild.id]:
        return False
    return True


def get_nickname(member):
    if member.nick:
        return member.nick
    else:
        return member.name


def get_duration(duration):
    ans = ""
    hours = duration // 3600
    minutes = (duration // 60) - hours*60
    seconds = duration % 60
    if hours == 0:
        ans += "00"
    elif hours < 10:
        ans += "0"+str(hours)
    else:
        ans += str(hours)

    if minutes == 0:
        ans += ":00"
    elif minutes < 10:
        ans += ":0"+str(minutes)
    else:
        ans += ":"+str(minutes)

    if seconds == 0:
        ans += ":00"
    elif seconds < 10:
        ans += ":0"+str(seconds)
    else:
        ans += ":"+str(seconds)
    return ans


def song_embed_builder(ctx, info, text):
    embed = disnake.Embed(
        title=info['title'],
        url=info['webpage_url'],
        description=text,
        color=disnake.Colour.from_rgb(0, 0, 0),
        timestamp=datetime.datetime.now())

    embed.set_author(name=info['uploader'])
    embed.set_thumbnail(url=f"https://img.youtube.com/vi/{info['id']}/0.jpg")
    embed.add_field(name="*Duration*",
                    value=get_duration(info['duration']), inline=True)
    embed.add_field(name="*Requested by*",
                    value=get_nickname(ctx.author), inline=True)
    return embed
