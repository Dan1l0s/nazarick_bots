import datetime
import helpers

class logger:
    def __init__(self, file, vcs, songs_queue):
        self.file = file
        self.vcs = vcs
        self.songs_queue = songs_queue
        
    def error(self, err):
        f = open(f'{self.file}.txt', "a")
        f.write(
            f"{datetime.datetime.now()} : ERROR :" + err)
        f.close()

    def skip(self, ctx):
        f = open(f'{self.file}.txt', "a")
        f.write(
            f"{datetime.datetime.now()} : SKIP: Skipped track at {ctx.guild.name} / {self.vcs[ctx.guild.id].channel}\n")
        f.close()

    def enabled(self):
        f = open(f'{self.file}.txt', "a")
        f.write(
            f"{datetime.datetime.now()} : Bot is On\n")
        f.close()

    def logged(self, entry):
        f = open(f'{self.file}.txt', "a")
        f.write(
            f"{datetime.datetime.now()} : AUDIT_LOG : {entry.user} did {entry.action} to {entry.target}\n")
        f.close()

    def added(self, info, ctx):
        f = open(f'{self.file}.txt', "a")
        f.write(
            f"{datetime.datetime.now()} : PLAY: Added {info['title']} to queue with duration of {helpers.get_duration(self.songs_queue[ctx.guild.id][0]['duration'])}\n")
        f.close()

    def playing(self, ctx):
        f = open(f'{self.file}.txt', "a")
        f.write(
            f"{datetime.datetime.now()} : PLAY: Playing {self.songs_queue[ctx.guild.id][0]['title']} in vc: {ctx.guild.name} / {self.vcs[ctx.guild.id].channel}\n")
        f.close()

    def finished(self, ctx):
        f = open(f'{self.file}.txt', "a")
        f.write(
            f"{datetime.datetime.now()} : STOP: Finished playing in vc: {ctx.guild.name} / {self.vcs[ctx.guild.id].channel}\n")
        f.close()
