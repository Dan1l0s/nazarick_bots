import config


def is_admin(ctx):
    if ctx.guild.id not in config.admin_ids or ctx.author.id not in config.admin_ids[ctx.guild.id]:
        return False
    return True
