#!/usr/bin/env bash
#
# SSH entry point for GitHub Actions. Runs ON THE VPS.
#
# Installed as a FORCED COMMAND in ~/.ssh/authorized_keys, so the CI key cannot
# open a shell - whatever GitHub sends arrives in $SSH_ORIGINAL_COMMAND and only
# the verbs below are accepted. See DEPLOYMENT.md.
#
#   ssh <user>@<vps> deploy          pull tested code, restart when idle
#   ssh <user>@<vps> upgrade-ytdlp   update yt-dlp, restart when idle
#   ssh <user>@<vps> status          read-only
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRANCH="${DEPLOY_BRANCH:-master}"

# SSH forced commands run non-interactively: ~/.bashrc and ~/.profile are NOT
# sourced, so PATH can be as bare as /usr/bin:/bin. A bare `python3` therefore
# works interactively but fails under CI - resolve it explicitly instead.
resolve_python() {
    if [ -n "${DEPLOY_PYTHON:-}" ]; then
        echo "${DEPLOY_PYTHON}"; return 0
    fi
    for candidate in \
        "${REPO_DIR}/.venv/bin/python" \
        "$(command -v python3 2>/dev/null || true)" \
        /usr/local/bin/python3 \
        /usr/bin/python3
    do
        if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then
            echo "${candidate}"; return 0
        fi
    done
    return 1
}

if ! PYTHON="$(resolve_python)"; then
    echo "deploy.sh: no python3 found. Set DEPLOY_PYTHON to an absolute path" >&2
    exit 1
fi

# Default to `deploy` for a bare `ssh user@host` with no command.
verb="${SSH_ORIGINAL_COMMAND:-deploy}"
verb="${verb%% *}"          # first word only; ignore anything appended

case "${verb}" in
    deploy)         manager_command="update ${BRANCH} when-idle" ;;
    upgrade-ytdlp)  manager_command="upgrade when-idle" ;;
    status)         manager_command="status" ;;
    *)
        echo "refused: '${verb}' is not an allowed action" >&2
        echo "allowed: deploy | upgrade-ytdlp | status" >&2
        exit 1
        ;;
esac

echo "[deploy.sh] repo=${REPO_DIR} python=${PYTHON} action=${verb}"

# --host 127.0.0.1: the supervisor is on this same machine, so the manager
# password never leaves loopback. Only the SSH session crosses the internet.
exec "${PYTHON}" "${REPO_DIR}/hosting/client_manager.py" \
    --host 127.0.0.1 \
    --command "${manager_command}"
