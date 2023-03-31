import datetime
import helpers
import os


class logger:
    def __init__(self, songs_queue):
        self.songs_queue = songs_queue

    def error(self, err, guild):
        abs_path = self.get_path(guild.name)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + " : ERROR :" + err)
        f.close()

    def skip(self, ctx):
        abs_path = self.get_path(ctx.guild.name)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : SKIP : Skipped track at {ctx.guild.voice_client.channel}\n")
        f.close()

    def enabled(self, bot):
        abs_path = self.get_path("general")
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : STARTUP : Bot is logged as {bot.user}\n")
        f.close()
        print(f"Bot is logged as {bot.user}")

    def logged(self, entry):
        abs_path = self.get_path(entry.user.guild.name)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(datetime.datetime.now().strftime("%H:%M:%S") +
                f" : AUDIT_LOG : {entry.user} did {entry.action} to {entry.target}\n")
        f.close()

    def added(self, ctx):
        abs_path = self.get_path(ctx.guild.name)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : PLAY : Added {self.songs_queue[ctx.guild.id][-1]['title']} to queue with duration of {helpers.get_duration(self.songs_queue[ctx.guild.id][-1]['duration'])}\n")
        f.close()

    def playing(self, ctx):
        abs_path = self.get_path(ctx.guild.name)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : PLAY : Playing {self.songs_queue[ctx.guild.id][0]['title']} in VC: {ctx.guild.voice_client.channel}\n")
        f.close()

    def finished(self, ctx):
        abs_path = self.get_path(ctx.guild.name)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : STOP : Finished playing in VC: {ctx.guild.name} / {ctx.guild.voice_client.channel}\n")
        f.close()

    def switched(self, member, before, after):
        abs_path = self.get_path(member.guild.name)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : VC : User {helpers.get_nickname(member)} switched VC from {before.channel.name} to {after.channel.name}\n")
        f.close()

    def connected(self, member, after):
        abs_path = self.get_path(member.guild.name)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : VC : User {helpers.get_nickname(member)} joined VC {after.channel.name}\n")
        f.close()

    def disconnected(self, member, before):
        abs_path = self.get_path(member.guild.name)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : VC : User {helpers.get_nickname(member)} left VC {before.channel.name}\n")
        f.close()

    def get_path(self, dir_name: str):
        if not os.path.exists(f'logs/{dir_name}'):
            os.makedirs(f'logs/{dir_name}')
        file_name = datetime.datetime.now().strftime('%d-%m-%Y')
        script_dir = os.path.dirname(__file__)
        rel_path = f"logs/{dir_name}/{file_name}"
        abs_path = os.path.join(script_dir, rel_path)
        return abs_path
