import datetime
import helpers

#----------------------------------------------------------------

def log_enabled():
    f = open("logs.txt", "a")
    f.write(
        f"{datetime.datetime.now()} : Bot is On\n")
    f.close()

#----------------------------------------------------------------

def log_audit_logged(entry):
    f = open("logs.txt", "a")
    f.write(
        f"{datetime.datetime.now()} : AUDIT_LOG : {entry.user} did {entry.action} to {entry.target}\n")
    f.close()

#----------------------------------------------------------------

def log_song_added(info, songs_queue, ctx):
    f = open("logs.txt", "a")
    f.write(
        f"{datetime.datetime.now()} : PLAY: Added {info['title']} to queue with duration of {helpers.get_duration(songs_queue[ctx.guild.id][0]['duration'])}\n")
    f.close()

#----------------------------------------------------------------

def log_playing_song(songs_queue, ctx, vcs):
    f=open("logs.txt", "a")
    f.write(
        f"{datetime.datetime.now()} : PLAY: Playing {songs_queue[ctx.guild.id][0]['title']} in vc: {ctx.guild.name} / {vcs[ctx.guild.id].channel}\n")
    f.close()

#----------------------------------------------------------------

def log_finished_playing(vcs, ctx):
    f = open("logs.txt", "a")
    f.write(
        f"{datetime.datetime.now()} : STOP: Finished playing in vc: {ctx.guild.name} / {vcs[ctx.guild.id].channel}\n")
    f.close()

#----------------------------------------------------------------

def log_skip(vcs, ctx):
    f = open("logs.txt", "a")
    f.write(
        f"{datetime.datetime.now()} : SKIP: Skipped track at {ctx.guild.name} / {vcs[ctx.guild.id].channel}\n")
    f.close()

#----------------------------------------------------------------

def log_err(err):
    f = open("logs.txt", "a")
    f.write(
        f"{datetime.datetime.now()} : ERROR :", err)
    f.close()

