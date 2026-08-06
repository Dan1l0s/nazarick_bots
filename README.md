# Nazarick Bots

- [About this project](#about-this-project)
- [Functionality](#functionality)
    - [Music bots](#music-bots)
    - [Logger bot](#logger-bot)
    - [Admin bot](#admin-bot)
- [How to install and launch](#how-to-install-and-launch)
    - [Dependencies](#dependencies)
    - [Keeping yt-dlp current](#keeping-yt-dlp-current)
    - [Before the first run](#before-the-first-run)
    - [Running the tests](#running-the-tests)
    - [FFmpeg installation](#ffmpeg-installation)
    - [How to launch code](#how-to-launch-code)
    - [How to create a discord bot](#how-to-create-a-discord-bot)
- [Deployment and operations](#deployment-and-operations)
- [License](#license)
    - [Third-party components](#third-party-components)

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
  <img src="https://github.com/Dan1l0s/nazarick_bots/assets/47472342/69d95c18-8422-43db-8ac7-2a055db34dd3" alt="Temporary channels demo"/>
</p>

There is also a ChatGPT integration: `/gpt`, replies to any of the bot's messages, or DMs. It splits long answers into chunks and decorates code into blocks:

<p align="center">
  <img src="https://i.imgur.com/uWCU08k.png" alt="ChatGPT code decoration and interaction example"/>
</p>

> **Currently disabled.** The code lives in `bots/music_leader.py` (not the admin
> bot) and is commented out, updated for the `openai>=1.0` SDK but not enabled.
> `bots/music_leader.py` lists the exact lines to uncomment; you also need to add
> `openai` to `requirements.txt` and set `openai_api_key` in `private_config.py`.

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

The admin bot also runs an anti-spam filter on every message: unsolicited Discord
invites, known scam phrasing, mass mentions, flooding and duplicate spam are
scored, and the total decides whether a message is deleted, the author timed out,
or banned. Admins and other bots are exempt. Every threshold is tunable in the
`antispam` dict in [public_config.py](configs/public_config.py) - including
`allowed_invite_codes`, which you should set to your own server's vanity code so
members are not punished for linking the server they are already in. See
[docs/LOGGING_AND_ANTISPAM.md](docs/LOGGING_AND_ANTISPAM.md).

## How to install and launch

### Dependencies

This is the list of required dependencies:

- General:
    - Python 3.10 or higher (3.11+ recommended; `match` statements set the 3.10 floor)
    - pip 23.2.1 or higher
    - disnake 2.9 or higher
    - aiosqlite 0.19 or higher (used by every bot - guild settings, XP and logs)

- Music bots:
    - FFmpeg 4.0 or higher (without live-video playback v3.5 is sufficient)
    - yt-dlp 2024.1.1 or higher, and keep it updated - see below
    - youtube-search 2.1.2 or higher

- Optional:
    - openai 1.0 or higher, only if you re-enable the `/gpt` commands. They ship
      commented out, so no OpenAI key is needed for a normal setup.

Exact versions live in [requirements.txt](requirements.txt) (runtime) and
[requirements-dev.txt](requirements-dev.txt) (adds the test suite).

You can execute the [setup file](setup.sh), which will install python and all required
libraries via pip from `requirements.txt`. Also, for linux users it will install FFmpeg.

On **Linux/macOS** (and Git Bash):

```bash
bash setup.sh                 # runtime deps, system Python (what the VPS deploy runs)
bash setup.sh --dev --venv    # recommended for local development
bash setup.sh --help          # all options
```

On **Windows**, use the PowerShell script instead - it creates the virtualenv,
installs the test dependencies, checks ffmpeg and runs the suite to prove the
environment works:

```powershell
.\tools\dev-setup.ps1                 # add -InstallHook for the pre-commit hook
.\tools\dev-setup.ps1 -Runtime        # runtime dependencies only
```

If PowerShell blocks the script, run it as
`powershell -ExecutionPolicy Bypass -File .\tools\dev-setup.ps1`.

> Do **not** run `bash setup.sh` from PowerShell. `bash` there is normally
> `C:\Windows\System32\bash.exe`, the WSL launcher - which fails with
> `execvpe(/bin/bash) failed` if no WSL distro is installed, and if one *is*
> installed does something worse: `setup.sh` takes its Linux branch and installs
> the packages and ffmpeg inside WSL, not on Windows. To use `setup.sh` on
> Windows anyway, call Git Bash explicitly:
> `& "C:\Program Files\Git\bin\bash.exe" setup.sh --dev --venv`

`--dev` adds the test dependencies; `--venv` creates and installs into `.venv`
instead of the system Python, which is also the fix if pip refuses with
`externally-managed-environment` (Debian 12+, Ubuntu 23.04+ - see PEP 668).

> **If you use `--venv` on a server**, point `ExecStart=` in
> `hosting/nazarick.service` at `<repo>/.venv/bin/python`. The supervisor launches
> the bots with `sys.executable`, so an interpreter mismatch means the bots start
> under the system Python and fail to import disnake.

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

This is already automated for the VPS deployment: a GitHub Actions job runs
daily, and the server restarts itself only if the version actually changed and
no bot is currently playing. See
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). If you run the bots somewhere else, a
weekly cron entry does the same job less carefully:

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
bash setup.sh --dev --venv    # or: pip install -r requirements-dev.txt
python -m pytest -q           # exactly what CI runs
```

Coverage is on by default, including a `--cov-fail-under` ratchet - so the command
can exit non-zero with every test passing, if coverage dropped. `--no-cov` is
roughly four times faster for an edit-run loop:

```bash
python -m pytest -q --no-cov              # whole suite, fast
python -m pytest tests/test_antispam.py -q --no-cov
python -m pytest -k invite -q --no-cov    # by name
python -m pytest --lf -q --no-cov         # only what failed last time
```

`htmlcov/index.html` holds the line-by-line coverage report after a full run.
To run the suite automatically before every commit:

```bash
cp tools/pre-commit .git/hooks/pre-commit
```

It aborts the commit if anything fails; `git commit --no-verify` bypasses it.
On Windows use `copy tools\pre-commit .git\hooks\pre-commit`.

The suite covers the helper layer, the music playback state machine, the leveling
system, the moderation filters, the anti-spam scoring, and the startup wiring.
Coverage is enforced by a floor in `pyproject.toml`, so a change that drops it
fails CI.

Design notes for the parts that are least obvious from the code live in
[docs/LOGGING_AND_ANTISPAM.md](docs/LOGGING_AND_ANTISPAM.md). The refactor
rationale that used to be in `CHANGES.md` is in the git history -
`git log --oneline` reads as a changelog, and each commit message explains why.

### FFmpeg installation

If you need music bots, you have to install FFmpeg.
Linux users will automatically get FFmpeg from the setup file, windows users will need to install it manually, there are 2 ways:

#### 1st way: Add FFmpeg to PATH (recommended)

1. Download [this archive](https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z) and unzip it to any folder you want (you mustn't uninstall ffmpeg during bot usage)
2. Press the "Start" button on the taskbar, search for "View advanced system settings," and open it. Proceed to the "Advanced" tab in the "System Properties" window and click on the "Environment Variables" button at the bottom
3. Select the "Path" variable under the "System variables" or "User variables" to add FFmpeg to path for all users or current user accordingly
4. Click on the "New" button, then type path to ffmpeg folder and subdirectory "bin", example: `C:\ffmpeg\bin`
5. Reboot your PC

#### 2nd way: Add FFmpeg to working directory

1. Download [this archive](https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z) and unzip its `bin` folder to any folder you want
2. Proceed to [bots/music_instance.py](bots/music_instance.py) and add to each `disnake.FFmpegPCMAudio` method `executable` parameter with absolute path to `ffmpeg.exe` file in the `bin` folder, example:
   `state.voice.play(disnake.FFmpegPCMAudio(source=link, **public_config.FFMPEG_OPTIONS, executable="C:\\nazarick_bots\\bin\\ffmpeg.exe"))`

### How to launch code

1. Rename [private_config_example.py](configs/private_config_example.py) to `private_config.py`
2. In `private_config.py` you have to edit all required variables (bots' info, openai api key and bot ids):

```python
# bots' specifications, value type: [[string, string, string], [string, string, string], ...]
# bot_type can be one of the following values: MusicLeader, MusicInstance, Admin, Logger
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

3. To launch code just execute [main.py](main.py) file
4. (Optional) Edit whatever you like in [public_config.py](configs/public_config.py), also you can add different ids to `private_config.py`, there are prompts to help you get started

### How to create a discord bot

1. Proceed to [Discord developer portal](https://discord.com/developers/applications/).
2. Create a new application by clicking the `New Application` button and typing application name.
3. Navigate to the `Bot` tab. Copy the token by clicking `Reset Token` and then using the `Copy` button.
4. To invite your bot go to the `OAuth2` tab, then tick the `bot` checkbox under `scopes`.
5. Tick the permissions required for your bot to function under Bot Permissions ("Administrator" permission is recommended for these bots)
6. Copy and paste the given URL into your browser, choose a server to invite the bot to, and click `Authorize`.

## Deployment and operations

Everything above is enough to run the bots locally. For a hosted setup there is a
supervisor process, a control port, idle-aware restarts and a CI/CD pipeline:

- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - step-by-step from a Windows PC to
  a running VPS: SSH keys, the GitHub secrets the workflows need, autostart on
  boot, and how deploys avoid touching your gitignored `private_config.py` and
  `db/`. `hosting/setup_cicd.sh` does most of it for you.
- **[docs/LOGGING_AND_ANTISPAM.md](docs/LOGGING_AND_ANTISPAM.md)** - what gets
  written to `logs/`, what gets reported to you over Discord and why the
  difference is decided at the point of logging, plus the anti-spam scoring model
  and how to tune it.

The moving parts, briefly:

| Piece                       | Role                                                                                                                                 |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `hosting/server_manager.py` | Supervisor. Owns the bot process, listens on a control port, uploads database backups, and defers restarts until nothing is playing. |
| `hosting/client_manager.py` | Client for that port - `status`, `reboot`, `update`, `upgrade`, `backup`, `cancel`. Run it with no arguments for a REPL.             |
| `hosting/deploy.sh`         | The only thing CI is allowed to run over SSH; accepts `deploy`, `upgrade-ytdlp` and `status` and nothing else.                       |
| `.github/workflows/`        | Tests on every push; deploy on green master; a daily yt-dlp upgrade.                                                                 |
| `tools/preflight.py`        | Pre-launch sanity check that contacts Discord at no point.                                                                           |

## License

Released under the [MIT License](LICENSE) — you may use, modify, self-host and
redistribute this, including commercially, provided the copyright notice is kept.
It comes with no warranty.

### Third-party components

This project depends on other people's work. None of it imposes copyleft
obligations here, but the notices are theirs:

| Component                                                       | License                                     |
| --------------------------------------------------------------- | ------------------------------------------- |
| [disnake](https://github.com/DisnakeDev/disnake)                | MIT                                         |
| [PyNaCl](https://github.com/pyca/pynacl) (via `disnake[voice]`) | Apache-2.0                                  |
| [aiosqlite](https://github.com/omnilib/aiosqlite)               | MIT                                         |
| [youtube-search](https://pypi.org/project/youtube-search/)      | MIT                                         |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp)                      | Unlicense (public domain)                   |
| [FFmpeg](https://ffmpeg.org/)                                   | LGPL-2.1+ or GPL-2+, depending on the build |

FFmpeg is invoked as a separate executable via `subprocess`, not linked into
this program, so its copyleft terms do not extend to this codebase. If you
redistribute a bundle that _includes_ an FFmpeg binary, its terms apply to that
binary — check which one your build is, since GPL builds (those configured with
`--enable-gpl`) carry stricter conditions than LGPL ones.

The MIT license covers this source code only. It grants no rights to the
_Overlord_ franchise names and characters referenced throughout the bots'
messages and defaults; those belong to their respective rights holders.
