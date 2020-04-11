import configparser
import os
import time
import signal
import subprocess
import sys
import threading


class Server:
    def __init__(self, config):
        signal.signal(signal.SIGTERM, self.terminate)

        java = config['java']
        self.starting_memory = '-Xms' + java['starting_memory']
        self.max_memory = '-Xmx' + java['max_memory']
        self.server_dir = java['server_dir']
        self.sc = ['java', self.starting_memory, self.max_memory, '-jar', 'server.jar', 'nogui']
        self.process = None
        self.timer = None

    def stop_server(self):
        if self.process is not None:
            self.process.stdin.write(b'stop\n')
            time.sleep(10)  # give server time to stop

    def terminate(self, signal_number, frame):
        self.stop_server()
        sys.exit()

    def shutdown(self):
        self.stop_server()
        os.system('sudo reboot now')

    def run(self):
        self.process = subprocess.Popen(self.sc, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        cwd=self.server_dir)

        self.timer = threading.Timer(3600, self.shutdown)
        self.timer.start()


def main():
    config = configparser.ConfigParser()
    config.read('server.ini')

    server = Server(config)
    server.run()


if __name__ == '__main__':
    main()
