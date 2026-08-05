#!/usr/bin/env python3
"""Compare the registered slash-command tree between two versions of the repo.

Constructs every bot for real (disnake objects, no network, no tokens used) and
dumps each bot's top-level commands plus their subcommand groups. Catches the
class of mistake AST comparison can't: a command that silently fails to
register because a decorator was dropped or a name collided.

Usage:
    python tools/compare_commands.py                      # dump this repo
    python tools/compare_commands.py /path/to/original    # diff against it
"""

import json
import os
import subprocess
import sys
import types
import warnings

DUMPER = r'''
import sys, types, json, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])
# The original bots/music_leader.py hard-imports openai at module level even
# though the GPT feature is disabled; stub it so both versions can be loaded.
sys.modules.setdefault("openai", types.ModuleType("openai"))
fake = types.ModuleType("configs.private_config")
fake.bots = []
fake.openai_api_key = "k"
fake.bot_ids = {"music_main": 1, "moderate": 2, "logs": 3}
fake.supreme_beings = [1]
fake.test_guilds = [2]
sys.modules["configs.private_config"] = fake
from concurrent.futures import ThreadPoolExecutor
from bots.music_leader import MusicBotLeader
from bots.log_bot import LogBot
from bots.admin_bot import AdminBot
pool = ThreadPoolExecutor(max_workers=1)
leader = MusicBotLeader("m", "t", pool)
log = LogBot("l", "t")
admin = AdminBot("a", "t")

def dump(bot):
    return {c.name: sorted(getattr(c, "children", {}) or {}) for c in bot.slash_commands}

print(json.dumps({"leader": dump(leader.bot), "admin": dump(admin.bot),
                  "logger": dump(log.bot)}, indent=1, sort_keys=True))
pool.shutdown()
'''


def dump_for(repo_root):
    result = subprocess.run([sys.executable, "-c", DUMPER, repo_root],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"Failed to load bots from {repo_root}")
    return result.stdout


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mine = dump_for(here)

    if len(sys.argv) < 2:
        print(mine)
        return 0

    theirs = dump_for(sys.argv[1])
    if mine == theirs:
        data = json.loads(mine)
        print("IDENTICAL command trees across all three bots:")
        for bot, cmds in sorted(data.items()):
            nodes = sum(1 + len(v) for v in cmds.values())
            print(f"  {bot}: {len(cmds)} top-level commands, {nodes} total nodes")
        return 0

    import difflib
    print("COMMAND TREES DIFFER:")
    for line in difflib.unified_diff(theirs.splitlines(), mine.splitlines(),
                                     "original", "refactored", lineterm=""):
        print(line)
    return 1


if __name__ == "__main__":
    sys.exit(main())
