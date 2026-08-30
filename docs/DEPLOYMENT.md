# Deployment setup

> Your PC is **Windows**, the VPS is **Linux**. Every command below is labelled
> with where it runs. Windows commands are PowerShell.

## First: what changes and what doesn't

The manager is now an internal service: it listens only on `127.0.0.1` on the
VPS. All old commands still work, but remote access goes through SSH rather
than exposing the password-only protocol to the Internet.

What's being added is a _second, separate_ way to reach the same supervisor:
GitHub Actions SSHes into the VPS and runs one restricted script there.

### Who runs what, where

| Thing                             | Runs on          | Talks to                | When                               |
| --------------------------------- | ---------------- | ----------------------- | ---------------------------------- |
| `server_manager.py`               | **VPS**          | starts/stops the bot    | always (you already run this)      |
| `client_manager.py` (interactive) | PC or **VPS**    | loopback / SSH tunnel   | when you type commands             |
| `main.py` (the bots)              | **VPS**          | Discord                 | started by the supervisor          |
| `deploy.sh`                       | **VPS**          | supervisor on localhost | only when GitHub Actions SSHes in  |
| Workflows                         | GitHub's servers | VPS over SSH            | on push / on schedule              |

`deploy.sh` also uses `client_manager.py`, but with `--host 127.0.0.1` — it's on
the same machine as the supervisor, so it connects to itself. Same script, two
different callers.

### The chain, end to end

```
you push to master
   -> GitHub runs tests (pytest)
   -> if green, GitHub SSHes: ssh you@vps deploy
   -> SSH is locked to ONE script: hosting/deploy.sh
   -> deploy.sh tells the local supervisor: "update master when-idle"
   -> supervisor waits until no bot is playing, then safely updates + restarts
```

---

## Step 1 — On your PC: make a key for GitHub

Do **not** reuse your personal key — GitHub gets a copy of whatever you give it.

**PowerShell:**

```powershell
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\nazarick_ci -C "github-actions"
```

Press **Enter twice** when it asks for a passphrase (CI can't type one).

> Don't use `-N ""` to skip the prompt. PowerShell mangles empty-string
> arguments to native programs, and you end up with a key that has a literal
> `""` passphrase — which then fails in Actions with a confusing error.

Two files now exist in `C:\Users\<you>\.ssh\`:

- `nazarick_ci` — **private**, goes to GitHub in step 4
- `nazarick_ci.pub` — **public**, goes to the VPS in step 2

### Which file is which

You never upload a file anywhere. You copy the **text** of the `.pub` one and
paste it into the setup command in step 2.

|               | Public — `nazarick_ci.pub`                              | Private — `nazarick_ci` (no extension)                         |
| ------------- | ------------------------------------------------------- | -------------------------------------------------------------- |
| Looks like    | **one** line: `ssh-ed25519 AAAAC3Nza... github-actions` | **many** lines, starting `-----BEGIN OPENSSH PRIVATE KEY-----` |
| Goes to       | the VPS (step 2)                                        | the GitHub secret `DEPLOY_SSH_KEY` (step 4)                    |
| Safe to share | yes — that's its purpose                                | **never** — anyone holding it can deploy                       |

> **Why no `dan1l0s@Dan1l0s` on the end, unlike my other keys?**
> Because `-C "github-actions"` set the comment explicitly. That trailing field
> is only a human-readable label — ssh ignores it completely. Naming this one
> `github-actions` is deliberate: opening `authorized_keys` in a year, you'll
> know instantly which line is CI and which is your laptop.

> **Don't reach for `ssh-copy-id`.** It isn't on Windows anyway, but the real
> problem is that it would install the key _without_ the `command="..."`
> restriction — handing CI a full shell instead of the three allowed actions.
> `setup_cicd.sh` in step 2 is what applies that restriction.

### Fix the key permissions now

Windows OpenSSH refuses to use a private key that other accounts can read:

```
@@@ WARNING: UNPROTECTED PRIVATE KEY FILE! @@@
Permissions for 'C:\Users\dan1l\.ssh\nazarick_ci' are too open.
This private key will be ignored.
```

From the repo, run:

```powershell
.\tools\fix_key_permissions.ps1
```

It rebuilds the file's ACL from scratch — one owner, one rule, inheritance
off — then prints the result and confirms ssh will accept it.

<details>
<summary>Why not just <code>icacls /inheritance:r /grant:r</code>?</summary>

That's the recipe you'll find everywhere, and it often leaves the key still
rejected, with an error like:

```
Try removing permissions for user: DAN1L0S\ (S-1-5-21-3764721633-...)
```

Note the empty user name after the backslash. That's an ACL entry whose account
no longer resolves to a name, so there is nothing to pass to `icacls /remove`.
`$env:USERNAME` on its own is also ambiguous — the grant can land on a
different principal than you expect.

Rebuilding the ACL sidesteps both problems: orphaned entries aren't carried
over, and the owner is set via the fully-qualified `DOMAIN\User`.

</details>

Now print the **public** key and copy it:

```powershell
Get-Content $env:USERPROFILE\.ssh\nazarick_ci.pub
```

## Step 2 — On the VPS: run the setup script

Paste the public key from step 1 into the command below:

```bash
cd /path/to/nazarick       # wherever you cloned it
git pull
bash setup.sh --venv
.venv/bin/python tools/preflight.py
bash hosting/setup_cicd.sh --pubkey "ssh-ed25519 AAAA...paste-it-here... github-actions"
```

> **The repo's location is never hardcoded.** `setup_cicd.sh` and `deploy.sh`
> both derive it from their own path, so the repo can live anywhere -
> `/srv/apps/nazarick`, `/opt/nazarick`, `/home/you/nazarick`. Nothing inside
> the project needs to know. See [Moving the repo](#moving-the-repo) if you
> relocate an existing install.

That single command does all the VPS-side work:

- checks `deploy.sh` has Unix line endings (a Windows checkout can break this)
- creates `run/`, makes `deploy.sh` executable
- requires a project virtualenv (or an explicit DEPLOY_PYTHON) and verifies it
- verifies `private_config.py` and `db/` are present
- **installs the restricted key line** into `~/.ssh/authorized_keys`, without
  touching your existing keys, taking a backup first, and skipping if already
  installed (safe to re-run)
- prints the exact GitHub secret values, including the `known_hosts` line
- tells you whether the supervisor needs restarting

Read its output — **section 6 has the values you need for step 4**, so keep
that terminal open.

### What it installed, and why it's safe

One line in `authorized_keys`:

```
command="bash /path/to/nazarick/hosting/deploy.sh",no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty,no-user-rc ssh-ed25519 AAAA...
```

sshd needs a concrete absolute path here - it has no notion of "the repo" - but
you never type it: the script fills in the checkout it was run from.

That `command=` prefix is the security boundary. The key can do exactly three
things — `deploy`, `upgrade-ytdlp`, `status` — and nothing else. No shell, no
file access, no port forwarding. Your own key is untouched.

## Step 3 — On the VPS: restart the supervisor

It's a long-running process, so it's still on the old code:

```bash
pkill -f server_manager.py
cd /path/to/nazarick/hosting
../.venv/bin/python server_manager.py <your-port> -r & disown
```

Re-run the setup script to confirm — its final section does a live end-to-end check:

```bash
bash hosting/setup_cicd.sh
```

You want to see `supervisor is running the NEW code`.

## Step 3b — Autostart on boot

Without this the bots stay down after a reboot. On the VPS:

```bash
bash hosting/setup_cicd.sh --install-service
sudo systemctl start nazarick
```

It installs a systemd unit with your real user, paths and port substituted in,
and enables it at boot. From then on:

```bash
sudo systemctl status nazarick     # is it up?
sudo systemctl restart nazarick    # restart supervisor + bots
sudo journalctl -u nazarick -f     # why did a start fail?
```

The unit supervises `server_manager.py`, not `main.py` — the manager owns
starting and stopping the bots, so pointing systemd at `main.py` too would give
you two competing supervisors. `KillMode=control-group` means a stop takes the
bots down with it rather than orphaning them holding voice connections and
sqlite files open.

If a manually-started supervisor is already running it holds the port, and the
service will crash-loop. Hand over cleanly:

```bash
pkill -f server_manager.py && sudo systemctl start nazarick
```

Re-running `setup_cicd.sh` with no arguments reports whether autostart is
configured, enabled and active.

## Step 4 — On your PC: verify the key, then give it to GitHub

**Test the restriction first** (PowerShell):

```powershell
ssh -i $env:USERPROFILE\.ssh\nazarick_ci <user>@<vps-ip> status
```

Expected: the bot status printout. Then confirm it's locked down:

```powershell
ssh -i $env:USERPROFILE\.ssh\nazarick_ci <user>@<vps-ip> "cat /etc/passwd"
```

Expected: `refused: 'cat' is not an allowed action`.

If both behave that way, the hard part is done.

### Add the secrets

GitHub → your repo → **Settings → Secrets and variables → Actions → New
repository secret**. Values come from **section 6** of the setup script:

| Name                 | Value                                                       |
| -------------------- | ----------------------------------------------------------- |
| `DEPLOY_SSH_KEY`     | the **private** key — see the copy command below            |
| `DEPLOY_HOST`        | from section 6                                              |
| `DEPLOY_USER`        | from section 6                                              |
| `DEPLOY_PORT`        | from section 6 — skip it entirely if you're on port 22      |
| `DEPLOY_KNOWN_HOSTS` | the line(s) printed under `DEPLOY_KNOWN_HOSTS` in section 6 |

Copy the private key to your clipboard (PowerShell):

```powershell
Get-Content $env:USERPROFILE\.ssh\nazarick_ci -Raw | Set-Clipboard
```

`-Raw` matters — without it PowerShell can drop the trailing newline and mangle
the line breaks, and Actions then fails with `invalid format`. Paste it whole,
including the `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END...` lines.

### Is this safe on a public repo?

Yes. Secrets are encrypted, masked in logs, and — the part that actually
matters — **GitHub does not provide them to workflows triggered by pull requests
from forks**. A stranger cannot open a PR that prints your IP or key. The deploy
workflow only runs on `workflow_run` (same-repo only) and manual dispatch.

And even if the key leaked, the forced command means it can only trigger a
deploy.

## Step 5 — Try a real deploy

**On your PC:**

```powershell
git commit --allow-empty -m "ci: test deploy pipeline"
git push origin master
```

Open the **Actions** tab. `tests` runs first; when green, `deploy` starts.
Then check through the restricted SSH key:

```powershell
ssh -i $env:USERPROFILE\.ssh\nazarick_ci <user>@<vps-ip> status
```

Two lines are new:

```
yt-dlp: 2026.07.04
Playback: no active plays
```

To watch the idle-gate work: start a song, push another commit, then `status`:

```
Playback: 1 active play(s) across 1 voice channel(s)
Queued action: update master (queued 42s ago; waiting because: 1 active play(s)...)
```

It deploys by itself once the music stops.

---

## Migrating to a new VPS

Moving to a different machine, rather than a different directory on the same
one. The repo is path-independent, so nothing inside it needs editing - the work
is in the state that does **not** live in git, and in the handful of places that
name the old host.

> **The one rule that matters: never run both machines at once.** The bots
> authenticate with the same Discord tokens. Two supervisors up simultaneously
> means every command gets answered twice and both instances fight over the
> voice connections. Build the new box completely, then cut over.

### What does not come from git

`git clone` gives you the code and nothing else. These are gitignored and must
be carried across by hand:

| Path | Why it matters |
| --- | --- |
| `configs/private_config.py` | bot tokens, manager password/port and optional WebDAV credentials |
| `db/bot_database.db` | per-guild settings and all XP history |

`logs/` and `run/` are recreated automatically. **Do not** copy `.venv` - it
bakes in absolute paths and the old machine's interpreter; build a fresh one.

### Phase 1 - build the new box (bots stay down)

```bash
sudo apt update && sudo apt install -y git python3 python3-pip python3-venv ffmpeg

sudo mkdir -p /srv/apps
sudo chown "$(id -un)" /srv/apps
git clone https://github.com/Dan1l0s/nazarick_bots /srv/apps/nazarick
cd /srv/apps/nazarick
bash setup.sh --venv
.venv/bin/python tools/preflight.py
```

From the OLD VPS, send the two gitignored things across:

```bash
scp configs/private_config.py you@new-vps:/srv/apps/nazarick/configs/
scp -r db you@new-vps:/srv/apps/nazarick/
```

Then install the CI key and the service - but do not start it yet:

```bash
bash hosting/setup_cicd.sh --pubkey "ssh-ed25519 AAAA...github-actions"
bash hosting/setup_cicd.sh --install-service
```

Reusing the same `nazarick_ci.pub` from the old machine is deliberate: the
private half is already in the `DEPLOY_SSH_KEY` secret, so that one secret never
has to be touched. Generate a new pair only if you think the old one leaked.

**Do not open the manager port in UFW.** The protocol has password
authentication but no TLS, and it is not a public API. The supervisor binds
only `127.0.0.1`; GitHub Actions reaches it through the restricted SSH command.
The server firewall therefore stays exactly as prepared for the shared VPS:

```bash
sudo ufw status numbered
# public: SSH, HTTP and HTTPS; no rule for hosting_port
```

For an interactive session from your PC, create a temporary tunnel with your
normal SSH account and keep `hosting_ip = "127.0.0.1"` locally:

```powershell
ssh -N -L 10000:127.0.0.1:10000 dan-vps
# in a second terminal:
python hosting/client_manager.py
```

Replace `10000` on both sides if `hosting_port` differs. Closing SSH closes the
tunnel; no permanent firewall exception is created.

### Phase 2 - cut over

On the **old** VPS - disable, not just stop, so a reboot cannot resurrect it:

```bash
sudo systemctl disable --now nazarick
```

Now re-copy the database, so nothing earned between phase 1 and the cutover is
lost, and so sqlite is not copied mid-write:

```bash
scp db/bot_database.db you@new-vps:/srv/apps/nazarick/db/
```

On the **new** VPS:

```bash
sudo systemctl start nazarick
```

### Phase 3 - the things that name the old host

GitHub -> Settings -> Secrets and variables -> Actions. Section 6 of
`setup_cicd.sh` on the new box prints every value:

| Secret | Action |
| --- | --- |
| `DEPLOY_HOST` | **update** - new IP or hostname |
| `DEPLOY_KNOWN_HOSTS` | **update** - a new machine has a new host key; stale here fails as `Host key verification failed` |
| `DEPLOY_USER` | update only if the account name differs |
| `DEPLOY_PORT` | update if sshd is not on 22; delete the secret if it now is |
| `DEPLOY_SSH_KEY` | leave alone, if you reused the same public key |

On **your PC**, update the `dan-vps` entry in `~/.ssh/config` if its address
changed. `hosting_ip` should remain `127.0.0.1` and is used through the SSH
tunnel above. If you reused an IP, `known_hosts` may still contain the old
machine's key; SSH will refuse the connection until that stale entry is removed.

### Phase 4 - verify, in this order

```powershell
ssh -i $env:USERPROFILE\.ssh\nazarick_ci <user>@<new-ip> status   # expect the status printout
ssh -i $env:USERPROFILE\.ssh\nazarick_ci <user>@<new-ip> "cat /etc/passwd"   # expect: refused
ssh dan-vps "systemctl status nazarick --no-pager"                  # service is healthy
ssh dan-vps "ss -ltn | grep ':10000 '"                              # must show 127.0.0.1 only
git commit --allow-empty -m "ci: test deploy to new vps" && git push
```

The last one is the only check that exercises the GitHub secrets. Watch the
Actions tab.

### Before you delete the old machine

Its `~/.ssh/authorized_keys` still contains the forced-command line for the CI
key. While that box is alive and reachable, anyone holding `DEPLOY_SSH_KEY` can
still trigger a deploy on it. Remove the line, or destroy the machine.

Two more things worth a glance: `backup_url` in `private_config.py` still points
at your WebDAV target and will now be written from the new host - confirm the
backups arrive - and a fresh **fail2ban** on the new box can ban GitHub runner
IPs during the first failed attempts, which shows up as `Connection timed out`
rather than anything about authentication. See the fail2ban note near the end of
this document.

---

## Moving the repo

The project itself is path-independent: `deploy.sh`, `setup_cicd.sh` and the
Python entry points all resolve the repository root from their own location, so
the checkout can sit anywhere. Exactly **two** absolute paths live *outside* the
repo and therefore do not move with it:

| Where | What it holds | Fixed by |
| --- | --- | --- |
| `~/.ssh/authorized_keys` | the forced command sshd runs for the CI key | `bash hosting/setup_cicd.sh` |
| `/etc/systemd/system/nazarick.service` | `WorkingDirectory` + `ExecStart` | `bash hosting/setup_cicd.sh --install-service` |

Both are regenerated from wherever you run the script, so relocating is three
commands. On the VPS:

```bash
sudo systemctl stop nazarick          # or: pkill -f server_manager.py
sudo mkdir -p /srv/apps
sudo mv /old/path/nazarick /srv/apps/nazarick
sudo chown -R "$(id -un)" /srv/apps/nazarick

cd /srv/apps/nazarick
bash hosting/setup_cicd.sh --install-service    # rewrites BOTH of the above
sudo systemctl start nazarick
```

`setup_cicd.sh` notices that the forced command still points at the old
location and re-points it at the current checkout, taking a backup of
`authorized_keys` first. It prints the old and new lines, so you can see the
change:

```
  [ ok ] re-pointed the existing forced command at this checkout (backup taken)
         was: command="bash /old/path/nazarick/hosting/deploy.sh"
         now: command="bash /srv/apps/nazarick/hosting/deploy.sh"
```

Then verify from your PC - this is the one check that exercises the whole SSH
path end to end:

```powershell
ssh -i $env:USERPROFILE\.ssh\nazarick_ci <user>@<vps-ip> status
```

Two things to watch out for:

- **`.venv`, if you use one, does not survive a move.** The `bin/python`
  symlink still resolves, but `activate` and every console script inside bake in
  the old absolute path. Recreate it: `rm -rf .venv && bash setup.sh --venv`.
- **`private_config.py` and `db/` are gitignored, not absent.** They live inside
  the repo directory, so `mv` carries them along - but if you *re-clone* at the
  new location instead of moving, copy those two across by hand or the bots
  start with no tokens and an empty database.

`DEPLOY_HOST`, `DEPLOY_USER` and the other GitHub secrets are unaffected: none
of them mention a path.

### A layout worth adopting

Nothing below is required - the project runs from any directory - but if you are
moving anyway, this keeps a VPS legible as it accumulates services:

```
/srv/
├── apps/          plain applications        -> /srv/apps/nazarick
├── compose/       docker compose projects
└── backups/       backup data
/var/www/          web static
```

---

## New commands

Everything you had still works. These are added:

| Command                     | What it does                                           |
| --------------------------- | ------------------------------------------------------ |
| `update <branch> when-idle` | queue a pull+restart until nothing is playing          |
| `reboot when-idle`          | queue a restart                                        |
| `upgrade`                   | update yt-dlp, restart **only if the version changed** |
| `upgrade when-idle`         | install now, restart when idle                         |
| `cancel`                    | drop whatever is queued                                |
| `status`                    | now also shows yt-dlp version, playback, queued action |

Each deferred form also has a one-word alias, which is what the REPL help lists
next to the immediate command: `reboot-idle`, `update-idle <branch>`,
`upgrade-idle`. They are exactly equivalent to appending `when-idle`.

A queued action waits for playback to end, runs anyway after 6 hours so a bot
stuck reporting "playing" cannot block it forever, and is replaced if you queue
another. `status` shows what is waiting and why.

`upgrade` is the manual version of what the daily workflow does — useful when
YouTube breaks playback and you don't want to wait for the schedule.

## Tuning

`hosting/server_manager.py`:

- `DEFERRED_POLL_INTERVAL` (20s) — how often "is it idle yet?" is re-checked
- `DEFERRED_FORCE_AFTER` (6h) — a queued action runs anyway after this long

`hosting/status.py`:

- `WRITE_INTERVAL` (15s) — how often the bot publishes playback status
- `STALE_AFTER` (120s) — status older than this counts as idle, assuming the
  bot process died or hung

## Why a deploy can't get stuck

Three independent releases, so a crashed or wedged bot can never block deploys:

1. No status file (bot not running) → idle
2. Status file older than `STALE_AFTER` → assumed dead → idle
3. `DEFERRED_FORCE_AFTER` elapsed → runs regardless

## Your config and database are safe

`private_config.py` and `db/` are gitignored, and the deploy checkout never
touches ignored files. Tracked local edits on the VPS are not silently stashed
or discarded: deployment refuses to proceed until you commit or revert them.

```
before:  private_config=TOKENS_LIVE  db=REAL_DB
after:   private_config=TOKENS_LIVE  db=REAL_DB
```

The one command that _would_ delete ignored state is `git clean -fdx`. It is
deliberately absent from the deploy path.

## Windows gotchas worth knowing

**Line endings.** A committed `.gitattributes` forces LF on `*.sh`, `*.py` and
`*.yml`. Without it, git on Windows can hand the VPS a CRLF `deploy.sh`, which
fails with:

```
/usr/bin/env: 'bash\r': No such file or directory
```

That error names the _interpreter_, not the file, which makes it needlessly hard
to diagnose. `setup_cicd.sh` section 1 checks for it explicitly.

**Key permissions.** Windows OpenSSH rejects private keys other accounts can
read. Step 1 includes the `icacls` fix.

**`~` in paths.** PowerShell doesn't reliably expand `~` for native programs
like `ssh-keygen`. Use `$env:USERPROFILE\.ssh\...` as shown.

## When something breaks

From your PC, as usual:

```
> status          what's the supervisor doing, is anything queued
> cancel          drop a queued action
> update master   deploy immediately, ignoring the idle gate
```

On the VPS, re-run the health check any time:

```bash
bash hosting/setup_cicd.sh
tail -f "$(git rev-parse --show-toplevel)/logs/$(date +%d-%m-%Y).txt"
```

**Deploy workflow can't connect?** Check `DEPLOY_HOST` / `DEPLOY_PORT`, and that
`DEPLOY_KNOWN_HOSTS` matches the current host key (it changes if you rebuild the
VPS — re-run `setup_cicd.sh` to get the new one).

### Reading an SSH failure

The exact wording tells you which layer failed, and they have completely
different causes. Check this before touching keys or secrets:

| ssh says | What happened | Where to look |
| --- | --- | --- |
| `Connection refused` | Host reachable, **nothing listening** on that port | `systemctl status ssh`; is sshd on the port `DEPLOY_PORT` says? |
| `connect to host ... port 22: Connection timed out` | Packets **dropped** — not refused. Host down, or a firewall is silently discarding them | provider console; `ufw status`, `iptables -L -n`, `fail2ban-client status sshd` |
| `Connection timed out during banner exchange` | TCP **connected**, sshd never answered. Loaded, wedged, or out of disk | `df -h`, `uptime`, `free -h`, `journalctl -u ssh -n 50` |
| `Permission denied (publickey)` | Reached sshd, key rejected | `DEPLOY_SSH_KEY` completeness; `~/.ssh/authorized_keys` |
| `Host key verification failed` | Reached sshd, host key changed | re-do `DEPLOY_KNOWN_HOSTS` |
| exit 126 / `Permission denied` on deploy.sh | Authenticated fine; the forced command can't execute | `git update-index --chmod=+x`, and the `bash` prefix in `authorized_keys` |

Refused vs. timed out is the most useful distinction: **refused means the host
answered**, timed out means nothing came back at all.

**Worth knowing about fail2ban.** A run of failed `publickey` attempts — say
while you were getting `DEPLOY_SSH_KEY` right — can get the *runner's* IP banned.
A ban DROPs packets, so the next workflow sees `Connection timed out` rather than
anything about authentication, and it looks like the VPS died. Your own SSH keeps
working, because your IP was never banned, which makes it more confusing still.

```bash
fail2ban-client status sshd          # look at "Banned IP list"
fail2ban-client set sshd unbanip <ip>
```

GitHub runners have no stable IPs to allowlist. If this keeps happening, moving
sshd to a non-standard port (and setting `DEPLOY_PORT`) cuts the background noise
that trains those jails.

**Connects but fails?** Try `ssh -i ... <user>@<vps> status` from your PC. If
that works but Actions doesn't, it's almost always `DEPLOY_SSH_KEY` pasted
incompletely — re-copy it with `-Raw` as shown in step 4.

**Bot didn't restart after a deploy?** It's probably queued behind playback. Run
`status` and look for `Queued action:`.

To roll back, deploy an older commit: `git revert` and push, or from your PC
`> update <branch-or-tag>`.
