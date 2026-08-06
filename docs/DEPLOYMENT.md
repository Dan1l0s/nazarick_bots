# Deployment setup

> Your PC is **Windows**, the VPS is **Linux**. Every command below is labelled
> with where it runs. Windows commands are PowerShell.

## First: what changes and what doesn't

**Nothing about how you use `client_manager.py` today changes.** You keep
running it on your PC, it keeps connecting to the VPS over the network, all the
old commands still work. It just gains a few new ones.

What's being added is a _second, separate_ way to reach the same supervisor:
GitHub Actions SSHes into the VPS and runs one restricted script there.

### Who runs what, where

| Thing                             | Runs on          | Talks to                | When                               |
| --------------------------------- | ---------------- | ----------------------- | ---------------------------------- |
| `server_manager.py`               | **VPS**          | starts/stops the bot    | always (you already run this)      |
| `client_manager.py` (interactive) | **your PC**      | VPS over the network    | when you type commands (unchanged) |
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
   -> supervisor waits until no bot is playing, then git pulls + restarts
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
cd /nazarick_bots          # your repo path
git pull
bash hosting/setup_cicd.sh --pubkey "ssh-ed25519 AAAA...paste-it-here... github-actions"
```

That single command does all the VPS-side work:

- checks `deploy.sh` has Unix line endings (a Windows checkout can break this)
- creates `run/`, makes `deploy.sh` executable
- finds your Python and warns if `deploy.sh` won't be able to
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
command="/nazarick_bots/hosting/deploy.sh",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc ssh-ed25519 AAAA...
```

That `command=` prefix is the security boundary. The key can do exactly three
things — `deploy`, `upgrade-ytdlp`, `status` — and nothing else. No shell, no
file access, no port forwarding. Your own key is untouched.

## Step 3 — On the VPS: restart the supervisor

It's a long-running process, so it's still on the old code:

```bash
pkill -f server_manager.py
cd /nazarick_bots/hosting
python3 server_manager.py <your-port> -r & disown
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
Then check from your PC, exactly as you always have:

```powershell
python hosting/client_manager.py
> status
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

`private_config.py` and `db/` are gitignored, and `git stash` / `git checkout`
never touch ignored files — tested directly against a scratch repo:

```
before:  private_config=TOKENS_LIVE  db=REAL_DB
after:   private_config=TOKENS_LIVE  db=REAL_DB
```

The one command that _would_ delete them is `git clean -fdx`. Don't add it to
the deploy path.

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
tail -f /nazarick_bots/logs/$(date +%d-%m-%Y).txt
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
