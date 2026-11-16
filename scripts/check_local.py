"""Run offline project checks before every commit."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [['-m', 'pytest', '-q']]

if __name__ == "__main__":
    for command in COMMANDS:
        subprocess.run([sys.executable, *command], cwd=ROOT, check=True)
