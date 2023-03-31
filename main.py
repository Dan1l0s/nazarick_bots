import threading
import subprocess


def start_music():
    subprocess.run('python music.py', shell=True)


def start_radio():
    subprocess.run('python radio.py', shell=True)


music = threading.Thread(target=start_music)
radio = threading.Thread(target=start_radio)

music.start()
radio.start()
