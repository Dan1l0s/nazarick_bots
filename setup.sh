#!/bin/bash
#
# Installs Python (Windows/Git Bash only), the project's Python dependencies,
# and FFmpeg (Linux only).
#
# WINDOWS USERS: run tools/dev-setup.ps1 from PowerShell instead. This script
# needs Git Bash - it only detects Windows via $OSTYPE = "msys". Invoking
# `bash setup.sh` from PowerShell picks up whichever bash is first on PATH,
# usually C:\Windows\System32\bash.exe (the WSL launcher), which either fails
# with "execvpe(/bin/bash) failed" when no distro is installed, or - worse, when
# one is - takes the Linux branch below and installs packages and ffmpeg inside
# WSL, a different machine from the one running your bots. To force Git Bash:
#     & "C:\Program Files\Git\bin\bash.exe" setup.sh --dev --venv
#
# Change from the original: dependencies now come from requirements.txt rather
# than a hardcoded list of `pip install --upgrade <pkg>` calls, so the runtime
# set has a single source of truth and version floors are respected. Pass
# --dev to also install the test dependencies.

platform="None"
requirements="requirements.txt"
use_venv=0
venv_dir=".venv"

usage() {
    cat <<'USAGE'
Usage: bash setup.sh [--dev] [--venv [DIR]]

  --dev         also install the test dependencies (requirements-dev.txt)
  --venv [DIR]  create/use a virtualenv (default .venv) and install into it,
                instead of installing into the system Python
  -h, --help    show this

Examples:
  bash setup.sh                      # what the VPS deploy runs: system Python
  bash setup.sh --dev --venv         # recommended for local development

IMPORTANT if you use --venv on the SERVER: the systemd unit
(hosting/nazarick.service) pins an absolute interpreter, and the supervisor
launches the bots with sys.executable - so the unit and the venv must agree.
Point ExecStart at <repo>/.venv/bin/python, or the bots will start under the
system Python and fail to import disnake. hosting/deploy.sh already prefers
.venv/bin/python when one exists.
USAGE
}

# Parse every argument, not just $1: the original only looked at "$1", so
# `--venv --dev` silently ignored --dev.
while [ $# -gt 0 ]; do
    case "$1" in
        --dev)
            requirements="requirements-dev.txt"
            ;;
        --venv)
            use_venv=1
            # Optional directory argument, but don't swallow the next flag.
            case "${2:-}" in
                ""|--*) ;;
                *) venv_dir="$2"; shift ;;
            esac
            ;;
        -h|--help)
            usage; exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

function detect_platform  {
    echo "Cheking platform..."
    if [ $OSTYPE = "msys" ]
    then
        echo "Platform: Windows"
        python=python
        platform="Windows"
        return 0
    fi
    if [ $OSTYPE = "linux-gnu" ] || [ $OSTYPE = "linux" ]
    then
        echo "Platform: Linux"
        python=python3
        platform="Linux"
        return 0
    fi
    echo "Setup script does not support platform: $OSTYPE"
    exit 1
}

function install_python {
    echo "Installing python..."
    if [ $platform = "Windows" ]
    then
        file="./setup_cache/python_installer.exe"
        if ! [ -f $file ]
        then
            eval "mkdir setup_cache"
            echo "Downloading python installer..."
            eval "curl -o setup_cache/python_installer.exe https://www.python.org/ftp/python/3.11.4/python-3.11.4-amd64.exe"
        fi
        echo "Openning python installer..."
        eval "./setup_cache/python_installer.exe"
        check_python
    fi

}
function check_python {
    echo "Checking python..."
    eval "command -v $python"
    status=$?
    if [ $status = 0 ]
    then
        eval "rm -rf ./setup_cache"
        echo "Python is installed"
    else
        echo "Python is not installed"
        install_python
    fi
}
function check_pip {
    echo "Checking pip..."
    eval "$python -m pip --version"
    if [ $? = 0 ]
    then
        eval "$python -m pip install --upgrade pip"
        if [ $? != 0 ]
        then
            echo "Failed to update pip"
            exit 1
        fi
    else
        eval "$python -m ensurepip --default-pip"
        if [ $? != 0 ]
        then
            echo "Failed to install pip"
            exit 1
        fi
    fi
    echo "Pip checked"
}
function create_venv {
    if [ $use_venv = 0 ]
    then
        return 0
    fi
    if [ -x "$venv_dir/bin/python" ]
    then
        python="$venv_dir/bin/python"
    elif [ -x "$venv_dir/Scripts/python.exe" ]
    then
        python="$venv_dir/Scripts/python.exe"
    else
        echo "Creating virtualenv in $venv_dir..."
        eval "$python -m venv \"$venv_dir\""
        if [ $? != 0 ]
        then
            echo "Failed to create a virtualenv in $venv_dir."
            echo "On Debian/Ubuntu the venv module ships separately:"
            echo "    sudo apt install python3-venv"
            exit 1
        fi
        # Windows layout differs from POSIX; pick whichever exists.
        if [ -x "$venv_dir/bin/python" ]
        then
            python="$venv_dir/bin/python"
        else
            python="$venv_dir/Scripts/python.exe"
        fi
    fi
    echo "Using interpreter: $python"
}

function install_requirements {
    echo "Installing dependencies from $requirements..."
    eval "$python -m pip install --upgrade -r $requirements"
    if [ $? != 0 ]
    then
        # PEP 668: Debian 12+ and Ubuntu 23.04+ mark the system Python as
        # "externally managed" and refuse a plain pip install. A venv is the
        # correct fix; --break-system-packages is the escape hatch, and is what
        # the existing VPS install effectively relies on.
        echo
        echo "Failed to install dependencies from $requirements"
        if [ $use_venv = 0 ]
        then
            echo
            echo "If the error above mentions 'externally-managed-environment',"
            echo "this Python refuses system-wide installs. Either:"
            echo "    bash setup.sh --venv ${requirements#requirements}   # recommended"
            echo "  or re-run pip yourself with --break-system-packages."
            echo "See --help for the systemd caveat before using --venv on a server."
        fi
        exit 1
    fi
}
function check_ffmpeg {
    echo "Checking FFmpeg..."
    eval "command -v ffmpeg"
    status=$?
    if [ $status = 0 ]
    then
        echo "FFmpeg is installed"
    else
        echo "FFmpeg is not installed"
        install_ffmpeg
    fi
}
function install_ffmpeg {
    if [ $platform = "Linux" ]
    then
        echo "Installing FFmpeg..."
        eval "sudo apt install ffmpeg"
        check_ffmpeg
    fi
    if [ $platform = "Windows" ]
    then
        echo "Please install FFmpeg from: https://www.gyan.dev/ffmpeg/builds/ and add it to path, to enable voice related bot functionality"
    fi
}

detect_platform
check_python
create_venv
# check_pip
install_requirements
check_ffmpeg

if [ $use_venv = 1 ]
then
    echo
    echo "Done. Activate the environment with:"
    if [ -x "$venv_dir/bin/activate" ] || [ -f "$venv_dir/bin/activate" ]
    then
        echo "    source $venv_dir/bin/activate"
    else
        echo "    $venv_dir\\Scripts\\Activate.ps1      (PowerShell)"
        echo "    source $venv_dir/Scripts/activate     (Git Bash)"
    fi
    echo
    echo "Run the tests with:  $python -m pytest -q"
fi
