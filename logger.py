import datetime
import helpers
import os
import disnake

class Logger:
    def __init__(self, state: bool):
        self.state = state

    def error(self, err, guild):
        if not self.state:
            return
        abs_path = self.get_path(guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + " : ERROR : " + str(err) + "\n")
        f.close()

#---------------- BASIC BOT ----------------------------------------------------------------

    def enabled(self, bot):
        if not self.state:
            return
        abs_path = self.get_path("general")
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : STARTUP : Bot is logged as {bot.user}\n")
        f.close()

    def lost_connection(self, bot):
        if not self.state:
            return
        abs_path = self.get_path("general")
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : BOT : Bot {bot.user} lost connection to Discord servers\n")
        f.close()

#---------------- MUSIC BOT ----------------------------------------------------------------

    def skip(self, inter):
        if not self.state:
            return
        abs_path = self.get_path(inter.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : SKIP : Skipped track in VC: {inter.guild.voice_client.channel}\n")
        f.close()
    
    def added(self, guild, track):
        if not self.state:
            return
        abs_path = self.get_path(guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : PLAY : Added {track['title']} to queue with duration of {helpers.get_duration(track)}\n")
        f.close()

    def playing(self, guild, track):
        if not self.state:
            return
        abs_path = self.get_path(guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : PLAY : Playing {track['title']} in VC: {guild.voice_client.channel}\n")
        f.close()

    def radio(self, guild, data):
        if not self.state:
            return
        abs_path = self.get_path(guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : RADIO : Playing {data['name']} in VC: {guild.voice_client.channel}\n")
        f.close()

    def finished(self, inter):
        if not self.state:
            return
        abs_path = self.get_path(inter.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : STOP : Finished playing in VC: {inter.guild.voice_client.channel}\n")
        f.close()

#---------------- ACTIONS ----------------------------------------------------------------

    def switched(self, member, before, after):
        if not self.state:
            return
        abs_path = self.get_path(member.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : VC : User {member} switched VC from {before.channel.name} to {after.channel.name}\n")
        f.close()

    def connected(self, member, after):
        if not self.state:
            return
        abs_path = self.get_path(member.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : VC : User {member} joined VC {after.channel.name}\n")
        f.close()

    def disconnected(self, member, before):
        if not self.state:
            return
        abs_path = self.get_path(member.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : VC : User {member} left VC {before.channel.name}\n")
        f.close()

    def deaf(self, member, after):
        if not self.state:
            return
        abs_path = self.get_path(member.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + (f" : VC : User {member} was deafened in guild\n" if after.deaf else f" : VC : User {member} was undeafened in guild\n"))
        f.close()

    def mute(self, member, after):
        if not self.state:
            return
        abs_path = self.get_path(member.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + (f" : VC : User {member} was muted in guild\n" if after.mute else f" : VC : User {member} was unmuted in guild\n"))
        f.close()

    def self_deaf(self, member, after):
        if not self.state:
            return
        abs_path = self.get_path(member.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + (f" : VC : User {member} deafened themself\n" if after.self_deaf else f" : VC : User {member} undeafened themself\n"))
        f.close()

    def self_mute(self, member, after):
        if not self.state:
            return
        abs_path = self.get_path(member.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + (f" : VC : User {member} muted themself\n" if after.self_mute else f" : VC : User {member} unmuted themself\n"))
        f.close()

    def self_video(self, member, after):
        if not self.state:
            return
        abs_path = self.get_path(member.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + (f" : VC : User {member} turned on their camera\n" if after.self_video else f" : VC : User {member} turned off their camera\n"))
        f.close()

    def self_stream(self, member, after):
        if not self.state:
            return
        abs_path = self.get_path(member.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + (f" : VC : User {member} started sharing their screen\n" if after.self_stream else f" : VC : User {member} stopped sharing their screen\n"))
        f.close()

    def member_join(self, member):
        if not self.state:
            return
        abs_path = self.get_path(member.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : GUILD : User {member} has joined the server\n")
        f.close()

    def member_remove(self, payload):
        if not self.state:
            return
        abs_path = self.get_path(payload.guild_id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : GUILD : User {payload.user} has left the server\n")
        f.close()

    def member_update(self, after):
        if not self.state:
            return
        abs_path = self.get_path(after.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : GUILD : User {after.name} has left the server\n")
        f.close()

#---------------- ENTRY_ACTION ----------------------------------------------------------------

    def entry_channel_create(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has created channel {entry.target.name}\n")
        f.close()

    def entry_channel_update(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has updated channel {entry.target.name}\n")
        f.close()    

    def entry_channel_delete(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has deleted channel {entry.before.name}\n")
        f.close()

    def entry_thread_create(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has created thread {entry.target.name}\n")
        f.close()

    def entry_thread_update(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has updated thread {entry.target.name}\n")
        f.close()    

    def entry_thread_delete(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has deleted thread {entry.before.name}\n")
        f.close()

    def entry_role_create(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has created role {entry.target.name}\n")
        f.close()

    def entry_role_update(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has updated role {entry.target.name}\n")
        f.close()    

    def entry_role_delete(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has deleted role {entry.before.name}\n")
        f.close()

    def entry_emoji_create(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has created emoji {entry.target.name}\n")
        f.close()

    def entry_emoji_update(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has updated emoji {entry.target.name}\n")
        f.close()    

    def entry_emoji_delete(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has deleted emoji {entry.before.name}\n")
        f.close()

    def entry_invite_create(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has created an invite\n")
        f.close()

    def entry_invite_update(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has updated an invite\n")
        f.close()    

    def entry_invite_delete(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has deleted an invite\n")
        f.close()

    def entry_sticker_create(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has created a sticker\n")
        f.close()

    def entry_sticker_update(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has updated a sticker\n")
        f.close()    

    def entry_sticker_delete(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has deleted a sticker\n")
        f.close()

    def entry_guild_scheduled_event_create(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has created a scheduled guild event\n")
        f.close()

    def entry_guild_scheduled_event_update(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has updated a scheduled guild event\n")
        f.close()    

    def entry_guild_scheduled_event_delete(self, entry):
        if not self.state:
            return
        abs_path = self.get_path(entry.user.guild.id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : ENTRY : User {entry.user} has deleted a scheduled guild event\n")
        f.close()    

#---------------- GPT ----------------------------------------------------------------

    def gpt(self, member, messages, guild_id="gpt"):
        if not self.state:
            return
        abs_path = self.get_path(guild_id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : GPT : User {member} used GPT with the query: `{messages[0]}` and got response `{messages[1]}`\n")
        f.close()

    def gpt_clear(self, member, guild_id="gpt"):
        if not self.state:
            return
        abs_path = self.get_path(guild_id)
        f = open(f'{abs_path}.txt', "a", encoding='utf-8')
        f.write(
            datetime.datetime.now().strftime("%H:%M:%S") + f" : GPT : User {member} cleared their chatGPT history\n")
        f.close()

#---------------- HELPING METHODS  ----------------------------------------------------------------

    def get_path(self, dir_name: str):
        if not self.state:
            return
        if not os.path.exists(f"logs/{dir_name}"):
            os.makedirs(f"logs/{dir_name}")
        file_name = datetime.datetime.now().strftime('%d-%m-%Y')
        script_dir = os.path.dirname(__file__)
        rel_path = f"logs/{dir_name}/{file_name}"
        abs_path = os.path.join(script_dir, rel_path)
        return abs_path

