# Nazarick Bots

## About this project

This project is a group of discord-bots written in python, made in the setting of the anime series "Overlord", specifically as the pleiades of the great tomb "Nazarick".

### List of bots currently developed:

-   Related music bots which support youtube playback and online radio
-   Bot for logging into the channel
-   Admin bot with temporary channels and level system (in development)

## Functionality

### Related music bots

One of the features of this project is a unique system of music bots. Several instances can be on the server at the same time playing in different channels, but the user interacts with only one bot using slash commands, which controls which bot will connect to the voice channel.

![Multiple instances playback demo](MULTIPLE_INSTANCES_DEMO)

Music bots also accept user requests, both as links and text queries. If a text query is received, the user will be prompted to select from several relevant options.

Music bots currently support the following commands:

-   **/play** - allows you to order songs that the bot will play in the voice channel, youtube playlists are also supported
-   **/playnow** - adds song to the first position in queue
-   **/skip** - skips current song
-   **/stop** - stops playback and clears queue
-   **/wrong** - removes the last added song from the queue
-   **/repeat** - switches the repeat mode, which repeats 1 song
-   **/radio** - allows you to order online radio, without the link playing anime radio, information about the current songs on which is displayed in the text channel
-   **/queue** - displays current queue
-   **/shuffle** - shuffles current queue
-   **/help** - displays list of commands

### Logger bot

Logger bot allows you to print to the text channel information about all events that occur on the server: the connection of participants to the voice channels, the actions of moderators, and so on in the form of fine-looking embes:

![Logger bot default log messages example](https://i.imgur.com/tJ26hOs.png)

The bot also allows you to automatically display information about new members on the server by sending welcome messages:

![Logger bot welcome message example](https://i.imgur.com/uF0vHPN.png)

### Admin bot

Admin bot allows moderators to clear messages, fix voice channels bitrate and do other admin stuff. Also it allows all users to create temporary channels which they can manage by connecting to a certain channel:

![Multiple instances playback demo](MULTIPLE_INSTANCES_DEMO)

In addition, admin bot has access to OpenAI API which allows users to interact ChatGPT using `/gpt` slash-command, replying to any message of this bot or just typing requests in bot's DM. This bot is useful as it parses ChatGPT's replies into chunks and, for example, decorates code into fine-looking blocks:

![ChatGPT code decoration and interaction example](https://i.imgur.com/uWCU08k.png)

## How to install and launch

### How to install dependencies

You need to execute file `setup.sh`, which will install python, all required libraries in python via pip. Also, for linux users it will install FFmpeg

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
2. Proceed to `music_instance.py` and add to each `.play` method `executable` parameter with absolute path to `ffmpeg.exe` file in the `bin` folder, example:
   `state.voice.play(disnake.FFmpegPCMAudio(source=link, **public_config.FFMPEG_OPTIONS, executable="C:\\nazarick_bots\\bin\\ffmpeg.exe"))`

### How to launch code

1. Rename `private_config_example.py` to `private_config.py`
2. In `private_config.py` you have to edit all required variables (bot tokens, openai api key and bot ids):
 <!-- code link placeholder -->
3. To launch code just execute `main.py` file
4. (Optional) Edit whatever you like in `public_config.py`, also you can add different ids to `private_config.py`, there are prompts to help you get started
