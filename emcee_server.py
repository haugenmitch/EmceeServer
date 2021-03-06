import configparser
import csv
import json
import logging
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import commands

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
            self.server_data_file = open('server_data.json', 'r+')
        except OSError:
            self.server_data_file = open('server_data.json', 'w+')
        file_text = self.server_data_file.read()
        self.server_data = {} if not file_text else json.loads(file_text, object_hook=self.recursive_datetime_parser)
        if self.server_data == {}:
            self.init_server_data()
        self.player_data = self.server_data['player_data']

        try:
            items_file = open('items.json', 'r')
            items_file_text = items_file.read()
            items = None if not items_file_text else json.loads(items_file_text)
            self.starter_kit = items['starter_kit'] if items is not None and 'starter_kit' in items else None
            self.player_guide = items['player_guide'] if items is not None and 'player_guide' in items else None
        except OSError:
            self.starter_kit = None
            self.player_guide = None

        # storing commands in a dict
        command_list = [x for x in dir(commands) if x[0:2] != '__' and x[-2:] != '__']
        self.command_dict = {}
        for command in command_list:
            self.command_dict[command] = getattr(commands, command)

        java = self.config['Java']
        self.starting_memory = '-Xms' + java['StartingMemory']
        self.max_memory = '-Xmx' + java['MaxMemory']
        self.server_dir = java['ServerDir'] if java['ServerDir'] != '' else (os.getcwd() + '/minecraft/')
        self.server_dir += '' if self.server_dir.endswith('/') else '/'
        self.sc = ['java', self.starting_memory, self.max_memory, '-jar', 'server.jar', 'nogui']
        self.process = None
        self.timer = None
        self.is_shutting_down = False
        self.server_stop_event = Event()
        self.expected_outputs = {}
        self.lock = Condition(lock=RLock())
        self.online_players = []

        self.cleanup_debug_folder()

    def recursive_datetime_parser(self, d):
        if type(d) is list:
            for i in range(len(d)):
                if type(d[i]) is dict or type(d[i]) is list:
                    d[i] = self.recursive_datetime_parser(d[i])
                elif type(d[i]) is str:
                    try:
                        d[i] = datetime.fromisoformat(d[i])
                    except ValueError:
                        pass
        elif type(d) is dict:
            for k, v in d.items():
                if type(v) is dict or type(v) is list:
                    d[k] = self.recursive_datetime_parser(v)
                elif type(v) is str:
                    try:
                        d[k] = datetime.fromisoformat(v)
                    except ValueError:
                        pass
        return d

    def init_server_data(self):
        self.server_data = {'player_data': {}}

    def cleanup_debug_folder(self):
        if self.server_dir is None:
            return
        debug_dir = self.server_dir + 'debug'
        for filename in os.listdir(debug_dir):
            filepath = os.path.join(debug_dir, filename)
            try:
                if os.path.isfile(filepath) or os.path.islink(filepath):
                    creation_datetime = datetime.strptime(filename, 'debug-report-%Y-%m-%d_%H.%M.%S.zip')
                    if (datetime.now() - creation_datetime) > timedelta(days=5):
                        os.remove(filepath)
                elif os.path.isdir(filepath):
                    creation_datetime = datetime.strptime(filename, 'debug-report-%Y-%m-%d_%H.%M.%S')
                    if (datetime.now() - creation_datetime) > timedelta(days=5):
                        shutil.rmtree(filepath)
            except OSError as e:
                logging.error(f'Failed to remove {filepath} because: {e}')

    def terminate(self, _signal_number, _frame):
        self.stop_server()

    def shutdown(self):
        self.is_shutting_down = True
        self.stop_server()

    def stop_server(self):
        self.timer.cancel()

        for username in self.online_players:
            self.send_command(f'kick {username} Server is shutting down')

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
                        if re.search(self.expected_outputs[name]['success_output'], line):
                            self.expected_outputs[name]['success'] = True
                        elif self.expected_outputs[name]['failure_output'] is not None and \
                                re.search(self.expected_outputs[name]['failure_output'], line):
                            pass
                        else:
                            continue  # skip the next lines if it wasn't a success or failure
                        self.expected_outputs[name]['output'] = line
                        output_captured |= self.expected_outputs[name]['capture_output']
                        self.lock.notify_all()

                if not output_captured:
                    t = Thread(name=str(line_count), target=self.parse_line, args=(line,))
                    t.start()
                line_count += 1
        self.server_stop_event.set()  # process will only send EOF when done executing

    def create_debug_report(self):
        output, _success = self.get_output(command='debug report',
                                           success_output=r'^.*?]: Created debug report in debug-report-.*$',
                                           timeout=3.0)
        if output is None:
            logging.error('Could not generate debug report')
            return None
        report_name = output[output.index('debug-report-'):]
        report_dir = f'{self.server_dir}debug/{report_name}'
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
            with open(entry[0] + '/entities.csv', newline='') as csv_file:
                csv_data = csv.reader(csv_file, delimiter=',')
                next(csv_data)  # bypass column name line
                for row in csv_data:
                    if row[4] == 'minecraft:player':
                        locations[row[6]] = {'x': float(row[0]), 'y': float(row[1]), 'z': float(row[2]), 'realm': realm}
        return locations

    def get_player_location(self, username):
        locations = self.get_player_locations()
        return locations[username] if username in locations else None

    def get_output(self, command, success_output, failure_output=None, capture_output=True, timeout=None):
        name = threading.current_thread().name
        with self.lock:
            self.expected_outputs[name] = {'success_output': success_output, 'failure_output': failure_output,
                                           'capture_output': capture_output, 'output': None, 'success': False}
            self.send_command(command)
            self.lock.wait_for(lambda: self.expected_outputs[name]['output'] is not None, timeout)
            line = self.expected_outputs[name]['output']
            success = self.expected_outputs[name]['success']
            del self.expected_outputs[name]
            return line, success

    def parse_line(self, line):
        with self.lock:
            line = re.sub(r'^.*?]:', '', line)
            line = line.strip()
            if line.startswith('*'):  # User used /me command
                pass
            elif line.startswith('<'):  # User entered something in chat
                self.parse_user_chat(line)
            elif line.startswith('['):  # op ran a command or objective was triggered or server message
                self.parse_command_message(line)
            else:  # server info
                self.parse_server_info(line)

    def parse_user_chat(self, line):
        groups = re.search(r'\<(?P<username>\w+)\> (?P<text>.+)$', line)
        username = groups.group('username')
        text = groups.group('text').strip()
        if text.startswith('*'):
            self.parse_player_text_command(username, text)
        else:
            pass  # non-command user chat

    def parse_player_text_command(self, username, command):
        command = command[1:] if command.startswith('*') else command
        tokens = command.split()
        mods = self.server_data['server_moderators'] if 'server_moderators' in self.server_data else None
        if tokens[0] == 'book':
            if self.player_guide is not None:
                self.send_command(f'give {username} {self.player_guide}')
        elif tokens[0] == 'mod':
            user = username if len(tokens) < 2 else tokens[1]
            if user == username and mods is None:
                self.server_data['server_moderators'] = [user]
                self.laud_player(username, 'You have been made a moderator')
            elif mods is not None and username in mods:
                if user not in mods:
                    mods.append(user)
                    self.laud_player(username, f'{user} has been made a moderator')
                else:
                    self.tell_player(username, f'{user} is already a moderator')
            else:
                self.warn_player(username, 'You are not a moderator')
        elif mods is not None and username in mods:  # mods only
            if tokens[0] == 'demod':
                user = username if len(tokens) < 2 else tokens[1]
                if user in mods:
                    mods.remove(user)
                    self.laud_player(username, f'{user} has been removed from the mod list')
                    if len(mods) == 0:
                        del self.server_data['server_moderators']
                        self.laud_player(username, 'All mods have been removed')
                else:
                    self.tell_player(username, f'{user} is not a moderator')
            elif tokens[0] == 'modlist':
                self.tell_player(username, ', '.join(mods))
            elif tokens[0] == 'create_wall':
                try:
                    size = int(tokens[1])
                    self.create_wall(username, size)
                except (ValueError, TypeError, IndexError):
                    self.warn_player(username, 'create_wall requires an integer size argument')
            elif tokens[0] == 'create_jail':
                try:
                    length = int(tokens[1])
                    self.create_jail(username, length)
                except (ValueError, TypeError, IndexError):
                    self.warn_player(username, 'create_wall requires an integer length argument')
            elif tokens[0] == 'reset_deaths':
                try:
                    user = tokens[1]
                    if self.reset_deaths(user):
                        self.laud_player(username, f'Death count for {user} has been reset')
                    else:
                        self.warn_player(username, f'{user} could not be found or have their death count reset')
                except IndexError:
                    self.warn_player(username, 'reset_deaths requires a username argument')
            else:
                self.send_command(command)
        else:
            self.tell_player(username, 'Command not recognized')

    def create_wall(self, username, size):
        location = self.get_player_location(username)
        if location is None:
            self.warn_player(username, 'Your location could not be found')
            return
        x, z = float(round(location['x'])), float(round(location['z']))
        self.send_command(f'worldborder center {x} {z}')
        self.send_command(f'worldborder set {size}')
        self.server_data['wall'] = {'center': {'x': x, 'z': z}, 'min_size': size, 'cooldown': datetime.now()}

    def get_wall_size(self):
        output = r'The world border is currently (?P<size>\d+) blocks wide'
        line, _success = self.get_output('worldborder get', output)
        return int(re.search(output, line).group('size'))

    def shrink_wall(self):
        if 'wall' not in self.server_data:
            return  # server world border hasn't been created yet
        diff = (self.server_data['wall']['cooldown'] - datetime.now()).total_seconds()
        if diff > 0:
            Timer(diff, self.shrink_wall).start()
            return  # don't start a shrink while the border is growing
        current_wall_size = self.get_wall_size()
        min_size = self.server_data['wall']['min_size']
        radius_decrease_amount = round((current_wall_size - min_size) / 2)
        if radius_decrease_amount <= 0:
            return  # don't shrink if no room to shrink
        # continuing on if there is room to shrink
        online_player_count = len(self.online_players)
        if online_player_count == 0:
            if self.server_data['wall']['shrinking'] if 'shrinking' in self.server_data['wall'] else False:
                self.send_command(f'worldborder add -0.00001')  # stop shrink if shrinking and last person logs off
                self.server_data['wall']['shrinking'] = False
            return  # Don't shrink if no players online to drive shrinking
        seconds_per_meter = 360
        time_s = round(radius_decrease_amount * seconds_per_meter / math.sqrt(online_player_count))
        self.send_command(f'worldborder add -0.00001')  # reset shrink speed. See 'wall' command for more information.
        self.send_command(f'worldborder set {min_size} {time_s}')
        self.server_data['wall']['shrinking'] = True

    def create_jail(self, username, length):
        location = self.get_player_location(username)
        if location is None:
            self.warn_player(username, 'Your location could not be found')
            return
        x, y, z = round(location['x'] - 0.5) + 0.5, location['y'], round(location['z'] - 0.5) + 0.5
        self.server_data['jail'] = {'location': {'x': x, 'y': y, 'z': z, 'realm': location['realm']}, 'length': length}
        self.laud_player(username, 'You have successfully set the jail location')

    def reset_deaths(self, username):
        if username not in self.player_data:
            return False
        self.player_data[username]['death_count'] = 0
        self.player_data[username]['tithe']['count'] = 0
        self.send_command(f'scoreboard players set {username} deaths 0')
        return True

    def parse_command_message(self, line):
        if line.startswith('[Server]'):  # server message
            pass
        else:  # command was executed
            line = line[1:-1]  # strip square brackets
            username = line[:line.index(':')]
            line = line[line.index(':') + 2:]
            if line.startswith('Triggered'):
                groups = re.search(r'Triggered \[(?P<trigger>\w+)]( \((?P<mode>added|set) (|value to )(?P<value>\d+)'
                                   r'( to value|)\)|)', line)
                trigger = groups.group('trigger')
                mode = None if groups.group('mode') is None else groups.group('mode')
                value = None if groups.group('value') is None else int(groups.group('value'))
                self.process_trigger(username, trigger, mode, value)

    def process_trigger(self, username, trigger, mode, value):
        if trigger.endswith('_cost'):
            trigger = trigger[:-5]
            self.command_dict[trigger].cost(self, username, mode, value)
            self.send_command(f'scoreboard players enable {username} {trigger + "_cost"}')
        elif trigger.endswith('_cooldown'):
            trigger = trigger[:-9]
            self.command_dict[trigger].cooldown(self, username, mode, value)
            self.send_command(f'scoreboard players enable {username} {trigger + "_cooldown"}')
        else:
            self.command_dict[trigger].execute(self, username, mode, value)
            self.send_command(f'scoreboard players enable {username} {trigger}')

    def get_player_item_count(self, username, item):
        cmd = f'clear {username} {item} 0'
        success_output = rf'Found (?P<value>\d+) matching items on player {username}'
        failure_output = f'No items were found on player {username}'
        line, success = self.get_output(cmd, success_output, failure_output)
        if success:
            return int(re.search(success_output, line).group('value'))
        else:
            return 0

    def remove_player_items(self, username, item, count):
        if count < 1:
            return False
        cmd = f'clear {username} {item} {count}'
        output = rf'Removed (?P<value>\d+) items from player {username}'
        fail_output = f'No items were found on player {username}'
        line, success = self.get_output(cmd, output, fail_output)
        if not success:
            return False
        removed_count = int(re.search(output, line).group('value'))
        if removed_count != count:
            self.send_command(f'give {username} {item} {removed_count}')
        return removed_count == count

    def warn_player(self, username, message):
        self.send_command(f'tellraw {username} {{"text":"{message}","color":"#FF0000"}}')

    def tell_player(self, username, message):
        self.send_command(f'tellraw {username} {{"text":"{message}"}}')

    def laud_player(self, username, message):
        self.send_command(f'tellraw {username} {{"text":"{message}","color":"green"}}')

    def process_player_logon(self, username):
        if username not in self.player_data:
            self.create_new_player(username)
            self.send_command(f'tell {username} Welcome to the server, {username}!')
            self.send_command(f'give {username} {self.player_guide}')
            self.give_starter_kit(username)

        for command in self.command_dict:
            self.send_command(f'scoreboard players set {username} {command} 0')
            self.send_command(f'scoreboard players enable {username} {command}')
            self.send_command(f'scoreboard players set {username} {command + "_cost"} 0')
            self.send_command(f'scoreboard players enable {username} {command + "_cost"}')
            self.send_command(f'scoreboard players set {username} {command + "_cooldown"} 0')
            self.send_command(f'scoreboard players enable {username} {command + "_cooldown"}')

            if command not in self.player_data[username]:
                self.player_data[username][command] = {}

        # setup death count for player
        self.send_command(f'scoreboard players set {username} deaths {self.player_data[username]["death_count"]}')

        self.player_data[username]['log_ons'].append(datetime.now())
        self.update_server_data_record()
        self.online_players.append(username)
        self.shrink_wall()
        if 'death_punishment' in self.player_data[username]:
            now = datetime.now()
            end_time = self.player_data[username]['death_punishment']['end_time']
            if type(end_time) is str:
                end_time = datetime.fromisoformat(end_time)
                self.player_data[username]['death_punishment']['end_time'] = end_time
            if end_time <= now:
                self.end_punishment(username)
            else:
                timer = Timer((end_time - now).total_seconds(), self.end_punishment, (username,))
                timer.start()
                self.player_data[username]['death_punishment']['timer'] = timer
                if not self.player_data[username]['death_punishment']['imprisoned']:
                    self.imprison_player(username)

    def process_player_logoff(self, username):
        with self.lock:
            self.player_data[username]['log_offs'].append(datetime.now())
            self.update_server_data_record()
            if 'death_punishment' in self.player_data[username]:
                self.player_data[username]['death_punishment']['timer'].cancel()
            self.online_players.remove(username)
            self.shrink_wall()

    def process_player_death(self, username):
        if 'jail' in self.server_data:
            if 'death_punishment' in self.player_data[username]:
                self.teleport_to_jail(username)  # teleport back to jail if player died in jail
            else:
                self.player_data[username]['death_count'] += 1
                self.update_server_data_record()
                self.tell_player(username, f'You have died {self.player_data[username]["death_count"]} times')
                self.punish_player_death(username, self.player_data[username]['death_count'])

    def punish_player_death(self, username, death_count):
        with self.lock:
            self.player_data[username]['death_punishment'] = {'location': None, 'end_time': None, 'timer': None,
                                                              'imprisoned': False}
            tithe_count = 0 if 'count' not in self.player_data[username]['tithe'] \
                else self.player_data[username]['tithe']['count']
            punishment_length = (death_count - tithe_count) * self.server_data['jail']['length']
            end_time = datetime.now() + timedelta(seconds=punishment_length)
            timer = Timer(punishment_length, self.end_punishment, (username,))
            self.player_data[username]['death_punishment']['timer'] = timer
            self.player_data[username]['death_punishment']['end_time'] = end_time

            self.send_command(f'gamemode adventure {username}')
            if self.imprison_player(username):
                timer.start()

    def imprison_player(self, username):
        location = self.get_player_location(username)
        if location is None:
            return False

        with self.lock:
            self.player_data[username]['death_punishment']['location'] = location

        if self.teleport_to_jail(username):
            with self.lock:
                self.player_data[username]['death_punishment']['imprisoned'] = True
            return True
        return False

    def teleport_to_jail(self, username):
        if 'jail' not in self.server_data or 'location' not in self.server_data['jail']:
            return False
        realm = self.server_data['jail']['location']['realm']
        x = self.server_data['jail']['location']['x']
        y = self.server_data['jail']['location']['y']
        z = self.server_data['jail']['location']['z']
        _line, success = self.get_output(command=f'execute in {realm} run tp {username} {x} {y} {z}',
                                         success_output=f'Teleported {username} to',
                                         failure_output='No entity was found', timeout=3.0)
        return success

    def end_punishment(self, username):
        with self.lock:
            if self.player_data[username]['death_punishment']['imprisoned']:
                self.release_player(username)
            self.send_command(f'gamemode survival {username}')
            del self.player_data[username]['death_punishment']

    def release_player(self, username):
        with self.lock:
            location = self.player_data[username]['death_punishment']['location']
        realm = location['realm']
        x = location['x']
        y = location['y']
        z = location['z']
        if 'wall' in self.server_data and 'center' in self.server_data['wall']:
            center_x, center_z = self.server_data['wall']['center']['x'], self.server_data['wall']['center']['z']
            radius = self.get_wall_size() / 2
            min_x, max_x = center_x - radius, center_x + radius
            min_z, max_z = center_z - radius, center_z + radius
            if x < min_x or x > max_x or z < min_z or z > max_z:
                self.send_command(f'tp {username} ~ ~ ~')
                self.tell_player(username, 'You have been teleported to spawn--your respawn point is outside the '
                                           'world border')
                return
        self.send_command(f'execute in {realm} run tp {username} {x} {y} {z}')

    def parse_server_info(self, line):
        first_token = line.split(' ', 1)[0]
        username = first_token if first_token in self.online_players or line.endswith('joined the game') else None

        if username is None:
            return
        elif line.endswith('joined the game'):
            self.process_player_logon(username)
        elif line.endswith('left the game'):
            self.process_player_logoff(username)
        elif re.search(fr'^{username} has (made the advancement|reached the goal|completed the challenge) \[.*]$',
                       line):
            self.send_command(f'tell {username} Congrats, {username}!')
            self.send_command(f'give {username} minecraft:emerald')
        elif line.startswith(f'{username} moved too quickly'):
            pass  # capture line but do nothing with it for right now
        elif line.startswith(f'{username} lost connection'):
            pass  # capture line but do nothing with it for right now
        elif line.startswith(f'{username} moved too quickly!'):
            pass  # capture line but do nothing with it for right now
        else:  # could be a death message
            death_count_string, _success = self.get_output(command=f'scoreboard players get {username} deaths',
                                                           success_output=rf'{username} has \d+ \[deaths]', timeout=3.0)
            if death_count_string is None:
                return
            death_count = int(re.search(rf'{username} has (\d+) \[deaths]', death_count_string).group(1))
            if death_count != self.player_data[username]['death_count']:
                self.process_player_death(username)

    def create_new_player(self, username):
        self.player_data[username] = {}
        new_player = self.player_data[username]
        new_player['log_ons'] = []
        new_player['log_offs'] = []
        new_player['death_count'] = 0
        new_player['cooldowns'] = {}
        self.update_server_data_record()

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

    def update_server_data_record(self):
        self.server_data_file.seek(0)
        self.server_data_file.write(json.dumps(self.server_data, indent=4, sort_keys=True, default=str, skipkeys=True))
        self.server_data_file.truncate()

    def handle_input(self):
        while True:
            cmd = input('$ ')
            self.send_command(cmd)

    def server_start(self):
        self.get_output(command='', success_output=r'^.*]: Done \(\d+.\d+s\)! For help, type "help"$')

        # setup objectives (do every server start cause why not?)
        for objective in self.command_dict:
            self.send_command(f'scoreboard objectives add {objective} trigger')
            self.send_command(f'scoreboard objectives add {objective + "_cost"} trigger')
            self.send_command(f'scoreboard objectives add {objective + "_cooldown"} trigger')

        self.send_command(f'scoreboard objectives add deaths deathCount')
        self.send_command('gamerule doImmediateRespawn true')
        self.shrink_wall()  # Stop wall shrink if players stayed on until previous server shutdown

    def run(self):
        self.process = subprocess.Popen(self.sc, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        cwd=self.server_dir, bufsize=1, universal_newlines=True)

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
        if not run_as_service:  # if this is run as a service, there is no need to listen for terminal input
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

        self.update_server_data_record()
        self.server_data_file.close()

        if self.is_shutting_down:
            if self.config.getboolean('DEFAULT', 'UpdateOnReboot'):
                os.system(f'git -C {os.getcwd()} pull')
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
