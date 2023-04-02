from threading import Thread
import subprocess


def start_music():
    subprocess.run('python music.py', shell=True)


def start_radio():
    subprocess.run('python radio.py', shell=True)


music = Thread(target=start_music)
radio = Thread(target=start_radio)

music.start()
radio.start()
