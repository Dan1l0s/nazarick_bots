#!/usr/bin/env bash
#
# One-shot CI/CD setup. RUN THIS ON THE VPS, as the user that runs the bot.
#
#   bash hosting/setup_cicd.sh                          # check + show what to do
#   bash hosting/setup_cicd.sh --pubkey "ssh-ed25519 AAAA... github-actions"
#   bash hosting/setup_cicd.sh --pubkey-file /tmp/nazarick_ci.pub
#
# With a public key it installs the restricted authorized_keys entry for you.
# Without one it only checks and reports. Safe to run repeatedly - every step
# is idempotent and it never overwrites an existing key line.
#
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_SH="${REPO_DIR}/hosting/deploy.sh"
AUTHORIZED_KEYS="${HOME}/.ssh/authorized_keys"

PUBKEY=""
problems=0

green() { printf '  \033[32m[ ok ]\033[0m %s\n' "$1"; }
warn()  { printf '  \033[33m[warn]\033[0m %s\n' "$1"; }
fail()  { printf '  \033[31m[FAIL]\033[0m %s\n' "$1"; problems=$((problems + 1)); }
head2() { printf '\n\033[1m%s\033[0m\n' "$1"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --pubkey)      PUBKEY="${2:-}"; shift 2 ;;
        --pubkey-file) PUBKEY="$(cat "${2:-}")"; shift 2 ;;
        -h|--help)     sed -n '2,12p' "$0"; exit 0 ;;
        *)             echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

echo "======================================================================"
echo "  Nazarick bots - CI/CD setup"
echo "  repo: ${REPO_DIR}"
echo "  user: $(id -un)"
echo "======================================================================"

# --------------------------------------------------------------------------
head2 "1. Line endings"
# A CRLF deploy.sh fails with "/usr/bin/env: 'bash\r': No such file" - an error
# that names the interpreter rather than the file, so it is worth checking.
if head -c 200 "${DEPLOY_SH}" 2>/dev/null | grep -q $'\r'; then
    fail "deploy.sh has Windows (CRLF) line endings and will not run"
    echo "         fix: sed -i 's/\r$//' ${DEPLOY_SH}"
    echo "         (the committed .gitattributes prevents this recurring)"
else
    green "deploy.sh has Unix line endings"
fi

# --------------------------------------------------------------------------
head2 "2. Directories and permissions"
if mkdir -p "${REPO_DIR}/run" 2>/dev/null; then
    green "run/ exists (bot publishes playback status here)"
else
    fail "could not create ${REPO_DIR}/run"
fi

if chmod +x "${DEPLOY_SH}" 2>/dev/null; then
    green "deploy.sh is executable"
else
    fail "could not chmod +x ${DEPLOY_SH}"
fi

# --------------------------------------------------------------------------
head2 "3. Python"
PYTHON=""
for candidate in "${REPO_DIR}/.venv/bin/python" "$(command -v python3 2>/dev/null || true)" \
                 /usr/local/bin/python3 /usr/bin/python3; do
    if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then PYTHON="${candidate}"; break; fi
done

if [ -z "${PYTHON}" ]; then
    fail "no python3 found"
else
    green "python: ${PYTHON} ($(${PYTHON} --version 2>&1))"
    # deploy.sh searches this same list, so a match here means it will work
    # even under the bare PATH that SSH forced commands get.
    if [ "${PYTHON}" = "/usr/bin/python3" ] || [ "${PYTHON}" = "/usr/local/bin/python3" ] \
       || [ "${PYTHON}" = "${REPO_DIR}/.venv/bin/python" ]; then
        green "deploy.sh will find this python without extra configuration"
        PY_PREFIX=""
    else
        warn "non-standard python location"
        echo "         prefix the forced command with: DEPLOY_PYTHON=${PYTHON}"
        PY_PREFIX="DEPLOY_PYTHON=${PYTHON} "
    fi
fi

# --------------------------------------------------------------------------
head2 "4. Configuration"
if [ -f "${REPO_DIR}/configs/private_config.py" ]; then
    green "configs/private_config.py present"
    PORT="$(${PYTHON} -c "
import sys; sys.path.insert(0, '${REPO_DIR}')
try:
    from configs.private_config import hosting_port; print(hosting_port)
except Exception: print('')
" 2>/dev/null)"
    if [ -n "${PORT}" ]; then
        green "manager port: ${PORT}"
    else
        fail "hosting_port is not set in private_config.py"
    fi
else
    fail "configs/private_config.py missing - the bots cannot start"
fi

if [ -f "${REPO_DIR}/db/bot_database.db" ]; then
    green "db/bot_database.db present (settings + XP)"
else
    warn "db/bot_database.db missing - bots would start with empty settings and XP"
fi

# --------------------------------------------------------------------------
head2 "5. Deploy key"
mkdir -p "${HOME}/.ssh" && chmod 700 "${HOME}/.ssh"
FORCED_PREFIX="command=\"${PY_PREFIX:-}${DEPLOY_SH}\",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc"

if [ -n "${PUBKEY}" ]; then
    # Keep only the type+base64 so a differing comment doesn't create a duplicate.
    KEY_BODY="$(echo "${PUBKEY}" | awk '{print $1" "$2}')"
    if [ -f "${AUTHORIZED_KEYS}" ] && grep -qF "${KEY_BODY}" "${AUTHORIZED_KEYS}"; then
        green "this key is already installed - leaving authorized_keys untouched"
    else
        cp -a "${AUTHORIZED_KEYS}" "${AUTHORIZED_KEYS}.bak.$(date +%s)" 2>/dev/null || true
        printf '%s %s\n' "${FORCED_PREFIX}" "${PUBKEY}" >> "${AUTHORIZED_KEYS}"
        chmod 600 "${AUTHORIZED_KEYS}"
        green "installed restricted key (existing keys untouched; backup taken)"
    fi
else
    warn "no --pubkey given; nothing installed"
    echo
    echo "  Add this ONE LINE to ${AUTHORIZED_KEYS}, then append your public key:"
    echo
    echo "    ${FORCED_PREFIX} ssh-ed25519 AAAA...your-key... github-actions"
    echo
    echo "  Or re-run:  bash hosting/setup_cicd.sh --pubkey-file /path/to/key.pub"
fi

# --------------------------------------------------------------------------
head2 "6. GitHub secrets"
SSH_PORT="$(grep -E '^\s*Port\s+' /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' | head -1)"
SSH_PORT="${SSH_PORT:-22}"
PUBLIC_IP="$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || true)"
[ -z "${PUBLIC_IP}" ] && PUBLIC_IP="<your-vps-ip>"

echo "  DEPLOY_USER        $(id -un)"
echo "  DEPLOY_HOST        ${PUBLIC_IP}"
if [ "${SSH_PORT}" != "22" ]; then
    echo "  DEPLOY_PORT        ${SSH_PORT}"
else
    echo "  DEPLOY_PORT        (skip - you are on the default 22)"
fi
echo "  DEPLOY_SSH_KEY     the PRIVATE half of the key above (from your PC)"
echo
echo "  DEPLOY_KNOWN_HOSTS  copy the line(s) below verbatim:"
for keyfile in /etc/ssh/ssh_host_ed25519_key.pub /etc/ssh/ssh_host_rsa_key.pub; do
    [ -f "${keyfile}" ] || continue
    KEYDATA="$(awk '{print $1" "$2}' "${keyfile}")"
    if [ "${SSH_PORT}" = "22" ]; then
        echo "    ${PUBLIC_IP} ${KEYDATA}"
    else
        echo "    [${PUBLIC_IP}]:${SSH_PORT} ${KEYDATA}"
    fi
done

# --------------------------------------------------------------------------
head2 "7. Supervisor"
if pgrep -f "server_manager.py" >/dev/null 2>&1; then
    green "server_manager.py is running"
    echo "         it still has the OLD code loaded - restart it to pick up the new commands:"
    echo "           pkill -f server_manager.py"
    echo "           cd ${REPO_DIR}/hosting && ${PYTHON} server_manager.py ${PORT:-<port>} -r & disown"
else
    warn "server_manager.py is not running"
    echo "         start it: cd ${REPO_DIR}/hosting && ${PYTHON} server_manager.py ${PORT:-<port>} -r & disown"
fi

# --------------------------------------------------------------------------
head2 "8. End-to-end check"
if pgrep -f "server_manager.py" >/dev/null 2>&1; then
    echo "  running: deploy.sh status"
    if OUT="$(SSH_ORIGINAL_COMMAND=status bash "${DEPLOY_SH}" 2>&1)"; then
        echo "${OUT}" | sed 's/^/    /'
        if echo "${OUT}" | grep -q "Playback:"; then
            green "supervisor is running the NEW code"
        else
            warn "no 'Playback:' line - the supervisor is still on the old code, restart it"
        fi
    else
        fail "deploy.sh could not reach the supervisor"
        echo "${OUT}" | sed 's/^/    /'
    fi
else
    warn "skipped - supervisor not running"
fi

echo
echo "======================================================================"
if [ "${problems}" -gt 0 ]; then
    echo "  ${problems} problem(s) above need fixing."
    echo "======================================================================"
    exit 1
fi
echo "  VPS side is ready. Next: add the secrets from section 6 to GitHub,"
echo "  then push to master. See docs/DEPLOYMENT.md."
echo "======================================================================"
