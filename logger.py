import datetime
import helpers
import os

# Generating 'logs' folder and a path to new log file

x = datetime.datetime.now()
if not os.path.exists('logs'):
   os.makedirs('logs')
file_name = x.strftime('%d-%m-%Y')
script_dir = os.path.dirname(__file__)
rel_path = "logs/" + file_name
abs_path = os.path.join(script_dir, rel_path)

#Logger

class logger:
    def __init__(self, vcs, songs_queue):
        self.vcs = vcs
        self.songs_queue = songs_queue
        
    def error(self, err):
        f = open(f'{abs_path}.txt', "a")
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + " : ERROR :" + err)
        f.close()

    def skip(self, ctx):
        f = open(f'{abs_path}.txt', "a")
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + " : SKIP : Skipped track at {ctx.guild.name} / {self.vcs[ctx.guild.id].channel}\n")
        f.close()

    def enabled(self):
        f = open(f'{abs_path}.txt', "a")
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + " : Bot is On\n")
        f.close()

    def logged(self, entry):
        f = open(f'{abs_path}.txt', "a")
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : AUDIT_LOG : {entry.user} did {entry.action} to {entry.target}\n")
        f.close()

    def added(self, info, ctx):
        f = open(f'{abs_path}.txt', "a")
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : PLAY : Added {info['title']} to queue with duration of {helpers.get_duration(self.songs_queue[ctx.guild.id][0]['duration'])}\n")
        f.close()

    def playing(self, ctx):
        f = open(f'{abs_path}.txt', "a")
        f.write(
           datetime.datetime.now().strftime("%H:%M:%S") + f" : PLAY : Playing {self.songs_queue[ctx.guild.id][0]['title']} in vc: {ctx.guild.name} / {self.vcs[ctx.guild.id].channel}\n")
        f.close()

    def finished(self, ctx):
        f = open(f'{abs_path}.txt', "a")
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : STOP : Finished playing in vc: {ctx.guild.name} / {self.vcs[ctx.guild.id].channel}\n")
        f.close()
