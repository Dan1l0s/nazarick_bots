#!/usr/bin/env bash
#
# One-shot CI/CD setup. RUN THIS ON THE VPS, as the user that runs the bot.
#
#   bash hosting/setup_cicd.sh                          # check + show what to do
#   bash hosting/setup_cicd.sh --pubkey "ssh-ed25519 AAAA... github-actions"
#   bash hosting/setup_cicd.sh --pubkey-file /tmp/nazarick_ci.pub
#   bash hosting/setup_cicd.sh --install-service        # autostart on boot (sudo)
#
# With a public key it installs the restricted authorized_keys entry for you.
# With --install-service it installs the systemd unit so the bots start at boot.
# Without either it only checks and reports. Safe to run repeatedly - every step
# is idempotent and it never overwrites an existing key line.
#
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_SH="${REPO_DIR}/hosting/deploy.sh"
AUTHORIZED_KEYS="${HOME}/.ssh/authorized_keys"

PUBKEY=""
INSTALL_SERVICE=0
problems=0

green() { printf '  \033[32m[ ok ]\033[0m %s\n' "$1"; }
warn()  { printf '  \033[33m[warn]\033[0m %s\n' "$1"; }
fail()  { printf '  \033[31m[FAIL]\033[0m %s\n' "$1"; problems=$((problems + 1)); }
head2() { printf '\n\033[1m%s\033[0m\n' "$1"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --pubkey)          PUBKEY="${2:-}"; shift 2 ;;
        --pubkey-file)     PUBKEY="$(cat "${2:-}")"; shift 2 ;;
        --install-service) INSTALL_SERVICE=1; shift ;;
        -h|--help)         sed -n '2,14p' "$0"; exit 0 ;;
        *)                 echo "unknown option: $1" >&2; exit 2 ;;
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

# Invoked as `bash <script>` rather than `<script>` directly, so the exec bit is
# irrelevant. It matters because the repo is committed from Windows, which has
# no exec bit: git stores mode 100644 and a fresh checkout on the VPS is not
# executable, which SSH reports only as "Permission denied" with exit 126.
# The mode is now also fixed in git (100755), but a `bash` prefix means a future
# checkout from a Windows machine cannot break deploys again either way.
FORCED_PREFIX="command=\"${PY_PREFIX:-}bash ${DEPLOY_SH}\",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc"

# Repair an entry installed by an older version of this script, which pointed
# the forced command straight at deploy.sh. If the exec bit is missing - which
# is the default for a repo committed from Windows - sshd fails with
# "Permission denied" and exit 126, and the deploy pipeline cannot deploy its own
# fix. Rewriting the existing line to `bash <script>` breaks that deadlock.
if [ -f "${AUTHORIZED_KEYS}" ] \
   && grep -q "command=\"[^\"]*${DEPLOY_SH}\"" "${AUTHORIZED_KEYS}" \
   && ! grep -q "command=\"[^\"]*bash ${DEPLOY_SH}\"" "${AUTHORIZED_KEYS}"; then
    cp -a "${AUTHORIZED_KEYS}" "${AUTHORIZED_KEYS}.bak.$(date +%s)"
    # Insert `bash ` immediately before the script path, leaving any
    # DEPLOY_PYTHON=... prefix and the key itself untouched.
    sed -i "s|command=\"\\(\\([A-Za-z_]*=[^ ]* \\)*\\)${DEPLOY_SH}\"|command=\"\\1bash ${DEPLOY_SH}\"|" \
        "${AUTHORIZED_KEYS}"
    if grep -q "command=\"[^\"]*bash ${DEPLOY_SH}\"" "${AUTHORIZED_KEYS}"; then
        green "repaired the existing forced command to use 'bash' (backup taken)"
        echo "         this fixes 'Permission denied' / exit 126 without needing the exec bit"
    else
        fail "could not rewrite the forced command - edit ${AUTHORIZED_KEYS} by hand"
        echo "         put 'bash ' immediately before ${DEPLOY_SH}"
    fi
fi

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
head2 "7. Autostart on boot (systemd)"
SERVICE_SRC="${REPO_DIR}/hosting/nazarick.service"
SERVICE_DST="/etc/systemd/system/nazarick.service"

if [ "${INSTALL_SERVICE}" -eq 1 ]; then
    if [ "$(id -u)" -ne 0 ] && ! command -v sudo >/dev/null 2>&1; then
        fail "installing the service needs root (or sudo)"
    elif [ -z "${PORT:-}" ]; then
        fail "cannot install the service without hosting_port from private_config.py"
    else
        SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
        # Substitute this machine's real user/paths/port into the template
        # rather than making the operator hand-edit the unit.
        TMP_UNIT="$(mktemp)"
        sed -e "s|^User=.*|User=$(id -un)|" \
            -e "s|^WorkingDirectory=.*|WorkingDirectory=${REPO_DIR}/hosting|" \
            -e "s|^ExecStart=.*|ExecStart=${PYTHON} ${REPO_DIR}/hosting/server_manager.py ${PORT} -r|" \
            "${SERVICE_SRC}" > "${TMP_UNIT}"

        if $SUDO cp "${TMP_UNIT}" "${SERVICE_DST}" 2>/dev/null; then
            rm -f "${TMP_UNIT}"
            $SUDO systemctl daemon-reload
            $SUDO systemctl enable nazarick >/dev/null 2>&1
            green "installed ${SERVICE_DST} and enabled it at boot"
            echo "         User=$(id -un)"
            echo "         ExecStart=${PYTHON} ${REPO_DIR}/hosting/server_manager.py ${PORT} -r"
            echo
            # Any manually-started supervisor must go first, or the service
            # cannot bind the port and will crash-loop.
            if pgrep -f "server_manager.py" >/dev/null 2>&1; then
                warn "a manually-started supervisor is running and holds the port"
                echo "         stop it, then hand over to systemd:"
                echo "           pkill -f server_manager.py && sudo systemctl start nazarick"
            else
                echo "  start it now with:  $SUDO systemctl start nazarick"
            fi
        else
            rm -f "${TMP_UNIT}"
            fail "could not write ${SERVICE_DST} - re-run with sudo"
        fi
    fi
elif [ -f "${SERVICE_DST}" ]; then
    if systemctl is-enabled nazarick >/dev/null 2>&1; then
        green "systemd service installed and enabled at boot"
    else
        warn "systemd service installed but NOT enabled at boot"
        echo "         enable it: sudo systemctl enable nazarick"
    fi
    systemctl is-active nazarick >/dev/null 2>&1 \
        && green "service is active" \
        || warn "service is not running: sudo systemctl start nazarick"
else
    warn "no autostart configured - the bots will NOT come back after a reboot"
    echo "         install it: bash hosting/setup_cicd.sh --install-service"
fi

head2 "8. Supervisor process"
if pgrep -f "server_manager.py" >/dev/null 2>&1; then
    green "server_manager.py is running"
    if [ -f "${SERVICE_DST}" ] && systemctl is-active nazarick >/dev/null 2>&1; then
        echo "         managed by systemd - restart with: sudo systemctl restart nazarick"
    else
        echo "         started manually; it still has the OLD code loaded."
        echo "         restart to pick up the new commands:"
        echo "           pkill -f server_manager.py"
        echo "           cd ${REPO_DIR}/hosting && ${PYTHON} server_manager.py ${PORT:-<port>} -r & disown"
    fi
else
    warn "server_manager.py is not running"
    if [ -f "${SERVICE_DST}" ]; then
        echo "         start it: sudo systemctl start nazarick"
    else
        echo "         start it: cd ${REPO_DIR}/hosting && ${PYTHON} server_manager.py ${PORT:-<port>} -r & disown"
    fi
fi

# --------------------------------------------------------------------------
head2 "9. End-to-end check"
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
