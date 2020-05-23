import configparser
import csv
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time as t

from datetime import datetime, date, time, timedelta
from threading import Thread, Timer, Event, RLock, Condition
from zipfile import ZipFile


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
            with open('server_properties.json', 'r') as spf:
                properties = json.loads(spf.read())
                self.mediumcore = properties['mediumcore']
        except OSError:
            print('Could not find or open server_properties.json')

        try:
            self.server_data_file = open('server_data.json', 'r+')
        except OSError:
            self.server_data_file = open('server_data.json', 'w+')
        file_text = self.server_data_file.read()
        self.server_data = {} if not file_text else json.loads(file_text)
        if self.server_data == {}:
            self.init_server_data()
        self.player_data = self.server_data['player_data']

        try:
            starter_kit_file = open('starter_kit.json', 'r')
            starter_kit_file_text = starter_kit_file.read()
            self.starter_kit = [] if not starter_kit_file_text else json.loads(starter_kit_file_text)
        except OSError:
            self.starter_kit = []

        with open('objectives.json') as objectives_file:
            self.objectives = json.loads(objectives_file.read())

        java = self.config['Java']
        self.starting_memory = '-Xms' + java['StartingMemory']
        self.max_memory = '-Xmx' + java['MaxMemory']
        self.server_dir = java['ServerDir']
        self.sc = ['java', self.starting_memory, self.max_memory, '-jar', 'server.jar', 'nogui']
        self.process = None
        self.timer = None
        self.is_shutting_down = False
        self.server_stop_event = Event()
        self.expected_outputs = {}
        self.lock = Condition(lock=RLock())
        self.online_players = []

    def init_server_data(self):
        self.server_data = {'player_data': {}}

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
        if command:
            logging.info('CMD: ' + command)
            self.process.stdin.write(command + '\n')

    def handle_stdout(self, stream):
        line_count = 0
        while True:
            line = stream.readline()
            if not line:  # EOF
                break
            line = line.strip()
            if line:
                logging.info(line)

                output_captured = False
                with self.lock:
                    for name in self.expected_outputs:
                        if re.search(self.expected_outputs[name]['output_form'], line):
                            self.expected_outputs[name]['output'] = line
                            output_captured |= self.expected_outputs[name]['capture_output']
                            self.lock.notify_all()

                if not output_captured:
                    t = Thread(name=str(line_count), target=self.parse_line, args=(line,))
                    t.start()
                line_count += 1
        self.server_stop_event.set()  # process will only send EOF when done executing

    def create_debug_report(self):
        output = self.get_output('debug report', r'^.*?]: Created debug report in debug-report-.*$', True, 3.0)
        if output is None:
            logging.error('Could not generate debug report')
            return None
        report_name = output[output.index('debug-report-'):]
        report_dir = f"{self.config['Java']['ServerDir']}debug/{report_name}"
        report_path = report_dir + '.zip'
        with ZipFile(report_path, 'r') as zip_file:
            zip_file.extractall(report_dir)
            return report_dir

    def get_player_locations(self):
        debug_dir = self.create_debug_report()
        if debug_dir is None:
            logging.error('Could not get player locations')
            return None
        locations = {}
        for entry in os.walk(debug_dir + '/levels'):
            if 'entities.csv' not in entry[2]:
                continue
            realm = ':'.join(entry[0].split('/')[-2:])
            with open(entry[0]+'/entities.csv', newline='') as csv_file:
                csv_data = csv.reader(csv_file, delimiter=',')
                next(csv_data)  # bypass column name line
                for row in csv_data:
                    if row[4] == 'minecraft:player':
                        locations[row[6]] = {'x': row[0], 'y': row[1], 'z': row[2], 'realm': realm}
        return locations

    def get_output(self, command, output_form, capture_output=True, timeout=None):
        name = threading.current_thread().name
        with self.lock:
            self.expected_outputs[name] = {'output_form': output_form, 'capture_output': capture_output, 'output': None}
            self.send_command(command)
            self.lock.wait_for(lambda: self.expected_outputs[name]['output'] is not None, timeout)
            return self.expected_outputs[name]['output']

    def parse_line(self, line):
        with self.lock:
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

    def process_player_logon(self, username):
        if username not in self.player_data:
            self.create_new_player(username)
            self.send_command(f'tell {username} Welcome to the server, {username}!')
            self.give_starter_kit(username)

        for objective in self.objectives:
            self.send_command(f'scoreboard players set {username} {objective} 0')
            if 'type' in self.objectives[objective] and self.objectives[objective][type] == 'trigger':
                self.send_command(f'scoreboard players enable {username} {objective}')

        # setup death count for player
        self.send_command(f'scoreboard players set {username} deaths {self.player_data[username]["death_count"]}')

        self.player_data[username]['log_ons'].append(datetime.now())
        self.update_player_data_record()
        self.online_players.append(username)

    def process_player_death(self, username, death_count):
        self.player_data[username]['death_count'] = death_count
        self.update_player_data_record()
        self.send_command(f'tell {username} You have died {death_count} times')

        self.imprison_player(username, death_count)

    def imprison_player(self, username, death_count):
        location = self.get_player_locations()[username]

        self.send_command(f'gamemode adventure {username}')
        to_realm = self.mediumcore['coordinates']['realm']
        to_x = self.mediumcore['coordinates']['x']
        to_y = self.mediumcore['coordinates']['y']
        to_z = self.mediumcore['coordinates']['z']
        self.send_command(f'execute in {to_realm} run tp {username} {to_x} {to_y} {to_z}')

        t.sleep(death_count * self.mediumcore['length'])

        from_realm = location['realm']
        from_x = location['x']
        from_y = location['y']
        from_z = location['z']
        self.send_command(f'execute in {from_realm} run tp {username} {from_x} {from_y} {from_z}')
        self.send_command(f'gamemode survival {username}')

    def parse_server_info(self, line):
        first_token = line.split(' ', 1)[0]
        username = first_token if first_token in self.online_players or line.endswith('joined the game') else None

        if username is None:
            return
        elif line.endswith('joined the game'):
            self.process_player_logon(username)
        elif line.endswith('left the game'):
            self.player_data[username]['log_offs'].append(datetime.now())
            self.update_player_data_record()
            self.online_players.remove(username)
        elif re.search(fr'^{username} has (made the advancement|reached the goal|completed the challenge) \[.*\]$',
                       line):
            self.send_command(f'tell {username} Congrats, {username}!')
            self.send_command(f'give {username} minecraft:emerald')
        else:  # could be a death message
            death_count_string = self.get_output(f'scoreboard players get {username} deaths',
                                                 rf'{username} has \d+ \[deaths]', True, 3.0)
            if death_count_string is None:
                return
            death_count = int(re.search(rf'{username} has (\d+) \[deaths]', death_count_string).group(1))
            if death_count != self.player_data[username]['death_count']:
                self.process_player_death(username, death_count)

    def create_new_player(self, username):
        self.player_data[username] = {}
        new_player = self.player_data[username]
        new_player['log_ons'] = []
        new_player['log_offs'] = []
        new_player['death_count'] = 0
        self.update_player_data_record()

    def give_starter_kit(self, username):
        for item in self.starter_kit:
            item_name = item[0]
            quantity = 1 if len(item) < 2 else item[1]
            slot = None if len(item) < 3 else item[2]
            if slot is None:
                self.send_command(f'give {username} {item_name} {quantity}')
            else:
                self.send_command(f'replaceitem entity {username} {slot} {item_name} {quantity}')

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
        self.server_data_file.seek(0)
        self.server_data_file.write(json.dumps(self.server_data, indent=4, sort_keys=True, default=str))
        self.server_data_file.truncate()

    def handle_input(self):
        while True:
            cmd = input('$ ')
            self.send_command(cmd)

    def server_start(self):
        self.get_output('', r'^.*]: Done \(\d+.\d+s\)! For help, type "help"$')

        # setup objectives (do every server start cause why not?)
        for objective in self.objectives:
            self.send_command(f'scoreboard objectives add {objective} {self.objectives[objective]["type"]}')

        self.send_command(f'scoreboard objectives add deaths deathCount')

    def run(self):
        self.process = subprocess.Popen(self.sc, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        cwd=self.server_dir, text=True, bufsize=1, universal_newlines=True)

        self.start_timer()

        # stdout
        stdout_thread = Thread(name='stdout', target=self.handle_stdout, args=(self.process.stdout,))
        stdout_thread.daemon = True
        stdout_thread.start()

        # stderr
        stderr_thread = Thread(name='stderr', target=self.handle_stderr, args=(self.process.stderr,))
        stderr_thread.daemon = True
        stderr_thread.start()

        # stdin
        stdin_thread = Thread(name='stdin', target=self.handle_input)
        stdin_thread.daemon = True
        run_as_service = self.config.getboolean('DEFAULT', 'RunAsService')
        if not run_as_service:
            stdin_thread.start()

        # server start
        server_start = Thread(name='server_start', target=self.server_start)
        server_start.daemon = True
        server_start.start()

        self.server_stop_event.wait()

        stdout_thread.join()
        stderr_thread.join()
        if not run_as_service:
            stdin_thread.join(timeout=0)
            print()  # Last command entry never got filled
        server_start.join(timeout=0)
        self.timer.cancel()
        self.server_data_file.close()

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
