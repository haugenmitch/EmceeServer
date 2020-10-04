import datetime
import math
from emcee_server import Server

HOURS_PER_EMERALD = 24


def execute(server: Server, username: str, mode: str = None, value: int = None):
    log_ons = server.player_data[username]['log_ons']
    log_offs = server.player_data[username]['log_offs']
    now = datetime.datetime.now()
    last = server.player_data[username]['collect']['last_collect'] \
        if 'last_collect' in server.player_data[username]['collect'] else None
    remainder = server.player_data[username]['collect']['remainder'] \
        if 'remainder' in server.player_data[username]['collect'] else 0
    server.player_data[username]['collect']['last_collect'] = now
    for i in range(len(log_offs)):
        if log_offs[i] < last:
            continue
        remainder += (log_ons[i + 1] - log_offs[i]).seconds / 3600.0
    emeralds = remainder // HOURS_PER_EMERALD
    remainder = math.fmod(remainder, HOURS_PER_EMERALD)
    server.player_data[username]['collect']['remainder'] = remainder
    server.player_data[username]['collect']['last_collect'] = last
    if emeralds > 0:
        server.send_command(f'give {username} minecraft:emerald {emeralds}')
    return True


def cost(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, f'[Collect] costs {0} emeralds')
    return 0


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, '[Collect] is ready to use')
    return True
