import configparser
import logging
import os
import signal
import subprocess
import sys
from datetime import datetime, date, time, timedelta
from threading import Thread, Timer, Event
import re
import json


class Server:
    def __init__(self, config):
        self.config = config
        signal.signal(signal.SIGTERM, self.terminate)

        if not os.path.exists("./logs"):
            os.makedirs("logs")
        logging.basicConfig(filename=datetime.now().strftime('./logs/%Y%m%d%H%M.log'), format='%(asctime)s:%('
                                                                                              'levelname)s:%('
                                                                                              'message)s',
                            level=logging.INFO)

        try:
            self.json_file = open('player_data.json', 'r+')
        except OSError:
            self.json_file = open('player_data.json', 'w+')
        file_text = self.json_file.read()
        self.player_data = {} if not file_text else json.loads(file_text)

        java = self.config['Java']
        self.starting_memory = '-Xms' + java['StartingMemory']
        self.max_memory = '-Xmx' + java['MaxMemory']
        self.server_dir = java['ServerDir']
        self.sc = ['java', self.starting_memory, self.max_memory, '-jar', 'server.jar', 'nogui']
        self.process = None
        self.timer = None
        self.is_shutting_down = False
        self.server_stop_event = Event()

    def terminate(self, signal_number, frame):
        self.stop_server()

    def shutdown(self):
        self.is_shutting_down = True
        self.stop_server()

    def stop_server(self):
        self.timer.cancel()
        if self.process is not None:
            self.send_command('stop')
            self.server_stop_event.wait()
        self.server_stop_event.set()  # Set the event in case the server never started

    def start_timer(self):
        reset_time = datetime.combine(date.today(), time(8, 0))
        reset_time += timedelta(days=1)
        total_time = reset_time - datetime.now()
        self.timer = Timer(total_time.total_seconds(), self.shutdown)
        self.timer.start()

    def send_command(self, command):
        command = command.strip()
        logging.info('CMD: ' + command)
        self.process.stdin.write(command + '\n')

    def handle_stdout(self, stream):
        while True:
            line = stream.readline()
            if not line:
                break
            line = line.strip()
            if line:
                logging.info(line)
                self.parse_line(line)
        self.server_stop_event.set()  # process will only send EOF when done executing

    def parse_line(self, line):
        line = re.sub(r'^.*?]:', '', line)
        line = line.strip()
        if line.startswith('*'):  # User used /me command
            pass
        elif line.startswith('<'):  # User entered something in chat
            pass
        elif line.startswith('['):  # op ran a command
            pass
        else:  # server info
            self.parse_server_info(line)

    def parse_server_info(self, line):
        username = line.split(' ', 1)[0]
        if line.endswith('joined the game'):
            if username not in self.player_data:
                self.create_new_player(username)
                self.send_command('/tell ' + username + ' Welcome to the server, ' + username + '!')
            self.player_data[username]['log_ons'].append(datetime.now())
            self.update_player_data_record()
        elif line.endswith('left the game'):
            self.player_data[username]['log_offs'].append(datetime.now())
            self.update_player_data_record()
        elif re.search(r'has made the advancement \[.*\]$', line):
            self.send_command('/tell ' + username + ' Congrats, ' + username + '!')
            self.send_command('/give ' + username + ' minecraft:emerald')

    def create_new_player(self, username):
        self.player_data[username] = {}
        new_player = self.player_data[username]
        new_player['log_ons'] = []
        new_player['log_offs'] = []
        self.update_player_data_record()

    def handle_stderr(self, stream):
        while True:
            line = stream.readline()
            if not line:
                break
            line = line.strip()
            if line:
                logging.error(line)
        self.server_stop_event.set()  # process will only send EOF when done executing

    def update_player_data_record(self):
        self.json_file.seek(0)
        self.json_file.write(json.dumps(self.player_data, indent=4, sort_keys=True, default=str))
        self.json_file.truncate()

    def handle_input(self):
        while True:
            cmd = input('$ ')
            self.send_command(cmd)

    def run(self):
        self.process = subprocess.Popen(self.sc, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        cwd=self.server_dir, text=True, bufsize=1, universal_newlines=True)

        self.start_timer()

        # stdout
        stdout_thread = Thread(target=self.handle_stdout, args=(self.process.stdout,))
        stdout_thread.daemon = True
        stdout_thread.start()

        # stderr
        stderr_thread = Thread(target=self.handle_stderr, args=(self.process.stderr,))
        stderr_thread.daemon = True
        stderr_thread.start()

        # stdin
        run_as_service = self.config.getboolean('DEFAULT', 'RunAsService')
        if not run_as_service:
            stdin_thread = Thread(target=self.handle_input)
            stdin_thread.daemon = True
            stdin_thread.start()

        self.server_stop_event.wait()

        stdout_thread.join()
        stderr_thread.join()
        if not run_as_service:
            stdin_thread.join(timeout=0)
            print()  # Last command entry never got filled
        self.timer.cancel()
        self.json_file.close()

        if self.is_shutting_down:
            os.system('sudo reboot now')
        else:
            sys.exit()


def main():
    config = configparser.ConfigParser()
    config.read('server.ini')

    server = Server(config)
    server.run()


if __name__ == '__main__':
    main()
