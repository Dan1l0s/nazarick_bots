#!/bin/bash

platform="None"

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
function install_package {
    eval "$python -m pip install --upgrade $1"
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
check_pip
install_package yt_dlp
install_package youtube_search
install_package disnake[voice]
install_package openai
check_ffmpeg
