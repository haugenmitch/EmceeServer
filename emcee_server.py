from datetime import datetime
import configparser
import logging
import os
import time
import signal
import subprocess
import sys
import threading


class Server:
    def __init__(self, config):
        signal.signal(signal.SIGTERM, self.terminate)

        if not os.path.exists("./logs"):
            os.makedirs("logs")
        logging.basicConfig(filename=datetime.now().strftime('./logs/%Y%m%d%H%M.log'), format='%(asctime)s:%('
                                                                                              'levelname)s:%('
                                                                                              'message)s',
                            level=logging.INFO)

        java = config['java']
        self.starting_memory = '-Xms' + java['starting_memory']
        self.max_memory = '-Xmx' + java['max_memory']
        self.server_dir = java['server_dir']
        self.sc = ['java', self.starting_memory, self.max_memory, '-jar', 'server.jar', 'nogui']
        self.process = None
        self.timer = None
        self.terminate = False
        self.shutdown = False

    def terminate(self, signal_number, frame):
        # self.timer.cancel()
        # self.stop_server()
        # sys.exit()

        self.terminate = True

    def shutdown(self):
        # self.stop_server()
        # os.system('sudo reboot now')

        self.shutdown = True

    def stop_server(self):
        if self.process is not None:
            self.process.stdin.write('stop\n')
            time.sleep(10)  # give server time to stop

    def run(self):
        self.process = subprocess.Popen(self.sc, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        cwd=self.server_dir, text=True)

        self.timer = threading.Timer(3600, self.shutdown)
        self.timer.start()

        while not self.terminate and not self.shutdown:
            out = self.process.stdout.readlines()
            err = self.process.stderr.readlines()
            for line in out:
                logging.info(line.strip())
            for line in err:
                logging.error(line.strip())

        self.stop_server()
        if self.shutdown:
            os.system('sudo reboot now')
        else:
            self.timer.cancel()
            sys.exit()


def main():
    config = configparser.ConfigParser()
    config.read('server.ini')

    server = Server(config)
    server.run()


if __name__ == '__main__':
    main()
