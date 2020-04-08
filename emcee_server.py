import signal
import os
import time
import sys
import subprocess


# Call the following to get the pid for the kill command:
# ps -ax | grep emcee_server.py
# kill -SIGTERM <pid>
# kill -15 <pid>
def terminate(signal_number, frame):
    print('Terminating')
    if process is not None:
        process.stdin.write(b'stop\n')
    time.sleep(5)
    print('Done')
    sys.exit()


signal.signal(signal.SIGTERM, terminate)

print('PID: ', os.getpid())

sc = ['java', '-Xms1G', '-Xmx2G', '-jar', 'server.jar', 'nogui']
process = subprocess.Popen(sc, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd='./minecraft/')

time.sleep(3600)  # 1 hour = 3600 seconds

process.stdin.write(b'stop\n')

print('Restarting server...')

time.sleep(15)

os.system('sudo reboot now')
