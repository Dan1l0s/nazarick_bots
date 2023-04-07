from threading import Thread
import subprocess


def start_music():
    subprocess.run('python music.py', shell=True)


def start_radio():
    subprocess.run('python radio.py', shell=True)


def start_reserve_music():
    subprocess.run('python music_reserve.py', shell=True)


music = Thread(target=start_music)
radio = Thread(target=start_radio)
reserve_music = Thread(target=start_reserve_music)

music.start()
radio.start()
reserve_music.start()
