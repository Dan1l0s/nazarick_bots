# Nazarick Bots

- ### [About this project](#about-this-project-1)
- ### [Functionality](#functionality-1)

  - #### [Music bots](#music-bots-1)
  - #### [Logger bot](#logger-bot-1)
  - #### [Admin bot](#admin-bot-1)

- ### [How to install and launch](#how-to-install-and-launch-1)

  - #### [Dependencies](#dependencies-1)
  - #### [FFmpeg installation](#ffmpeg-installation-1)
  - #### [How to launch code](#how-to-launch-code-1)
  - #### [How to create a discord bot](#how-to-create-a-discord-bot-1)

## About this project

This project is a group of discord-bots written in python, made in the setting of the anime series "Overlord", specifically as the pleiades of the Great Tomb of Nazarick.

### List of bots currently developed:

- Related music bots which support youtube playback and online radio
- Bot for logging into the channel
- Admin bot with temporary channels and leveling system

## Functionality

### Music bots

One of the features of this project is a unique system of music bots. Several instances can be on the server at the same time playing in different channels, but the user interacts with only one bot using slash commands, which controls which bot will connect to the voice channel.

<p align="center">
  <img src="https://github.com/Dan1l0s/nazarick_bots/assets/47472342/1463b495-92d4-414c-8632-72744fc0d5fa" alt="Multiple instances playback demo"/>
</p>

Music bots also accept user requests, both as links and text queries. If a text query is received, the user will be prompted to select from several relevant options.

Music bots currently support the following commands:

- **/play** - allows you to order songs that the bot will play in the voice channel, youtube playlists are also supported
- **/playnow** - adds song to the first position in queue
- **/skip** - skips current song
- **/stop** - stops playback and clears queue
- **/wrong** - removes the last added song from the queue
- **/repeat** - switches the repeat mode, which repeats 1 song
- **/radio** - allows you to order online radio, without the link playing anime radio, information about the current songs on which is displayed in the text channel
- **/queue** - displays current queue
- **/shuffle** - shuffles current queue
- **/help** - displays list of commands

### Logger bot

Logger bot allows you to print to the text channel information about all events that occur on the server: the connection of participants to the voice channels, the actions of moderators, and so on in the form of fine-looking embeds:

<p align="center">
  <img src="https://i.imgur.com/tJ26hOs.png" alt="Logger bot default log messages example"/>
</p>

The bot also allows you to automatically display information about new members on the server by sending welcome messages:

<p align="center">
  <img src="https://i.imgur.com/uF0vHPN.png" alt="Logger bot welcome message example"/>
</p>

Logger bot currently supports the following commands:

- **/set logs common** - allows server admin to set a channel to post logs messages to (admin-related functionality is dependent on Admin bot)
- **/set logs status** - allows server admin to set a channel to post status changes logs to (admin-related functionality)
- **/set logs welcome** - allows server admin to set a channel to post welcome messages to (admin-related functionality)
- **/welcome** - allows to create a welcome banner manually
- **/help** - displays list of commands

### Admin bot

Admin bot allows moderators to clear messages, fix voice channels bitrate and do other admin stuff. Also it allows all users to create temporary channels which they can manage by connecting to a certain channel:

<p align="center">
  <img src="https://github.com/Dan1l0s/discord_bots/assets/47472342/69d95c18-8422-43db-8ac7-2a055db34dd3" alt="Temporary channels demo"/>
</p>

In addition, admin bot has access to OpenAI API which allows users to interact ChatGPT using `/gpt` slash-command, replying to any message of this bot or just typing requests in bot's DM. This bot is useful as it parses ChatGPT's replies into chunks and, for example, decorates code into fine-looking blocks:

<p align="center">
  <img src="https://i.imgur.com/uWCU08k.png" alt="ChatGPT code decoration and interaction example"/>
</p>

Also, admin bot has leveling system which allows users to create their own ranks (roles) for each discord server and get voice and text xp during chatting, each rank requires an exact number of experience, the ranks are assigned automatically when user has enough experience:

<p align="center">
  <img src="https://i.imgur.com/p5Wo1gd.png" alt="Leveling system ranks list example"/>
</p>

Admin bot currently supports the following commands:

- **/admin (add) (remove) (list)** - allows server owner to add or remove an admin, also allows common users to display the list of server admins
- **/rank (add) (remove) (reset) (list)** - allows server admins to add, remove or reset ranks for server ranks system, also allows common users to display the list of current server ranks.
- **/xp (set) (reset) (show)** - allows server admins to add or reset user's experience in the leveling system, also allows common users to show someone's xp
- **/set private (channel) (category)** - allows server admin to set a channel to create temporary channels when connecting to this channel or to specify a category where temporary channels will be created at
- **/bitrate** - allows server admin to fix voice channels' bitrate (the bitrate is set to the highest value possible for each server)
- **/clear** - allows server admin to clear custom amount of messages in the text channel
- **/help** - displays list of commands

## How to install and launch

### Dependencies

This is the list of required dependencies:

- General:

  - Python 3.11 or higher
  - pip 23.2.1 or higher
  - Disnake 2.9 or higher

- Music bot:

  - FFmpeg 4.0 or higher (without live-video playback v3.5 is sufficient)
  - yt-dlp 2023.7.6 or higher
  - youtube-search 2.1.2 or higher

- Admin bot:
  - openai 0.27.9 or higher
  - aiosqlite 0.19.0 or higher

Exact versions live in [requirements.txt](requirements.txt) (runtime) and
[requirements-dev.txt](requirements-dev.txt) (adds the test suite).

You can execute the [setup file](setup.sh), which will install python and all required
libraries via pip from `requirements.txt`. Also, for linux users it will install FFmpeg.
Pass `--dev` (`bash setup.sh --dev`) to include the test dependencies.

### Keeping yt-dlp current

**This is the single most common cause of "the music bot stopped working".**
YouTube changes its player regularly and playback breaks until yt-dlp ships a fix -
usually within a day or two. `yt-dlp` is deliberately left unpinned in
`requirements.txt` for this reason.

Update and restart:

```bash
pip install -U yt-dlp
# then, via hosting/client_manager.py:
reboot
```

Worth automating - e.g. a weekly cron entry:

```
0 5 * * 1 pip install -U yt-dlp && <restart command>
```

### Before the first run

This checkout deliberately does **not** contain `configs/private_config.py`
(gitignored, holds your bot tokens) or `db/` (gitignored, holds every guild's
settings and all user XP). Copy both from your existing checkout before
starting, then verify:

```bash
cp ../configs/private_config.py configs/
cp -r ../db .
python tools/preflight.py
```

`preflight.py` checks the Python version, dependencies, ffmpeg, that
private_config has every field the bots read and a valid bot list, and that
`db/bot_database.db` actually carries your settings and XP over. It exits
non-zero if anything blocking is wrong and contacts Discord at no point.

**Starting without `db/` is the mistake to avoid**: the bots create the schema
on demand, so they'd come up against an empty database and every guild's log
channel, admin list and ranks - plus all user XP - would appear wiped.

### Running the tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

The suite covers the helper layer, the music playback state machine, the leveling
system, the moderation filters, and the startup wiring. See
[CHANGES.md](CHANGES.md) for what changed in the refactor and why, including an
audit table of every behavioral difference from the original.

### FFmpeg installation

If you need music bots, you have to install FFmpeg.
Linux users will automatically get FFmpeg from the setup file, windows users will need to install it manually, there are 2 ways:

#### 1st way: Add FFmpeg to PATH (recommended)

1. Download [this archieve](https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z) and unzip it to any folder you want (you mustn't uninstall ffmpeg during bot usage)
2. Press the "Start" button on the taskbar, search for "View advanced system settings," and open it. Proceed to the "Advanced" tab in the "System Properties" window and click on the "Environment Variables" button at the bottom
3. Select the "Path" variable under the "System variables" or "User variables" to add FFmpeg to path for all users or current user accordingly
4. Click on the "New" button, then type path to ffmpeg folder and subdirectory "bin", example: `C:\ffmpeg\bin`
5. Reboot your PC

#### 2nd way: Add FFmpeg to working directory

1. Download [this archieve](https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z) and unzip its `bin` folder to any folder you want
2. Proceed to `music_instance.py` and add to each `disnake.FFmpegPCMAudio` method `executable` parameter with absolute path to `ffmpeg.exe` file in the `bin` folder, example:
   `state.voice.play(disnake.FFmpegPCMAudio(source=link, **public_config.FFMPEG_OPTIONS, executable="C:\\nazarick_bots\\bin\\ffmpeg.exe"))`

### How to launch code

1. Rename [private_config_example.py](configs/private_config_example.py) to `private_config.py`
2. In `private_config.py` you have to edit all required variables (bots' info, openai api key and bot ids):

```python
# bots' specifications, value type: [[string, string, string], [string, string, string], ...]
# bot_type can be one of a folowing values: MusicLeader, MusicInstance, Admin, Logger
bots = [
    ["bot_name1", "bot_type1", "bot_token1"],
    ["bot_name1", "bot_type1", "bot_token1"],
]


# openai api key, value type: string
openai_api_key = "api_key"


# bots' discord ids, values type: {string: int}
bot_ids = {
    "bot_name1": bot_id1, "bot_name2": bot_id2,
}
```

4. To launch code just execute [main.py](main.py) file
5. (Optional) Edit whatever you like in [public_config.py](configs/public_config.py), also you can add different ids to `private_config.py`, there are prompts to help you get started

### How to create a discord bot

1. Proceed to [Discord developer portal](https://discord.com/developers/applications/).
2. Create a new application by clicking the `New Application` button and typing application name.
3. Navigate to the `Bot` tab. Copy the token by clicking `Reset Token` and then using the `Copy` button.
4. To invite your bot go to the `OAuth2` tab, then tick the `bot` checkbox under `scopes`.
5. Tick the permissions required for your bot to function under Bot Permissions ("Administrator" permission is recommended for these bots)
6. Copy and paste the given URL into your browser, choose a server to invite the bot to, and click `Authorize`.
