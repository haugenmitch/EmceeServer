import configparser
import os
import time
import signal
import subprocess
import sys


# Call the following to get the pid for the kill command:
# ps -ax | grep emcee_server.py
# kill -SIGTERM <pid>
# kill -15 <pid>
def terminate(signal_number, frame):
    if process is not None:
        process.stdin.write(b'stop\n')
    sys.exit()


signal.signal(signal.SIGTERM, terminate)

config = configparser.ConfigParser()
config.read('server.ini')
java = config['java']
starting_memory = '-Xms' + java['starting_memory']
max_memory = '-Xmx' + java['max_memory']
server_dir = java['server_dir']
sc = ['java', starting_memory, max_memory, '-jar', 'server.jar', 'nogui']
process = subprocess.Popen(sc, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=server_dir)

time.sleep(3600)  # 1 hour = 3600 seconds

process.stdin.write(b'stop\n')

time.sleep(10)  # give server time to stop

os.system('sudo reboot now')
