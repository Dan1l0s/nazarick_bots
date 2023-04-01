import config


def is_admin(member):
    if member.guild.id not in config.admin_ids or member.id not in config.admin_ids[member.guild.id]:
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
