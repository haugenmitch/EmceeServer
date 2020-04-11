import configparser
import os
import time
import signal
import subprocess
import sys


class Server:
    def __init__(self, config):
        signal.signal(signal.SIGTERM, self.terminate)

        java = config['java']
        self.starting_memory = '-Xms' + java['starting_memory']
        self.max_memory = '-Xmx' + java['max_memory']
        self.server_dir = java['server_dir']
        self.sc = ['java', self.starting_memory, self.max_memory, '-jar', 'server.jar', 'nogui']
        self.process = None

    def terminate(self, signal_number, frame):
        if self.process is not None:
            self.process.stdin.write(b'stop\n')
            time.sleep(10)  # give server time to stop
        sys.exit()

    def run(self):
        self.process = subprocess.Popen(self.sc, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        cwd=self.server_dir)

        time.sleep(3600)  # 1 hour = 3600 seconds

        self.process.stdin.write(b'stop\n')
        time.sleep(10)  # give server time to stop

        os.system('sudo reboot now')


def main():
    config = configparser.ConfigParser()
    config.read('server.ini')

    server = Server(config)
    server.run()


if __name__ == '__main__':
    main()
